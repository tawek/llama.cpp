"""
System monitor using psutil and nvidia-smi.
Tracks CPU, memory, swap, and GPU stats.
"""

import subprocess
import threading
import time
from typing import Optional


class SystemMonitor:
    def __init__(self):
        self._cpu_percent = 0.0
        self._memory = {'total': 0, 'used': 0, 'percent': 0.0}
        self._swap = {'total': 0, 'used': 0, 'percent': 0.0}
        self._gpu = {'total': 0, 'used': 0, 'percent': 0.0, 'temp': 0, 'error': True}
        self._last_cpu_call = 0.0
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, interval: float = 1.0):
        """Start periodic monitoring."""
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True)
        self._thread.start()

    def stop(self):
        """Stop monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    @property
    def cpu_percent(self) -> float:
        return self._cpu_percent

    @property
    def memory(self) -> dict:
        return dict(self._memory)

    @property
    def swap(self) -> dict:
        return dict(self._swap)

    @property
    def gpu(self) -> dict:
        return dict(self._gpu)

    def get_snapshot(self) -> dict:
        """Get current snapshot of all metrics."""
        self._update_cpu()
        self._update_memory()
        self._update_swap()
        self._update_gpu()
        return {
            'cpu': self._cpu_percent,
            'memory': dict(self._memory),
            'swap': dict(self._swap),
            'gpu': dict(self._gpu)
        }

    def _monitor_loop(self, interval: float):
        while self._running:
            self._update_cpu()
            self._update_memory()
            self._update_swap()
            self._update_gpu()
            time.sleep(interval)

    def _update_cpu(self):
        try:
            import psutil
            self._cpu_percent = psutil.cpu_percent(interval=0.1)
        except ImportError:
            pass

    def _update_memory(self):
        try:
            import psutil
            mem = psutil.virtual_memory()
            self._memory = {
                'total': mem.total / (1024 ** 3),
                'used': mem.used / (1024 ** 3),
                'percent': mem.percent
            }
        except ImportError:
            pass

    def _update_swap(self):
        try:
            import psutil
            swap = psutil.swap_memory()
            self._swap = {
                'total': swap.total / (1024 ** 3),
                'used': swap.used / (1024 ** 3),
                'percent': swap.percent
            }
        except ImportError:
            pass

    def _update_gpu(self):
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.used,memory.total,temperature.gpu,utilization.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    parts = [p.strip() for p in lines[0].split(',')]
                    if len(parts) >= 4:
                        self._gpu = {
                            'used': float(parts[0]),
                            'total': float(parts[1]),
                            'temp': int(parts[2]),
                            'percent': float(parts[3].split()[0]),
                            'error': False
                        }
                        return
            self._gpu['error'] = True
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            self._gpu['error'] = True
