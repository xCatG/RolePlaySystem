# Package Testing Scripts

This directory contains scripts for testing the Python package publishing infrastructure.

## Scripts

- **test-build.sh** - Tests package building process
- **test-install.sh** - Tests package installation in clean environment
- **inspect-package.sh** - Inspects package contents and structure
- **test-gcp-upload.sh** - Tests GCP Artifact Registry upload (interactive)

## Usage

All scripts can be run from the project root using Make targets:

```bash
make test-package-build    # Run build test
make test-package-install  # Run installation test  
make inspect-package       # Inspect package contents
make test-gcp-upload       # Test GCP upload (interactive)
make test-package-all      # Run all tests except GCP
```

Or run directly:

```bash
./test/python/packaging/test-build.sh
./test/python/packaging/test-install.sh
./test/python/packaging/inspect-package.sh
./test/python/packaging/test-gcp-upload.sh
```

## Requirements

- Virtual environment with dependencies installed (`venv/`)
- Package source code in `src/python/role_play/`
- For GCP tests: `gcloud` CLI and appropriate project permissions

See `/PACKAGE_TESTING.md` for detailed testing documentation.