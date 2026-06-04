"""
System monitor using /proc/stat, /proc/meminfo, and nvidia-smi.
No external dependencies required on Linux.
"""

import subprocess
import threading
import time
from typing import Optional


def _read_proc_stat():
    """Return (user, nice, system, idle, iowait, irq, softirq, steal) from /proc/stat."""
    with open('/proc/stat') as f:
        for line in f:
            if line.startswith('cpu '):
                fields = line.split()
                # fields[0] == 'cpu', rest are counters
                nums = [int(x) for x in fields[1:]]
                # pad to at least 8 fields
                while len(nums) < 8:
                    nums.append(0)
                return tuple(nums[:8])
    return (0,) * 8


def _read_proc_meminfo():
    """Return dict of key -> kB from /proc/meminfo."""
    info = {}
    with open('/proc/meminfo') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(':')
                try:
                    info[key] = int(parts[1])
                except ValueError:
                    pass
    return info


class SystemMonitor:
    def __init__(self):
        self._cpu_percent = 0.0
        self._memory = {'total': 0.0, 'used': 0.0, 'percent': 0.0}
        self._swap   = {'total': 0.0, 'used': 0.0, 'percent': 0.0}
        self._gpu    = {'total': 0.0, 'used': 0.0, 'percent': 0.0,
                        'temp': 0, 'error': True}
        self._prev_stat = None          # previous /proc/stat snapshot
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, interval: float = 2.0):
        """Start periodic background monitoring."""
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop, args=(interval,), daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)

    # ── Public snapshot ───────────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        """Non-blocking: return cached values updated by background thread.
        If the thread was never started, compute inline (one-shot, CPU may be 0)."""
        if not self._running:
            self._update_cpu()
            self._update_mem()
            self._update_gpu()
        return {
            'cpu':    self._cpu_percent,
            'memory': dict(self._memory),
            'swap':   dict(self._swap),
            'gpu':    dict(self._gpu),
        }

    # ── Background loop ───────────────────────────────────────────────────

    def _monitor_loop(self, interval: float):
        while self._running:
            self._update_cpu()
            self._update_mem()
            self._update_gpu()
            time.sleep(interval)

    # ── Individual updaters ───────────────────────────────────────────────

    def _update_cpu(self):
        try:
            cur = _read_proc_stat()
            if self._prev_stat is not None:
                prev = self._prev_stat
                # idle = idle + iowait (indices 3, 4)
                prev_idle = prev[3] + prev[4]
                cur_idle  = cur[3]  + cur[4]
                prev_total = sum(prev)
                cur_total  = sum(cur)
                delta_total = cur_total - prev_total
                delta_idle  = cur_idle  - prev_idle
                if delta_total > 0:
                    self._cpu_percent = (1.0 - delta_idle / delta_total) * 100.0
            self._prev_stat = cur
        except OSError:
            pass

    def _update_mem(self):
        try:
            info = _read_proc_meminfo()
            total_kb = info.get('MemTotal', 0)
            avail_kb = info.get('MemAvailable', info.get('MemFree', 0))
            used_kb  = total_kb - avail_kb

            total_gib = total_kb / (1024 ** 2)
            used_gib  = used_kb  / (1024 ** 2)
            pct = used_kb / total_kb * 100.0 if total_kb else 0.0

            self._memory = {
                'total':   total_gib,
                'used':    used_gib,
                'percent': pct,
            }

            stotal_kb = info.get('SwapTotal', 0)
            sfree_kb  = info.get('SwapFree',  0)
            sused_kb  = stotal_kb - sfree_kb
            spct = sused_kb / stotal_kb * 100.0 if stotal_kb else 0.0

            self._swap = {
                'total':   stotal_kb / (1024 ** 2),
                'used':    sused_kb  / (1024 ** 2),
                'percent': spct,
            }
        except OSError:
            pass

    def _update_gpu(self):
        try:
            result = subprocess.run(
                ['nvidia-smi',
                 '--query-gpu=memory.used,memory.total,temperature.gpu,utilization.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                parts = [p.strip() for p in result.stdout.strip().split(',')]
                if len(parts) >= 4:
                    self._gpu = {
                        'used':    float(parts[0]),
                        'total':   float(parts[1]),
                        'temp':    int(parts[2]),
                        'percent': float(parts[3]),
                        'error':   False,
                    }
                    return
            self._gpu['error'] = True
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
            self._gpu['error'] = True
