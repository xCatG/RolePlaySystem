# Role Play System - Environment Configuration Guide

This document describes the different environments and their configurations for the Role Play System.

## Environment Overview

The system supports three primary environments:

| Environment | Purpose | Storage | Locking | Debug | JWT Expiry |
|-------------|---------|---------|---------|-------|------------|
| **Development** | Local development & testing | File system | File locks | ON | 24 hours |
| **Beta** | Pre-production testing | GCS | Object locks | OFF | 72 hours |
| **Production** | Live system | GCS | Object locks* | OFF | 168 hours |

*Production is configured for easy migration to Redis locking when needed.

## Environment Detection

The system determines the environment through:

1. **CONFIG_FILE** environment variable (highest priority)
2. **ENV** environment variable 
3. Default to `dev` if not specified

```python
# Environment detection order
config_file = os.getenv("CONFIG_FILE")
if config_file:
    # Use specified config file
else:
    env = os.getenv("ENV", "dev").lower()
    config_file = f"config/{env}.yaml"
```

## Development Environment

### Configuration File: `config/dev.yaml`

**Purpose**: Local development with minimal external dependencies

**Key Features**:
- File-based storage in `./data` directory
- File-based locking (OS-level)
- Debug mode enabled
- Permissive CORS for localhost
- Short JWT expiration for testing
- All storage types available (file, GCS, S3)

**Default Settings**:
```yaml
storage:
  type: file
  base_dir: ./data
  lock:
    strategy: file
```

**Running Locally**:
```bash
# Using default dev config
python src/python/run_server.py

# Or explicitly
ENV=dev python src/python/run_server.py

# With custom storage
STORAGE_TYPE=gcs GCS_BUCKET=my-dev-bucket python src/python/run_server.py
```

## Beta Environment

### Configuration File: `config/beta.yaml`

**Purpose**: Pre-production testing on Google Cloud

**Key Features**:
- Google Cloud Storage backend
- Object-based locking (GCS atomic operations)
- Structured JSON logging for Cloud Logging
- Restricted CORS to beta frontend URL
- Medium JWT expiration (3 days)
- Cloud-only storage (no file system option)

**Required Environment Variables**:
```bash
JWT_SECRET_KEY=<from-secret-manager>
GCP_PROJECT_ID=<your-project-id>
```

**Optional Overrides**:
```bash
GCS_BUCKET=roleplay-beta-storage  # Default
GCS_PREFIX=beta/                   # Default
FRONTEND_URL=https://beta.example.com
LOG_LEVEL=INFO                     # Default
```

**Deployment**:
```bash
# Deploy to Cloud Run
gcloud run deploy roleplay-api-beta \
    --set-env-vars="ENV=beta" \
    --set-env-vars="CONFIG_FILE=/app/config/beta.yaml" \
    --set-secrets="JWT_SECRET_KEY=jwt-secret-key:latest"
```

## Production Environment

### Configuration File: `config/prod.yaml`

**Purpose**: Live production system

**Key Features**:
- Google Cloud Storage backend
- Object-based locking (configured for Redis migration)
- Minimal logging (WARNING level)
- Restricted CORS to production frontend
- Long JWT expiration (7 days)
- Rate limiting enabled
- Higher performance settings

**Required Environment Variables**:
```bash
JWT_SECRET_KEY=<from-secret-manager>
GCP_PROJECT_ID=<your-project-id>
```

**Optional Overrides**:
```bash
GCS_BUCKET=roleplay-prod-storage   # Default
GCS_PREFIX=prod/                    # Default
FRONTEND_URL=https://roleplay.example.com
LOG_LEVEL=WARNING                   # Default
RATE_LIMIT_ENABLED=true            # Default
REQUEST_TIMEOUT=30                 # Default (seconds)
```

**Deployment**:
```bash
# Deploy to Cloud Run
gcloud run deploy roleplay-api-prod \
    --set-env-vars="ENV=prod" \
    --set-env-vars="CONFIG_FILE=/app/config/prod.yaml" \
    --set-secrets="JWT_SECRET_KEY=jwt-secret-key:latest" \
    --min-instances=2
```

## Storage Configuration by Environment

### Development
- **Available Types**: file, gcs, s3
- **Default**: file system (`./data`)
- **Locking**: File locks for file storage, object locks for cloud
- **Use Cases**: Local testing, cloud integration testing

### Beta
- **Available Types**: gcs, s3 (enforced by storage factory)
- **Default**: GCS with `roleplay-beta-storage` bucket
- **Locking**: Object-based (GCS atomic operations)
- **Use Cases**: Integration testing, performance testing, UAT

### Production
- **Available Types**: gcs, s3 (enforced by storage factory)
- **Default**: GCS with `roleplay-prod-storage` bucket
- **Locking**: Object-based (ready for Redis migration)
- **Use Cases**: Live system

## Locking Strategy Migration Path

The system is designed for easy locking strategy migration:

### Current State (Object Locking)
```yaml
lock:
  strategy: object
  lease_duration_seconds: 30
```

### Future State (Redis Locking)
```yaml
lock:
  strategy: redis
  lease_duration_seconds: 30
  redis_host: redis.example.com
  redis_port: 6379
  redis_password: ${REDIS_PASSWORD}
```

**When to Migrate**:
- Lock acquisition failures > 5%
- Lock latency > 500ms p99
- Concurrent users > 1000
- Lock contention on hot resources

## Environment Variables Reference

### Common Variables

| Variable | Description | Dev Default | Beta Default | Prod Default |
|----------|-------------|-------------|--------------|--------------|
| `ENV` | Environment name | dev | beta | prod |
| `CONFIG_FILE` | Config file path | config/dev.yaml | config/beta.yaml | config/prod.yaml |
| `HOST` | Server host | 0.0.0.0 | 0.0.0.0 | 0.0.0.0 |
| `PORT` | Server port | 8000 | 8080 | 8080 |
| `JWT_SECRET_KEY` | JWT signing key | development-secret-key | (required) | (required) |
| `JWT_EXPIRE_HOURS` | Token expiration | 24 | 72 | 168 |

### Storage Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `STORAGE_TYPE` | Storage backend type | file, gcs, s3 |
| `STORAGE_PATH` | File storage path | ./data |
| `GCS_BUCKET` | GCS bucket name | roleplay-beta-storage |
| `GCS_PREFIX` | GCS key prefix | beta/ |
| `GCP_PROJECT_ID` | Google Cloud project | my-project-123 |
| `GCP_CREDENTIALS_FILE` | Service account JSON | /path/to/sa.json |

### Lock Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOCK_STRATEGY` | Locking strategy | file (dev), object (beta/prod) |
| `LOCK_LEASE_DURATION` | Lock lease seconds | 60 (dev), 45 (beta), 30 (prod) |
| `LOCK_RETRY_ATTEMPTS` | Retry attempts | 3 (dev), 5 (beta/prod) |
| `LOCK_RETRY_DELAY` | Retry delay seconds | 1.0 (dev), 0.5 (beta), 0.3 (prod) |

## Configuration Precedence

Configuration values are resolved in this order (highest to lowest priority):

1. **Environment variables** - Override any config file setting
2. **Config file values** - From the loaded YAML file
3. **Default values** - Hardcoded in the application

Example:
```yaml
# In beta.yaml
jwt_expire_hours: "${JWT_EXPIRE_HOURS:72}"

# Can be overridden by:
JWT_EXPIRE_HOURS=48 python run_server.py
```

## Testing Environment Configurations

### Local Testing of Beta/Prod Configs

```bash
# Test beta configuration locally
ENV=beta STORAGE_TYPE=file python src/python/run_server.py

# Test with GCS emulator
ENV=beta STORAGE_EMULATOR_HOST=localhost:8089 python src/python/run_server.py
```

### Environment-Specific Tests

```python
# In tests
@pytest.mark.parametrize("env", ["dev", "beta", "prod"])
def test_storage_factory_by_environment(env):
    # Test that each environment creates appropriate storage
    pass
```

## Security Considerations

### Development
- **Relaxed Security**: Default JWT secret, permissive CORS
- **Local Storage**: No cloud credentials needed
- **Debug Mode**: Full error traces exposed

### Beta
- **Moderate Security**: Requires real JWT secret
- **Cloud IAM**: Service account with limited permissions
- **Structured Logs**: Sensitive data filtered

### Production
- **Strict Security**: 
  - Strong JWT secret from Secret Manager
  - Minimal logging (WARNING+)
  - Rate limiting enabled
  - Least-privilege service accounts
  - No debug information exposed

## Monitoring by Environment

### Development
- Console logging
- Local file logs
- No external monitoring

### Beta
- Cloud Logging (JSON format)
- Basic metrics to Cloud Monitoring
- Error alerting for testing

### Production
- Cloud Logging (WARNING+ only)
- Full metrics suite
- Alerting for:
  - High error rates
  - Lock contention
  - Resource exhaustion
  - Latency spikes

## Troubleshooting

### Environment Not Loading

```bash
# Check which config is being loaded
python -c "import os; print(os.getenv('CONFIG_FILE', f\"config/{os.getenv('ENV', 'dev')}.yaml\"))"

# Verify config file exists
ls -la config/

# Test config loading
python src/python/role_play/server/config_loader.py
```

### Storage Issues by Environment

**Development**:
```bash
# Check file permissions
ls -la ./data/

# Verify storage path
echo $STORAGE_PATH
```

**Beta/Production**:
```bash
# Check GCS access
gsutil ls gs://$GCS_BUCKET/

# Verify credentials
gcloud auth application-default print-access-token
```

### Lock Contention Issues

**Development**: Usually not an issue with file locks

**Beta/Production**:
1. Check lock metrics in monitoring
2. Review lease duration settings
3. Consider Redis migration if:
   - Acquisition failures > 5%
   - P99 latency > 500ms

## Best Practices

1. **Never use dev config in production**
2. **Always use Secret Manager for production secrets**
3. **Test configuration changes in beta first**
4. **Monitor lock performance metrics**
5. **Use environment-specific service accounts**
6. **Keep dev/beta/prod data completely separated**
7. **Document all environment-specific features**