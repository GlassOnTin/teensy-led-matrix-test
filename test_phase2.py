#!/usr/bin/env python3
"""
Test Phase 2 Enhanced Protocol and Resource Management
"""

import time
import sys
import os

# Add python_utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python_utils'))

from serial_connection import TeensyConnection
from protocol_v2 import ProtocolV2Connection, FrameType, CommandType
from resource_manager import resource_manager
from performance_monitor import performance_monitor, PerformanceContext
from matrix_state import matrix_state
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_basic_connection():
    """Test basic connection functionality"""
    print("=== Testing Basic Connection ===")

    conn = TeensyConnection()
    if conn.connect():
        print("✓ Basic connection established")
        stats = conn.get_stats()
        print(f"Connection stats: {stats}")

        # Test frame writing
        frame_data = bytes([0xFF, 0xFE, 0xFD]) + bytes([128, 0, 128] * 1024)  # Purple pattern
        if conn.write_frame(frame_data):
            print("✓ Frame write successful")
        else:
            print("✗ Frame write failed")

        conn.close()
        return True
    else:
        print("✗ Basic connection failed")
        return False


def test_enhanced_protocol():
    """Test enhanced protocol v2 features"""
    print("\n=== Testing Enhanced Protocol v2 ===")

    conn = TeensyConnection()
    if not conn.connect():
        print("✗ Connection failed")
        return False

    if conn._enhanced_connection:
        print("✓ Enhanced protocol v2 enabled")

        # Test ping
        if conn._enhanced_connection.protocol_handler.ping():
            print("✓ Ping successful")
        else:
            print("⚠ Ping failed (firmware may not support v2)")

        # Test mode setting
        if conn.set_mode('s'):
            print("✓ Mode setting successful")
        else:
            print("⚠ Mode setting failed")

        # Test brightness setting
        if conn.set_brightness(0.5):
            print("✓ Brightness setting successful")
        else:
            print("⚠ Brightness setting failed")

        # Get protocol stats
        stats = conn._enhanced_connection.protocol_handler.get_stats()
        print(f"Protocol stats: {stats}")

    else:
        print("⚠ Enhanced protocol not available, using basic protocol")

    conn.close()
    return True


def test_resource_management():
    """Test resource management features"""
    print("\n=== Testing Resource Management ===")

    # Test frame buffer pool
    pool_stats = resource_manager.frame_pool.get_stats()
    print(f"Frame pool stats: {pool_stats}")

    # Test buffer allocation/deallocation
    buffers = []
    for i in range(5):
        buffer = resource_manager.frame_pool.get_buffer()
        buffers.append(buffer)

    print(f"Allocated 5 buffers, pool stats: {resource_manager.frame_pool.get_stats()}")

    # Return buffers
    for buffer in buffers:
        resource_manager.frame_pool.return_buffer(buffer)

    print(f"Returned buffers, pool stats: {resource_manager.frame_pool.get_stats()}")

    # Test frame queue
    from resource_manager import FrameBuffer
    frame_buf = FrameBuffer(rgb_data=b'test', timestamp=time.time(), priority=1)

    if resource_manager.frame_queue.put(frame_buf):
        print("✓ Frame queue put successful")

    retrieved = resource_manager.frame_queue.get(timeout=0.1)
    if retrieved:
        print("✓ Frame queue get successful")
    else:
        print("✗ Frame queue get failed")

    # Test system stats
    stats = resource_manager.get_system_stats()
    print(f"System stats: {stats}")

    return True


def test_performance_monitoring():
    """Test performance monitoring"""
    print("\n=== Testing Performance Monitoring ===")

    # Test FPS tracking
    fps_tracker = performance_monitor.create_fps_tracker('test')
    for i in range(10):
        fps_tracker.frame_rendered()
        time.sleep(0.016)  # ~60 FPS

    print(f"Test FPS: {fps_tracker.get_fps():.1f}")

    # Test latency tracking
    tracker = performance_monitor.create_latency_tracker('test_latency')
    event_id = tracker.start('test_event')
    time.sleep(0.01)  # 10ms operation
    latency = tracker.end(event_id)
    print(f"Test latency: {latency*1000:.1f}ms")

    # Test context manager
    with PerformanceContext('test_context'):
        time.sleep(0.005)  # 5ms operation

    # Test metric recording
    performance_monitor.record_metric('test_metric', 42.0)
    performance_monitor.record_throughput('test_throughput', 5)

    # Get comprehensive stats
    stats = performance_monitor.get_all_stats()
    print("Performance stats available:", list(stats.keys()))

    # Print summary
    print(performance_monitor.get_summary())

    return True


def test_connection_health():
    """Test connection health monitoring"""
    print("\n=== Testing Connection Health Monitoring ===")

    conn = TeensyConnection()
    if conn.connect():
        print("✓ Connection established for health test")

        # Let health monitoring run for a few seconds
        time.sleep(3)

        if resource_manager.connection_health:
            health = resource_manager.connection_health.get_health_summary()
            print(f"Connection health: {health}")
        else:
            print("⚠ Connection health monitoring not available")

        conn.close()
        return True
    else:
        print("✗ Connection failed for health test")
        return False


def test_integration():
    """Test full integration with performance monitoring"""
    print("\n=== Testing Full Integration ===")

    conn = TeensyConnection()
    if not conn.connect():
        print("✗ Connection failed")
        return False

    print("✓ Connection established")

    # Send test frames with performance monitoring
    test_frames = 10
    start_time = time.time()

    for i in range(test_frames):
        # Create test pattern
        frame_data = bytes([0xFF, 0xFE, 0xFD])
        for y in range(16):
            for x in range(64):
                # Animated rainbow pattern
                hue = (x + y + i * 4) % 256
                frame_data += bytes([hue, 255 - hue, (hue + 128) % 256])

        # Write with performance tracking
        if not conn.write_frame(frame_data):
            print(f"✗ Frame {i} write failed")
            break

        time.sleep(0.033)  # ~30 FPS

    elapsed = time.time() - start_time
    actual_fps = test_frames / elapsed
    print(f"✓ Sent {test_frames} frames in {elapsed:.2f}s ({actual_fps:.1f} fps)")

    # Get final stats
    conn_stats = conn.get_stats()
    perf_stats = performance_monitor.get_all_stats()
    resource_stats = resource_manager.get_system_stats()

    print(f"Connection stats: {conn_stats}")
    print(f"Performance FPS: {perf_stats.get('fps', {})}")
    print(f"Resource usage: {resource_stats.get('memory', {})}")

    conn.close()
    return True


def main():
    """Run all Phase 2 tests"""
    print("Starting Phase 2 Enhanced Protocol and Resource Management Tests\n")

    tests = [
        ("Basic Connection", test_basic_connection),
        ("Enhanced Protocol v2", test_enhanced_protocol),
        ("Resource Management", test_resource_management),
        ("Performance Monitoring", test_performance_monitoring),
        ("Connection Health", test_connection_health),
        ("Full Integration", test_integration)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"✓ {test_name} PASSED")
                passed += 1
            else:
                print(f"✗ {test_name} FAILED")
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}")

    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    print(f"Success rate: {passed/total*100:.1f}%")

    if passed == total:
        print("🎉 All Phase 2 tests passed!")
    else:
        print("⚠ Some tests failed - see output above")

    # Cleanup
    try:
        resource_manager.cleanup()
        performance_monitor.stop()
    except:
        pass


if __name__ == "__main__":
    main()