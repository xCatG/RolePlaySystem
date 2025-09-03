#!/usr/bin/env python3
"""
Quick script to fix relative imports in the role_play_system package.

This converts relative imports (from ..module) to absolute imports (from role_play_system.module)
for better package compatibility when installed.
"""

import os
import re
from pathlib import Path

def fix_imports_in_file(file_path):
    """Fix relative imports in a single Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Track if we made any changes
        original_content = content
        
        # Pattern to match relative imports
        patterns = [
            # from ..module import something
            (r'from \.\.(\w+)', r'from role_play_system.\1'),
            # from ..module.submodule import something  
            (r'from \.\.(\w+)\.(\w+)', r'from role_play_system.\1.\2'),
            # from ..module.submodule.subsubmodule import something
            (r'from \.\.(\w+)\.(\w+)\.(\w+)', r'from role_play_system.\1.\2.\3'),
            # from ...module import something (three dots)
            (r'from \.\.\.(\w+)', r'from role_play_system.\1'),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        
        # Only write if we made changes
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed imports in {file_path}")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False

def fix_imports_in_directory(directory):
    """Fix relative imports in all Python files in a directory."""
    directory = Path(directory)
    if not directory.exists():
        print(f"Directory {directory} does not exist")
        return
    
    files_fixed = 0
    total_files = 0
    
    for py_file in directory.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue  # Skip __init__.py files for now
            
        total_files += 1
        if fix_imports_in_file(py_file):
            files_fixed += 1
    
    print(f"Fixed imports in {files_fixed}/{total_files} files")

if __name__ == "__main__":
    # Get the role_play package directory
    script_dir = Path(__file__).parent
    package_dir = script_dir / "src" / "python" / "role_play"
    
    if not package_dir.exists():
        print(f"Package directory {package_dir} not found")
        exit(1)
    
    print("🔧 Fixing relative imports in role_play_system package...")
    print(f"Package directory: {package_dir}")
    print()
    
    fix_imports_in_directory(package_dir)
    print()
    print("✅ Import fixing complete!")
    print()
    print("Note: After fixing imports, you should:")
    print("1. Rebuild the package: cd src/python && ./build.sh")
    print("2. Test the installation: ./test-install.sh")