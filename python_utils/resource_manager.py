#!/usr/bin/env python3
"""
Resource Management System for LED Matrix
Handles frame buffers, process lifecycle, and memory management.
"""

import threading
import time
import queue
import psutil
import os
import signal
import gc
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class FrameBuffer:
    """Frame buffer with metadata"""
    rgb_data: bytes
    timestamp: float
    sequence: int = 0
    priority: int = 0  # Higher = more important
    metadata: Dict[str, Any] = field(default_factory=dict)


class FrameBufferPool:
    """Thread-safe frame buffer pool to prevent memory fragmentation"""

    def __init__(self, size: int = 20, frame_size: int = 3072):
        self.size = size
        self.frame_size = frame_size
        self._pool = queue.Queue(maxsize=size)
        self._lock = threading.Lock()
        self._allocated = 0
        self._stats = {
            'allocations': 0,
            'deallocations': 0,
            'pool_hits': 0,
            'pool_misses': 0
        }

        # Pre-allocate buffers
        for _ in range(size):
            buffer = bytearray(frame_size)
            self._pool.put(buffer)

    def get_buffer(self) -> bytearray:
        """Get a buffer from the pool"""
        try:
            buffer = self._pool.get_nowait()
            self._stats['pool_hits'] += 1
            with self._lock:
                self._allocated += 1
            return buffer
        except queue.Empty:
            # Pool exhausted, allocate new buffer
            self._stats['pool_misses'] += 1
            with self._lock:
                self._allocated += 1
            self._stats['allocations'] += 1
            return bytearray(self.frame_size)

    def return_buffer(self, buffer: bytearray):
        """Return buffer to pool"""
        with self._lock:
            self._allocated -= 1

        if len(buffer) == self.frame_size:
            try:
                # Clear buffer and return to pool
                buffer[:] = b'\x00' * self.frame_size
                self._pool.put_nowait(buffer)
                self._stats['deallocations'] += 1
            except queue.Full:
                # Pool is full, let it be garbage collected
                pass

    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics"""
        with self._lock:
            return {
                **self._stats,
                'allocated': self._allocated,
                'pool_size': self._pool.qsize(),
                'memory_mb': (self._allocated * self.frame_size) / (1024 * 1024)
            }


class FrameQueue:
    """Priority queue for frame buffering with overflow protection"""

    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self._queue = queue.PriorityQueue(maxsize=max_size)
        self._lock = threading.Lock()
        self._sequence = 0
        self._dropped_frames = 0

    def put(self, frame_buffer: FrameBuffer, block: bool = False) -> bool:
        """Add frame to queue"""
        try:
            # Use negative priority for max-heap behavior
            priority_item = (-frame_buffer.priority, frame_buffer.timestamp, frame_buffer)
            self._queue.put(priority_item, block=block, timeout=0.001)
            return True
        except queue.Full:
            if not block:
                # Drop lowest priority frame if queue is full
                try:
                    # Get lowest priority item (last in queue)
                    dropped_item = self._queue.get_nowait()
                    self._dropped_frames += 1
                    logger.debug(f"Dropped frame due to queue overflow")

                    # Add new frame
                    self._queue.put(priority_item, block=False)
                    return True
                except (queue.Empty, queue.Full):
                    self._dropped_frames += 1
                    return False
            return False

    def get(self, timeout: Optional[float] = None) -> Optional[FrameBuffer]:
        """Get next frame from queue"""
        try:
            priority_item = self._queue.get(timeout=timeout)
            return priority_item[2]  # Return the FrameBuffer
        except queue.Empty:
            return None

    def size(self) -> int:
        """Get current queue size"""
        return self._queue.qsize()

    def get_dropped_count(self) -> int:
        """Get number of dropped frames"""
        return self._dropped_frames

    def clear(self):
        """Clear all frames from queue"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break


class ProcessTracker:
    """Track and manage spawned processes"""

    def __init__(self):
        self._processes: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register_process(self, pid: int, name: str, start_time: float, **metadata):
        """Register a process for tracking"""
        with self._lock:
            self._processes[pid] = {
                'name': name,
                'start_time': start_time,
                'last_seen': time.time(),
                **metadata
            }

    def update_process(self, pid: int, **metadata):
        """Update process metadata"""
        with self._lock:
            if pid in self._processes:
                self._processes[pid].update(metadata)
                self._processes[pid]['last_seen'] = time.time()

    def unregister_process(self, pid: int):
        """Remove process from tracking"""
        with self._lock:
            self._processes.pop(pid, None)

    def get_active_processes(self) -> List[Dict[str, Any]]:
        """Get list of tracked processes"""
        with self._lock:
            active = []
            for pid, info in self._processes.items():
                try:
                    # Check if process is still alive
                    process = psutil.Process(pid)
                    if process.is_running():
                        active.append({
                            'pid': pid,
                            'status': process.status(),
                            'memory_mb': process.memory_info().rss / (1024 * 1024),
                            'cpu_percent': process.cpu_percent(),
                            **info
                        })
                    else:
                        # Process died, remove from tracking
                        self._processes.pop(pid, None)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process no longer exists
                    self._processes.pop(pid, None)

            return active

    def cleanup_orphaned_processes(self, max_age_seconds: float = 300):
        """Clean up old processes that may be orphaned"""
        current_time = time.time()
        orphaned = []

        with self._lock:
            for pid, info in list(self._processes.items()):
                age = current_time - info['start_time']
                if age > max_age_seconds:
                    try:
                        process = psutil.Process(pid)
                        if process.is_running():
                            orphaned.append((pid, info['name'], age))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Process already gone
                        self._processes.pop(pid, None)

        # Terminate orphaned processes
        for pid, name, age in orphaned:
            logger.warning(f"Terminating orphaned process {name} (PID {pid}, age {age:.1f}s)")
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)
                # Force kill if still alive
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            except ProcessLookupError:
                pass
            self.unregister_process(pid)


class MemoryMonitor:
    """Monitor and manage memory usage"""

    def __init__(self, warning_threshold_mb: float = 512, critical_threshold_mb: float = 1024):
        self.warning_threshold = warning_threshold_mb
        self.critical_threshold = critical_threshold_mb
        self._callbacks: List[Callable[[str, Dict], None]] = []

    def add_callback(self, callback: Callable[[str, Dict], None]):
        """Add callback for memory events"""
        self._callbacks.append(callback)

    def check_memory_usage(self) -> Dict[str, Any]:
        """Check current memory usage"""
        process = psutil.Process()
        memory_info = process.memory_info()

        stats = {
            'rss_mb': memory_info.rss / (1024 * 1024),
            'vms_mb': memory_info.vms / (1024 * 1024),
            'percent': process.memory_percent(),
            'timestamp': time.time()
        }

        # Check thresholds
        if stats['rss_mb'] > self.critical_threshold:
            self._notify_callbacks('critical', stats)
        elif stats['rss_mb'] > self.warning_threshold:
            self._notify_callbacks('warning', stats)

        return stats

    def force_garbage_collection(self):
        """Force garbage collection"""
        collected = gc.collect()
        logger.info(f"Garbage collection freed {collected} objects")
        return collected

    def _notify_callbacks(self, level: str, stats: Dict[str, Any]):
        """Notify registered callbacks"""
        for callback in self._callbacks:
            try:
                callback(level, stats)
            except Exception as e:
                logger.error(f"Memory callback error: {e}")


class ConnectionHealthMonitor:
    """Monitor connection health and performance"""

    def __init__(self, connection):
        self.connection = connection
        self._health_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None

    def start_monitoring(self, interval: float = 5.0):
        """Start health monitoring"""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self):
        """Stop health monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)

    def _monitor_loop(self, interval: float):
        """Monitor loop"""
        while self._monitoring:
            try:
                # Check connection health
                health_data = self._check_health()

                with self._lock:
                    self._health_history.append(health_data)
                    # Keep only last 100 entries
                    if len(self._health_history) > 100:
                        self._health_history = self._health_history[-100:]

                time.sleep(interval)
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                time.sleep(interval)

    def _check_health(self) -> Dict[str, Any]:
        """Check connection health"""
        health = {
            'timestamp': time.time(),
            'connected': False,
            'ping_time': None,
            'error_count': 0
        }

        try:
            # Check if connection exists and is open
            if hasattr(self.connection, 'ser') and self.connection.ser:
                health['connected'] = self.connection.ser.is_open

                # Ping test if protocol v2 is available
                if hasattr(self.connection, 'protocol_handler') and self.connection.protocol_handler:
                    start_time = time.time()
                    if self.connection.protocol_handler.ping():
                        health['ping_time'] = time.time() - start_time
                    else:
                        health['error_count'] = 1

        except Exception as e:
            logger.debug(f"Health check error: {e}")
            health['error_count'] = 1

        return health

    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary"""
        with self._lock:
            if not self._health_history:
                return {'status': 'unknown', 'history_length': 0}

            recent = self._health_history[-10:]  # Last 10 checks
            connected_count = sum(1 for h in recent if h['connected'])
            error_count = sum(h['error_count'] for h in recent)
            avg_ping = None

            ping_times = [h['ping_time'] for h in recent if h['ping_time'] is not None]
            if ping_times:
                avg_ping = sum(ping_times) / len(ping_times)

            status = 'healthy'
            if connected_count < len(recent) * 0.8:  # Less than 80% connected
                status = 'unstable'
            elif error_count > len(recent) * 0.5:  # More than 50% errors
                status = 'poor'

            return {
                'status': status,
                'connected_ratio': connected_count / len(recent) if recent else 0,
                'error_count': error_count,
                'avg_ping_ms': avg_ping * 1000 if avg_ping else None,
                'history_length': len(self._health_history),
                'last_check': recent[-1]['timestamp'] if recent else None
            }


class ResourceManager:
    """Central resource management system"""

    def __init__(self):
        self.frame_pool = FrameBufferPool()
        self.frame_queue = FrameQueue()
        self.process_tracker = ProcessTracker()
        self.memory_monitor = MemoryMonitor()
        self.connection_health: Optional[ConnectionHealthMonitor] = None

        # Setup memory callbacks
        self.memory_monitor.add_callback(self._handle_memory_event)

        # Register current process
        self.process_tracker.register_process(
            os.getpid(),
            'led_matrix_main',
            time.time(),
            type='main'
        )

    def set_connection(self, connection):
        """Set connection for health monitoring"""
        if self.connection_health:
            self.connection_health.stop_monitoring()

        self.connection_health = ConnectionHealthMonitor(connection)
        self.connection_health.start_monitoring()

    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        stats = {
            'timestamp': time.time(),
            'frame_pool': self.frame_pool.get_stats(),
            'frame_queue': {
                'size': self.frame_queue.size(),
                'dropped': self.frame_queue.get_dropped_count()
            },
            'memory': self.memory_monitor.check_memory_usage(),
            'processes': self.process_tracker.get_active_processes(),
            'connection_health': None
        }

        if self.connection_health:
            stats['connection_health'] = self.connection_health.get_health_summary()

        return stats

    def cleanup(self):
        """Cleanup resources"""
        logger.info("Starting resource cleanup...")

        # Clear frame queue
        self.frame_queue.clear()

        # Force garbage collection
        self.memory_monitor.force_garbage_collection()

        # Cleanup orphaned processes
        self.process_tracker.cleanup_orphaned_processes()

        # Stop health monitoring
        if self.connection_health:
            self.connection_health.stop_monitoring()

        logger.info("Resource cleanup completed")

    def _handle_memory_event(self, level: str, stats: Dict[str, Any]):
        """Handle memory usage events"""
        if level == 'warning':
            logger.warning(f"Memory usage warning: {stats['rss_mb']:.1f} MB")
            # Clear frame queue to free memory
            dropped = self.frame_queue.size()
            self.frame_queue.clear()
            if dropped > 0:
                logger.info(f"Cleared {dropped} frames from queue")

        elif level == 'critical':
            logger.error(f"Critical memory usage: {stats['rss_mb']:.1f} MB")
            # Aggressive cleanup
            self.frame_queue.clear()
            self.memory_monitor.force_garbage_collection()
            # Could also restart the process here if needed


# Global instance
resource_manager = ResourceManager()