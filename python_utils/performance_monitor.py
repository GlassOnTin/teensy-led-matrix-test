#!/usr/bin/env python3
"""
Performance Monitoring System for LED Matrix
Collects and analyzes performance metrics across all components.
"""

import time
import threading
import statistics
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    """Single metric data point"""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """Time series of metrics"""
    name: str
    values: deque = field(default_factory=lambda: deque(maxlen=1000))
    tags: Dict[str, str] = field(default_factory=dict)

    def add_value(self, value: float, timestamp: Optional[float] = None):
        """Add value to series"""
        if timestamp is None:
            timestamp = time.time()
        self.values.append((timestamp, value))

    def get_recent(self, seconds: float = 60.0) -> List[tuple]:
        """Get values from last N seconds"""
        cutoff = time.time() - seconds
        return [(ts, val) for ts, val in self.values if ts >= cutoff]

    def get_stats(self, seconds: float = 60.0) -> Dict[str, float]:
        """Get statistical summary"""
        recent = [val for ts, val in self.get_recent(seconds)]
        if not recent:
            return {}

        return {
            'count': len(recent),
            'min': min(recent),
            'max': max(recent),
            'avg': statistics.mean(recent),
            'median': statistics.median(recent),
            'last': recent[-1] if recent else None
        }


class FPSCalculator:
    """Calculate frames per second with smoothing"""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.frame_times = deque(maxlen=window_size)
        self.last_frame_time = None

    def frame_rendered(self):
        """Call when a frame is rendered"""
        now = time.time()
        if self.last_frame_time is not None:
            frame_time = now - self.last_frame_time
            self.frame_times.append(frame_time)
        self.last_frame_time = now

    def get_fps(self) -> float:
        """Get current FPS"""
        if len(self.frame_times) < 2:
            return 0.0

        avg_frame_time = statistics.mean(self.frame_times)
        return 1.0 / avg_frame_time if avg_frame_time > 0 else 0.0

    def get_frame_time_ms(self) -> float:
        """Get average frame time in milliseconds"""
        if not self.frame_times:
            return 0.0
        return statistics.mean(self.frame_times) * 1000


class LatencyTracker:
    """Track latency between events"""

    def __init__(self, name: str):
        self.name = name
        self.pending: Dict[str, float] = {}
        self.completed = deque(maxlen=1000)
        self._lock = threading.Lock()

    def start(self, event_id: str) -> str:
        """Start tracking an event"""
        with self._lock:
            self.pending[event_id] = time.time()
        return event_id

    def end(self, event_id: str) -> Optional[float]:
        """End tracking and return latency"""
        with self._lock:
            if event_id in self.pending:
                start_time = self.pending.pop(event_id)
                latency = time.time() - start_time
                self.completed.append((time.time(), latency))
                return latency
        return None

    def get_recent_latencies(self, seconds: float = 60.0) -> List[float]:
        """Get recent latencies"""
        cutoff = time.time() - seconds
        with self._lock:
            return [latency for ts, latency in self.completed if ts >= cutoff]

    def get_stats(self, seconds: float = 60.0) -> Dict[str, float]:
        """Get latency statistics"""
        latencies = self.get_recent_latencies(seconds)
        if not latencies:
            return {}

        return {
            'count': len(latencies),
            'min_ms': min(latencies) * 1000,
            'max_ms': max(latencies) * 1000,
            'avg_ms': statistics.mean(latencies) * 1000,
            'p50_ms': statistics.median(latencies) * 1000,
            'p95_ms': statistics.quantiles(latencies, n=20)[18] * 1000 if len(latencies) >= 20 else max(latencies) * 1000
        }


class ThroughputCalculator:
    """Calculate throughput (items per second)"""

    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        self.events = deque()
        self._lock = threading.Lock()

    def add_event(self, count: int = 1):
        """Add events"""
        now = time.time()
        with self._lock:
            self.events.append((now, count))
            self._cleanup_old_events(now)

    def _cleanup_old_events(self, now: float):
        """Remove events outside window"""
        cutoff = now - self.window_seconds
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()

    def get_throughput(self) -> float:
        """Get current throughput (events per second)"""
        now = time.time()
        with self._lock:
            self._cleanup_old_events(now)
            if not self.events:
                return 0.0

            total_events = sum(count for ts, count in self.events)
            time_span = now - self.events[0][0] if self.events else 0.0
            return total_events / time_span if time_span > 0 else 0.0


class PerformanceMonitor:
    """Central performance monitoring system"""

    def __init__(self, save_interval: float = 30.0):
        self.save_interval = save_interval
        self._metrics: Dict[str, MetricSeries] = {}
        self._fps_calculators: Dict[str, FPSCalculator] = {}
        self._latency_trackers: Dict[str, LatencyTracker] = {}
        self._throughput_calculators: Dict[str, ThroughputCalculator] = {}
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []

        # Built-in metrics
        self._create_builtin_metrics()

        # Auto-save thread
        self._saving = True
        self._save_thread = threading.Thread(target=self._save_loop, daemon=True)
        self._save_thread.start()

    def _create_builtin_metrics(self):
        """Create standard metrics"""
        # FPS trackers
        self.create_fps_tracker('display')
        self.create_fps_tracker('processing')

        # Latency trackers
        self.create_latency_tracker('frame_pipeline')
        self.create_latency_tracker('serial_write')
        self.create_latency_tracker('api_request')

        # Throughput calculators
        self.create_throughput_tracker('frames_sent')
        self.create_throughput_tracker('api_calls')

    def create_metric(self, name: str, tags: Dict[str, str] = None) -> MetricSeries:
        """Create or get metric series"""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = MetricSeries(name=name, tags=tags or {})
            return self._metrics[name]

    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a metric value"""
        metric = self.create_metric(name, tags)
        metric.add_value(value)

    def create_fps_tracker(self, name: str) -> FPSCalculator:
        """Create FPS tracker"""
        with self._lock:
            if name not in self._fps_calculators:
                self._fps_calculators[name] = FPSCalculator()
            return self._fps_calculators[name]

    def record_frame(self, tracker_name: str = 'display'):
        """Record a frame render"""
        if tracker_name in self._fps_calculators:
            self._fps_calculators[tracker_name].frame_rendered()

    def create_latency_tracker(self, name: str) -> LatencyTracker:
        """Create latency tracker"""
        with self._lock:
            if name not in self._latency_trackers:
                self._latency_trackers[name] = LatencyTracker(name)
            return self._latency_trackers[name]

    def start_latency(self, tracker_name: str, event_id: str = None) -> str:
        """Start latency measurement"""
        if event_id is None:
            event_id = f"{tracker_name}_{time.time()}"

        if tracker_name in self._latency_trackers:
            return self._latency_trackers[tracker_name].start(event_id)
        return event_id

    def end_latency(self, tracker_name: str, event_id: str) -> Optional[float]:
        """End latency measurement"""
        if tracker_name in self._latency_trackers:
            return self._latency_trackers[tracker_name].end(event_id)
        return None

    def create_throughput_tracker(self, name: str) -> ThroughputCalculator:
        """Create throughput tracker"""
        with self._lock:
            if name not in self._throughput_calculators:
                self._throughput_calculators[name] = ThroughputCalculator()
            return self._throughput_calculators[name]

    def record_throughput(self, tracker_name: str, count: int = 1):
        """Record throughput events"""
        if tracker_name in self._throughput_calculators:
            self._throughput_calculators[tracker_name].add_event(count)

    def get_all_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        stats = {
            'timestamp': time.time(),
            'metrics': {},
            'fps': {},
            'latency': {},
            'throughput': {}
        }

        with self._lock:
            # Metric series stats
            for name, series in self._metrics.items():
                stats['metrics'][name] = series.get_stats()

            # FPS stats
            for name, calc in self._fps_calculators.items():
                stats['fps'][name] = {
                    'fps': calc.get_fps(),
                    'frame_time_ms': calc.get_frame_time_ms()
                }

            # Latency stats
            for name, tracker in self._latency_trackers.items():
                stats['latency'][name] = tracker.get_stats()

            # Throughput stats
            for name, calc in self._throughput_calculators.items():
                stats['throughput'][name] = calc.get_throughput()

        return stats

    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for periodic stats"""
        self._callbacks.append(callback)

    def _save_loop(self):
        """Periodic save/callback loop"""
        while self._saving:
            try:
                stats = self.get_all_stats()

                # Call registered callbacks
                for callback in self._callbacks:
                    try:
                        callback(stats)
                    except Exception as e:
                        logger.error(f"Performance callback error: {e}")

                time.sleep(self.save_interval)
            except Exception as e:
                logger.error(f"Performance save loop error: {e}")
                time.sleep(1.0)

    def save_to_file(self, filename: str):
        """Save current stats to file"""
        try:
            stats = self.get_all_stats()
            with open(filename, 'w') as f:
                json.dump(stats, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving performance data: {e}")

    def get_summary(self) -> str:
        """Get human-readable performance summary"""
        stats = self.get_all_stats()

        lines = ["=== Performance Summary ==="]

        # FPS
        if stats['fps']:
            lines.append("\nFPS:")
            for name, fps_data in stats['fps'].items():
                lines.append(f"  {name}: {fps_data['fps']:.1f} fps ({fps_data['frame_time_ms']:.1f}ms)")

        # Latency
        if any(stats['latency'].values()):
            lines.append("\nLatency:")
            for name, lat_data in stats['latency'].items():
                if lat_data:
                    lines.append(f"  {name}: avg={lat_data['avg_ms']:.1f}ms p95={lat_data['p95_ms']:.1f}ms")

        # Throughput
        if stats['throughput']:
            lines.append("\nThroughput:")
            for name, rate in stats['throughput'].items():
                lines.append(f"  {name}: {rate:.1f}/sec")

        return "\n".join(lines)

    def stop(self):
        """Stop monitoring"""
        self._saving = False
        if self._save_thread.is_alive():
            self._save_thread.join(timeout=1.0)


# Global instance
performance_monitor = PerformanceMonitor()


class PerformanceContext:
    """Context manager for tracking performance"""

    def __init__(self, tracker_name: str, event_id: str = None):
        self.tracker_name = tracker_name
        self.event_id = event_id or f"{tracker_name}_{time.time()}"

    def __enter__(self):
        performance_monitor.start_latency(self.tracker_name, self.event_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        performance_monitor.end_latency(self.tracker_name, self.event_id)


# Decorator for tracking function performance
def track_performance(tracker_name: str):
    """Decorator to track function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with PerformanceContext(tracker_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator