#!/usr/bin/env python3
"""
Flask web interface for aircraft ticker display
Serves both web preview and image frames for LED matrix streaming
"""

from flask import Flask, render_template, Response, jsonify, request
from PIL import Image
import io
import json
import time
from typing import Optional
from .aircraft_data import AircraftDataSource
from .ticker_renderer import TickerRenderer

app = Flask(__name__)

data_source: Optional[AircraftDataSource] = None
renderer: Optional[TickerRenderer] = None

config = {
    'source_url': 'http://airspy.local/tar1090/data/aircraft.json',
    'observer_lat': 52.2,
    'observer_lon': -4.5,
    'max_distance_nm': 50,
    'min_altitude': 1000,
    'scroll_speed': 1,
    'update_interval': 5.0,
}


def init_app():
    global data_source, renderer

    data_source = AircraftDataSource(
        source_url=config['source_url'],
        observer_lat=config['observer_lat'],
        observer_lon=config['observer_lon']
    )

    renderer = TickerRenderer(width=64, height=16, font_size=6)


@app.route('/')
def index():
    return render_template('ticker.html', config=config)


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    global data_source, renderer

    if request.method == 'POST':
        data = request.json
        config.update(data)

        data_source = AircraftDataSource(
            source_url=config['source_url'],
            observer_lat=config['observer_lat'],
            observer_lon=config['observer_lon']
        )

        return jsonify({'status': 'ok', 'config': config})

    return jsonify(config)


@app.route('/api/aircraft')
def api_aircraft():
    if not data_source:
        return jsonify({'error': 'Not initialized'}), 500

    aircraft = data_source.fetch_aircraft(
        max_distance_nm=config['max_distance_nm'],
        min_altitude=config['min_altitude']
    )

    return jsonify({
        'count': len(aircraft),
        'aircraft': [
            {
                'hex': ac.hex,
                'callsign': ac.callsign,
                'altitude': ac.altitude,
                'ground_speed': ac.ground_speed,
                'distance_nm': ac.distance_nm,
                'track': ac.track,
            }
            for ac in aircraft[:50]
        ]
    })


@app.route('/frame.png')
def frame_png():
    if not data_source or not renderer:
        return "Not initialized", 500

    aircraft = data_source.fetch_aircraft(
        max_distance_nm=config['max_distance_nm'],
        min_altitude=config['min_altitude']
    )

    frame_array = renderer.render_frame(aircraft, scroll_speed=config['scroll_speed'])

    img = Image.fromarray(frame_array.astype('uint8'), 'RGB')

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    return Response(buf, mimetype='image/png')


def generate_stream():
    if not data_source or not renderer:
        return

    last_update = 0

    while True:
        current_time = time.time()

        if current_time - last_update > config['update_interval']:
            aircraft = data_source.fetch_aircraft(
                max_distance_nm=config['max_distance_nm'],
                min_altitude=config['min_altitude']
            )
            last_update = current_time
        else:
            aircraft = getattr(generate_stream, '_aircraft_cache', [])

        generate_stream._aircraft_cache = aircraft

        frame_array = renderer.render_frame(aircraft, scroll_speed=config['scroll_speed'])

        img = Image.fromarray(frame_array.astype('uint8'), 'RGB')

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        frame_data = buf.getvalue()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')

        time.sleep(0.05)


@app.route('/stream.mjpeg')
def stream_mjpeg():
    return Response(generate_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Aircraft ticker web server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5555, help='Port to bind to')
    parser.add_argument('--source', default=config['source_url'], help='Aircraft data source URL')
    parser.add_argument('--lat', type=float, default=config['observer_lat'], help='Observer latitude')
    parser.add_argument('--lon', type=float, default=config['observer_lon'], help='Observer longitude')
    parser.add_argument('--max-distance', type=float, default=config['max_distance_nm'],
                        help='Maximum distance in nautical miles')
    parser.add_argument('--min-altitude', type=int, default=config['min_altitude'],
                        help='Minimum altitude in feet')

    args = parser.parse_args()

    config['source_url'] = args.source
    config['observer_lat'] = args.lat
    config['observer_lon'] = args.lon
    config['max_distance_nm'] = args.max_distance
    config['min_altitude'] = args.min_altitude

    init_app()

    print(f"Aircraft ticker server starting on http://{args.host}:{args.port}")
    print(f"Observer position: {args.lat:.4f}, {args.lon:.4f}")
    print(f"Max distance: {args.max_distance}nm, Min altitude: {args.min_altitude}ft")

    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == '__main__':
    main()