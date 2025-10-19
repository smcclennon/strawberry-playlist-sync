#!/usr/bin/env python3
"""
Strawberry Playlist Synchronisation Daemon

Monitors .m3u8 playlist files for changes and synchronises them with Strawberry's
SQLite database. This allows seamless playlist editing on Android (via Poweramp)
that automatically syncs to the Linux Strawberry music player.

Copyright (c) 2025 Shiraz McClennon
Licensed under the MIT License. See LICENSE file for details.
"""

import os
import sys
import time
import sqlite3
import logging
import urllib.parse
import json
import argparse
import shutil
import psutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class Config:
    """Configuration manager for the playlist sync daemon"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self._setup_paths()
    
    @classmethod
    def get_default_config(cls) -> Dict:
        """
        Get the default configuration dictionary
        
        Returns:
            Dictionary containing default configuration values
        """
        return {
            "playlist_directory": "~/Music",
            "strawberry_db_path": "~/.local/share/strawberry/strawberry/strawberry.db",
            "log_file": "playlist_sync.log",
            "cache_file": "playlist_sync_cache.json",
            "backup_directory": "backups",
            "backup_retention": 3,
            "monitoring": {
                "debounce_delay": 2.0,
                "max_retries": 3,
                "retry_delay": 0.5
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(levelname)s - %(message)s"
            }
        }
    
    def _load_config(self) -> Dict:
        """Load configuration from file or create default"""
        # Check if config file exists first
        if not self.config_file.exists():
            print(f"Config file not found: {self.config_file.resolve()}")
            print(f"Using default configuration (run with --create-config to create a config file)")
        else:
            # Try to load existing config file
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load config file {self.config_file.resolve()}: {e}")
                print("Using default configuration")
        
        # Return default config using the shared method
        return self.get_default_config()
    
    def _setup_paths(self):
        """Convert tilde paths to absolute paths and set up path attributes"""
        self.playlist_dir = Path(os.path.expanduser(self.config["playlist_directory"]))
        self.strawberry_db = Path(os.path.expanduser(self.config["strawberry_db_path"]))
        
        # Log, cache, and backup files/directories are relative to script directory (where config file is located)
        # Resolve the config file path to get the absolute directory
        config_file_resolved = self.config_file.resolve()
        script_dir = config_file_resolved.parent
        self.log_file = script_dir / self.config["log_file"]
        self.cache_file = script_dir / self.config["cache_file"]
        self.backup_dir = script_dir / self.config["backup_directory"]
    
    def get_monitoring_config(self) -> Dict:
        """Get monitoring configuration"""
        return self.config.get("monitoring", {})
    
    def get_logging_config(self) -> Dict:
        """Get logging configuration"""
        return self.config.get("logging", {})
    
    def create_config_file(self) -> bool:
        """
        Create a configuration file with default settings
        
        Returns:
            True if config file was created successfully, False if skipped or failed
        """
        try:
            # Check if config file already exists
            if self.config_file.exists():
                print(f"⚠️  Configuration file already exists: {self.config_file.resolve()}")
                print("❌ Configuration file creation skipped")
                return False
            
            # Get default configuration using the shared method
            default_config = self.get_default_config()
            
            # Write config file with nice formatting
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Configuration file created: {self.config_file.resolve()}")
            print("📝 Please review and edit the configuration file to match your setup:")
            print(f"   - playlist_directory: Path to your playlist directory")
            print(f"   - strawberry_db_path: Path to Strawberry's database file")
            print(f"   - Other settings can be left as defaults")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create configuration file: {e}")
            return False


# Global configuration instance - will be set in main()
config = None

# Set up a basic logger that can be used when the module is imported
# This will be reconfigured in main() when running as a daemon
logger = logging.getLogger(__name__)
if not logger.handlers:
    # Only add handler if none exists (avoid duplicate handlers)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class PlaylistCache:
    """Manages playlist synchronisation cache and tracking"""
    
    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self.is_first_run = not cache_file.exists()  # Track if this is the first run
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from file or create default"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    logger.info(f"Loaded cache for {len(cache.get('playlists', {}))} playlists")
                    return cache
        except Exception as e:
            logger.warning(f"Failed to load cache file: {e}")
        
        # Return default cache
        return {"playlists": {}}
    
    def _save_cache(self) -> None:
        """Save cache to file"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache file: {e}")
    
    def create_database_backup(self, db_path: Path, backup_dir: Path, config: Dict) -> Optional[Path]:
        """
        Create a backup of the database with intelligent naming and retention
        
        Args:
            db_path: Path to the original database
            backup_dir: Directory to store the backup
            config: Configuration dictionary for backup settings
            
        Returns:
            Path to the backup file if successful, None otherwise
        """
        try:
            if not db_path.exists():
                logger.error(f"Database file not found: {db_path}")
                return None
            
            # Ensure backup directory exists
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if this is the very first backup (backup directory was just created and empty)
            existing_backups = list(backup_dir.glob("*.db"))
            is_very_first_backup = len(existing_backups) == 0
            
            if is_very_first_backup:
                # Special backup name for the very first use
                backup_filename = f"{db_path.stem}_before_first_use{db_path.suffix}"
                backup_path = backup_dir / backup_filename
                logger.info(f"Creating initial backup before first use: {backup_filename}")
            else:
                # Regular startup backup with timestamp
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                backup_filename = f"{db_path.stem}_backup_startup_{timestamp}{db_path.suffix}"
                backup_path = backup_dir / backup_filename
                logger.info(f"Creating startup backup: {backup_filename}")
                
                # Clean up old startup backups based on retention policy
                self._cleanup_old_backups(backup_dir, db_path.stem, config.get("backup_retention", 3))
            
            # Copy the database file
            shutil.copy2(db_path, backup_path)
            
            # Verify backup was created successfully
            if backup_path.exists() and backup_path.stat().st_size > 0:
                logger.info(f"✅ Database backup created successfully: {backup_path}")
                return backup_path
            else:
                logger.error("❌ Database backup verification failed")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            return None
    
    def _cleanup_old_backups(self, backup_dir: Path, db_stem: str, retention_count: int) -> None:
        """
        Clean up old startup backups, keeping only the most recent ones
        
        Args:
            backup_dir: Directory containing backups
            db_stem: Database filename stem (without extension)
            retention_count: Number of startup backups to keep
        """
        try:
            # Find all startup backup files (exclude the special "before_first_use" backup)
            startup_backup_pattern = f"{db_stem}_backup_startup_*.db"
            startup_backups = list(backup_dir.glob(startup_backup_pattern))
            
            if len(startup_backups) >= retention_count:
                # Sort by modification time (oldest first)
                startup_backups.sort(key=lambda p: p.stat().st_mtime)
                
                # Calculate how many to delete
                to_delete = len(startup_backups) - retention_count + 1  # +1 because we're about to create a new one
                
                for backup_to_delete in startup_backups[:to_delete]:
                    try:
                        backup_to_delete.unlink()
                        logger.info(f"🗑️  Removed old backup: {backup_to_delete.name}")
                    except Exception as e:
                        logger.warning(f"Failed to remove old backup {backup_to_delete.name}: {e}")
                        
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")
    
    def get_last_modified(self, playlist_name: str) -> Optional[float]:
        """Get the last recorded modification time for a playlist"""
        return self.cache.get("playlists", {}).get(playlist_name, {}).get("last_modified")
    
    def update_playlist(self, playlist_name: str, modified_time: float) -> None:
        """Update the modification time for a playlist"""
        if "playlists" not in self.cache:
            self.cache["playlists"] = {}
        
        self.cache["playlists"][playlist_name] = {
            "last_modified": modified_time,
            # "last_synced": time.time()
        }
        self._save_cache()
    
    def needs_sync(self, playlist_path: Path) -> bool:
        """Check if a playlist needs synchronisation based on modification time"""
        try:
            current_mtime = playlist_path.stat().st_mtime
            recorded_mtime = self.get_last_modified(playlist_path.stem)
            
            if recorded_mtime is None:
                logger.info(f"Playlist not previously synced: {playlist_path.name}")
                return True
            
            if current_mtime > recorded_mtime:
                logger.info(f"Playlist modified since last sync: {playlist_path.name}")
                return True
            
            logger.debug(f"Playlist unchanged since last sync: {playlist_path.name}")
            return False
            
        except Exception as e:
            logger.warning(f"Failed to check modification time for {playlist_path.name}: {e}")
            return True  # Sync if we can't determine the state


class M3U8Parser:
    """Parser for M3U8 playlist files"""
    
    def __init__(self, monitoring_config: Dict):
        self.max_retries = monitoring_config.get("max_retries", 3)
        self.retry_delay = monitoring_config.get("retry_delay", 0.5)
    
    def parse_playlist(self, file_path: Path) -> List[str]:
        """
        Parse an M3U8 file and extract relative file paths
        
        Args:
            file_path: Path to the M3U8 file
            
        Returns:
            List of relative file paths from the playlist
        """
        import time
        
        for attempt in range(self.max_retries + 1):
            tracks = []
            try:
                # Check if file exists and has content
                if not file_path.exists():
                    logger.warning(f"Playlist file does not exist: {file_path}")
                    return []
                
                file_size = file_path.stat().st_size
                if file_size == 0:
                    if attempt < self.max_retries:
                        logger.warning(f"Playlist file is empty, retrying in {self.retry_delay}s (attempt {attempt + 1}/{self.max_retries + 1}): {file_path.name}")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        logger.warning(f"Playlist file remains empty after {self.max_retries} retries: {file_path.name}")
                        return []
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and M3U8 metadata
                        if line and not line.startswith('#'):
                            tracks.append(line)
                
                # If we got tracks, we're done
                if tracks:
                    logger.info(f"Parsed {len(tracks)} tracks from {file_path.name}")
                    return tracks
                elif attempt < self.max_retries:
                    # File exists but no tracks found, might be incomplete write
                    logger.warning(f"No tracks found in playlist, retrying in {self.retry_delay}s (attempt {attempt + 1}/{self.max_retries + 1}): {file_path.name}")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.warning(f"No tracks found in playlist after {self.max_retries} retries: {file_path.name}")
                    return []
                    
            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning(f"Failed to parse {file_path} (attempt {attempt + 1}/{self.max_retries + 1}): {e}")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"Failed to parse {file_path} after {self.max_retries} retries: {e}")
                    return []
        
        return tracks


class StrawberryDB:
    """Interface for Strawberry's SQLite database"""
    
    # Supported database schema versions
    SUPPORTED_SCHEMA_VERSIONS = [20, 21]
    
    def __init__(self, db_path: Path, playlist_dir: Path, ignore_schema_version: bool = False):
        self.db_path = db_path
        self.playlist_dir = playlist_dir
        self.ignore_schema_version = ignore_schema_version
        
        # Check schema version on initialization
        if not self.ignore_schema_version:
            self._check_schema_version()
    
    def _log_schema_error_with_bypass_warning(self, error_message: str) -> None:
        """Log schema error with consistent bypass warning"""
        logger.error(error_message)
        logger.error("⚠️  WARNING: Bypassing this check could cause data corruption or loss!")
        logger.error("Use --ignore-database-schema-version to bypass this check at your own risk.")
    
    def _handle_schema_check_failure(self, error_message: str) -> None:
        """Handle schema check failure with consistent error logging and exit"""
        self._log_schema_error_with_bypass_warning(error_message)
        sys.exit(1)
        
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection"""
        return sqlite3.connect(str(self.db_path))
    
    def _check_schema_version(self) -> None:
        """Check if the database schema version is supported"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if schema_version table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
                if not cursor.fetchone():
                    logger.warning("Database schema_version table not found - this may be an older or incompatible database")
                    self._handle_schema_check_failure("Unsupported database schema.")
                
                # Get current schema version
                cursor.execute("SELECT version FROM schema_version LIMIT 1")
                result = cursor.fetchone()
                
                if not result:
                    self._handle_schema_check_failure("No schema version found in database")
                
                current_version = result[0]
                
                if current_version not in self.SUPPORTED_SCHEMA_VERSIONS:
                    error_msg = (f"Unsupported database schema version: {current_version}\n"
                               f"Supported versions: {', '.join(map(str, self.SUPPORTED_SCHEMA_VERSIONS))}\n"
                               f"This version of the sync daemon may not work correctly with this database.")
                    self._handle_schema_check_failure(error_msg)
                
                logger.info(f"Database schema version {current_version} is supported")
                
        except sqlite3.Error as e:
            self._handle_schema_check_failure(f"Failed to check database schema version: {e}")
        except SystemExit:
            raise  # Re-raise sys.exit calls
        except Exception as e:
            self._handle_schema_check_failure(f"Unexpected error checking schema version: {e}")
    
    def find_song_by_path(self, relative_path: str, playlist_file_path: Optional[Path] = None) -> Optional[int]:
        """
        Find a song's rowid by its relative file path
        
        Args:
            relative_path: Relative path from M3U8 file (e.g., "music/Artist/Song.flac" or "../DJFB/Song.mp3")
            playlist_file_path: Path to the playlist file for resolving relative paths
            
        Returns:
            Song's rowid if found, None otherwise
        """
        # Handle relative paths that start with ../ or ./
        if playlist_file_path and (relative_path.startswith('../') or relative_path.startswith('./')):
            # Resolve relative to the playlist file's directory
            playlist_dir = playlist_file_path.parent
            resolved_path = (playlist_dir / relative_path).resolve()
            absolute_path = resolved_path
        else:
            # Convert relative path to absolute using playlist directory as base
            absolute_path = self.playlist_dir / relative_path
        
        # Use custom encoding that matches Strawberry's behaviour - only encode spaces and unsafe URL characters
        # Keep certain special characters unencoded as Strawberry stores them literally
        # Based on testing: safe chars include !$&*()-_=+[];:'@~,. whilst encoding `¬|"£%^{}#<>?\¹²³€½¾ and spaces
        file_url = f"file://{urllib.parse.quote(str(absolute_path), safe=':/?[]@!$&\'()*+,;=.~')}"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rowid FROM songs WHERE url = ?", (file_url,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_playlist_id(self, playlist_name: str) -> Optional[int]:
        """
        Get playlist rowid by name
        
        Args:
            playlist_name: Name of the playlist
            
        Returns:
            Playlist's rowid if found, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rowid FROM playlists WHERE name = ?", (playlist_name,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def create_playlist(self, playlist_name: str) -> int:
        """
        Create a new playlist
        
        Args:
            playlist_name: Name of the new playlist
            
        Returns:
            The rowid of the created playlist
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO playlists (name, last_played, ui_order, is_favorite) VALUES (?, -1, -1, 1)",
                (playlist_name,)
            )
            conn.commit()
            return cursor.lastrowid
    
    def clear_playlist(self, playlist_id: int) -> None:
        """
        Remove all items from a playlist
        
        Args:
            playlist_id: The playlist's rowid
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM playlist_items WHERE playlist = ?", (playlist_id,))
            conn.commit()
    
    def add_song_to_playlist(self, playlist_id: int, song_id: int) -> None:
        """
        Add a song to a playlist
        
        Args:
            playlist_id: The playlist's rowid
            song_id: The song's rowid
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Insert playlist item with minimal required fields
            # type=2 indicates a local file, collection_id references the song
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
                (playlist_id, song_id)
            )
            conn.commit()
    
    def sync_playlist(self, playlist_name: str, track_paths: List[str], playlist_file_path: Optional[Path] = None) -> bool:
        """
        Synchronise a playlist with the given track paths
        
        Args:
            playlist_name: Name of the playlist to sync
            track_paths: List of relative file paths
            playlist_file_path: Path to the playlist file for resolving relative paths
            
        Returns:
            True if sync was successful, False otherwise
        """
        try:
            # Get or create playlist
            playlist_id = self.get_playlist_id(playlist_name)
            if playlist_id is None:
                logger.info(f"Creating new playlist: {playlist_name}")
                playlist_id = self.create_playlist(playlist_name)
            
            # Clear existing playlist items
            self.clear_playlist(playlist_id)
            logger.info(f"Cleared existing items from playlist: {playlist_name}")
            
            # Add new tracks
            added_count = 0
            missing_count = 0
            
            for track_path in track_paths:
                song_id = self.find_song_by_path(track_path, playlist_file_path)
                if song_id:
                    self.add_song_to_playlist(playlist_id, song_id)
                    added_count += 1
                else:
                    logger.warning(f"Song not found in database: {track_path}")
                    missing_count += 1
            
            logger.info(f"Playlist '{playlist_name}' synchronised: {added_count} tracks added, {missing_count} tracks missing")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync playlist '{playlist_name}': {e}")
            return False


class PlaylistEventHandler(FileSystemEventHandler):
    """Handles file system events for M3U8 files"""
    
    def __init__(self, cache: PlaylistCache, config: Config, ignore_schema_version: bool = False):
        self.db = StrawberryDB(config.strawberry_db, config.playlist_dir, ignore_schema_version)
        self.parser = M3U8Parser(config.get_monitoring_config())
        self.cache = cache
        self.config = config
        # Debounce mechanism to avoid multiple rapid updates
        self.last_modified = {}
        self.debounce_delay = config.get_monitoring_config().get("debounce_delay", 2.0)
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Only process M3U8 files
        if file_path.suffix.lower() != '.m3u8':
            return
        
        # Debounce rapid successive modifications
        current_time = time.time()
        if file_path in self.last_modified:
            if current_time - self.last_modified[file_path] < self.debounce_delay:
                return
        
        self.last_modified[file_path] = current_time
        
        logger.info(f"Detected change in playlist: {file_path.name}")
        self.sync_playlist_file(file_path)
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Only process M3U8 files
        if file_path.suffix.lower() != '.m3u8':
            return
        
        logger.info(f"Detected new playlist: {file_path.name}")
        self.sync_playlist_file(file_path)
    
    def sync_playlist_file(self, file_path: Path, update_cache: bool = True):
        """
        Synchronise a single playlist file with the database
        
        Args:
            file_path: Path to the M3U8 file
            update_cache: Whether to update the cache with the new modification time
        """
        try:
            # Parse the playlist file
            track_paths = self.parser.parse_playlist(file_path)
            
            if not track_paths:
                logger.warning(f"No tracks found in {file_path.name}")
                return
            
            # Extract playlist name (remove .m3u8 extension)
            playlist_name = file_path.stem
            
            # Sync with database
            success = self.db.sync_playlist(playlist_name, track_paths, file_path)
            
            if success:
                logger.info(f"Successfully synchronised playlist: {playlist_name}")
                
                # Update cache with current modification time
                if update_cache:
                    try:
                        mtime = file_path.stat().st_mtime
                        self.cache.update_playlist(playlist_name, mtime)
                        logger.debug(f"Updated cache for playlist: {playlist_name}")
                    except Exception as e:
                        logger.warning(f"Failed to update cache for {playlist_name}: {e}")
            else:
                logger.error(f"Failed to synchronise playlist: {playlist_name}")
                
        except Exception as e:
            logger.error(f"Error processing playlist {file_path.name}: {e}")


def check_for_running_instances() -> None:
    """
    Check if another instance of this script is already running
    
    Exits with error code 1 if another instance is found
    """
    current_pid = os.getpid()
    script_name = Path(__file__).name
    
    running_instances = []
    
    try:
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if not cmdline:
                    continue
                
                # Check if this process is running our script
                if (len(cmdline) >= 2 and 
                    'python' in cmdline[0] and 
                    script_name in cmdline[1] and 
                    proc.info['pid'] != current_pid):
                    running_instances.append(proc.info['pid'])
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process might have disappeared or we don't have access
                continue
                
    except Exception as e:
        # If we can't check processes, log a warning but continue
        print(f"Warning: Could not check for running instances: {e}")
        return
    
    if running_instances:
        print("❌ Error: Another instance of the Strawberry Playlist Synchronisation Daemon is already running!")
        print(f"   Found running instance(s) with PID(s): {', '.join(map(str, running_instances))}")
        print()
        print("💡 To resolve this issue:")
        for pid in running_instances:
            print(f"   kill {pid}")
        print()
        print("   Or to kill all instances:")
        print(f"   pkill -f {script_name}")
        sys.exit(1)


def main():
    """Main daemon function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Strawberry Playlist Synchronisation Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--config-file', '-c', 
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )
    parser.add_argument(
        '--ignore-database-schema-version',
        action='store_true',
        help='Bypass database schema version check (WARNING: may cause data corruption or loss!)'
    )
    parser.add_argument(
        '--create-config',
        action='store_true',
        help='Create a configuration file with default settings'
    )
    args = parser.parse_args()
    
    # Handle --create-config flag
    if args.create_config:
        config_manager = Config(args.config_file)
        success = config_manager.create_config_file()
        sys.exit(0 if success else 1)
    
    # Initialize configuration with specified config file
    global config
    config = Config(args.config_file)
    
    # Configure the existing global logger with file output and proper settings
    log_config = config.get_logging_config()
    
    # Clear any existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Add file handler and console handler
    file_handler = logging.FileHandler(config.log_file)
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Set formatter for both handlers
    formatter = logging.Formatter(log_config.get("format", "%(asctime)s - %(levelname)s - %(message)s"))
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Set log level
    logger.setLevel(getattr(logging, log_config.get("level", "INFO")))
    
    logger.info("Starting Strawberry Playlist Synchronisation Daemon")
    if config.config_file.exists():
        logger.info(f"Using configuration file: {config.config_file.resolve()}")
    else:
        logger.info(f"Using default configuration (config file not found: {config.config_file.resolve()}) - run with --create-config to create a config file")
    logger.info(f"Playlist directory: {config.playlist_dir}")
    logger.info(f"Database: {config.strawberry_db}")
    
    # Verify paths exist
    if not config.playlist_dir.exists():
        logger.error(f"Playlist directory does not exist: {config.playlist_dir}")
        sys.exit(1)
    
    if not config.strawberry_db.exists():
        logger.error(f"Strawberry database does not exist: {config.strawberry_db}")
        sys.exit(1)
    
    # Initialize cache
    cache = PlaylistCache(config.cache_file)
    
    # Create database backup on every startup with intelligent naming and retention
    logger.info("🔄 Creating database backup...")
    backup_path = cache.create_database_backup(config.strawberry_db, config.backup_dir, config.config)
    if backup_path:
        logger.info(f"📁 Database backup location: {backup_path}")
    else:
        logger.warning("⚠️  Failed to create database backup - proceeding with sync anyway")
    
    # Set up file system monitoring
    event_handler = PlaylistEventHandler(cache, config, args.ignore_database_schema_version)
    observer = Observer()
    observer.schedule(event_handler, str(config.playlist_dir), recursive=False)
    
    # Start monitoring
    observer.start()
    logger.info(f"Monitoring playlist files in: {config.playlist_dir}")
    
    try:
        # Perform selective initial sync based on modification times
        logger.info("Checking playlists for changes since last sync...")
        m3u8_files = list(config.playlist_dir.glob("*.m3u8"))
        
        sync_count = 0
        skip_count = 0
        
        for m3u8_file in m3u8_files:
            if cache.needs_sync(m3u8_file):
                logger.info(f"Initial sync: {m3u8_file.name}")
                event_handler.sync_playlist_file(m3u8_file, update_cache=True)
                sync_count += 1
            else:
                logger.debug(f"Skipping unchanged playlist: {m3u8_file.name}")
                skip_count += 1
        
        logger.info(f"Initial synchronisation complete: {sync_count} playlists synced, {skip_count} playlists skipped")
        logger.info("Monitoring for changes...")
        
        # Keep the daemon running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        observer.stop()
        observer.join()
        logger.info("Strawberry Playlist Synchronisation Daemon stopped")


if __name__ == "__main__":
    check_for_running_instances()
    main() 