#!/usr/bin/env python3
"""
REST API server for LED Matrix control.
Provides family-friendly interface for text display and device control.
"""

import asyncio
import time
import os
import sys
import signal
import socket
from typing import Dict, Any, Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
import uvicorn

try:
    from .config_manager import config_manager
    from .matrix_state import matrix_state, MatrixMode, TextState
    from .text_scroller import TextScroller
    from .serial_connection import TeensyConnection
except ImportError:
    # Handle direct execution
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from config_manager import config_manager
    from matrix_state import matrix_state, MatrixMode, TextState
    from text_scroller import TextScroller
    from serial_connection import TeensyConnection


# Pydantic models for API requests/responses
class TextRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=200)
    color: str = Field(default="white", pattern="^(red|green|blue|yellow|cyan|magenta|white|rainbow|orange|purple|pink)$")
    effect: str = Field(default="scroll", pattern="^(scroll|fade|bounce|typewriter|rainbow|pulse|static)$")
    font: str = Field(default="medium", pattern="^(small|medium|large)$")
    duration: float = Field(default=0, ge=0, le=300)  # 0 = indefinite, max 5 minutes
    position: str = Field(default="center", pattern="^(left|center|right)$")


class PresetRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    message: str = Field(..., min_length=1, max_length=200)
    color: str = "white"
    effect: str = "scroll"
    font: str = "medium"


class PowerRequest(BaseModel):
    state: bool


class BrightnessRequest(BaseModel):
    level: int = Field(..., ge=0, le=255)


class ModeRequest(BaseModel):
    mode: str = Field(..., pattern="^(off|effects|text|streaming)$")


class EffectRequest(BaseModel):
    effect: str = Field(..., min_length=1, max_length=50)
    duration: float = Field(default=0, ge=0, le=3600)  # Max 1 hour


class StatusResponse(BaseModel):
    power: bool
    brightness: int
    mode: str
    active_effect: str
    text_state: Dict[str, Any]
    frame_stats: Dict[str, Any]
    connections: int
    uptime: float


class SingletonLock:
    """Ensure only one API server instance can run at a time."""

    def __init__(self, port: int = 8080):
        self.port = port
        self.lock_file = Path(__file__).parent.parent / "state" / f"api_server_{port}.pid"
        self.lock_file.parent.mkdir(exist_ok=True)
        self._acquired = False

    def acquire(self) -> bool:
        """Acquire singleton lock. Returns True if successful."""
        # First check if port is already in use
        if self._is_port_in_use():
            existing_pid = self._get_existing_pid()
            if existing_pid:
                print(f"❌ API server already running on port {self.port} (PID: {existing_pid})")
                print(f"   Use 'kill {existing_pid}' to stop it, or choose a different port")
            else:
                print(f"❌ Port {self.port} is already in use by another process")
            return False

        # Check PID file
        if self.lock_file.exists():
            try:
                with open(self.lock_file, 'r') as f:
                    existing_pid = int(f.read().strip())

                # Check if process is still running
                if self._is_process_running(existing_pid):
                    print(f"❌ API server already running (PID: {existing_pid})")
                    print(f"   Use 'kill {existing_pid}' to stop it")
                    return False
                else:
                    # Stale PID file, remove it
                    self.lock_file.unlink()
                    print(f"🧹 Removed stale PID file")
            except (ValueError, IOError):
                # Invalid PID file, remove it
                self.lock_file.unlink()
                print(f"🧹 Removed invalid PID file")

        # Create new PID file
        try:
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            self._acquired = True

            # Setup cleanup on exit
            signal.signal(signal.SIGTERM, self._cleanup_handler)
            signal.signal(signal.SIGINT, self._cleanup_handler)

            return True
        except IOError as e:
            print(f"❌ Failed to create PID file: {e}")
            return False

    def release(self):
        """Release the singleton lock."""
        if self._acquired and self.lock_file.exists():
            try:
                self.lock_file.unlink()
                self._acquired = False
                print("🔓 Released singleton lock")
            except IOError:
                pass

    def _is_port_in_use(self) -> bool:
        """Check if the port is already in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', self.port))
            return result == 0

    def _get_existing_pid(self) -> Optional[int]:
        """Get PID from existing lock file."""
        if self.lock_file.exists():
            try:
                with open(self.lock_file, 'r') as f:
                    return int(f.read().strip())
            except (ValueError, IOError):
                pass
        return None

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is running."""
        try:
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
            return True
        except (OSError, ProcessLookupError):
            return False

    def _cleanup_handler(self, signum, frame):
        """Signal handler for clean shutdown."""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.release()
        sys.exit(0)


class LEDMatrixAPI:
    """Main API class for LED Matrix control."""

    def __init__(self):
        self.app = FastAPI(
            title="LED Matrix Control API",
            description="Family-friendly API for controlling LED Matrix display",
            version="1.0.0"
        )
        self.teensy_connection: Optional[TeensyConnection] = None
        self.text_scroller: Optional[TextScroller] = None
        self.websocket_connections: List[WebSocket] = []
        self.start_time = time.time()

        self._setup_routes()
        self._setup_websockets()
        self._setup_event_handlers()

    def _setup_routes(self):
        """Setup API routes."""

        @self.app.get("/", response_class=RedirectResponse)
        async def root():
            return "/web/"

        @self.app.get("/api/status", response_model=StatusResponse)
        async def get_status():
            """Get current device status."""
            state = matrix_state.get_state_dict()
            return StatusResponse(
                power=state['power'],
                brightness=state['brightness'],
                mode=state['mode'],
                active_effect=state['active_effect'],
                text_state=state['text_state'],
                frame_stats=state['frame_stats'],
                connections=len(matrix_state.get_connections()),
                uptime=time.time() - self.start_time
            )

        @self.app.post("/api/power")
        async def set_power(request: PowerRequest):
            """Control device power state."""
            matrix_state.power = request.state
            if request.state:
                await self._ensure_connection()
                if matrix_state.mode == MatrixMode.TEXT and matrix_state.text_state.message:
                    await self._display_text()
            else:
                await self._disconnect()
            return {"status": "success", "power": request.state}

        @self.app.post("/api/brightness")
        async def set_brightness(request: BrightnessRequest):
            """Set display brightness."""
            matrix_state.brightness = request.level
            if self.teensy_connection:
                self.teensy_connection.brightness = request.level / 255.0
            return {"status": "success", "brightness": request.level}

        @self.app.post("/api/mode")
        async def set_mode(request: ModeRequest):
            """Set operating mode."""
            old_mode = matrix_state.mode
            matrix_state.mode = MatrixMode(request.mode)

            await self._ensure_connection()

            if matrix_state.mode == MatrixMode.EFFECTS:
                await self._switch_to_effects()
            elif matrix_state.mode == MatrixMode.TEXT:
                await self._display_text()
            elif matrix_state.mode == MatrixMode.OFF:
                await self._disconnect()

            return {"status": "success", "mode": request.mode, "previous": old_mode.value}

        @self.app.post("/api/text")
        async def display_text(request: TextRequest):
            """Display text message with effects."""
            # Update state
            matrix_state.update_text(
                message=request.message,
                color=request.color,
                effect=request.effect,
                font=request.font,
                duration=request.duration,
                position=request.position
            )
            matrix_state.mode = MatrixMode.TEXT

            await self._ensure_connection()
            await self._display_text()

            return {
                "status": "success",
                "text_state": matrix_state.text_state.__dict__
            }

        @self.app.get("/api/text/presets")
        async def get_presets():
            """Get available text presets."""
            return config_manager.get_text_presets()

        @self.app.post("/api/text/presets")
        async def create_preset(request: PresetRequest):
            """Create new text preset."""
            presets = config_manager.get_text_presets()
            presets[request.name] = {
                "message": request.message,
                "color": request.color,
                "effect": request.effect,
                "font": request.font
            }

            # Save to config
            config_manager.update_config("presets", f"text_presets.{request.name}", presets[request.name])

            return {"status": "success", "preset": request.name}

        @self.app.post("/api/text/presets/{preset_name}")
        async def activate_preset(preset_name: str):
            """Activate a text preset."""
            preset = config_manager.get_preset_by_name(preset_name)
            if not preset:
                raise HTTPException(status_code=404, detail="Preset not found")

            # Apply preset
            matrix_state.update_text(**preset)
            matrix_state.mode = MatrixMode.TEXT

            await self._ensure_connection()
            await self._display_text()

            return {"status": "success", "preset": preset_name, "text_state": preset}

        @self.app.get("/api/effects")
        async def get_effects():
            """Get available effects."""
            return {
                "built_in": ["rainbow", "fire", "plasma", "starfield", "matrix_rain"],
                "text_effects": list(config_manager.get_text_effects().keys())
            }

        @self.app.post("/api/effects/start")
        async def start_effect(request: EffectRequest):
            """Start built-in effect."""
            matrix_state.active_effect = request.effect
            matrix_state.mode = MatrixMode.EFFECTS

            await self._ensure_connection()
            await self._switch_to_effects()

            return {"status": "success", "effect": request.effect}

        @self.app.post("/api/effects/stop")
        async def stop_effects():
            """Stop current effects."""
            matrix_state.mode = MatrixMode.OFF
            await self._disconnect()
            return {"status": "success"}

        @self.app.get("/api/fonts")
        async def get_fonts():
            """Get available fonts."""
            return config_manager.get_display().get('fonts', {
                "small": {"name": "5x8_basic", "width": 5, "height": 8},
                "medium": {"name": "8x8_bold", "width": 8, "height": 8},
                "large": {"name": "8x16_display", "width": 8, "height": 16}
            })

    def _setup_websockets(self):
        """Setup WebSocket endpoints for real-time updates."""

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.websocket_connections.append(websocket)

            try:
                # Send initial status
                status = await self.app.routes[1].endpoint()  # get_status endpoint
                await websocket.send_json({"type": "status", "data": status.dict()})

                # Keep connection alive and handle client messages
                while True:
                    try:
                        data = await websocket.receive_json()
                        # Handle client requests if needed
                    except WebSocketDisconnect:
                        break
            except Exception as e:
                print(f"WebSocket error: {e}")
            finally:
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)

    def _setup_event_handlers(self):
        """Setup event handlers for state changes."""

        async def broadcast_update(event_type: str, data: Any):
            """Broadcast state changes to WebSocket clients."""
            if self.websocket_connections:
                message = {"type": event_type, "data": data}
                disconnected = []

                for websocket in self.websocket_connections:
                    try:
                        await websocket.send_json(message)
                    except:
                        disconnected.append(websocket)

                # Remove disconnected clients
                for ws in disconnected:
                    self.websocket_connections.remove(ws)

        # Register event handlers
        matrix_state.on('power_changed', lambda et, data: asyncio.create_task(broadcast_update(et, data)))
        matrix_state.on('brightness_changed', lambda et, data: asyncio.create_task(broadcast_update(et, data)))
        matrix_state.on('mode_changed', lambda et, data: asyncio.create_task(broadcast_update(et, data)))
        matrix_state.on('text_changed', lambda et, data: asyncio.create_task(broadcast_update(et, data)))

    async def _ensure_connection(self):
        """Ensure Teensy connection is established."""
        if not matrix_state.power:
            return

        if not self.teensy_connection:
            self.teensy_connection = TeensyConnection()

        if not self.teensy_connection.ser or not self.teensy_connection.ser.is_open:
            # Run blocking connection in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self.teensy_connection.connect, 's')
            if not success:
                raise HTTPException(status_code=503, detail="Unable to connect to LED matrix")

    async def _disconnect(self):
        """Disconnect from Teensy."""
        if self.teensy_connection:
            self.teensy_connection.close()
            self.teensy_connection = None

    async def _switch_to_effects(self):
        """Switch to built-in effects mode."""
        if self.teensy_connection:
            self.teensy_connection.ser.write(b'e')
            self.teensy_connection.ser.flush()

    async def _display_text(self):
        """Display current text state with actual text rendering."""
        text_state = matrix_state.text_state

        if not self.teensy_connection:
            return

        # Stop any existing text task
        if hasattr(self, '_text_task') and self._text_task:
            self._text_task.cancel()
            try:
                await self._text_task
            except asyncio.CancelledError:
                pass

        # Wait a moment for clean transition
        await asyncio.sleep(0.1)

        # Create and start new text display task
        self._text_task = asyncio.create_task(self._run_text_display(text_state))

    async def _run_text_display(self, text_state: TextState):
        """Run text display in background task."""
        try:
            # Ensure we have a valid connection
            if not self.teensy_connection or not self.teensy_connection.ser or not self.teensy_connection.ser.is_open:
                await self._ensure_connection()
                if not self.teensy_connection:
                    print("Failed to establish connection for text display")
                    return

            # Switch to streaming mode
            self.teensy_connection.ser.write(b's')
            self.teensy_connection.ser.flush()
            await asyncio.sleep(0.1)  # Give firmware time to switch

            # Create text scroller with proper configuration and reset state
            scroller = TextScroller()
            scroller.color_mode = text_state.color
            scroller.scroll_speed = 30  # Default speed

            # Reset scroll position for clean start
            scroller.scroll_position = scroller.width  # Start off-screen right
            scroller.color_phase = 0  # Reset color animation phase

            # Get text to display
            text = text_state.message or "Hello World!"

            # Main text rendering loop (adapted from run_text_scroller)
            start_time = time.time()
            last_frame_time = start_time

            while True:
                current_time = time.time()
                delta_time = current_time - last_frame_time

                # Update scroll position and render text
                text_width = scroller.render_text(text)
                scroller.update_scroll(delta_time, text_width)

                # Add effects if specified
                if text_state.effect and text_state.effect != 'none':
                    scroller.add_effects(text_state.effect)

                # Convert frame buffer to hardware format
                frame_bytes = bytes([0xFF, 0xFE, 0xFD]) + scroller.frame_buffer.flatten().tobytes()

                # Send to hardware
                if not self.teensy_connection.write_frame(frame_bytes, apply_brightness=False):
                    print("Text display write error")
                    break

                last_frame_time = current_time

                # Check duration limit
                if text_state.duration and (current_time - start_time) >= text_state.duration:
                    break

                # Frame rate control (30 FPS)
                await asyncio.sleep(1/30)

        except asyncio.CancelledError:
            # Clean shutdown - switch back to effects
            if self.teensy_connection:
                self.teensy_connection.ser.write(b'e')
                self.teensy_connection.ser.flush()
            raise
        except Exception as e:
            print(f"Text display error: {e}")
            # Switch back to effects on error (if connection still valid)
            try:
                if self.teensy_connection and self.teensy_connection.ser and self.teensy_connection.ser.is_open:
                    self.teensy_connection.ser.write(b'e')
                    self.teensy_connection.ser.flush()
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")

    def setup_static_files(self, static_dir: str):
        """Setup static file serving for web interface."""
        if Path(static_dir).exists():
            self.app.mount("/web", StaticFiles(directory=static_dir, html=True), name="web")


def create_app() -> FastAPI:
    """Factory function to create FastAPI app."""
    api = LEDMatrixAPI()

    # Setup static files if web interface exists
    web_dir = Path(__file__).parent.parent / "web_interface" / "static"
    if web_dir.exists():
        api.setup_static_files(str(web_dir))

    return api.app


def run_server(host: str = "0.0.0.0", port: int = 8080, debug: bool = False):
    """Run the API server."""
    # Acquire singleton lock
    singleton_lock = SingletonLock(port)
    if not singleton_lock.acquire():
        sys.exit(1)

    try:
        app = create_app()

        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="debug" if debug else "info",
            reload=debug
        )

        server = uvicorn.Server(config)
        print(f"🔒 Acquired singleton lock for port {port}")
        print(f"🌐 Starting LED Matrix API server on http://{host}:{port}")
        print(f"📱 Web interface: http://{host}:{port}/web/")
        print(f"📖 API docs: http://{host}:{port}/docs")

        # Save state before starting
        matrix_state.save_persistent()

        try:
            server.run()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down server...")
        finally:
            # Save state on shutdown
            matrix_state.save_persistent()
    finally:
        # Always release the lock
        singleton_lock.release()


if __name__ == "__main__":
    import sys

    # Simple CLI for development
    host = "0.0.0.0"
    port = 8080
    debug = "--debug" in sys.argv

    if "--host" in sys.argv:
        idx = sys.argv.index("--host")
        if idx + 1 < len(sys.argv):
            host = sys.argv[idx + 1]

    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    run_server(host, port, debug)