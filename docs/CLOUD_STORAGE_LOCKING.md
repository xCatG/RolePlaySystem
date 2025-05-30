# Cloud Storage Locking Solutions

This document explains the different approaches to handling concurrency and locking with cloud storage backends.

## Current Implementation

The role play system provides **storage-layer locking guarantees** through different mechanisms based on the storage backend:

### 1. FileStorage (Local Development)
- **Locking Mechanism**: `FileLock` library
- **Granularity**: Per-file locking
- **Concurrency**: Thread-safe with 5-second timeout
- **Use Case**: Local development, single-server deployments

```python
# Automatic file locking for local storage
async with FileLock(lock_file, timeout=5):
    with open(log_file, 'a') as f:
        f.write(json.dumps(data) + '\n')
```

### 2. Cloud Storage (GCS/S3) - Current
- **Locking Mechanism**: Atomic read-modify-write operations
- **Granularity**: Per-object atomicity
- **Concurrency**: Race conditions possible with high concurrency
- **Use Case**: Low-to-medium concurrency production deployments

```python
# Atomic operations but potential race conditions
blob = bucket.blob(key)
content = blob.download_as_text() if blob.exists() else ""
content += new_line
blob.upload_from_string(content)  # Atomic upload
```

## Enhanced Locking Options

### 1. Redis-Based Distributed Locking (Recommended)

**Advantages:**
- ✅ True distributed locking across multiple servers
- ✅ Configurable timeouts and automatic lock expiration
- ✅ Works with any cloud storage backend
- ✅ Battle-tested Redis infrastructure

**Implementation:**
```python
async with acquire_distributed_lock(log_key, timeout=10):
    # Read-modify-write operation protected by Redis lock
    content = await storage.read_log(log_key)
    content.append(new_entry)
    await storage.write_log(log_key, content)
```

**Configuration:**
```bash
# Add to .env file
REDIS_URL=redis://localhost:6379/0

# For production with Redis cluster
REDIS_URL=redis://redis-cluster.example.com:6379/0
```

**Trade-offs:**
- ➕ Excellent concurrency guarantees
- ➕ Fast lock acquisition/release
- ➕ Auto-expiring locks prevent deadlocks
- ➖ Additional infrastructure dependency (Redis)
- ➖ Network overhead for lock operations

### 2. Cloud-Native Locking Services

#### Google Cloud Firestore Transactions
```python
@firestore.transactional
def append_with_lock(transaction, log_ref, data):
    doc = log_ref.get(transaction=transaction)
    current_content = doc.to_dict().get('content', [])
    current_content.append(data)
    transaction.set(log_ref, {'content': current_content})
```

**Advantages:**
- ✅ ACID transactions
- ✅ No additional infrastructure
- ✅ Automatic scaling

**Trade-offs:**
- ➕ Strong consistency guarantees
- ➕ Integrated with GCP ecosystem
- ➖ Vendor lock-in
- ➖ Different API from object storage

#### AWS DynamoDB Conditional Writes
```python
table.put_item(
    Item={'log_key': key, 'content': new_content},
    ConditionExpression='attribute_not_exists(lock_owner) OR lock_expires < :now',
    ExpressionAttributeValues={':now': int(time.time())}
)
```

**Advantages:**
- ✅ Conditional writes prevent conflicts
- ✅ No lock management overhead
- ✅ Serverless scaling

**Trade-offs:**
- ➕ No lock cleanup required
- ➕ Built-in conflict detection
- ➖ Vendor lock-in
- ➖ Different data model

### 3. Object-Based Distributed Locking

Uses the cloud storage itself to store lock files:

```python
# Try to create lock object with condition "if not exists"
lock_object = f"locks/{log_key}.lock"
try:
    storage.create_object_if_not_exists(lock_object, {
        'owner': instance_id,
        'expires_at': utc_now() + timedelta(seconds=30)
    })
    # Lock acquired, perform operation
    await append_to_log(log_key, data)
finally:
    storage.delete_object_if_owner(lock_object, instance_id)
```

**Trade-offs:**
- ➕ No additional infrastructure
- ➕ Uses existing storage backend
- ➖ Slower than dedicated locking services
- ➖ Complex lock cleanup logic
- ➖ Potential for stale locks

## Recommendations by Use Case

### Low Concurrency (< 10 concurrent writes)
**Current Implementation**: Atomic read-modify-write
- Simplest setup, no additional dependencies
- Race conditions rare at low concurrency
- Good for MVP and small deployments

### Medium Concurrency (10-100 concurrent writes)
**Recommended**: Redis-based distributed locking
- Add Redis to your infrastructure
- Configure `REDIS_URL` environment variable
- Excellent performance/complexity trade-off

### High Concurrency (100+ concurrent writes)
**Recommended**: Dedicated logging infrastructure
- Use message queues (Pub/Sub, SQS, Kafka)
- Separate logging service with proper queuing
- Consider append-only databases (ClickHouse, TimescaleDB)

### Enterprise/Production
**Recommended**: Cloud-native solutions
- Google Cloud: Firestore + Cloud Logging
- AWS: DynamoDB + CloudWatch Logs
- Azure: Cosmos DB + Application Insights

## Migration Path

1. **Start**: Current atomic operations (no additional setup)
2. **Scale**: Add Redis for distributed locking
3. **Optimize**: Move to cloud-native logging services
4. **Enterprise**: Dedicated logging infrastructure

## Configuration Examples

### Redis Distributed Locking
```yaml
# config/prod.yaml
storage_type: "gcs"
gcs_bucket_name: "my-app-storage"
redis_url: "redis://redis.internal:6379/0"
```

### Environment Variables
```bash
# Basic cloud storage
STORAGE_TYPE=gcs
GCS_BUCKET_NAME=my-app-logs

# With distributed locking
REDIS_URL=redis://localhost:6379/0

# Production with Redis Cluster
REDIS_URL=redis://redis-cluster.prod:6379/0
```

## Performance Comparison

| Approach | Latency | Throughput | Complexity | Infrastructure |
|----------|---------|------------|------------|----------------|
| Atomic Operations | ~50ms | Medium | Low | None |
| Redis Locking | ~10ms | High | Medium | Redis |
| Firestore | ~20ms | High | Medium | GCP |
| DynamoDB | ~15ms | Very High | Medium | AWS |
| Message Queue | ~5ms | Very High | High | Queue Service |

## Implementation Status

- ✅ **FileStorage**: File locking implemented
- ✅ **GCS/S3**: Atomic operations implemented  
- 🚧 **Redis Locking**: Framework implemented, needs integration
- ⏳ **Cloud-native**: Design phase
- ⏳ **Message Queue**: Future enhancement

The system currently provides solid locking guarantees for most use cases, with clear upgrade paths for higher concurrency requirements.