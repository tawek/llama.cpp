"""
Server identity management for detachable servers.
Maintains identity files at ~/.llama-gui/servers/<pid>.json
so that a detached or externally-run server can be discovered
and re-attached on a subsequent GUI session.
"""

import os
import json
import time
from typing import Optional


class ServerIdentity:
    """Identity metadata for a running llama-server process."""

    def __init__(
        self,
        pid: int,
        host: str = '127.0.0.1',
        port: int = 8080,
        log_path: str = '',
        command: str = '',
        profile: str = '',
    ):
        self.pid = pid
        self.host = host
        self.port = port
        self.log_path = log_path
        self.command = command
        self.profile = profile
        self.started_at: float = time.time()

    def save(self):
        path = self._path_for(self.pid)
        os.makedirs(self._dir(), exist_ok=True)
        data = {
            'pid': self.pid,
            'host': self.host,
            'port': self.port,
            'log_path': self.log_path,
            'command': self.command,
            'profile': self.profile,
            'started_at': self.started_at,
        }
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)

    def remove(self):
        path = self._path_for(self.pid)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    @classmethod
    def _dir(cls) -> str:
        return os.path.expanduser('~/.llama-gui/servers')

    @classmethod
    def _path_for(cls, pid: int) -> str:
        return os.path.join(cls._dir(), f'{pid}.json')

    @classmethod
    def is_alive(cls, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    @classmethod
    def load(cls, pid: int) -> Optional['ServerIdentity']:
        path = cls._path_for(pid)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            identity = cls(
                pid=data['pid'],
                host=data.get('host', '127.0.0.1'),
                port=data.get('port', 8080),
                log_path=data.get('log_path', ''),
                command=data.get('command', ''),
                profile=data.get('profile', ''),
            )
            identity.started_at = data.get('started_at', 0)
            return identity
        except (json.JSONDecodeError, OSError, KeyError):
            return None

    @classmethod
    def discover(cls) -> list['ServerIdentity']:
        identities = []
        sdir = cls._dir()
        if not os.path.isdir(sdir):
            return identities
        for fname in os.listdir(sdir):
            if not fname.endswith('.json'):
                continue
            pid_str = fname[:-5]
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            if cls.is_alive(pid):
                identity = cls.load(pid)
                if identity:
                    identities.append(identity)
            else:
                try:
                    os.remove(os.path.join(sdir, fname))
                except OSError:
                    pass
        return identities


class LogFileTailer:
    """Tails a log file, reading new lines since the last read.

    Starts at the end of the file (only new lines) unless
    ``start_from_end`` is False, in which case it reads all
    existing content first.
    """

    def __init__(self, path: str, start_from_end: bool = True):
        self._path = path
        self._file: Optional[open] = None  # type: ignore[assignment]

    def open(self, start_from_end: bool = True):
        if self._file is not None:
            self.close()
        self._file = open(self._path, 'r')
        if start_from_end:
            self._file.seek(0, 2)

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None

    def read_new_lines(self) -> list[str]:
        if self._file is None:
            return []
        try:
            lines = self._file.readlines()
            return [line.rstrip('\n\r') for line in lines if line.strip()]
        except (OSError, ValueError):
            return []

    def get_path(self) -> str:
        return self._path

    def read_tail(self, max_bytes: int = 100000, max_lines: int = 1000) -> list[str]:
        """Read up to ``max_lines`` lines from the tail of the file.

        Useful for loading recent history when reattaching.
        """
        try:
            size = os.path.getsize(self._path)
            if size == 0:
                return []
            seek_pos = max(0, size - max_bytes)
            with open(self._path, 'r') as f:
                f.seek(seek_pos)
                if seek_pos > 0:
                    f.readline()
                lines = f.readlines()
            tail = [line.rstrip('\n\r') for line in lines if line.strip()]
            if len(tail) > max_lines:
                tail = tail[-max_lines:]
            return tail
        except OSError:
            return []

    def __del__(self):
        self.close()
