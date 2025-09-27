#!/usr/bin/env python3
"""
Stream aircraft ticker display to Teensy LED matrix
Connects to Flask app's frame stream and sends to serial
"""

import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from serial_connection import TeensyConnection
from adsb_ticker.aircraft_data import AircraftDataSource
from adsb_ticker.ticker_renderer import TickerRenderer


def stream_to_led_matrix(source_url: str, observer_lat: float, observer_lon: float,
                          max_distance_nm: float = 50, min_altitude: int = 1000,
                          scroll_speed: int = 1, update_interval: float = 5.0,
                          brightness: float = 0.375):
    print(f"Aircraft ticker LED matrix streamer")
    print(f"Source: {source_url}")
    print(f"Observer: {observer_lat:.4f}, {observer_lon:.4f}")
    print(f"Max distance: {max_distance_nm}nm, Min altitude: {min_altitude}ft")
    print()

    data_source = AircraftDataSource(
        source_url=source_url,
        observer_lat=observer_lat,
        observer_lon=observer_lon
    )

    renderer = TickerRenderer(width=64, height=16, font_size=6)

    conn = TeensyConnection(brightness=brightness)

    if not conn.connect(mode='s'):
        print("Error: Could not connect to Teensy LED matrix")
        return 1

    print("Connected to LED matrix. Streaming aircraft ticker...")
    print("Press Ctrl+C to stop\n")

    last_update = 0
    frame_count = 0
    start_time = time.time()

    try:
        while True:
            current_time = time.time()

            if current_time - last_update > update_interval:
                aircraft = data_source.fetch_aircraft(
                    max_distance_nm=max_distance_nm,
                    min_altitude=min_altitude
                )

                print(f"\rAircraft: {len(aircraft):3d}  Frames: {frame_count:6d}  "
                      f"FPS: {frame_count / (current_time - start_time):.1f}", end='', flush=True)

                last_update = current_time
            else:
                aircraft = getattr(stream_to_led_matrix, '_aircraft_cache', [])

            stream_to_led_matrix._aircraft_cache = aircraft

            frame_array = renderer.render_frame(aircraft, scroll_speed=scroll_speed)

            frame_data = bytearray([0xFF, 0xFE, 0xFD])

            for y in range(16):
                for x in range(64):
                    r, g, b = frame_array[y, x]
                    frame_data.extend([r, g, b])

            if not conn.write_frame(bytes(frame_data), apply_brightness=True):
                print("\nError writing frame, reconnecting...")
                if not conn.connect(mode='s'):
                    print("Reconnection failed")
                    return 1

            frame_count += 1

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nStopping...")
        elapsed = time.time() - start_time
        print(f"Streamed {frame_count} frames in {elapsed:.1f}s")
        print(f"Average FPS: {frame_count / elapsed:.2f}")

    finally:
        conn.close()

    return 0


def main():
    parser = argparse.ArgumentParser(description='Stream aircraft ticker to LED matrix')
    parser.add_argument('--source', default='http://airspy.local/tar1090/data/aircraft.json',
                        help='Aircraft data source URL')
    parser.add_argument('--lat', type=float, default=52.2,
                        help='Observer latitude')
    parser.add_argument('--lon', type=float, default=-4.5,
                        help='Observer longitude')
    parser.add_argument('--max-distance', type=float, default=50,
                        help='Maximum distance in nautical miles')
    parser.add_argument('--min-altitude', type=int, default=1000,
                        help='Minimum altitude in feet')
    parser.add_argument('--scroll-speed', type=int, default=1,
                        help='Scroll speed (1-10)')
    parser.add_argument('--update-interval', type=float, default=5.0,
                        help='Aircraft data update interval in seconds')
    parser.add_argument('--brightness', type=float, default=0.375,
                        help='LED brightness (0.0-1.0)')

    args = parser.parse_args()

    return stream_to_led_matrix(
        source_url=args.source,
        observer_lat=args.lat,
        observer_lon=args.lon,
        max_distance_nm=args.max_distance,
        min_altitude=args.min_altitude,
        scroll_speed=args.scroll_speed,
        update_interval=args.update_interval,
        brightness=args.brightness
    )


if __name__ == '__main__':
    sys.exit(main())