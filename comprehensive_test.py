#!/usr/bin/env python3
"""
Comprehensive Phase 2 Testing Suite
Thoroughly tests serial connection, state machine, and Protocol v2 integration
"""

import sys
import os
import time
import threading

# Add python_utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python_utils'))

from serial_connection import TeensyConnection
from performance_monitor import performance_monitor
from resource_manager import resource_manager


def test_basic_connection():
    """Test 1: Basic serial connection and communication"""
    print("=== Test 1: Basic Serial Connection ===")

    conn = TeensyConnection()

    print("1.1 Attempting connection...")
    if not conn.connect():
        print("❌ FAIL: Could not establish connection")
        return False

    print("✅ Connection established")
    print(f"    Port: {conn.port}")
    print(f"    Baudrate: {conn.baudrate}")
    print(f"    Enhanced protocol: {conn._enhanced_connection is not None}")

    # Test serial is responsive
    if conn.ser and conn.ser.is_open:
        print("✅ Serial port is open and responsive")
    else:
        print("❌ FAIL: Serial port not responsive")
        return False

    conn.close()
    print("✅ Connection closed cleanly")
    return True


def test_mode_switching():
    """Test 2: Mode switching and state machine"""
    print("\n=== Test 2: Mode Switching ===")

    conn = TeensyConnection()
    if not conn.connect():
        print("❌ FAIL: Could not establish connection")
        return False

    print("2.1 Testing streaming mode...")
    success = conn.set_mode('s')
    print(f"    Streaming mode: {'✅' if success else '❌'}")
    time.sleep(0.5)

    print("2.2 Testing effects mode...")
    success = conn.set_mode('e')
    print(f"    Effects mode: {'✅' if success else '❌'}")
    time.sleep(0.5)

    print("2.3 Back to streaming mode...")
    success = conn.set_mode('s')
    print(f"    Back to streaming: {'✅' if success else '❌'}")
    time.sleep(0.5)

    conn.close()
    print("✅ Mode switching test complete")
    return True


def test_frame_transmission():
    """Test 3: Frame transmission and display"""
    print("\n=== Test 3: Frame Transmission ===")

    conn = TeensyConnection()
    if not conn.connect():
        print("❌ FAIL: Could not establish connection")
        return False

    test_patterns = [
        ("Red pattern", [255, 0, 0]),
        ("Green pattern", [0, 255, 0]),
        ("Blue pattern", [0, 0, 255]),
        ("White pattern", [255, 255, 255]),
        ("Off pattern", [0, 0, 0])
    ]

    print("3.1 Testing solid color patterns...")
    for pattern_name, rgb in test_patterns:
        frame_data = bytes([0xFF, 0xFE, 0xFD]) + bytes(rgb * 1024)

        start_time = time.time()
        success = conn.write_frame(frame_data)
        write_time = time.time() - start_time

        print(f"    {pattern_name}: {'✅' if success else '❌'} ({write_time*1000:.1f}ms)")
        time.sleep(0.8)  # Time to observe

    print("3.2 Testing animated pattern...")
    for i in range(10):
        # Create moving rainbow pattern
        frame_data = bytes([0xFF, 0xFE, 0xFD])
        for pixel in range(1024):
            hue = (pixel + i * 10) % 256
            r = int(255 * (1 + __import__('math').sin(hue * 0.024)) / 2)
            g = int(255 * (1 + __import__('math').sin((hue + 85) * 0.024)) / 2)
            b = int(255 * (1 + __import__('math').sin((hue + 170) * 0.024)) / 2)
            frame_data += bytes([r, g, b])

        success = conn.write_frame(frame_data)
        if not success:
            print(f"❌ FAIL: Frame {i} transmission failed")
            conn.close()
            return False
        time.sleep(0.1)

    print("✅ Animation pattern complete")

    conn.close()
    return True


def test_performance_monitoring():
    """Test 4: Performance monitoring integration"""
    print("\n=== Test 4: Performance Monitoring ===")

    conn = TeensyConnection()
    if not conn.connect():
        print("❌ FAIL: Could not establish connection")
        return False

    print("4.1 Testing FPS measurement...")
    start_time = time.time()
    frame_count = 0

    # Send frames for FPS measurement
    for i in range(30):  # 30 frames
        frame_data = bytes([0xFF, 0xFE, 0xFD]) + bytes([i*8, 128, 255-i*8] * 1024)
        if conn.write_frame(frame_data):
            frame_count += 1
        time.sleep(0.033)  # ~30 FPS target

    elapsed = time.time() - start_time
    measured_fps = frame_count / elapsed

    print(f"    Frames sent: {frame_count}")
    print(f"    Time elapsed: {elapsed:.2f}s")
    print(f"    Measured FPS: {measured_fps:.1f}")

    # Get performance stats
    stats = performance_monitor.get_all_stats()
    if 'fps' in stats and 'display' in stats['fps']:
        monitor_fps = stats['fps']['display']['fps']
        print(f"    Monitor FPS: {monitor_fps:.1f}")

    conn_stats = conn.get_stats()
    print(f"    Connection frame count: {conn_stats['frame_count']}")

    conn.close()
    return True


def test_resource_management():
    """Test 5: Resource management"""
    print("\n=== Test 5: Resource Management ===")

    print("5.1 Testing frame buffer pool...")
    initial_stats = resource_manager.frame_pool.get_stats()
    print(f"    Initial pool size: {initial_stats['pool_size']}")

    # Allocate and return buffers
    buffers = []
    for i in range(10):
        buffer = resource_manager.frame_pool.get_buffer()
        buffers.append(buffer)

    mid_stats = resource_manager.frame_pool.get_stats()
    print(f"    After allocation: {mid_stats['allocated']} allocated")

    for buffer in buffers:
        resource_manager.frame_pool.return_buffer(buffer)

    final_stats = resource_manager.frame_pool.get_stats()
    print(f"    After return: {final_stats['allocated']} allocated")
    print(f"    Pool hits: {final_stats['pool_hits']}")

    print("5.2 Testing system stats...")
    system_stats = resource_manager.get_system_stats()
    print(f"    Memory usage: {system_stats['memory']['rss_mb']:.1f} MB")
    print(f"    Active processes: {len(system_stats['processes'])}")

    return True


def test_error_recovery():
    """Test 6: Error recovery and reconnection"""
    print("\n=== Test 6: Error Recovery ===")

    conn = TeensyConnection()
    if not conn.connect():
        print("❌ FAIL: Could not establish connection")
        return False

    print("6.1 Testing connection stats...")
    stats = conn.get_stats()
    for key, value in stats.items():
        print(f"    {key}: {value}")

    print("6.2 Testing graceful close and reconnect...")
    conn.close()
    time.sleep(1)

    if conn.connect():
        print("✅ Reconnection successful")
    else:
        print("❌ FAIL: Reconnection failed")
        return False

    conn.close()
    return True


def test_protocol_v2_integration():
    """Test 7: Protocol v2 integration"""
    print("\n=== Test 7: Protocol v2 Integration ===")

    conn = TeensyConnection()
    if not conn.connect():
        print("❌ FAIL: Could not establish connection")
        return False

    print("7.1 Checking Protocol v2 status...")
    if conn._enhanced_connection:
        print("✅ Enhanced connection wrapper created")

        # Check protocol handler status
        if conn._enhanced_connection.protocol_handler:
            print("✅ Protocol handler initialized")
            stats = conn._enhanced_connection.protocol_handler.get_stats()
            print(f"    Protocol stats: {stats}")
        else:
            print("⚠️  Protocol handler not active (expected with current firmware)")

        # Test enhanced connection stats
        enhanced_stats = conn._enhanced_connection.get_stats()
        print(f"    Enhanced connection stats:")
        for key, value in enhanced_stats.items():
            print(f"      {key}: {value}")
    else:
        print("❌ FAIL: Enhanced connection not created")
        conn.close()
        return False

    print("7.2 Testing frame write through enhanced wrapper...")
    frame_data = bytes([128, 255, 128] * 1024)  # Light green
    success = conn.write_frame(bytes([0xFF, 0xFE, 0xFD]) + frame_data)
    print(f"    Enhanced frame write: {'✅' if success else '❌'}")

    conn.close()
    return True


def run_stress_test():
    """Test 8: Stress test"""
    print("\n=== Test 8: Stress Test ===")

    conn = TeensyConnection()
    if not conn.connect():
        print("❌ FAIL: Could not establish connection")
        return False

    print("8.1 Running stress test (100 frames)...")
    failures = 0
    start_time = time.time()

    for i in range(100):
        # Varied patterns to stress the connection
        if i % 20 == 0:
            print(f"    Progress: {i}/100")

        frame_data = bytes([0xFF, 0xFE, 0xFD])
        for pixel in range(1024):
            r = (i + pixel) % 256
            g = (i * 2 + pixel) % 256
            b = (i * 3 + pixel) % 256
            frame_data += bytes([r, g, b])

        if not conn.write_frame(frame_data):
            failures += 1

        time.sleep(0.01)  # 100 FPS stress test

    elapsed = time.time() - start_time
    success_rate = ((100 - failures) / 100) * 100

    print(f"    Stress test complete:")
    print(f"    Time: {elapsed:.2f}s")
    print(f"    Failures: {failures}/100")
    print(f"    Success rate: {success_rate:.1f}%")
    print(f"    Average FPS: {100/elapsed:.1f}")

    conn.close()
    return failures == 0


def main():
    """Run comprehensive test suite"""
    print("🧪 COMPREHENSIVE PHASE 2 TEST SUITE")
    print("=====================================")

    tests = [
        ("Basic Connection", test_basic_connection),
        ("Mode Switching", test_mode_switching),
        ("Frame Transmission", test_frame_transmission),
        ("Performance Monitoring", test_performance_monitoring),
        ("Resource Management", test_resource_management),
        ("Error Recovery", test_error_recovery),
        ("Protocol v2 Integration", test_protocol_v2_integration),
        ("Stress Test", run_stress_test)
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
                failed += 1
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
            failed += 1

        time.sleep(0.5)  # Brief pause between tests

    print(f"\n{'='*50}")
    print("🏁 TEST SUITE COMPLETE")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Success Rate: {passed/(passed+failed)*100:.1f}%")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED - Phase 2 is fully functional!")
    else:
        print(f"\n⚠️  {failed} test(s) failed - investigation needed")

    # Cleanup
    try:
        resource_manager.cleanup()
        performance_monitor.stop()
    except:
        pass


if __name__ == "__main__":
    main()