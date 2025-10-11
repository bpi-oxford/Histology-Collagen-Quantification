"""
Windows libvips PATH configuration helper
This module must be imported at the start of any script that uses pyvips on Windows.

Usage:
    import vips_path_windows  # Import at the very start
    import pyvips  # Now this will work
"""

import os
import sys
from pathlib import Path
import configparser

def read_config():
    """Read libvips installation path from config file."""
    config_file = Path(__file__).parent.parent / ".vips_config.ini"

    if config_file.exists():
        config = configparser.ConfigParser()
        config.read(config_file)

        if 'libvips' in config:
            install_dir = config['libvips'].get('install_dir', '').strip()
            if install_dir:
                return install_dir

            # Try search paths
            search_paths = config['libvips'].get('search_paths', '').strip()
            if search_paths:
                return [p.strip() for p in search_paths.split(',')]

    return None

def get_vips_dirs():
    """Get list of libvips directories to search."""
    vips_dirs = []

    # First try config file
    config_path = read_config()
    if config_path:
        if isinstance(config_path, str):
            vips_dirs.append(config_path)
        elif isinstance(config_path, list):
            vips_dirs.extend(config_path)

    # Fallback to common locations
    vips_dirs.extend([
        r'C:\vips-dev-8.16.0',
        r'C:\vips-dev-8.15',
        r'D:\vips\vips-dev-8.16.0',
        r'D:\MSVC-build\vips\vips-dev-8.16.0',
    ])

    return vips_dirs

def setup_vips_path():
    """Add libvips bin directory to PATH if not already present."""

    vips_dirs = get_vips_dirs()

    # Check each directory
    for vips_dir in vips_dirs:
        vips_bin = os.path.join(vips_dir, 'bin')

        if os.path.exists(vips_bin):
            # Add to PATH if not already there
            if vips_bin not in os.environ['PATH']:
                os.environ['PATH'] = vips_bin + ';' + os.environ['PATH']
                print(f"✓ Added libvips to PATH: {vips_bin}", file=sys.stderr)
            else:
                print(f"✓ libvips already in PATH: {vips_bin}", file=sys.stderr)
            return True

    # If we get here, libvips was not found
    print("=" * 60, file=sys.stderr)
    print("ERROR: libvips not found!", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("Please install libvips using one of these methods:", file=sys.stderr)
    print("1. Run: bash setup_windows.sh", file=sys.stderr)
    print("2. Manual install from: https://www.libvips.org/install.html", file=sys.stderr)
    print(f"\nSearched locations:", file=sys.stderr)
    for vips_dir in vips_dirs:
        print(f"  - {os.path.join(vips_dir, 'bin')}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    sys.exit(1)

# Auto-configure when imported
setup_vips_path()
