#!/usr/bin/env python3
"""
Installation script for Strawberry Playlist Synchronisation Daemon

This script provides installation and configuration options for integrating
the playlist sync daemon with GNOME desktop environments.

Copyright (c) 2025 Shiraz McClennon
Licensed under the MIT License. See LICENSE file for details.
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional


class GnomeInstaller:
    """Handles GNOME desktop integration for the playlist sync daemon"""
    
    def __init__(self):
        self.script_dir = Path(__file__).parent.resolve()
        self.daemon_script = self.script_dir / "strawberry_playlist_sync.py"
        self.applications_dir = Path.home() / ".local" / "share" / "applications"
        self.autostart_dir = Path.home() / ".config" / "autostart"
        self.desktop_file_name = "strawberry-playlist-sync.desktop"
        
    def _ensure_directories_exist(self):
        """Ensure required directories exist"""
        self.applications_dir.mkdir(parents=True, exist_ok=True)
        self.autostart_dir.mkdir(parents=True, exist_ok=True)
    
    def _create_desktop_file_content(self, config_file: Optional[str] = None) -> str:
        """
        Create the content for the .desktop file
        
        Args:
            config_file: Optional path to configuration file
            
        Returns:
            Desktop file content as string
        """
        # Get the Python interpreter used to run this script
        python_interpreter = sys.executable
        
        # Build the command line arguments
        exec_args = [python_interpreter, str(self.daemon_script)]
        if config_file:
            exec_args.extend(["--config-file", config_file])
        
        exec_command = " ".join(exec_args)
        
        return f"""[Desktop Entry]
Name=Playlist Sync
GenericName=Music Playlist Synchronisation Daemon
Comment=Monitors M3U8 playlist files and synchronises them with Strawberry Music Player
Type=Application
Exec={exec_command}
Path={self.script_dir}
Terminal=false
Categories=AudioVideo;Audio;Player;
Keywords=music;playlist;sync;strawberry;
Icon=strawberry
StartupNotify=true
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=10
"""
    
    def install_desktop_file(self, config_file: Optional[str] = None, autostart: bool = True) -> bool:
        """
        Install the desktop file for the playlist sync daemon
        
        Args:
            config_file: Optional path to configuration file
            autostart: Whether to enable autostart functionality
            
        Returns:
            True if installation was successful, False otherwise
        """
        try:
            # Verify the daemon script exists
            if not self.daemon_script.exists():
                print(f"❌ Daemon script not found: {self.daemon_script}")
                return False
            
            # Make sure the daemon script is executable
            self.daemon_script.chmod(0o755)
            
            # Ensure directories exist
            self._ensure_directories_exist()
            
            # Create desktop file content
            desktop_content = self._create_desktop_file_content(config_file)
            
            # Write to applications directory
            app_desktop_file = self.applications_dir / self.desktop_file_name
            with open(app_desktop_file, 'w', encoding='utf-8') as f:
                f.write(desktop_content)
            
            print(f"✅ Desktop file created: {app_desktop_file}")
            
            # If autostart is enabled, also create in autostart directory
            if autostart:
                autostart_desktop_file = self.autostart_dir / self.desktop_file_name
                with open(autostart_desktop_file, 'w', encoding='utf-8') as f:
                    f.write(desktop_content)
                
                print(f"✅ Autostart file created: {autostart_desktop_file}")
                print("🚀 The daemon will now start automatically on login")
            
            # Update desktop database
            try:
                subprocess.run(["update-desktop-database", str(self.applications_dir)], 
                             check=False, capture_output=True)
                print("🔄 Desktop database updated")
            except FileNotFoundError:
                print("⚠️  update-desktop-database not found, desktop file may not appear immediately")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to install desktop file: {e}")
            return False
    
    def uninstall_desktop_file(self) -> bool:
        """
        Remove the desktop file and autostart entry
        
        Returns:
            True if uninstallation was successful, False otherwise
        """
        try:
            removed_files = []
            
            # Remove from applications directory
            app_desktop_file = self.applications_dir / self.desktop_file_name
            if app_desktop_file.exists():
                app_desktop_file.unlink()
                removed_files.append(str(app_desktop_file))
            
            # Remove from autostart directory
            autostart_desktop_file = self.autostart_dir / self.desktop_file_name
            if autostart_desktop_file.exists():
                autostart_desktop_file.unlink()
                removed_files.append(str(autostart_desktop_file))
            
            if removed_files:
                print("✅ Removed desktop files:")
                for file_path in removed_files:
                    print(f"   • {file_path}")
                
                # Update desktop database
                try:
                    subprocess.run(["update-desktop-database", str(self.applications_dir)], 
                                 check=False, capture_output=True)
                    print("🔄 Desktop database updated")
                except FileNotFoundError:
                    pass
                
                print("🛑 Autostart disabled - daemon will no longer start automatically")
            else:
                print("ℹ️  No desktop files found to remove")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to uninstall desktop file: {e}")
            return False
    
    def check_installation_status(self) -> dict:
        """
        Check the current installation status
        
        Returns:
            Dictionary with installation status information
        """
        app_desktop_file = self.applications_dir / self.desktop_file_name
        autostart_desktop_file = self.autostart_dir / self.desktop_file_name
        
        return {
            "daemon_script_exists": self.daemon_script.exists(),
            "daemon_script_path": str(self.daemon_script),
            "desktop_file_installed": app_desktop_file.exists(),
            "desktop_file_path": str(app_desktop_file) if app_desktop_file.exists() else None,
            "autostart_enabled": autostart_desktop_file.exists(),
            "autostart_file_path": str(autostart_desktop_file) if autostart_desktop_file.exists() else None,
        }


def check_gnome_environment() -> bool:
    """
    Check if we're running in a GNOME environment
    
    Returns:
        True if GNOME is detected, False otherwise
    """
    desktop_session = os.environ.get("DESKTOP_SESSION", "").lower()
    xdg_current_desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    
    gnome_indicators = ["gnome", "ubuntu", "pop"]
    
    return any(indicator in desktop_session for indicator in gnome_indicators) or \
           any(indicator in xdg_current_desktop for indicator in gnome_indicators)


def main():
    """Main installation function"""
    parser = argparse.ArgumentParser(
        description="Installation script for Strawberry Playlist Synchronisation Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 install.py --gnome-desktop                    # Install with autostart
  python3 install.py --gnome-desktop --no-autostart    # Install without autostart
  python3 install.py --gnome-desktop --config my.json  # Install with custom config
  python3 install.py --gnome-desktop --uninstall       # Remove installation
  python3 install.py --status                           # Check installation status
        """
    )
    
    parser.add_argument(
        '--gnome-desktop',
        action='store_true',
        help='Install GNOME desktop integration (.desktop file)'
    )
    parser.add_argument(
        '--uninstall',
        action='store_true',
        help='Remove desktop integration (use with --gnome-desktop)'
    )
    parser.add_argument(
        '--config-file', '-c',
        help='Path to configuration file to use in desktop entry'
    )
    parser.add_argument(
        '--no-autostart',
        action='store_true',
        help='Install desktop file but do not enable autostart'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Check current installation status'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force installation even if GNOME is not detected'
    )
    
    args = parser.parse_args()
    
    # Check if any action was specified
    if not any([args.gnome_desktop, args.status]):
        parser.print_help()
        sys.exit(1)
    
    installer = GnomeInstaller()
    
    # Handle status check
    if args.status:
        status = installer.check_installation_status()
        print("📊 Installation Status:")
        print(f"   Daemon script: {'✅ Found' if status['daemon_script_exists'] else '❌ Not found'}")
        print(f"   Path: {status['daemon_script_path']}")
        print(f"   Desktop file: {'✅ Installed' if status['desktop_file_installed'] else '❌ Not installed'}")
        if status['desktop_file_path']:
            print(f"   Desktop path: {status['desktop_file_path']}")
        print(f"   Autostart: {'✅ Enabled' if status['autostart_enabled'] else '❌ Disabled'}")
        if status['autostart_file_path']:
            print(f"   Autostart path: {status['autostart_file_path']}")
        return
    
    # Handle GNOME desktop integration
    if args.gnome_desktop:
        # Check GNOME environment unless forced
        if not args.force and not check_gnome_environment():
            print("⚠️  GNOME desktop environment not detected.")
            print("   This installer is designed for GNOME-based systems.")
            print("   Use --force to install anyway, or check your desktop environment.")
            sys.exit(1)
        
        if args.uninstall:
            print("🗑️  Uninstalling GNOME desktop integration...")
            success = installer.uninstall_desktop_file()
            sys.exit(0 if success else 1)
        else:
            print("📦 Installing GNOME desktop integration...")
            
            # Validate config file if specified
            if args.config_file:
                config_path = Path(args.config_file)
                if not config_path.exists():
                    print(f"❌ Configuration file not found: {config_path}")
                    sys.exit(1)
                print(f"📄 Using configuration file: {config_path.resolve()}")
            
            autostart = not args.no_autostart
            success = installer.install_desktop_file(args.config_file, autostart)
            
            if success:
                print()
                print("🎉 Installation completed successfully!")
                print()
                print("📋 What was installed:")
                print("   • Desktop entry for application menu")
                if autostart:
                    print("   • Autostart entry for automatic daemon startup")
                print()
                print("🔧 Next steps:")
                print("   1. Configure your settings in the config file")
                print("   2. Log out and log back in (or restart) to enable autostart")
                print("   3. The daemon will start automatically on future logins")
                print()
                print("💡 Tip: Use 'python3 install.py --status' to check installation status")
            
            sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 