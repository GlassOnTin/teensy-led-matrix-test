#!/usr/bin/env python3
"""
Aircraft data fetcher for ADSB sources (tar1090/adsb.fi)
"""

import requests
import math
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Aircraft:
    hex: str
    callsign: Optional[str] = None
    registration: Optional[str] = None
    aircraft_type: Optional[str] = None
    altitude: Optional[int] = None
    ground_speed: Optional[float] = None
    track: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    distance_nm: Optional[float] = None
    distance_km: Optional[float] = None
    squawk: Optional[str] = None
    category: Optional[str] = None
    seen: Optional[float] = None

    def __str__(self):
        parts = []
        if self.callsign:
            parts.append(self.callsign.strip())
        else:
            parts.append(self.hex.upper())

        if self.distance_nm is not None:
            parts.append(f"{self.distance_nm:.1f}nm")

        if self.altitude is not None:
            parts.append(f"{self.altitude}ft")

        if self.ground_speed is not None:
            parts.append(f"{int(self.ground_speed)}kt")

        return " ".join(parts)


class AircraftDataSource:
    def __init__(self, source_url: str, observer_lat: float, observer_lon: float):
        self.source_url = source_url
        self.observer_lat = observer_lat
        self.observer_lon = observer_lon

    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
        R_nm = 3440.065
        R_km = 6371.0

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * \
            math.sin(delta_lon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        return R_nm * c, R_km * c

    def fetch_aircraft(self, max_distance_nm: Optional[float] = None,
                       min_altitude: Optional[int] = None) -> List[Aircraft]:
        try:
            response = requests.get(self.source_url, timeout=5)
            response.raise_for_status()
            data = response.json()

            aircraft_list = []

            for ac_data in data.get('aircraft', []):
                if 'lat' not in ac_data or 'lon' not in ac_data:
                    continue

                lat = ac_data['lat']
                lon = ac_data['lon']

                dist_nm, dist_km = self.haversine_distance(
                    self.observer_lat, self.observer_lon, lat, lon
                )

                if max_distance_nm and dist_nm > max_distance_nm:
                    continue

                altitude = ac_data.get('alt_baro')
                if min_altitude and (altitude is None or altitude < min_altitude):
                    continue

                flight = ac_data.get('flight', '').strip()

                aircraft = Aircraft(
                    hex=ac_data['hex'],
                    callsign=flight if flight else None,
                    altitude=altitude,
                    ground_speed=ac_data.get('gs'),
                    track=ac_data.get('track'),
                    lat=lat,
                    lon=lon,
                    distance_nm=dist_nm,
                    distance_km=dist_km,
                    squawk=ac_data.get('squawk'),
                    category=ac_data.get('category'),
                    seen=ac_data.get('seen')
                )

                aircraft_list.append(aircraft)

            aircraft_list.sort(key=lambda x: x.distance_nm if x.distance_nm else float('inf'))

            return aircraft_list

        except Exception as e:
            print(f"Error fetching aircraft data: {e}")
            return []


if __name__ == "__main__":
    source = AircraftDataSource(
        source_url="http://airspy.local/tar1090/data/aircraft.json",
        observer_lat=52.2,
        observer_lon=-4.5
    )

    aircraft = source.fetch_aircraft(max_distance_nm=50, min_altitude=1000)

    print(f"Found {len(aircraft)} aircraft:")
    for i, ac in enumerate(aircraft[:10], 1):
        print(f"{i}. {ac}")