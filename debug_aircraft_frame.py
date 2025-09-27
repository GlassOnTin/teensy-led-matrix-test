#!/usr/bin/env python3
import sys
sys.path.insert(0, 'python_utils/adsb_ticker')
from aircraft_data import AircraftDataSource
from ticker_renderer import TickerRenderer
import numpy as np

source = AircraftDataSource('http://airspy.local/tar1090/data/aircraft.json', 52.2, -4.5)
aircraft = source.fetch_aircraft(max_distance_nm=50, min_altitude=1000)

print(f"Aircraft found: {len(aircraft)}")
if aircraft:
    print(f"First: {aircraft[0]}")

renderer = TickerRenderer(width=64, height=16, font_size=12)

for i in range(3):
    frame = renderer.render_frame(aircraft, scroll_speed=1)
    non_zero = (frame > 0).sum()
    max_val = frame.max()
    print(f"Frame {i}: non_zero={non_zero}, max={max_val}, scroll={renderer.scroll_offset}")

    if non_zero > 0:
        # Show what pixels are lit
        y_coords, x_coords, c_coords = np.where(frame > 0)
        print(f"  First 5 lit pixels: ", end="")
        for j in range(min(5, len(y_coords))):
            print(f"[{y_coords[j]},{x_coords[j]}]={frame[y_coords[j],x_coords[j],c_coords[j]]} ", end="")
        print()