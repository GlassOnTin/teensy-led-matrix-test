#!/usr/bin/env python3
"""
Aircraft ticker display renderer for LED matrix (64x16)
Uses horizontal scrolling text with minimal 5x8 font
"""

from PIL import Image, ImageDraw, ImageFont
import numpy as np
from typing import List, Tuple, Optional

try:
    from .aircraft_data import Aircraft
except ImportError:
    from aircraft_data import Aircraft


class TickerRenderer:
    def __init__(self, width: int = 64, height: int = 16, font_size: int = 6):
        self.width = width
        self.height = height
        self.font_size = font_size
        self.scroll_offset = 0
        self.text_cache = None
        self.text_width = 0
        self.page_index = 0
        self.last_page_change = 0
        self.page_duration = 10.0  # seconds per page

    def format_aircraft_page(self, aircraft_list: List[Aircraft], page_index: int, per_page: int = 3) -> List[str]:
        if not aircraft_list:
            return ["No aircraft"]

        start_idx = page_index * per_page
        end_idx = start_idx + per_page
        page_aircraft = aircraft_list[start_idx:end_idx]

        if not page_aircraft:
            return ["No more aircraft"]

        lines = []
        for i, ac in enumerate(page_aircraft, start_idx + 1):
            callsign = (ac.callsign or ac.hex.upper())[:7]
            dist = f"{ac.distance_nm:.0f}nm" if ac.distance_nm else "?nm"
            alt = f"{ac.altitude//100}k" if ac.altitude else "?k"

            lines.append(f"{i}:{callsign} {dist} {alt}ft")

        return lines

    def render_multiline_to_image(self, lines: List[str], color: Tuple[int, int, int] = (255, 255, 0)) -> Image.Image:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", self.font_size)
        except:
            font = ImageFont.load_default()

        img = Image.new('RGB', (self.width, self.height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        line_height = self.height // 3

        for i, line in enumerate(lines[:3]):
            y_pos = i * line_height
            draw.text((1, y_pos), line, font=font, fill=color)

        return img

    def render_frame(self, aircraft_list: List[Aircraft], scroll_speed: int = 2) -> np.ndarray:
        import time

        current_time = time.time()

        if current_time - self.last_page_change > self.page_duration:
            self.page_index += 1
            if not aircraft_list or self.page_index * 3 >= len(aircraft_list):
                self.page_index = 0
            self.last_page_change = current_time

        lines = self.format_aircraft_page(aircraft_list, self.page_index, per_page=3)
        frame = self.render_multiline_to_image(lines)

        frame_array = np.array(frame)
        frame_array = np.flipud(frame_array)

        return frame_array

    def reset_scroll(self):
        self.scroll_offset = 0


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))

    from aircraft_data import Aircraft

    test_aircraft = [
        Aircraft(hex="ABC123", callsign="TEST1", altitude=5000, ground_speed=250, distance_nm=5.2),
        Aircraft(hex="DEF456", callsign="TEST2", altitude=12000, ground_speed=380, distance_nm=15.7),
        Aircraft(hex="GHI789", callsign="TEST3", altitude=35000, ground_speed=450, distance_nm=42.3),
    ]

    renderer = TickerRenderer()

    for i in range(10):
        frame = renderer.render_frame(test_aircraft)
        if i % 5 == 0:
            print(f"Frame {i}: shape={frame.shape}, scroll={renderer.scroll_offset}")

    print("Test render complete")