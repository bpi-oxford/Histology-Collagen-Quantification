#!/bin/bash

# Windows Setup Script for Histology Collagen Quantification
# This script automates libvips installation on Windows via Git Bash
# Compatible with Git Bash/MSYS2 on Windows

set -e  # Exit on any error

echo "=========================================="
echo "  Windows Environment Setup"
echo "  Histology Collagen Quantification"
echo "=========================================="
echo

# Configuration
LIBVIPS_VERSION="8.16.0"
LIBVIPS_URL="https://github.com/libvips/build-win64-mxe/releases/download/v${LIBVIPS_VERSION}/vips-dev-w64-all-${LIBVIPS_VERSION}.zip"
DEFAULT_INSTALL_DIR="C:/vips-dev-${LIBVIPS_VERSION}"
INSTALL_DIR=""  # Will be set by user prompt
TEMP_DIR="/tmp/libvips_install"

# Function to check if running on Windows
check_windows() {
    if [[ ! "$OSTYPE" =~ ^(msys|cygwin|win32) ]]; then
        echo "Error: This script is designed for Windows (Git Bash/MSYS2)"
        echo "Detected OS: $OSTYPE"
        exit 1
    fi
    echo "✓ Detected Windows environment"
}

# Function to check Python installation
check_python() {
    echo
    echo "Checking Python installation..."

    if ! command -v python &> /dev/null; then
        echo "Error: Python is not installed or not in PATH"
        echo
        echo "Please install Python 3.8+ from: https://www.python.org/downloads/"
        echo "Make sure to check 'Add Python to PATH' during installation"
        exit 1
    fi

    python_version=$(python --version 2>&1 | awk '{print $2}')
    echo "✓ Found Python $python_version"

    # Check if it's 64-bit Python
    python_arch=$(python -c "import platform; print(platform.architecture()[0])")
    if [[ "$python_arch" != "64bit" ]]; then
        echo "Warning: Python is not 64-bit ($python_arch detected)"
        echo "libvips requires 64-bit Python. Please install 64-bit Python."
        exit 1
    fi
    echo "✓ Python is 64-bit"
}

# Function to prompt for installation directory
prompt_install_dir() {
    echo
    echo "=========================================="
    echo "  libvips Installation Location"
    echo "=========================================="
    echo
    echo "Choose installation directory for libvips."
    echo "Default: $DEFAULT_INSTALL_DIR"
    echo
    echo "Notes:"
    echo "- Use forward slashes (/) or double backslashes (\\\\)"
    echo "- Avoid spaces in path if possible"
    echo "- Requires write permissions"
    echo

    while true; do
        read -r -p "Install directory (press Enter for default): " user_install_dir

        if [[ -z "$user_install_dir" ]]; then
            INSTALL_DIR="$DEFAULT_INSTALL_DIR"
        else
            # Normalize path separators (backslash to forward slash)
            INSTALL_DIR="${user_install_dir//\\//}"

            # Remove any ANSI escape sequences and control characters
            INSTALL_DIR=$(echo "$INSTALL_DIR" | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g' | sed 's/[[:cntrl:]]//g')

            # Trim leading/trailing whitespace
            INSTALL_DIR=$(echo "$INSTALL_DIR" | xargs)
        fi

        echo
        echo "Parsed path: $INSTALL_DIR"
        echo
        read -r -p "Is this correct? (Y/n): " confirm
        confirm=${confirm:-Y}

        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            break
        fi
        echo "Let's try again..."
        echo
    done

    echo "✓ Will install to: $INSTALL_DIR"
}

# Function to check if libvips is already installed
check_existing_libvips() {
    echo
    echo "Checking for existing libvips installation..."

    # Convert Windows path to Unix-style for checking
    install_dir_unix=$(cygpath -u "$INSTALL_DIR" 2>/dev/null || echo "$INSTALL_DIR")

    if [[ -d "$install_dir_unix" ]]; then
        echo "Found existing libvips installation at: $INSTALL_DIR"
        echo
        read -r -p "Reinstall libvips? (y/N): " reinstall
        if [[ ! "$reinstall" =~ ^[Yy]$ ]]; then
            echo "Using existing installation"
            return 1
        fi
        echo "Removing existing installation..."
        rm -rf "$install_dir_unix"
    fi
    return 0
}

# Function to download and install libvips
install_libvips() {
    echo
    echo "=========================================="
    echo "  Installing libvips"
    echo "=========================================="
    echo "Version: $LIBVIPS_VERSION"
    echo "Install location: $INSTALL_DIR"
    echo

    # Create temp directory
    mkdir -p "$TEMP_DIR"
    cd "$TEMP_DIR"

    # Download libvips
    echo "Downloading libvips..."
    zip_file="vips-dev-w64-all-${LIBVIPS_VERSION}.zip"

    if command -v curl &> /dev/null; then
        curl -L -o "$zip_file" "$LIBVIPS_URL"
    elif command -v wget &> /dev/null; then
        wget -O "$zip_file" "$LIBVIPS_URL"
    else
        echo "Error: Neither curl nor wget found. Cannot download libvips."
        echo "Please install Git for Windows which includes curl."
        exit 1
    fi

    echo "✓ Download complete"

    # Extract to install directory
    echo
    echo "Extracting libvips..."
    unzip -q "$zip_file"

    # Move to final location
    extracted_dir=$(find . -maxdepth 1 -type d -name "vips-dev-*" | head -1)
    if [[ -z "$extracted_dir" ]]; then
        echo "Error: Could not find extracted directory"
        exit 1
    fi

    # Convert to Windows path for moving
    install_dir_unix=$(cygpath -u "$INSTALL_DIR" 2>/dev/null || echo "$INSTALL_DIR")
    mkdir -p "$(dirname "$install_dir_unix")"
    mv "$extracted_dir" "$install_dir_unix"

    echo "✓ libvips installed to: $INSTALL_DIR"

    # Cleanup
    cd ~
    rm -rf "$TEMP_DIR"
}

# Function to write config file
write_config_file() {
    echo
    echo "Writing configuration file..."

    config_file=".vips_config.ini"

    # Convert to Windows-style path with backslashes for config
    install_dir_win=$(cygpath -w "$INSTALL_DIR" 2>/dev/null || echo "$INSTALL_DIR")

    cat > "$config_file" << EOF
# libvips Configuration File
# Auto-generated by setup_windows.sh on $(date)
# This file stores the libvips installation path for automatic detection

[libvips]
# Installation directory (bin subdirectory will be added to PATH)
install_dir = ${install_dir_win}

# Additional search paths (comma-separated, optional)
search_paths = C:\\vips-dev-8.16.0,C:\\vips-dev-8.15,D:\\vips\\vips-dev-8.16.0,D:\\MSVC-build\\vips\\vips-dev-8.16.0
EOF

    echo "✓ Configuration saved to: $config_file"
}

# Function to create Python path setup helper
create_python_helper() {
    echo
    echo "=========================================="
    echo "  Creating Python Configuration Helper"
    echo "=========================================="

    # Ensure python directory exists
    mkdir -p "python"

    helper_file="python/vips_path_windows.py"

    cat > "$helper_file" << 'EOF'
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
EOF

    echo "✓ Created: $helper_file"
    echo
    echo "This helper will automatically read from .vips_config.ini and configure PATH."
}

# Function to check conda/mamba installation
check_conda() {
    echo
    echo "=========================================="
    echo "  Checking Conda/Mamba"
    echo "=========================================="

    if command -v mamba &> /dev/null; then
        echo "✓ Found mamba"
        CONDA_CMD="mamba"
    elif command -v conda &> /dev/null; then
        echo "✓ Found conda"
        CONDA_CMD="conda"
    else
        echo "Warning: Neither conda nor mamba found"
        echo
        echo "To create the Python environment, please install:"
        echo "- Miniforge (recommended): https://github.com/conda-forge/miniforge"
        echo "- or Miniconda: https://docs.conda.io/en/latest/miniconda.html"
        echo
        read -r -p "Skip environment creation? (y/N): " skip_env
        if [[ "$skip_env" =~ ^[Yy]$ ]]; then
            return 1
        fi
        exit 1
    fi
    return 0
}

# Function to create conda environment
create_environment() {
    echo
    echo "=========================================="
    echo "  Creating Conda Environment"
    echo "=========================================="
    echo

    if [[ ! -f "env.yaml" ]]; then
        echo "Error: env.yaml not found"
        echo "Please run this script from the project root directory"
        exit 1
    fi

    # Check if environment already exists
    if $CONDA_CMD env list | grep -q "^collagen_quant "; then
        echo "Environment 'collagen_quant' already exists"
        read -r -p "Recreate environment? (y/N): " recreate
        if [[ "$recreate" =~ ^[Yy]$ ]]; then
            echo "Removing existing environment..."
            $CONDA_CMD env remove -n collagen_quant -y
        else
            echo "Skipping environment creation"
            return 0
        fi
    fi

    echo "Creating environment from env.yaml..."
    $CONDA_CMD env create -f env.yaml

    echo
    echo "✓ Environment created successfully"
}

# Function to test installation
test_installation() {
    echo
    echo "=========================================="
    echo "  Testing Installation"
    echo "=========================================="

    # Create a test script
    test_script="$TEMP_DIR/test_vips.py"
    mkdir -p "$TEMP_DIR"

    cat > "$test_script" << 'EOF'
import sys
sys.path.insert(0, 'python')

try:
    import vips_path_windows
    import pyvips

    print(f"✓ pyvips version: {pyvips.version(0)}.{pyvips.version(1)}.{pyvips.version(2)}")
    print("✓ libvips is working correctly!")
    sys.exit(0)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
EOF

    echo "Testing pyvips import..."
    if python "$test_script"; then
        echo
        echo "✓ Installation test passed!"
        return 0
    else
        echo
        echo "✗ Installation test failed"
        echo "Please check the error messages above"
        return 1
    fi
}

# Main installation flow
main() {
    # Return to script directory
    cd "$(dirname "${BASH_SOURCE[0]}")"

    echo "This script will:"
    echo "  1. Check Python installation (requires 64-bit Python 3.8+)"
    echo "  2. Download and install libvips $LIBVIPS_VERSION"
    echo "  3. Create Python PATH configuration helper"
    echo "  4. Create conda environment (optional)"
    echo "  5. Test the installation"
    echo
    read -r -p "Continue? (Y/n): " continue_install
    continue_install=${continue_install:-Y}

    if [[ ! "$continue_install" =~ ^[Yy]$ ]]; then
        echo "Installation cancelled"
        exit 0
    fi

    # Run installation steps
    check_windows
    check_python

    # Prompt for installation directory
    prompt_install_dir

    if check_existing_libvips; then
        install_libvips
    fi

    # Write config file with installation path
    write_config_file

    # Create Python helper that reads from config
    create_python_helper

    # Optional conda environment setup
    if check_conda; then
        read -r -p "Create conda environment now? (Y/n): " create_env
        create_env=${create_env:-Y}
        if [[ "$create_env" =~ ^[Yy]$ ]]; then
            create_environment
        fi
    fi

    # Test installation
    test_installation
    test_result=$?

    # Final instructions
    echo
    echo "=========================================="
    echo "  Setup Complete!"
    echo "=========================================="
    echo
    echo "Installation Summary:"
    echo "  libvips location: $INSTALL_DIR"
    echo "  Python helper: python/vips_path_windows.py"
    echo
    echo "Next steps:"
    echo "1. Activate the conda environment:"
    echo "   conda activate collagen_quant"
    echo
    echo "2. All Python scripts will automatically configure libvips PATH"
    echo "   by importing vips_path_windows at the start"
    echo
    echo "3. Your Python scripts should start with:"
    echo "   import vips_path_windows"
    echo "   import pyvips"
    echo
    echo "For more information, see README.MD"
    echo "=========================================="

    if [[ $test_result -ne 0 ]]; then
        exit 1
    fi
}

# Run main installation
main
