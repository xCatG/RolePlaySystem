"""
Resources Directory

This directory contains static resources that are packaged and distributed with the application.

Contents:
- scenarios.json - Pre-defined role-play scenarios
- Other static configuration files that don't change at runtime

Usage:
These resources are loaded using Python's resource management APIs to ensure they work correctly whether the code is:
- Running from source
- Installed as a package
- Packaged in a Docker container
- Deployed to production

Important:
These files are read-only at runtime. User data and runtime state should be stored in the configured storage backend (file/GCS/S3).
"""