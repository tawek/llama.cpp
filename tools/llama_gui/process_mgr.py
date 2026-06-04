"""
Process manager for llama-server.
Handles launching, stopping, and monitoring the server process.
"""

import subprocess
import threading
import queue
import os
import time
from typing import Optional, Callable


class ServerProcess:
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._stdout_queue: queue.Queue = queue.Queue()
        self._stderr_queue: queue.Queue = queue.Queue()
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._running = False
        self._callbacks = {
            'stdout': [],
            'stderr': [],
            'stopped': []
        }

    def on_stdout(self, callback: Callable):
        self._callbacks['stdout'].append(callback)

    def on_stderr(self, callback: Callable):
        self._callbacks['stderr'].append(callback)

    def on_stopped(self, callback: Callable):
        self._callbacks['stopped'].append(callback)

    def start(self, command: str, cwd: Optional[str] = None,
              env: Optional[dict] = None):
        """Start the server process with the given command string."""
        if self._running:
            self.stop()

        cmd_parts = self._parse_command(command)

        try:
            self._process = subprocess.Popen(
                cmd_parts,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
        except (FileNotFoundError, OSError) as e:
            self._process = None
            self._running = False
            for cb in self._callbacks['stopped']:
                try:
                    cb()
                except Exception:
                    pass
            return False

        self._running = True
        self._stdout_thread = threading.Thread(
            target=self._read_stream,
            args=(self._process.stdout,),
            daemon=True
        )
        self._stdout_thread.start()

        return True

    def stop(self):
        """Stop the server process."""
        if not self._running or not self._process:
            return False

        try:
            if os.name == 'nt':
                self._process.terminate()
            else:
                self._process.terminate()

            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        except Exception:
            try:
                self._process.kill()
            except Exception:
                pass

        self._running = False
        self._process = None

        for cb in self._callbacks['stopped']:
            try:
                cb()
            except Exception:
                pass

        return True

    def restart(self, command: str, cwd: Optional[str] = None,
                env: Optional[dict] = None):
        """Restart the server with a new command."""
        self.stop()
        time.sleep(0.5)
        return self.start(command, cwd, env)

    @property
    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    @property
    def returncode(self) -> Optional[int]:
        if self._process is None:
            return None
        return self._process.returncode

    @property
    def pid(self) -> Optional[int]:
        if self._process is None:
            return None
        return self._process.pid

    def get_output(self, block: bool = True, timeout: Optional[float] = None) -> Optional[str]:
        """Get next line from output queue."""
        try:
            return self._stdout_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def _read_stream(self, stream):
        """Read from stream and put lines into queue."""
        try:
            for line in stream:
                if not self._running:
                    break
                self._stdout_queue.put(line.rstrip('\n'))
                for cb in self._callbacks['stdout']:
                    try:
                        cb(line.rstrip('\n'))
                    except Exception:
                        pass
        except ValueError:
            pass

        self._running = False
        for cb in self._callbacks['stopped']:
            try:
                cb()
            except Exception:
                pass

    def _parse_command(self, command: str) -> list:
        """Parse command string into list of arguments."""
        import shlex
        try:
            return shlex.split(command)
        except ValueError:
            # Fallback: simple split
            return command.split()
