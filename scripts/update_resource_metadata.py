#!/usr/bin/env python3
"""
Script to update resource metadata (last_modified timestamp and version).

This helps manual editors maintain proper metadata when modifying resource files.

Usage: 
    python scripts/update_resource_metadata.py [file_or_directory] [--bump-version]
    
Options:
    --bump-version: Increment the patch version (e.g., 1.0 -> 1.1)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "python"))

from role_play.common.resource_loader import ResourceLoader


def get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def bump_version(version: str) -> str:
    """Bump the patch version number."""
    try:
        parts = version.split('.')
        if len(parts) == 2:
            major, minor = parts
            return f"{major}.{int(minor) + 1}"
        else:
            # If not in expected format, just return as-is
            return version
    except:
        return version


def update_file_metadata(
    file_path: str, 
    bump_version_flag: bool = False,
    modified_by: str = "manual"
) -> Tuple[bool, str]:
    """Update metadata in a single JSON file."""
    try:
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if file has been modified
        old_timestamp = data.get("last_modified", "")
        old_version = data.get("resource_version", "1.0")
        
        # Update timestamp
        new_timestamp = get_current_timestamp()
        data["last_modified"] = new_timestamp
        
        # Update modified_by
        data["modified_by"] = modified_by
        
        # Add version if missing
        if "resource_version" not in data:
            data["resource_version"] = "1.0"
            print(f"  Added missing resource_version: 1.0")
        
        # Bump version if requested
        if bump_version_flag and "resource_version" in data:
            new_version = bump_version(data["resource_version"])
            if new_version != data["resource_version"]:
                data["resource_version"] = new_version
                print(f"  Bumped version: {old_version} -> {new_version}")
        
        # Check if version is supported
        if data["resource_version"] not in ResourceLoader.SUPPORTED_VERSIONS:
            print(f"  WARNING: Version {data['resource_version']} is not in supported versions: "
                  f"{', '.join(ResourceLoader.SUPPORTED_VERSIONS)}")
        
        # Write back with proper formatting
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')  # Add trailing newline
        
        # Report changes
        if old_timestamp != new_timestamp:
            print(f"  Updated timestamp: {old_timestamp} -> {new_timestamp}")
        
        return True, "OK"
        
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def process_path(
    path: str, 
    bump_version_flag: bool = False,
    modified_by: str = "manual"
) -> bool:
    """Process a file or directory."""
    all_success = True
    
    if os.path.isfile(path):
        # Single file
        if path.endswith('.json'):
            print(f"Processing {path}...")
            success, error = update_file_metadata(path, bump_version_flag, modified_by)
            if success:
                print("  ✓ Updated successfully")
            else:
                print(f"  ✗ Failed: {error}")
                all_success = False
        else:
            print(f"Skipping non-JSON file: {path}")
    
    elif os.path.isdir(path):
        # Directory - process all JSON files
        print(f"Processing directory: {path}\n")
        
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, path)
                    
                    print(f"Processing {rel_path}...")
                    success, error = update_file_metadata(
                        file_path, bump_version_flag, modified_by
                    )
                    if success:
                        print("  ✓ Updated successfully")
                    else:
                        print(f"  ✗ Failed: {error}")
                        all_success = False
                    print()
    
    else:
        print(f"Error: Path not found: {path}")
        all_success = False
    
    return all_success


def main():
    """Main entry point."""
    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: python update_resource_metadata.py <file_or_directory> [options]")
        print("\nOptions:")
        print("  --bump-version    Increment the patch version")
        print("  --modified-by=X   Set modified_by field (default: 'manual')")
        print("\nExample:")
        print("  python update_resource_metadata.py data/resources/")
        print("  python update_resource_metadata.py data/resources/scenarios/scenarios.json --bump-version")
        sys.exit(1)
    
    path = sys.argv[1]
    bump_version_flag = "--bump-version" in sys.argv
    
    # Check for modified-by argument
    modified_by = "manual"
    for arg in sys.argv:
        if arg.startswith("--modified-by="):
            modified_by = arg.split("=", 1)[1]
    
    # Process the path
    success = process_path(path, bump_version_flag, modified_by)
    
    print("\n" + "="*60)
    if success:
        print("✓ All files updated successfully!")
        
        # Run validation
        print("\nRunning validation...")
        validation_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "validate_resources.py"
        )
        
        # Determine resources directory for validation
        if os.path.isfile(path):
            # Find parent resources directory
            resources_dir = path
            while os.path.basename(resources_dir) != "resources" and resources_dir != "/":
                resources_dir = os.path.dirname(resources_dir)
        else:
            resources_dir = path
        
        os.system(f"python {validation_script} {resources_dir}")
        
    else:
        print("✗ Some files failed to update.")
        sys.exit(1)


if __name__ == "__main__":
    main()