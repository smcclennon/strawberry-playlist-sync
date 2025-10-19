#!/usr/bin/env python3
"""
Test script for the Strawberry Playlist Synchronisation Daemon

This script provides comprehensive testing functionality with command line flags
for testing specific components of the playlist synchronisation system.

Copyright (c) 2025 Shiraz McClennon
Licensed under the MIT License. See LICENSE file for details.
"""

import argparse
import sys
import logging
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional

# Import from the main module
from strawberry_playlist_sync import (
    Config, PlaylistCache, M3U8Parser, StrawberryDB, PlaylistEventHandler
)

# Set up logging for tests
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestRunner:
    """Main test runner class"""
    
    def __init__(self, config_file: Optional[str] = None, ignore_schema_version: bool = False):
        """Initialize test runner with optional config file"""
        if config_file:
            self.config = Config(config_file)
        else:
            self.config = Config()
        
        self.ignore_schema_version = ignore_schema_version
        self.test_results = []
    
    def log_result(self, test_name: str, success: bool, message: str = ""):
        """Log a test result"""
        status = "PASS" if success else "FAIL"
        result = f"[{status}] {test_name}"
        if message:
            result += f": {message}"
        
        logger.info(result)
        self.test_results.append((test_name, success, message))
    
    def test_config(self) -> bool:
        """Test configuration loading and path resolution"""
        logger.info("Testing configuration system...")
        
        try:
            # Test path expansion
            if not self.config.playlist_dir.is_absolute():
                self.log_result("Config path expansion", False, "Playlist directory path not absolute")
                return False
            
            if not self.config.strawberry_db.is_absolute():
                self.log_result("Config path expansion", False, "Database path not absolute")
                return False
            
            # Test config access
            monitoring_config = self.config.get_monitoring_config()
            if not isinstance(monitoring_config, dict):
                self.log_result("Config access", False, "Monitoring config not a dictionary")
                return False
            
            logging_config = self.config.get_logging_config()
            if not isinstance(logging_config, dict):
                self.log_result("Config access", False, "Logging config not a dictionary")
                return False
            
            self.log_result("Configuration system", True)
            return True
            
        except Exception as e:
            self.log_result("Configuration system", False, str(e))
            return False
    
    def test_cache(self) -> bool:
        """Test playlist cache functionality"""
        logger.info("Testing cache system...")
        
        try:
            # Create temporary cache file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                temp_cache_file = Path(f.name)
            
            try:
                # Test cache creation and basic operations
                cache = PlaylistCache(temp_cache_file)
                
                # Test initial state
                if cache.get_last_modified("test_playlist") is not None:
                    self.log_result("Cache initial state", False, "Expected None for non-existent playlist")
                    return False
                
                # Test update and retrieval
                test_time = 1234567890.0
                cache.update_playlist("test_playlist", test_time)
                
                retrieved_time = cache.get_last_modified("test_playlist")
                if retrieved_time != test_time:
                    self.log_result("Cache update/retrieval", False, f"Expected {test_time}, got {retrieved_time}")
                    return False
                
                # Test persistence
                cache2 = PlaylistCache(temp_cache_file)
                retrieved_time2 = cache2.get_last_modified("test_playlist")
                if retrieved_time2 != test_time:
                    self.log_result("Cache persistence", False, f"Expected {test_time}, got {retrieved_time2}")
                    return False
                
                self.log_result("Cache system", True)
                return True
                
            finally:
                # Clean up
                if temp_cache_file.exists():
                    temp_cache_file.unlink()
                    
        except Exception as e:
            self.log_result("Cache system", False, str(e))
            return False
    
    def test_m3u8_parser(self) -> bool:
        """Test M3U8 parser functionality"""
        logger.info("Testing M3U8 parser...")
        
        try:
            parser = M3U8Parser(self.config.get_monitoring_config())
            
            # Create temporary M3U8 file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.m3u8', delete=False) as f:
                f.write("#EXTM3U\n")
                f.write("#EXTINF:244,Artist - Song 1\n")
                f.write("music/Artist/Song1.flac\n")
                f.write("#EXTINF:265,Artist - Song 2\n")
                f.write("music/Artist/Song2.flac\n")
                temp_m3u8_file = Path(f.name)
            
            try:
                # Test parsing
                tracks = parser.parse_playlist(temp_m3u8_file)
                
                expected_tracks = [
                    "music/Artist/Song1.flac",
                    "music/Artist/Song2.flac"
                ]
                
                if tracks != expected_tracks:
                    self.log_result("M3U8 parsing", False, f"Expected {expected_tracks}, got {tracks}")
                    return False
                
                self.log_result("M3U8 parser", True)
                return True
                
            finally:
                # Clean up
                if temp_m3u8_file.exists():
                    temp_m3u8_file.unlink()
                    
        except Exception as e:
            self.log_result("M3U8 parser", False, str(e))
            return False
    
    def test_database_connection(self) -> bool:
        """Test database connection and basic operations"""
        logger.info("Testing database connection...")
        
        try:
            if not self.config.strawberry_db.exists():
                self.log_result("Database connection", False, f"Database file not found: {self.config.strawberry_db}")
                return False
            
            db = StrawberryDB(self.config.strawberry_db, self.config.playlist_dir, self.ignore_schema_version)
            
            # Test connection
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='songs'")
                if not cursor.fetchone():
                    self.log_result("Database schema", False, "Songs table not found")
                    return False
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='playlists'")
                if not cursor.fetchone():
                    self.log_result("Database schema", False, "Playlists table not found")
                    return False
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='playlist_items'")
                if not cursor.fetchone():
                    self.log_result("Database schema", False, "Playlist_items table not found")
                    return False
            
            self.log_result("Database connection", True)
            return True
            
        except Exception as e:
            self.log_result("Database connection", False, str(e))
            return False
    
    def test_playlist_sync(self, playlist_file: str) -> bool:
        """Test playlist synchronisation with a specific file"""
        logger.info(f"Testing playlist synchronisation with {playlist_file}...")
        
        try:
            playlist_path = Path(playlist_file)
            if not playlist_path.exists():
                self.log_result("Playlist sync", False, f"Playlist file not found: {playlist_file}")
                return False
            
            # Create cache and event handler
            cache = PlaylistCache(self.config.cache_file)
            handler = PlaylistEventHandler(cache, self.config, self.ignore_schema_version)
            
            # Test sync
            handler.sync_playlist_file(playlist_path, update_cache=False)
            
            # Verify playlist was created/updated in database
            db = StrawberryDB(self.config.strawberry_db, self.config.playlist_dir, self.ignore_schema_version)
            playlist_name = playlist_path.stem
            playlist_id = db.get_playlist_id(playlist_name)
            
            if playlist_id is None:
                self.log_result("Playlist sync", False, f"Playlist '{playlist_name}' not found in database after sync")
                return False
            
            # Check playlist has items
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM playlist_items WHERE playlist = ?", (playlist_id,))
                item_count = cursor.fetchone()[0]
                
                if item_count == 0:
                    self.log_result("Playlist sync", False, f"Playlist '{playlist_name}' has no items after sync")
                    return False
            
            self.log_result("Playlist sync", True, f"Playlist '{playlist_name}' synced with {item_count} items")
            return True
            
        except Exception as e:
            self.log_result("Playlist sync", False, str(e))
            return False
    
    def test_song_lookup(self, song_path: str) -> bool:
        """Test song lookup by path"""
        logger.info(f"Testing song lookup for {song_path}...")
        
        try:
            db = StrawberryDB(self.config.strawberry_db, self.config.playlist_dir, self.ignore_schema_version)
            
            # Handle relative paths that need a playlist file context
            playlist_file_path = None
            if song_path.startswith('../') or song_path.startswith('./'):
                # For relative paths, we need to provide a playlist file path context
                # Assume the playlist is in the playlist directory for testing purposes
                playlist_file_path = self.config.playlist_dir / "test_playlist.m3u8"
            
            song_id = db.find_song_by_path(song_path, playlist_file_path)
            
            if song_id is None:
                self.log_result("Song lookup", False, f"Song not found: {song_path}")
                return False
            
            self.log_result("Song lookup", True, f"Song found with ID: {song_id}")
            return True
            
        except Exception as e:
            self.log_result("Song lookup", False, str(e))
            return False
    
    def list_tables(self) -> bool:
        """List all tables in the Strawberry database"""
        logger.info("Listing database tables...")
        
        try:
            db = StrawberryDB(self.config.strawberry_db, self.config.playlist_dir, self.ignore_schema_version)
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = cursor.fetchall()
                
                logger.info("Database tables:")
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                    count = cursor.fetchone()[0]
                    logger.info(f"  {table[0]}: {count} rows")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return False
    
    def search_songs(self, search_term: str) -> bool:
        """Search for songs in the database by title, artist, or filename"""
        logger.info(f"Searching for songs matching: {search_term}")
        
        try:
            db = StrawberryDB(self.config.strawberry_db, self.config.playlist_dir, self.ignore_schema_version)
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Search in title, artist, album, and url fields
                search_pattern = f"%{search_term}%"
                cursor.execute("""
                    SELECT rowid, title, artist, album, url 
                    FROM songs 
                    WHERE title LIKE ? OR artist LIKE ? OR album LIKE ? OR url LIKE ?
                    ORDER BY title, artist
                    LIMIT 20
                """, (search_pattern, search_pattern, search_pattern, search_pattern))
                
                results = cursor.fetchall()
                
                if not results:
                    logger.info(f"No songs found matching '{search_term}'")
                    return True
                
                logger.info(f"Found {len(results)} songs matching '{search_term}':")
                for row in results:
                    rowid, title, artist, album, url = row
                    logger.info(f"  ID {rowid}: {artist} - {title} ({album})")
                    logger.info(f"    URL: {url}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to search songs: {e}")
            return False
    
    def inspect_database(self, table_name: str = "songs", limit: int = 10) -> bool:
        """Inspect database table structure and sample data"""
        logger.info(f"Inspecting table '{table_name}' (showing all rows)...")
        
        try:
            db = StrawberryDB(self.config.strawberry_db, self.config.playlist_dir, self.ignore_schema_version)
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get table schema
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                if not columns:
                    logger.error(f"Table '{table_name}' not found")
                    return False
                
                logger.info(f"Table '{table_name}' schema:")
                for col in columns:
                    cid, name, type_name, notnull, default, pk = col
                    pk_str = " (PRIMARY KEY)" if pk else ""
                    notnull_str = " NOT NULL" if notnull else ""
                    default_str = f" DEFAULT {default}" if default else ""
                    logger.info(f"  {name}: {type_name}{pk_str}{notnull_str}{default_str}")
                
                # Get all data (no limit)
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                
                if rows:
                    logger.info(f"\nAll data from '{table_name}' ({len(rows)} rows):")
                    column_names = [col[1] for col in columns]
                    
                    for i, row in enumerate(rows, 1):
                        logger.info(f"  Row {i}:")
                        for col_name, value in zip(column_names, row):
                            # Truncate long values for readability
                            if isinstance(value, str) and len(value) > 100:
                                value = value[:97] + "..."
                            logger.info(f"    {col_name}: {value}")
                        logger.info("")
                else:
                    logger.info(f"Table '{table_name}' is empty")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to inspect table '{table_name}': {e}")
            return False
    
    def test_schema_compatibility(self) -> bool:
        """
        Comprehensive schema compatibility test for validating database schema versions
        
        Tests all tables, columns, and operations used by the playlist sync daemon
        to determine if the current database schema is compatible.
        """
        logger.info("=== Strawberry Database Schema Compatibility Test ===\n")
        
        try:
            db = StrawberryDB(self.config.strawberry_db, self.config.playlist_dir, True)  # Bypass version check
            
            # Track overall compatibility status
            is_compatible = True
            warnings = []
            errors = []
            
            # 1. Get schema version
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                try:
                    cursor.execute("SELECT version FROM schema_version LIMIT 1")
                    result = cursor.fetchone()
                    schema_version = result[0] if result else "Unknown"
                    logger.info(f"Schema Version: {schema_version}\n")
                except Exception as e:
                    logger.error(f"Failed to read schema version: {e}")
                    schema_version = "Unknown"
                    errors.append("Cannot read schema_version table")
                    is_compatible = False
                
                # 2. Check required tables exist
                logger.info("Checking Required Tables...")
                required_tables = ["songs", "playlists", "playlist_items"]
                
                for table_name in required_tables:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                    if cursor.fetchone():
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        logger.info(f"  ✓ {table_name} ({count} rows)")
                    else:
                        logger.error(f"  ✗ {table_name} (missing)")
                        errors.append(f"Required table '{table_name}' is missing")
                        is_compatible = False
                
                logger.info("")
                
                # 3. Check required columns
                logger.info("Checking Required Columns...")
                
                # Define required columns for each table
                # Format: {table: {column: expected_type}}
                required_columns = {
                    "songs": {
                        "url": "TEXT"
                    },
                    "playlists": {
                        "name": "TEXT",
                        "last_played": "INTEGER",
                        "ui_order": "INTEGER",
                        "is_favorite": "INTEGER"
                    },
                    "playlist_items": {
                        "playlist": "INTEGER",
                        "type": "INTEGER",
                        "collection_id": "INTEGER",
                        "track": "INTEGER",
                        "disc": "INTEGER",
                        "year": "INTEGER",
                        "originalyear": "INTEGER",
                        "compilation": "INTEGER",
                        "beginning": "INTEGER",
                        "length": "INTEGER",
                        "bitrate": "INTEGER",
                        "samplerate": "INTEGER",
                        "bitdepth": "INTEGER",
                        "source": "INTEGER",
                        "directory_id": "INTEGER",
                        "filetype": "INTEGER",
                        "filesize": "INTEGER",
                        "mtime": "INTEGER",
                        "ctime": "INTEGER",
                        "unavailable": "INTEGER",
                        "playcount": "INTEGER",
                        "skipcount": "INTEGER",
                        "lastplayed": "INTEGER",
                        "lastseen": "INTEGER",
                        "compilation_detected": "INTEGER",
                        "compilation_on": "INTEGER",
                        "compilation_off": "INTEGER",
                        "compilation_effective": "INTEGER",
                        "effective_originalyear": "INTEGER",
                        "rating": "INTEGER",
                        "art_embedded": "INTEGER",
                        "art_unset": "INTEGER"
                    }
                }
                
                for table_name, columns in required_columns.items():
                    logger.info(f"  {table_name} table:")
                    
                    # Get actual table schema
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    actual_columns = {row[1]: row[2] for row in cursor.fetchall()}  # name: type
                    
                    # Check each required column
                    for col_name, expected_type in columns.items():
                        if col_name in actual_columns:
                            actual_type = actual_columns[col_name]
                            if actual_type == expected_type:
                                logger.info(f"    ✓ {col_name} ({actual_type})")
                            else:
                                logger.warning(f"    ⚠ {col_name} (type mismatch: expected {expected_type}, got {actual_type})")
                                warnings.append(f"{table_name}.{col_name} type mismatch")
                        else:
                            logger.error(f"    ✗ {col_name} (missing)")
                            errors.append(f"Required column '{table_name}.{col_name}' is missing")
                            is_compatible = False
                    
                    # Report new/additional columns
                    new_columns = set(actual_columns.keys()) - set(columns.keys())
                    if new_columns:
                        logger.info(f"    ℹ New columns detected: {', '.join(sorted(new_columns))}")
                
                logger.info("")
                
                # 4. Test database operations
                logger.info("Testing Database Operations...")
                test_playlist_name = "__schema_compat_test_playlist__"
                test_playlist_id = None
                
                try:
                    # Test SELECT from songs (find any song)
                    cursor.execute("SELECT rowid, url FROM songs LIMIT 1")
                    test_song = cursor.fetchone()
                    if test_song:
                        logger.info("  ✓ SELECT from songs")
                    else:
                        logger.warning("  ⚠ SELECT from songs (no songs in database)")
                        warnings.append("No songs in database to test with")
                    
                    # Test SELECT from playlists
                    cursor.execute("SELECT rowid, name FROM playlists LIMIT 1")
                    if cursor.fetchone():
                        logger.info("  ✓ SELECT from playlists")
                    else:
                        logger.warning("  ⚠ SELECT from playlists (no playlists in database)")
                    
                    # Test INSERT into playlists
                    cursor.execute(
                        "INSERT INTO playlists (name, last_played, ui_order, is_favorite) VALUES (?, -1, -1, 1)",
                        (test_playlist_name,)
                    )
                    test_playlist_id = cursor.lastrowid
                    conn.commit()
                    logger.info("  ✓ INSERT into playlists")
                    
                    # Test INSERT into playlist_items (if we have a test song)
                    if test_song and test_playlist_id:
                        cursor.execute(
                            """INSERT INTO playlist_items 
                               (playlist, type, collection_id, track, disc, year, originalyear, 
                                compilation, beginning, length, bitrate, samplerate, bitdepth, 
                                source, directory_id, filetype, filesize, mtime, ctime, unavailable,
                                playcount, skipcount, lastplayed, lastseen, compilation_detected,
                                compilation_on, compilation_off, compilation_effective, 
                                effective_originalyear, rating, art_embedded, art_unset)
                               VALUES (?, 2, ?, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, 2, -1, 0, 0, -1, -1, 0,
                                       0, 0, -1, -1, 0, 0, 0, 0, 0, -1, 0, 0)""",
                            (test_playlist_id, test_song[0])
                        )
                        conn.commit()
                        logger.info("  ✓ INSERT into playlist_items")
                        
                        # Test DELETE from playlist_items
                        cursor.execute("DELETE FROM playlist_items WHERE playlist = ?", (test_playlist_id,))
                        conn.commit()
                        logger.info("  ✓ DELETE from playlist_items")
                    else:
                        logger.warning("  ⚠ Skipped playlist_items tests (no test data)")
                    
                    # Clean up test playlist
                    if test_playlist_id:
                        cursor.execute("DELETE FROM playlists WHERE rowid = ?", (test_playlist_id,))
                        conn.commit()
                    
                except Exception as e:
                    logger.error(f"  ✗ Database operation failed: {e}")
                    errors.append(f"Database operation error: {e}")
                    is_compatible = False
                    
                    # Try to clean up if something went wrong
                    try:
                        if test_playlist_id:
                            cursor.execute("DELETE FROM playlist_items WHERE playlist = ?", (test_playlist_id,))
                            cursor.execute("DELETE FROM playlists WHERE rowid = ?", (test_playlist_id,))
                            conn.commit()
                    except:
                        pass
                
                logger.info("")
                
                # 5. Generate compatibility report
                logger.info("=== Compatibility Report ===")
                
                if is_compatible and not errors:
                    if warnings:
                        logger.info("Status: COMPATIBLE (with warnings)")
                        logger.info(f"Schema Version {schema_version} is supported.")
                        logger.info("All required tables and columns are present.")
                        logger.info("All database operations completed successfully.")
                        logger.info(f"\nWarnings ({len(warnings)}):")
                        for warning in warnings:
                            logger.info(f"  ⚠ {warning}")
                    else:
                        logger.info("Status: COMPATIBLE")
                        logger.info(f"Schema Version {schema_version} is fully supported.")
                        logger.info("All required tables and columns are present.")
                        logger.info("All database operations completed successfully.")
                    
                    if schema_version not in StrawberryDB.SUPPORTED_SCHEMA_VERSIONS and schema_version != "Unknown":
                        logger.info(f"\nRecommendation: Add version {schema_version} to SUPPORTED_SCHEMA_VERSIONS")
                else:
                    logger.error("Status: INCOMPATIBLE")
                    logger.error(f"Schema Version {schema_version} has compatibility issues.")
                    logger.error(f"\nErrors ({len(errors)}):")
                    for error in errors:
                        logger.error(f"  ✗ {error}")
                    if warnings:
                        logger.warning(f"\nWarnings ({len(warnings)}):")
                        for warning in warnings:
                            logger.warning(f"  ⚠ {warning}")
                    logger.error("\nRecommendation: Do NOT add this version to SUPPORTED_SCHEMA_VERSIONS")
                
                return is_compatible
                
        except Exception as e:
            logger.error(f"Schema compatibility test failed: {e}")
            return False
    
    def test_database_backup(self) -> bool:
        """Test database backup functionality"""
        logger.info("Testing database backup functionality...")
        
        try:
            # Create a temporary cache file path that doesn't exist
            with tempfile.NamedTemporaryFile(suffix='.json', delete=True) as f:
                temp_cache_path = Path(f.name)
            
            # Ensure the temp cache file doesn't exist (simulating first run)
            if temp_cache_path.exists():
                temp_cache_path.unlink()
            
            # Create cache instance (should detect first run)
            cache = PlaylistCache(temp_cache_path)
            
            if not cache.is_first_run:
                self.log_result("Database backup detection", False, "Failed to detect first run")
                return False
            
            # Test backup creation
            backup_dir = Path(tempfile.mkdtemp())
            try:
                backup_path = cache.create_database_backup(self.config.strawberry_db, backup_dir, self.config.config)
                
                if backup_path is None:
                    self.log_result("Database backup creation", False, "Backup creation returned None")
                    return False
                
                if not backup_path.exists():
                    self.log_result("Database backup creation", False, "Backup file was not created")
                    return False
                
                # Verify backup file has content
                if backup_path.stat().st_size == 0:
                    self.log_result("Database backup creation", False, "Backup file is empty")
                    return False
                
                # Verify backup filename format
                if "before_first_use" not in backup_path.name:
                    self.log_result("Database backup naming", False, f"Unexpected backup filename: {backup_path.name}")
                    return False
                
                self.log_result("Database backup functionality", True, f"Backup created: {backup_path.name}")
                return True
                
            finally:
                # Clean up backup directory
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                    
        except Exception as e:
            self.log_result("Database backup functionality", False, str(e))
            return False
    
    def run_all_tests(self, sync_playlist: Optional[str] = None, test_song: Optional[str] = None) -> bool:
        """Run all available tests"""
        logger.info("Running all tests...")
        
        all_passed = True
        
        # Core system tests
        all_passed &= self.test_config()
        all_passed &= self.test_cache()
        all_passed &= self.test_database_backup()
        all_passed &= self.test_m3u8_parser()
        all_passed &= self.test_database_connection()
        
        # Playlist sync test
        playlist_to_test = None
        if sync_playlist:
            # Use specified playlist
            playlist_path = Path(sync_playlist)
            if not playlist_path.is_absolute():
                playlist_path = self.config.playlist_dir / sync_playlist
            if playlist_path.exists():
                playlist_to_test = str(playlist_path)
            else:
                logger.warning(f"Specified playlist not found: {sync_playlist}")
        
        if not playlist_to_test:
            # Search for any M3U8 file in playlist directory
            m3u8_files = list(self.config.playlist_dir.glob("*.m3u8"))
            if m3u8_files:
                playlist_to_test = str(m3u8_files[0])
                logger.info(f"Found M3U8 file for testing: {m3u8_files[0].name}")
            else:
                logger.warning("No M3U8 files found in playlist directory, skipping playlist sync test")
        
        if playlist_to_test:
            all_passed &= self.test_playlist_sync(playlist_to_test)
        
        # Song lookup test
        song_to_test = None
        if test_song:
            # Use specified song
            song_to_test = test_song
        else:
            # Search for any audio file in playlist directory
            audio_extensions = ['*.flac', '*.mp3', '*.wav', '*.m4a', '*.ogg']
            for pattern in audio_extensions:
                audio_files = list(self.config.playlist_dir.rglob(pattern))
                if audio_files:
                    # Get relative path from playlist directory
                    relative_path = audio_files[0].relative_to(self.config.playlist_dir)
                    song_to_test = str(relative_path)
                    logger.info(f"Found audio file for testing: {relative_path}")
                    break
            
            if not song_to_test:
                logger.warning("No audio files found in playlist directory, skipping song lookup test")
        
        if song_to_test:
            all_passed &= self.test_song_lookup(song_to_test)
        
        return all_passed
    
    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "="*50)
        logger.info("TEST SUMMARY")
        logger.info("="*50)
        
        passed = sum(1 for _, success, _ in self.test_results if success)
        total = len(self.test_results)
        
        for test_name, success, message in self.test_results:
            status = "PASS" if success else "FAIL"
            result = f"[{status}] {test_name}"
            if message:
                result += f": {message}"
            logger.info(result)
        
        logger.info("="*50)
        logger.info(f"TOTAL: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 All tests passed!")
        else:
            logger.error(f"❌ {total - passed} test(s) failed")


def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(
        description="Test script for Strawberry Playlist Synchronisation Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 test.py --all                    # Run all tests (auto-detect files)
  python3 test.py --all --sync playlist.m3u8  # Run all tests with specific playlist
  python3 test.py --all --song "Artist/Track.flac" # Run all tests with specific song
  python3 test.py --config                 # Test configuration system
  python3 test.py --cache                  # Test cache functionality
  python3 test.py --parser                 # Test M3U8 parser
  python3 test.py --database               # Test database connection
  python3 test.py --sync playlist.m3u8 # Test playlist sync
  python3 test.py --song "Artist/Track.flac" # Test song lookup
  python3 test.py --list-tables            # List all database tables
  python3 test.py --search-songs "Hello"  # Search for songs by title/artist
  python3 test.py --inspect songs          # Inspect table structure and data
  python3 test.py --test-schema-compatibility # Test database schema compatibility
  python3 test.py --config-file config.json --all # Use custom config
        """
    )
    
    parser.add_argument('--config-file', '-c', help='Path to configuration file')
    parser.add_argument('--all', '-a', action='store_true', help='Run all tests (auto-detects files or uses specified --sync/--song)')
    parser.add_argument('--config', action='store_true', help='Test configuration system')
    parser.add_argument('--cache', action='store_true', help='Test cache functionality')
    parser.add_argument('--parser', action='store_true', help='Test M3U8 parser')
    parser.add_argument('--database', action='store_true', help='Test database connection')
    parser.add_argument('--sync', metavar='PLAYLIST', help='Test playlist synchronisation with specified file (relative to playlist directory, can be used with --all)')
    parser.add_argument('--song', metavar='PATH', help='Test song lookup by relative path (relative to playlist directory, can be used with --all)')
    parser.add_argument('--list-tables', action='store_true', help='List all tables in the Strawberry database')
    parser.add_argument('--search-songs', metavar='TERM', help='Search for songs by title, artist, album, or filename')
    parser.add_argument('--inspect', metavar='TABLE', help='Inspect database table structure and sample data (default: songs)')
    parser.add_argument('--test-schema-compatibility', action='store_true', help='Run comprehensive schema compatibility tests for the current database version')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--ignore-database-schema-version', '-i', action='store_true', help='Bypass database schema version check (WARNING: may cause data corruption or loss!)')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check if any test was specified
    if not any([args.all, args.config, args.cache, args.parser, args.database, args.sync, args.song, 
                args.list_tables, args.search_songs, args.inspect, args.test_schema_compatibility]):
        parser.print_help()
        sys.exit(1)
    
    # Initialize test runner
    try:
        runner = TestRunner(args.config_file, args.ignore_database_schema_version)
    except Exception as e:
        logger.error(f"Failed to initialize test runner: {e}")
        sys.exit(1)
    
    # Run specified tests
    success = True
    
    if args.all:
        success = runner.run_all_tests(args.sync, args.song)
    else:
        if args.config:
            success &= runner.test_config()
        if args.cache:
            success &= runner.test_cache()
        if args.parser:
            success &= runner.test_m3u8_parser()
        if args.database:
            success &= runner.test_database_connection()
        if args.sync:
            success &= runner.test_playlist_sync(args.sync)
        if args.song:
            success &= runner.test_song_lookup(args.song)
        if args.list_tables:
            success &= runner.list_tables()
        if args.search_songs:
            success &= runner.search_songs(args.search_songs)
        if args.inspect:
            success &= runner.inspect_database(args.inspect)
        if args.test_schema_compatibility:
            success &= runner.test_schema_compatibility()
    
    # Print summary only for actual tests, not for database inspection
    if any([args.all, args.config, args.cache, args.parser, args.database, args.sync, args.song, args.test_schema_compatibility]):
        runner.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 