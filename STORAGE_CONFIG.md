# Storage Configuration Guide for Development

## Overview

The Role Play System supports multiple storage backends, with full flexibility in the development environment. You can easily switch between local file storage and cloud storage (GCS or S3) using environment variables.

## Quick Start

### Using Local File Storage (Default)
```bash
# Default configuration - uses ./data directory
python src/python/run_server.py

# Or explicitly set file storage
STORAGE_TYPE=file STORAGE_PATH=./data python src/python/run_server.py
```

### Using Google Cloud Storage (GCS)
```bash
# Set up GCS storage
export STORAGE_TYPE=gcs
export GCS_BUCKET=your-dev-bucket
export GCS_PREFIX=dev/
export GCP_PROJECT_ID=your-project-id

# Option 1: Using Application Default Credentials
gcloud auth application-default login
python src/python/run_server.py

# Option 2: Using Service Account
export GCP_CREDENTIALS_FILE=/path/to/service-account.json
python src/python/run_server.py
```

### Using Amazon S3
```bash
# Set up S3 storage
export STORAGE_TYPE=s3
export S3_BUCKET=your-dev-bucket
export S3_PREFIX=dev/
export AWS_REGION=us-west-2
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
python src/python/run_server.py
```

## Environment Variables Reference

### Common Variables
- `STORAGE_TYPE`: Storage backend type (`file`, `gcs`, or `s3`)
- `LOCK_STRATEGY`: Locking strategy (`file`, `object`, or `redis`)
- `LOCK_LEASE_DURATION`: Lock lease duration in seconds (default: 60)

### File Storage Variables
- `STORAGE_PATH`: Directory path for file storage (default: `./data`)

### GCS Variables
- `GCS_BUCKET`: GCS bucket name (required)
- `GCS_PREFIX`: Object key prefix (default: `dev/`)
- `GCP_PROJECT_ID`: Google Cloud project ID
- `GCP_CREDENTIALS_FILE`: Path to service account JSON (optional)

### S3 Variables
- `S3_BUCKET`: S3 bucket name (required)
- `S3_PREFIX`: Object key prefix (default: `dev/`)
- `AWS_REGION`: AWS region (default: `us-east-1`)
- `AWS_ACCESS_KEY_ID`: AWS access key (optional if using IAM roles)
- `AWS_SECRET_ACCESS_KEY`: AWS secret key (optional if using IAM roles)

## Lock Strategies

### File Storage
- Default: `file` (OS-level file locks)
- Alternative: `redis` (for distributed development)

### Cloud Storage (GCS/S3)
- Default: `object` (uses atomic operations)
- Alternative: `redis` (for high-contention scenarios)

## Examples

### Local Development with File Storage
```bash
# Standard local development
STORAGE_TYPE=file \
STORAGE_PATH=./data \
python src/python/run_server.py
```

### Development with GCS
```bash
# Using GCS with Application Default Credentials
STORAGE_TYPE=gcs \
GCS_BUCKET=roleplay-dev-bucket \
GCS_PREFIX=dev/$(whoami)/ \
python src/python/run_server.py
```

### Testing Cloud Storage Locally
```bash
# Use Docker container with GCS configuration
make run-local-docker \
  STORAGE_TYPE=gcs \
  GCS_BUCKET=roleplay-dev-bucket \
  GCS_PREFIX=dev/local-test/
```

### Mixed Team Development
Different team members can use different storage backends:

```bash
# Developer A: Using local files
STORAGE_TYPE=file python src/python/run_server.py

# Developer B: Using shared GCS bucket
STORAGE_TYPE=gcs GCS_BUCKET=team-dev-bucket python src/python/run_server.py
```

## Switching Storage Backends

You can switch storage backends at any time by changing environment variables. Note that data is not automatically migrated between backends.

### Migration Example
```bash
# Export data from file storage
STORAGE_TYPE=file python scripts/export_data.py

# Import to GCS
STORAGE_TYPE=gcs GCS_BUCKET=new-bucket python scripts/import_data.py
```

## Troubleshooting

### GCS Authentication Issues
```bash
# Check current credentials
gcloud auth application-default print-access-token

# Re-authenticate
gcloud auth application-default login

# Use service account
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

### File Permission Issues
```bash
# Ensure data directory exists and is writable
mkdir -p ./data
chmod 755 ./data
```

### Lock Contention
If experiencing lock timeouts:
1. Increase `LOCK_LEASE_DURATION` (e.g., to 120 seconds)
2. Consider using Redis locking for better performance
3. Check for crashed processes holding stale locks

## Best Practices

1. **Local Development**: Use file storage for speed and simplicity
2. **Integration Testing**: Use GCS/S3 to match production behavior
3. **CI/CD**: Use cloud storage with separate prefixes per build
4. **Team Development**: Use cloud storage with user-specific prefixes

## Environment Restrictions

- **Dev Environment**: All storage types allowed (file, gcs, s3)
- **Beta/Prod Environments**: Only cloud storage allowed (gcs, s3)

This ensures production-ready configurations while maintaining development flexibility.