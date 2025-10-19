# Strawberry Playlist Synchronisation Daemon

A Python daemon that synchronises `.m3u8` playlist files with the Strawberry Music Player's SQLite database. Perfect for keeping your desktop playlists in sync with mobile music players like Poweramp via Syncthing.

## Features

- **🔄 Real-time sync**: Automatically detects changes to M3U8 files and updates Strawberry playlists
- **📱 Unidirectional sync**: Reads M3U8 files edited on other devices and synchronised back to this one via Syncthing, for example
- **🛡️ Read-only M3U8 access**: Never writes to M3U8 files, eliminating risk of playlist corruption
- **⚡ Smart caching**: Only syncs changed playlists for optimal performance
- **🔒 Database safety**: Automatic backups on startup
- **📝 Comprehensive logging**: Detailed logs for troubleshooting
- **🧪 Built-in testing**: Test suite for validating configuration and functionality
- **🖥️ Desktop integration**: Optional GNOME autostart and application menu integration
- **📊 Schema validation**: Ensures compatibility with your Strawberry database version

## Requirements

- Python 3.6+
- Strawberry Music Player
- SQLite3
- Linux (untested on Windows or macOS)

## Installation

1. **Clone or download** this repository to your preferred location
2. **Install dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Configure** the daemon by editing `config.json` (see Configuration section)

4. **Test** your configuration:
   ```bash
   python3 test.py --all
   # If above fails, test a specific song you know is in the Strawberry database:
   python3 test.py --all --song '/path/to/song.flac'
   ```

5. **Run** the daemon:
   ```bash
   python3 strawberry_playlist_sync.py
   ```

### Example Output

```bash
2025-06-08 04:03:38,488 - INFO - Starting Strawberry Playlist Synchronisation Daemon
2025-06-08 04:03:38,488 - INFO - Using configuration file: /home/user/strawberry-playlist-sync/config.json
2025-06-08 04:03:38,488 - INFO - Playlist directory: /home/user/Music
2025-06-08 04:03:38,488 - INFO - Database: /home/user/.local/share/strawberry/strawberry/strawberry.db
2025-06-08 04:03:38,488 - INFO - Loaded cache for 146 playlists
2025-06-08 04:03:38,488 - INFO - 🔄 Creating database backup...
2025-06-08 04:03:38,488 - INFO - Creating startup backup: strawberry_backup_startup_20250608_040338.db
2025-06-08 04:03:38,491 - INFO - 🗑️   Removed old backup: strawberry_backup_startup_20250608_024353.db
2025-06-08 04:03:38,506 - INFO - ✅ Database backup created successfully: /home/user/strawberry-playlist-sync/backups/strawberry_backup_startup_20250608_040338.db
2025-06-08 04:03:38,506 - INFO - 📁 Database backup location: /home/user/strawberry-playlist-sync/backups/strawberry_backup_startup_20250608_040338.db
2025-06-08 04:03:38,507 - INFO - Database schema version 20 is supported
2025-06-08 04:03:38,508 - INFO - Monitoring playlist files in: /home/user/Music
2025-06-08 04:03:38,508 - INFO - Checking playlists for changes since last sync...
2025-06-08 04:03:38,509 - INFO - Initial synchronisation complete: 0 playlists synced, 146 playlists skipped
2025-06-08 04:03:38,509 - INFO - Monitoring for changes...
2025-06-09 13:52:59,646 - INFO - Detected change in playlist: Pop.m3u8
2025-06-09 13:52:59,646 - INFO - Parsed 23 tracks from Pop.m3u8
2025-06-09 13:52:59,651 - INFO - Cleared existing items from playlist: Pop
2025-06-09 13:52:59,726 - INFO - Playlist 'Pop' synchronised: 23 tracks added, 0 tracks missing
2025-06-09 13:52:59,726 - INFO - Successfully synchronised playlist: Pop
```

## Configuration

If you need to create a custom configuration file, run `python3 strawberry_playlist_sync.py [--config-file <path>] --create-config` to create a new config file.

```json
{
    "playlist_directory": "~/Music",
    "strawberry_db_path": "~/.local/share/strawberry/strawberry/strawberry.db",
    "log_file": "playlist_sync.log",
    "log_level": "INFO",
    "cache_file": "playlist_sync_cache.json",
    "backup_directory": "backups",
    "backup_retention": 3
}
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `playlist_directory` | Directory containing your `.m3u8` files | **Required** |
| `strawberry_db_path` | Path to Strawberry's collection database | **Required** |
| `log_file` | Log file name (relative to script directory) | `"playlist_sync.log"` |
| `log_level` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `"INFO"` |
| `cache_file` | Cache file for tracking playlist changes | `"playlist_sync_cache.json"` |
| `backup_directory` | Directory for database backups (relative to script directory) | `"backups"` |
| `backup_retention` | Number of startup backups to keep (0 = unlimited) | `3` |

### Finding Your Strawberry Database

The Strawberry database is typically located at:
- **Linux**: `~/.local/share/strawberry/strawberry/strawberry.db`

## Testing

The included test script validates your configuration and tests all components:

```bash
# Test everything
python3 test.py --all

# Test specific components
python3 test.py --config          # Configuration validation
python3 test.py --database        # Database connectivity
python3 test.py --parser          # M3U8 parsing
python3 test.py --sync playlist.m3u8  # Test specific playlist sync

# Test song lookup
python3 test.py --song "music/Artist/Song.flac"

# Verbose output
python3 test.py --all --verbose
```

### Example Test Output

```bash
$ python3 test.py --all
🧪 Running comprehensive test suite...

✅ Configuration Test
   📄 Config file: config.json
   📁 Playlist directory: /home/user/Music/Playlists (exists)
   🗄️ Database path: /home/user/.local/share/strawberry/strawberry/strawberry.db (exists)

✅ Database Test
   🔗 Connection: Successful
   📊 Schema version: 20 (supported)
   🎵 Songs in database: 1,247

✅ M3U8 Parser Test
   📝 Test playlist created: /tmp/test_playlist.m3u8
   🎵 Parsed 3 songs successfully
   🧹 Cleanup completed

✅ Playlist Sync Test
   📝 Test playlist: test_sync_playlist.m3u8
   🎵 Songs found: 2/2
   ✅ Playlist created successfully
   🧹 Cleanup completed

🎉 All tests passed! Your configuration is ready.
```

## Desktop Integration (Optional)

For GNOME desktop environments, you can install desktop integration for automatic startup and application menu entry:

### Installation Options

Install GNOME desktop integration for automatic startup:

```bash
# Install with autostart (default)
python3 install.py --gnome-desktop

# Install with custom config
python3 install.py --gnome-desktop --config-file my_config.json

# Install without autostart
python3 install.py --gnome-desktop --no-autostart

# Check installation status
python3 install.py --status

# Uninstall
python3 install.py --gnome-desktop --uninstall

# Show help
python3 install.py --help
```

#### Example Install Output

```bash
$ python3 install.py --gnome-desktop --config-file config.json
📦 Installing GNOME desktop integration...
📄 Using configuration file: /home/user/playlist-sync/config.json
✅ Desktop file created: /home/user/.local/share/applications/strawberry-playlist-sync.desktop
✅ Autostart file created: /home/user/.config/autostart/strawberry-playlist-sync.desktop
🚀 The daemon will now start automatically on login
🔄 Desktop database updated

🎉 Installation completed successfully!

📋 What was installed:
   • Desktop entry for application menu
   • Autostart entry for automatic daemon startup

🔧 Next steps:
   1. Configure your settings in the config file
   2. Log out and log back in (or restart) to enable autostart
   3. The daemon will start automatically on future logins

💡 Tip: Use 'python3 install.py --status' to check installation status
```

## How It Works

### M3U8 File Format
The daemon parses M3U8 playlist files with the following format:
```
#EXTM3U
#EXTINF:265,Artist - Title
music/Artist/Artist - Title.flac
#EXTINF:244,Imagine Dragons - Wrecked
music/Imagine Dragons/Imagine Dragons - Wrecked.flac
```

**Relative Path Support**: The daemon supports both standard relative paths (relative to the playlist directory) and playlist-relative paths:

```
#EXTM3U
#EXTINF:244,Standard relative path
music/Artist/Song.flac
#EXTINF:265,Playlist-relative path
../OtherFolder/Song.mp3
#EXTINF:180,Current directory relative
./Song.wav
```

- **Standard paths** (e.g., `music/Artist/Song.flac`) are resolved relative to the configured playlist directory
- **Playlist-relative paths** (e.g., `../Artist/Song.mp3`) are resolved relative to the playlist file's location
- **Current directory paths** (e.g., `./Song.wav`) are resolved relative to the playlist file's directory

### Database Integration
- **Songs Table**: Matches file paths from M3U8 to songs in Strawberry's database using the `url` field
- **Playlists Table**: Creates or updates playlists by name (M3U8 filename without extension)
- **Playlist Items Table**: Links songs to playlists using `collection_id` references

### Synchronisation Process
1. **File Monitoring**: Uses `watchdog` to detect changes to `.m3u8` files
2. **Parsing**: Extracts relative file paths from M3U8 format with retry logic
3. **Database Lookup**: Finds corresponding songs in Strawberry's database
4. **Playlist Update**: Clears existing playlist items and adds new ones
5. **Caching**: Updates modification time cache to avoid redundant syncing
6. **Logging**: Records all operations for debugging

### Sync Direction and Safety

**⚠️ IMPORTANT**: This daemon provides **unidirectional sync only** - from M3U8 files to Strawberry database.

- **✅ M3U8 → Strawberry**: Automatically syncs changes from `.m3u8` files to Strawberry playlists
- **❌ Strawberry → M3U8**: Does NOT automatically export Strawberry playlists back to M3U8 files
- **🛡️ Read-Only M3U8**: The daemon never writes to M3U8 files, eliminating any risk of M3U8 corruption

**To export Strawberry playlists back to M3U8 format:**
1. Open the saved playlist in Strawberry Music Player
2. Press `Ctrl+S` (or File → Save Playlist)
3. Choose "M3U format" and save with `.m3u8` file extension
4. The exported M3U8 file will then be monitored for future changes

This design ensures your M3U8 files remain safe from any potential corruption whilst providing seamless one-way synchronisation from your mobile device edits to your desktop music player.

### Smart Caching System
- **Initial Sync**: Only syncs playlists that have changed since last run
- **Modification Tracking**: Stores last modified times in JSON cache
- **Performance**: Dramatically reduces startup time for large playlist collections

### Automatic Database Backup
- **Startup Protection**: Automatically creates a database backup on every daemon startup
- **Special First Backup**: The very first backup is named `strawberry_before_first_use.db` and is never deleted
- **Regular Startup Backups**: Subsequent startups create timestamped backups: `strawberry_backup_startup_YYYYMMDD_HHMMSS.db`
- **Automatic Retention**: Keeps only the configured number of startup backups (default: 3), automatically removing older ones
- **Backup Location**: Stored in the configured backup directory (script directory) with timestamps
- **Safety First**: Ensures you always have recent backups before any sync operations

## Usage with Poweramp and Syncthing

1. **Android Setup**:
   - Install Poweramp on your Android device
   - Configure Syncthing to sync your playlist directory
   - **Important**: Playlists created directly in Poweramp remain in Poweramp's internal database and are NOT written to `.m3u8` files on disk
   - **Workaround**: Create initial `.m3u8` playlist files using another application (such as via Strawberry Music Player playlist export to `.m3u8`) first
   - Once `.m3u8` files exist on disk, Poweramp will automatically synchronise its internal database with these files when you edit playlists
   - Edit existing playlists in Poweramp (changes are written to the corresponding `.m3u8` files)

2. **Linux Setup**:
   - Configure the daemon with your playlist directory path
   - Run the daemon on your Linux machine
   - Changes sync via Syncthing and are automatically applied to Strawberry

3. **Workflow (Android → Linux)**:
   - **Prerequisites**: Ensure `.m3u8` playlist files already exist on disk (create them in Strawberry and export to `.m3u8` first if needed)
   - Edit playlists on Android → Poweramp updates `.m3u8` files
   - Syncthing syncs changes to Linux
   - Daemon detects file changes and updates Strawberry database
   - Strawberry shows updated playlists when double-clicking the playlist in the sidebar (if playlist is already open in a tab, you will need to close and re-open it to see the changes)

4. **Reverse Workflow (Linux → Android)**:
   - Create/edit playlists in Strawberry Music Player
   - Export to M3U8: Open playlist → `Ctrl+S` → Save as M3U format with `.m3u8` extension
   - Syncthing syncs the M3U8 file to Android
   - Poweramp detects file change and shows the updated playlist

**Note**: The daemon only handles the Android → Linux direction automatically. Linux → Android requires manual export from Strawberry to maintain M3U8 file safety.

## Troubleshooting

### Common Issues

1. **Songs not found in database**:
   - Ensure Strawberry has scanned your music library
   - Check that file paths in M3U8 match actual file locations
   - Verify file permissions
   - Test with: `python3 test.py --song "path/to/song.flac"`

2. **Database locked errors**:
   - Close Strawberry before running initial sync
   - The daemon handles concurrent access during normal operation

3. **Configuration issues**:
   - Test configuration: `python3 test.py --config`
   - Check paths exist and are accessible
   - Verify JSON syntax in config file

4. **Playlist sync failures**:
   - Test specific playlist: `python3 test.py --sync playlist.m3u8`
   - Check M3U8 file format and encoding
   - Review logs for detailed error messages

### Log Files

- **Application logs**: Located in the script directory as specified in config
- **Test logs**: Displayed on console during test runs

### Manual Testing

Test individual components:
```bash
# Test configuration loading
python3 test.py --config

# Test database connectivity
python3 test.py --database

# Test M3U8 parsing
python3 test.py --parser

# Test complete workflow
python3 test.py --all
```

## File Structure

```
script-directory/                  # Where you run the daemon from
├── strawberry_playlist_sync.py    # Main daemon script
├── config.json                    # Default configuration file
├── test.py                        # Comprehensive test script
├── install.py                     # Desktop integration installer
├── requirements.txt               # Python dependencies
├── README.md                      # This file
├── playlist_sync.log              # Application logs (created at runtime)
├── playlist_sync_cache.json       # Playlist state cache (created at runtime)
├── backups/                       # Database backups directory (created at runtime)
│   └── strawberry_before_first_sync_backup_*.db
└── my_custom_config.json          # Custom config files (if used)

your-playlist-directory/           # Your playlist and music files
├── *.m3u8                         # Your playlist files
├── music/                         # Your music collection
│   ├── Artist1/
│   │   └── Song.flac
│   └── Artist2/
│       └── Song.mp3
└── ...
```

**Note**: Log, cache, and backup files are created in the same directory as your configuration file (script directory), not in the playlist directory. This keeps your playlist directory clean and allows for better organisation of daemon-related files.

## Contributing

This daemon was created to solve a specific synchronisation problem between Android and Linux music players. Feel free to adapt it for your own use case or contribute improvements.

### Development

1. Fork the repository
2. Make your changes
3. Run the test suite: `python3 test.py --all`
4. Submit a pull request

### Database Schema Compatibility

The daemon includes automatic database schema version checking to ensure compatibility with your Strawberry database:

- **Supported Schema Version**: Currently supports Strawberry database schema version **20**
- **Automatic Checking**: The daemon checks the schema version on startup and exits if incompatible
- **Bypass Option**: Use `--ignore-database-schema-version` to bypass the check (**⚠️ WARNING: may cause data corruption or loss!**)

**Schema Version Errors**: If you encounter a schema version error, it means your Strawberry database uses a different schema version than what this daemon supports. This could happen if:
- You're using a newer version of Strawberry with schema changes
- You're using an older version of Strawberry
- The database is corrupted or incompatible

**Recommended Actions**:
1. Check your Strawberry version and update if necessary
2. **Always backup your database before proceeding**
3. Only use `--ignore-database-schema-version` if you understand the risks of potential data corruption or loss
4. Test thoroughly with a backup database first

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Shiraz McClennon
