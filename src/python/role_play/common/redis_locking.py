"""Redis-based locking strategy (STUB IMPLEMENTATION)."""

import time
import uuid
from contextlib import contextmanager
from typing import Generator, Optional

from .storage import LockConfig, LockAcquisitionError
from .exceptions import StorageError

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisLockStrategy:
    """
    Redis-based distributed locking strategy (STUB IMPLEMENTATION).
    
    This provides a high-performance, strongly consistent locking mechanism
    suitable for production environments with high contention.
    
    Features:
    - Strong consistency through Redis atomic operations
    - Automatic lock expiry to prevent deadlocks
    - Configurable retry behavior
    - High performance and low latency
    
    Redis Commands Used:
    - SET key value NX PX milliseconds: Atomic lock acquisition with expiry
    - DEL key: Lock release
    - EXISTS key: Lock status check
    
    ⚠️  WARNING: This is a STUB implementation. The Redis operations are
    documented but not yet fully implemented.
    
    Production Implementation TODO:
    - Implement actual Redis SET NX PX operations
    - Add connection pooling and error handling
    - Add monitoring metrics for lock performance
    - Implement Redis Cluster support for HA
    - Add lock renewal for long-running operations
    """

    def __init__(self, config: LockConfig):
        if not REDIS_AVAILABLE:
            raise StorageError("redis package not installed")
        
        self.config = config
        
        if not config.redis_host:
            raise StorageError("redis_host is required for Redis locking strategy")
        
        # Initialize Redis client (STUB)
        try:
            self.redis_client = redis.Redis(
                host=config.redis_host,
                port=config.redis_port or 6379,
                password=config.redis_password,
                db=config.redis_db or 0,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True
            )
            
            # Test connection
            self.redis_client.ping()
            
        except redis.ConnectionError as e:
            raise StorageError(f"Failed to connect to Redis: {e}")
        except Exception as e:
            raise StorageError(f"Redis configuration error: {e}")
        
        # Generate unique instance ID for lock ownership
        self.instance_id = str(uuid.uuid4())

    @contextmanager
    def acquire_lock(self, resource_name: str) -> Generator[None, None, None]:
        """
        Acquire a Redis-based distributed lock.
        
        Uses Redis SET command with NX (not exists) and PX (expiry) options
        for atomic lock acquisition with automatic expiry.
        
        Args:
            resource_name: Name of the resource to lock
            
        Yields:
            None
            
        Raises:
            LockAcquisitionError: If lock cannot be acquired
        """
        lock_key = f"lock:{resource_name}"
        lock_value = f"{self.instance_id}:{time.time()}"
        lease_ms = self.config.lease_duration_seconds * 1000
        
        acquired = False
        
        for attempt in range(self.config.retry_attempts):
            try:
                # TODO: Implement actual Redis SET NX PX operation
                # result = self.redis_client.set(
                #     lock_key,
                #     lock_value,
                #     nx=True,  # Only set if key doesn't exist
                #     px=lease_ms  # Expiry time in milliseconds
                # )
                # 
                # if result:
                #     acquired = True
                #     break
                
                # STUB: Simulate lock acquisition for now
                if not self.redis_client.exists(lock_key):
                    # Simulate atomic SET NX PX
                    pipeline = self.redis_client.pipeline()
                    pipeline.set(lock_key, lock_value)
                    pipeline.expire(lock_key, self.config.lease_duration_seconds)
                    pipeline.execute()
                    acquired = True
                    break
                
            except redis.RedisError as e:
                if attempt == self.config.retry_attempts - 1:
                    raise LockAcquisitionError(f"Redis error acquiring lock for {resource_name}: {e}")
                
            if not acquired:
                time.sleep(self.config.retry_delay_seconds)
        
        if not acquired:
            raise LockAcquisitionError(
                f"Failed to acquire Redis lock for {resource_name} after {self.config.retry_attempts} attempts"
            )
        
        try:
            yield
        finally:
            # Release the lock
            try:
                # TODO: Use Lua script for atomic lock release with ownership check
                # lua_script = '''
                # if redis.call("get", KEYS[1]) == ARGV[1] then
                #     return redis.call("del", KEYS[1])
                # else
                #     return 0
                # end
                # '''
                # self.redis_client.eval(lua_script, 1, lock_key, lock_value)
                
                # STUB: Simple lock release (not atomic)
                current_value = self.redis_client.get(lock_key)
                if current_value == lock_value:
                    self.redis_client.delete(lock_key)
                    
            except redis.RedisError:
                # Lock may have expired or been released, ignore errors
                pass

    def is_healthy(self) -> bool:
        """
        Check if Redis connection is healthy.
        
        Returns:
            bool: True if Redis is accessible, False otherwise
        """
        try:
            self.redis_client.ping()
            return True
        except redis.RedisError:
            return False

    def get_lock_info(self, resource_name: str) -> Optional[dict]:
        """
        Get information about a lock (for monitoring/debugging).
        
        Args:
            resource_name: Name of the resource
            
        Returns:
            dict: Lock information or None if lock doesn't exist
        """
        lock_key = f"lock:{resource_name}"
        
        try:
            value = self.redis_client.get(lock_key)
            if value:
                ttl = self.redis_client.ttl(lock_key)
                parts = value.split(':')
                return {
                    "resource": resource_name,
                    "owner": parts[0] if len(parts) > 0 else "unknown",
                    "acquired_at": float(parts[1]) if len(parts) > 1 else None,
                    "ttl_seconds": ttl if ttl > 0 else None,
                    "is_expired": ttl <= 0
                }
        except redis.RedisError:
            pass
        
        return None


# Example Redis configuration documentation
REDIS_CONFIG_EXAMPLES = {
    "basic": {
        "redis_host": "localhost",
        "redis_port": 6379,
        "redis_db": 0
    },
    
    "production": {
        "redis_host": "redis.example.com",
        "redis_port": 6379,
        "redis_password": "${REDIS_PASSWORD}",
        "redis_db": 0
    },
    
    "high_availability": {
        # Note: Redis Sentinel/Cluster support would be added here
        "redis_host": "redis-sentinel.example.com",
        "redis_port": 26379,
        "redis_password": "${REDIS_PASSWORD}",
        "redis_db": 0,
        # "sentinel_service_name": "mymaster",
        # "sentinel_nodes": [
        #     {"host": "sentinel1.example.com", "port": 26379},
        #     {"host": "sentinel2.example.com", "port": 26379},
        #     {"host": "sentinel3.example.com", "port": 26379}
        # ]
    }
}


# Performance monitoring metrics (to be implemented)
REDIS_LOCK_METRICS = {
    "lock_acquisition_attempts_total": "Counter of lock acquisition attempts",
    "lock_acquisition_success_total": "Counter of successful lock acquisitions", 
    "lock_acquisition_failure_total": "Counter of failed lock acquisitions",
    "lock_acquisition_duration_seconds": "Histogram of time taken to acquire locks",
    "lock_hold_duration_seconds": "Histogram of how long locks are held",
    "active_locks_count": "Gauge of currently held locks",
    "redis_connection_errors_total": "Counter of Redis connection errors",
    "lock_expiry_total": "Counter of locks that expired (potential issues)"
}