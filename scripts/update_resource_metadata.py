#!/usr/bin/env python3
"""
Script to update resource metadata (last_modified timestamp and version).

This helps manual editors maintain proper metadata when modifying resource files.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "python"))

from role_play.common.resource_loader import ResourceLoader


class ResourceUpdater:
    """A class to encapsulate resource metadata update logic."""

    def __init__(self, path: str, bump_version: bool, modified_by: str):
        self.path = path
        self.bump_version = bump_version
        self.modified_by = modified_by
        self.success_count = 0
        self.fail_count = 0

    def run(self) -> bool:
        """Process a file or directory."""
        if os.path.isfile(self.path):
            self._process_file(self.path)
        elif os.path.isdir(self.path):
            self._process_directory(self.path)
        else:
            print(f"Error: Path not found: {self.path}", file=sys.stderr)
            return False
        
        print(f"\nProcessed {self.success_count + self.fail_count} files. "
              f"({self.success_count} succeeded, {self.fail_count} failed)")
        return self.fail_count == 0

    def _process_directory(self, directory_path: str):
        """Process all JSON files in a directory."""
        print(f"Processing directory: {directory_path}\n")
        for root, _, files in os.walk(directory_path):
            for file in sorted(files):
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    self._process_file(file_path)

    def _process_file(self, file_path: str):
        """Update metadata for a single file."""
        rel_path = os.path.relpath(file_path, self.path if os.path.isdir(self.path) else os.path.dirname(self.path))
        print(f"Processing {rel_path}...")
        
        try:
            with open(file_path, 'r+', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    raise IOError(f"Invalid JSON: {e}")

                self._update_metadata(data)

                # Write back with proper formatting
                f.seek(0)
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.truncate()
                f.write('\n')

            print("  ✓ Updated successfully")
            self.success_count += 1
        except (IOError, OSError) as e:
            print(f"  ✗ Failed: {e}")
            self.fail_count += 1
        print()

    def _update_metadata(self, data: dict[str, Any]):
        """Update the metadata in the provided data dictionary."""
        old_timestamp = data.get("last_modified")
        new_timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        data["last_modified"] = new_timestamp
        data["modified_by"] = self.modified_by

        if old_timestamp != new_timestamp:
            print(f"  Updated timestamp: {old_timestamp} -> {new_timestamp}")

        if self.bump_version:
            old_version = data.get("resource_version", "1.0")
            new_version = self._bump_patch_version(old_version)
            data["resource_version"] = new_version
            if old_version != new_version:
                print(f"  Bumped version: {old_version} -> {new_version}")
        
        version = data.get("resource_version")
        if version and version not in ResourceLoader.SUPPORTED_VERSIONS:
            print(f"  WARNING: Version {version} is not in supported versions: "
                  f"{', '.join(ResourceLoader.SUPPORTED_VERSIONS)}")

    @staticmethod
    def _bump_patch_version(version_str: str) -> str:
        """Bumps the patch number of a version string (e.g., '1.0' -> '1.1')."""
        try:
            parts = version_str.split('.')
            if len(parts) == 2:
                return f"{parts[0]}.{int(parts[1]) + 1}"
        except (ValueError, IndexError):
            pass
        return version_str


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Update resource metadata (timestamp, version).",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "path",
        help="Path to a single JSON file or a directory of resources."
    )
    parser.add_argument(
        "--bump-version",
        action="store_true",
        help="Increment the patch version (e.g., 1.0 -> 1.1)."
    )
    parser.add_argument(
        "--modified-by",
        default="manual",
        help="Set the 'modified_by' field (default: 'manual')."
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip the validation step after updating."
    )
    args = parser.parse_args()

    updater = ResourceUpdater(args.path, args.bump_version, args.modified_by)
    success = updater.run()

    print("\n" + "="*60)
    if not success:
        print("✗ Some files failed to update.")
        sys.exit(1)
    
    print("✓ All files updated successfully!")

    if not args.no_validate:
        print("\nRunning validation...")
        validation_script = Path(__file__).parent / "validate_resources.py"
        
        # Determine the root resources directory for validation
        resources_dir = args.path
        if os.path.isfile(resources_dir):
            # Traverse up to find a 'resources' directory
            p = Path(resources_dir).parent
            while p.name != 'resources' and p.parent != p:
                p = p.parent
            resources_dir = str(p) if p.name == 'resources' else args.path

        subprocess.run([sys.executable, str(validation_script), resources_dir], check=False)
    else:
        print("\nSkipping validation step.")


if __name__ == "__main__":
    main()
