"""
ADSB Aircraft Ticker Display

A reusable Flask-based web interface that displays aircraft data from
tar1090/adsb.fi sources on a scrolling ticker display optimized for
64x16 LED matrix displays.
"""

from .aircraft_data import Aircraft, AircraftDataSource
from .ticker_renderer import TickerRenderer
from .flask_app import app, init_app

__all__ = ['Aircraft', 'AircraftDataSource', 'TickerRenderer', 'app', 'init_app']