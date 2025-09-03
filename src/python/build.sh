#!/bin/bash
set -e

# Navigate to the package directory
cd "$(dirname "$0")/role_play"

# Remove old build artifacts
echo "Cleaning old build artifacts..."
rm -rf dist build *.egg-info

# Install necessary build tools
echo "Installing build dependencies..."
python3 -m pip install --upgrade setuptools wheel

# Build the source and wheel distributions
echo "Building the package..."
python3 setup.py sdist bdist_wheel

echo "Build complete. Artifacts are in dist/"
