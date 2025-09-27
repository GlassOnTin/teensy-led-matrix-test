#!/usr/bin/env python3
"""
Device locking mechanism to prevent multiple processes from accessing the same serial device.
Uses file-based locking for cross-process synchronization.
"""

import fcntl
import os
import time
import tempfile
from pathlib import Path
from typing import Optional


class DeviceLock:
    """File-based exclusive lock for serial devices."""

    def __init__(self, device_path: str, timeout: float = 5.0):
        """
        Initialize device lock.

        Args:
            device_path: Path to serial device (e.g., '/dev/ttyACM0')
            timeout: Maximum time to wait for lock acquisition
        """
        self.device_path = device_path
        self.timeout = timeout
        self.lock_file: Optional[int] = None
        self.lock_path = self._get_lock_path()

    def _get_lock_path(self) -> Path:
        """Generate lock file path based on device path."""
        # Convert device path to safe filename
        safe_name = self.device_path.replace('/', '_').replace('\\', '_')
        lock_dir = Path(tempfile.gettempdir()) / "led_matrix_locks"
        lock_dir.mkdir(exist_ok=True)
        return lock_dir / f"{safe_name}.lock"

    def acquire(self) -> bool:
        """
        Acquire exclusive lock on device.

        Returns:
            True if lock acquired successfully, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            try:
                # Open lock file
                self.lock_file = os.open(str(self.lock_path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC)

                # Try to acquire exclusive lock (non-blocking)
                fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Write process info to lock file
                lock_info = f"PID: {os.getpid()}\nDevice: {self.device_path}\nTime: {time.time()}\n"
                os.write(self.lock_file, lock_info.encode())
                os.fsync(self.lock_file)

                return True

            except (OSError, IOError) as e:
                # Lock is held by another process
                if self.lock_file:
                    try:
                        os.close(self.lock_file)
                    except:
                        pass
                    self.lock_file = None

                # Wait briefly before retrying
                time.sleep(0.1)

        return False

    def release(self):
        """Release the device lock."""
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
                os.close(self.lock_file)
                self.lock_file = None

                # Clean up lock file if possible
                try:
                    self.lock_path.unlink()
                except:
                    pass
            except:
                pass

    def is_locked(self) -> bool:
        """Check if device is currently locked."""
        try:
            test_fd = os.open(str(self.lock_path), os.O_CREAT | os.O_WRONLY)
            fcntl.flock(test_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(test_fd, fcntl.LOCK_UN)
            os.close(test_fd)
            return False
        except (OSError, IOError):
            return True

    def get_lock_info(self) -> Optional[str]:
        """Get information about current lock holder."""
        if not self.lock_path.exists():
            return None

        try:
            with open(self.lock_path, 'r') as f:
                return f.read().strip()
        except:
            return None

    def __enter__(self):
        """Context manager entry."""
        if not self.acquire():
            lock_info = self.get_lock_info()
            if lock_info:
                raise RuntimeError(f"Could not acquire device lock for {self.device_path}. "
                                 f"Lock held by:\n{lock_info}")
            else:
                raise RuntimeError(f"Could not acquire device lock for {self.device_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()


def cleanup_stale_locks(max_age_seconds: float = 300):
    """Clean up lock files older than max_age_seconds."""
    lock_dir = Path(tempfile.gettempdir()) / "led_matrix_locks"
    if not lock_dir.exists():
        return

    current_time = time.time()
    for lock_file in lock_dir.glob("*.lock"):
        try:
            # Check if lock file is old
            if current_time - lock_file.stat().st_mtime > max_age_seconds:
                # Try to acquire lock to see if it's stale
                lock = DeviceLock("dummy", timeout=0.1)
                lock.lock_path = lock_file
                if lock.acquire():
                    lock.release()  # Will clean up the file
        except:
            pass


if __name__ == "__main__":
    # Test the locking mechanism
    import sys

    if len(sys.argv) != 2:
        print("Usage: python device_lock.py <device_path>")
        sys.exit(1)

    device = sys.argv[1]
    print(f"Testing lock for device: {device}")

    try:
        with DeviceLock(device, timeout=2.0) as lock:
            print("✅ Lock acquired successfully")
            print("Press Enter to release lock...")
            input()
            print("🔓 Releasing lock")
    except RuntimeError as e:
        print(f"❌ Failed to acquire lock: {e}")
        sys.exit(1)