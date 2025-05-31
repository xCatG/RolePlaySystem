"""Storage and locking performance monitoring (STUB IMPLEMENTATION)."""

import time
from contextlib import contextmanager
from typing import Dict, Any, Optional, Generator
from dataclasses import dataclass, field
from collections import defaultdict, deque
from threading import Lock

from .exceptions import StorageError


@dataclass
class LockMetrics:
    """Metrics for lock operations."""
    acquisition_attempts: int = 0
    acquisition_successes: int = 0
    acquisition_failures: int = 0
    total_acquisition_time: float = 0.0
    total_hold_time: float = 0.0
    active_locks: int = 0
    expired_locks: int = 0
    
    # Recent operation times for percentile calculations
    recent_acquisition_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    recent_hold_times: deque = field(default_factory=lambda: deque(maxlen=1000))


@dataclass 
class StorageMetrics:
    """Metrics for storage operations."""
    read_operations: int = 0
    write_operations: int = 0
    delete_operations: int = 0
    list_operations: int = 0
    total_read_time: float = 0.0
    total_write_time: float = 0.0
    
    # Error tracking
    read_errors: int = 0
    write_errors: int = 0
    connection_errors: int = 0


class StorageMonitor:
    """
    Storage and locking performance monitor (STUB IMPLEMENTATION).
    
    Tracks key metrics for storage operations and distributed locking
    to help identify performance bottlenecks and optimize configurations.
    
    ⚠️  WARNING: This is a STUB implementation for demonstration.
    Production implementation would integrate with proper monitoring
    systems like Prometheus, Grafana, or cloud monitoring services.
    
    Key Metrics Tracked:
    - Lock acquisition success/failure rates
    - Lock acquisition and hold times
    - Storage operation latencies
    - Error rates by operation type
    - Active lock counts
    
    Production TODO:
    - Integrate with Prometheus metrics
    - Add proper metric aggregation
    - Implement alerting on threshold breaches
    - Add dashboard configuration templates
    - Support metric export in multiple formats
    """

    def __init__(self):
        self._lock = Lock()
        self._lock_metrics: Dict[str, LockMetrics] = defaultdict(LockMetrics)
        self._storage_metrics = StorageMetrics()
        self._start_time = time.time()

    @contextmanager
    def monitor_lock_acquisition(
        self, 
        resource_name: str, 
        lock_strategy: str = "unknown"
    ) -> Generator[None, None, None]:
        """
        Monitor lock acquisition performance.
        
        Args:
            resource_name: Name of the resource being locked
            lock_strategy: Strategy used for locking (file, object, redis)
            
        Yields:
            None
        """
        metric_key = f"{lock_strategy}:{resource_name}"
        start_time = time.time()
        
        with self._lock:
            self._lock_metrics[metric_key].acquisition_attempts += 1
        
        success = False
        hold_start_time = None
        
        try:
            yield
            success = True
            hold_start_time = time.time()
            
        except Exception:
            with self._lock:
                self._lock_metrics[metric_key].acquisition_failures += 1
            raise
            
        finally:
            end_time = time.time()
            acquisition_time = (hold_start_time or end_time) - start_time
            
            with self._lock:
                metrics = self._lock_metrics[metric_key]
                
                if success:
                    metrics.acquisition_successes += 1
                    metrics.total_acquisition_time += acquisition_time
                    metrics.recent_acquisition_times.append(acquisition_time)
                    
                    if hold_start_time:
                        hold_time = end_time - hold_start_time
                        metrics.total_hold_time += hold_time
                        metrics.recent_hold_times.append(hold_time)

    @contextmanager 
    def monitor_storage_operation(
        self, 
        operation_type: str
    ) -> Generator[None, None, None]:
        """
        Monitor storage operation performance.
        
        Args:
            operation_type: Type of operation (read, write, delete, list)
            
        Yields:
            None
        """
        start_time = time.time()
        success = False
        
        try:
            yield
            success = True
            
        except Exception:
            with self._lock:
                if operation_type == "read":
                    self._storage_metrics.read_errors += 1
                elif operation_type == "write":
                    self._storage_metrics.write_errors += 1
            raise
            
        finally:
            operation_time = time.time() - start_time
            
            with self._lock:
                if success:
                    if operation_type == "read":
                        self._storage_metrics.read_operations += 1
                        self._storage_metrics.total_read_time += operation_time
                    elif operation_type == "write":
                        self._storage_metrics.write_operations += 1
                        self._storage_metrics.total_write_time += operation_time
                    elif operation_type == "delete":
                        self._storage_metrics.delete_operations += 1
                    elif operation_type == "list":
                        self._storage_metrics.list_operations += 1

    def record_connection_error(self, backend_type: str) -> None:
        """Record a connection error for monitoring."""
        with self._lock:
            self._storage_metrics.connection_errors += 1

    def record_lock_expiry(self, resource_name: str, lock_strategy: str) -> None:
        """Record a lock expiry event."""
        metric_key = f"{lock_strategy}:{resource_name}"
        with self._lock:
            self._lock_metrics[metric_key].expired_locks += 1

    def get_lock_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of lock metrics.
        
        Returns:
            dict: Summary of lock performance metrics
        """
        with self._lock:
            total_attempts = sum(m.acquisition_attempts for m in self._lock_metrics.values())
            total_successes = sum(m.acquisition_successes for m in self._lock_metrics.values())
            total_failures = sum(m.acquisition_failures for m in self._lock_metrics.values())
            
            success_rate = (total_successes / total_attempts * 100) if total_attempts > 0 else 0
            
            # Calculate average acquisition time
            all_acquisition_times = []
            for metrics in self._lock_metrics.values():
                all_acquisition_times.extend(list(metrics.recent_acquisition_times))
            
            avg_acquisition_time = (
                sum(all_acquisition_times) / len(all_acquisition_times)
                if all_acquisition_times else 0
            )
            
            return {
                "total_attempts": total_attempts,
                "total_successes": total_successes,
                "total_failures": total_failures,
                "success_rate_percent": round(success_rate, 2),
                "average_acquisition_time_ms": round(avg_acquisition_time * 1000, 2),
                "active_strategies": list(set(
                    key.split(':')[0] for key in self._lock_metrics.keys()
                )),
                "most_contended_resources": self._get_most_contended_resources()
            }

    def get_storage_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of storage metrics.
        
        Returns:
            dict: Summary of storage performance metrics
        """
        with self._lock:
            total_ops = (
                self._storage_metrics.read_operations +
                self._storage_metrics.write_operations +
                self._storage_metrics.delete_operations +
                self._storage_metrics.list_operations
            )
            
            avg_read_time = (
                self._storage_metrics.total_read_time / self._storage_metrics.read_operations
                if self._storage_metrics.read_operations > 0 else 0
            )
            
            avg_write_time = (
                self._storage_metrics.total_write_time / self._storage_metrics.write_operations
                if self._storage_metrics.write_operations > 0 else 0
            )
            
            return {
                "total_operations": total_ops,
                "read_operations": self._storage_metrics.read_operations,
                "write_operations": self._storage_metrics.write_operations,
                "delete_operations": self._storage_metrics.delete_operations,
                "list_operations": self._storage_metrics.list_operations,
                "average_read_time_ms": round(avg_read_time * 1000, 2),
                "average_write_time_ms": round(avg_write_time * 1000, 2),
                "read_errors": self._storage_metrics.read_errors,
                "write_errors": self._storage_metrics.write_errors,
                "connection_errors": self._storage_metrics.connection_errors,
                "uptime_seconds": round(time.time() - self._start_time, 2)
            }

    def _get_most_contended_resources(self, limit: int = 5) -> list:
        """Get the most contended resources by attempt count."""
        sorted_resources = sorted(
            self._lock_metrics.items(),
            key=lambda x: x[1].acquisition_attempts,
            reverse=True
        )
        
        return [
            {
                "resource": key.split(':', 1)[1] if ':' in key else key,
                "strategy": key.split(':', 1)[0] if ':' in key else "unknown",
                "attempts": metrics.acquisition_attempts,
                "failures": metrics.acquisition_failures
            }
            for key, metrics in sorted_resources[:limit]
        ]

    def export_metrics_for_prometheus(self) -> str:
        """
        Export metrics in Prometheus format (STUB).
        
        Returns:
            str: Metrics in Prometheus exposition format
        """
        # TODO: Implement actual Prometheus metric formatting
        lock_summary = self.get_lock_metrics_summary()
        storage_summary = self.get_storage_metrics_summary()
        
        return f"""
# HELP storage_lock_attempts_total Total number of lock acquisition attempts
# TYPE storage_lock_attempts_total counter
storage_lock_attempts_total {lock_summary['total_attempts']}

# HELP storage_lock_successes_total Total number of successful lock acquisitions
# TYPE storage_lock_successes_total counter
storage_lock_successes_total {lock_summary['total_successes']}

# HELP storage_operations_total Total number of storage operations
# TYPE storage_operations_total counter
storage_operations_total {storage_summary['total_operations']}

# HELP storage_errors_total Total number of storage errors
# TYPE storage_errors_total counter
storage_errors_total {storage_summary['read_errors'] + storage_summary['write_errors']}
""".strip()

    def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._lock_metrics.clear()
            self._storage_metrics = StorageMetrics()
            self._start_time = time.time()


# Global monitor instance (singleton pattern)
_global_monitor: Optional[StorageMonitor] = None


def get_storage_monitor() -> StorageMonitor:
    """Get the global storage monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = StorageMonitor()
    return _global_monitor


# Decision matrix for when to evolve locking strategy
LOCK_STRATEGY_DECISION_CRITERIA = {
    "success_rate_threshold": 95.0,  # Switch to Redis if success rate drops below 95%
    "avg_acquisition_time_ms_threshold": 1000,  # Switch if acquisition takes >1s
    "contention_attempts_threshold": 100,  # High contention indicator
    "error_rate_threshold": 5.0  # Switch if error rate exceeds 5%
}


def should_upgrade_locking_strategy(monitor: StorageMonitor) -> Dict[str, Any]:
    """
    Analyze metrics to determine if locking strategy should be upgraded.
    
    Args:
        monitor: Storage monitor instance
        
    Returns:
        dict: Analysis results with recommendations
    """
    lock_metrics = monitor.get_lock_metrics_summary()
    criteria = LOCK_STRATEGY_DECISION_CRITERIA
    
    recommendations = []
    
    if lock_metrics['success_rate_percent'] < criteria['success_rate_threshold']:
        recommendations.append(
            f"Low success rate ({lock_metrics['success_rate_percent']}%) - consider Redis locking"
        )
    
    if lock_metrics['average_acquisition_time_ms'] > criteria['avg_acquisition_time_ms_threshold']:
        recommendations.append(
            f"High acquisition latency ({lock_metrics['average_acquisition_time_ms']}ms) - consider Redis locking"
        )
    
    # Check for high contention
    contended_resources = [
        r for r in lock_metrics['most_contended_resources']
        if r['attempts'] > criteria['contention_attempts_threshold']
    ]
    
    if contended_resources:
        recommendations.append(
            f"High contention detected on {len(contended_resources)} resources - consider Redis locking"
        )
    
    return {
        "should_upgrade": len(recommendations) > 0,
        "current_strategy_performance": "poor" if recommendations else "acceptable",
        "recommendations": recommendations,
        "suggested_strategy": "redis" if recommendations else "current",
        "metrics_summary": lock_metrics
    }