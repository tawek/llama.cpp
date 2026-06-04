"""
Monitor tab - displays server metrics and system resources.
Polls /slots, /metrics, /props endpoints and system_monitor.
"""

import tkinter as tk
from tkinter import ttk


class MonitorTab(ttk.Frame):
    """Real-time monitoring panel."""

    def __init__(self, parent, main_window=None):
        super().__init__(parent)
        self._main_window = main_window
        self._server_api = None
        self._sys_monitor = None
        self._process_mgr = None
        self._refresh_ms = 2000
        self._after_id = None
        self._metrics = {}
        self._build_ui()

    def set_dependencies(self, server_api, sys_monitor, process_mgr):
        """Inject dependencies."""
        self._server_api = server_api
        self._sys_monitor = sys_monitor
        self._process_mgr = process_mgr

    def _build_ui(self):
        # Server metrics frame
        sm_frame = ttk.LabelFrame(self, text='Server Metrics', padding=(8, 4))
        sm_frame.pack(side='left', fill='both', expand=True, padx=4, pady=4)

        self._lbl_prompt_tps = ttk.Label(sm_frame, text='Prompt: -- tok/s', font=('Segoe UI', 9))
        self._lbl_prompt_tps.pack(fill='x', pady=1)
        self._lbl_gen_tps = ttk.Label(sm_frame, text='Gen: -- tok/s', font=('Segoe UI', 9))
        self._lbl_gen_tps.pack(fill='x', pady=1)
        self._lbl_draft = ttk.Label(sm_frame, text='Draft: --%', font=('Segoe UI', 9))
        self._lbl_draft.pack(fill='x', pady=1)
        self._lbl_kv = ttk.Label(sm_frame, text='KV Cache: -- MiB', font=('Segoe UI', 9))
        self._lbl_kv.pack(fill='x', pady=1)
        self._lbl_graphs = ttk.Label(sm_frame, text='Graphs: --', font=('Segoe UI', 9))
        self._lbl_graphs.pack(fill='x', pady=1)
        self._lbl_status = ttk.Label(sm_frame, text='Status: Idle', foreground='gray')
        self._lbl_status.pack(fill='x', pady=1)

        # Slots frame
        slots_frame = ttk.LabelFrame(self, text='Slots', padding=(8, 4))
        slots_frame.pack(side='left', fill='both', expand=True, padx=4, pady=4)

        self._slots_text = tk.Text(slots_frame, height=12, width=30,
                                    font=('Consolas', 9), state='disabled')
        slots_scroll = ttk.Scrollbar(slots_frame, orient='vertical',
                                      command=self._slots_text.yview)
        self._slots_text.configure(yscrollcommand=slots_scroll.set)
        self._slots_text.pack(side='left', fill='both', expand=True)
        slots_scroll.pack(side='right', fill='y')

        # System resources frame
        sys_frame = ttk.LabelFrame(self, text='System Resources', padding=(8, 4))
        sys_frame.pack(side='left', fill='both', expand=True, padx=4, pady=4)

        self._lbl_cpu = ttk.Label(sys_frame, text='CPU: --%', font=('Segoe UI', 9))
        self._lbl_cpu.pack(fill='x', pady=1)
        self._lbl_mem = ttk.Label(sys_frame, text='MEM: -- GiB', font=('Segoe UI', 9))
        self._lbl_mem.pack(fill='x', pady=1)
        self._lbl_swap = ttk.Label(sys_frame, text='SWAP: -- GiB', font=('Segoe UI', 9))
        self._lbl_swap.pack(fill='x', pady=1)
        self._lbl_gpu = ttk.Label(sys_frame, text='GPU: --%', font=('Segoe UI', 9))
        self._lbl_gpu.pack(fill='x', pady=1)
        self._lbl_vram = ttk.Label(sys_frame, text='VRAM: -- MiB', font=('Segoe UI', 9))
        self._lbl_vram.pack(fill='x', pady=1)
        self._lbl_temp = ttk.Label(sys_frame, text='Temp: --C', font=('Segoe UI', 9))
        self._lbl_temp.pack(fill='x', pady=1)

        # Bottom controls
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.pack(fill='x', padx=8, pady=4)

        ttk.Label(ctrl_frame, text='Refresh:').pack(side='left')
        self._refresh_var = tk.StringVar(value='2000')
        ttk.Spinbox(ctrl_frame, from_=500, to=10000, increment=500,
                    width=8, textvariable=self._refresh_var).pack(side='left', padx=4)
        ttk.Label(ctrl_frame, text='ms').pack(side='left', padx=2)

        self._btn_start = ttk.Button(ctrl_frame, text='Start Monitoring',
                                      command=self._start_monitoring)
        self._btn_start.pack(side='left', padx=4)
        self._btn_stop = ttk.Button(ctrl_frame, text='Stop', state='disabled',
                                     command=self._stop_monitoring)
        self._btn_stop.pack(side='left', padx=2)

    def _start_monitoring(self):
        self._btn_start.config(state='disabled')
        self._btn_stop.config(state='normal')
        self._refresh_ms = int(self._refresh_var.get())
        self._poll_once()
        self._schedule_next()

    def _stop_monitoring(self):
        self._btn_start.config(state='normal')
        self._btn_stop.config(state='disabled')
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

    def _schedule_next(self):
        self._after_id = self.after(self._refresh_ms, self._poll_once)

    def _poll_once(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        self._fetch_server_metrics()
        self._fetch_slots()
        self._fetch_system_stats()
        self._schedule_next()

    def _fetch_server_metrics(self):
        if not self._server_api:
            return

        health = self._server_api.health() or self._server_api.health_v1()
        if health:
            status = health.get('status', 'unknown')
            color = 'green' if status == 'ok' else 'red'
            self._lbl_status.config(text=f'Status: {status}', foreground=color)
        else:
            self._lbl_status.config(text='Status: Disconnected', foreground='gray')

        # Fetch Prometheus metrics from /metrics
        raw = self._server_api.metrics() if self._server_api else None
        if raw:
            from api_client import parse_prometheus_metrics
            parsed = parse_prometheus_metrics(raw)
            if parsed.get('prompt_tokens_seconds', 0) > 0:
                self._lbl_prompt_tps.config(
                    text=f'Prompt: {parsed["prompt_tokens_seconds"]:.1f} tok/s')
            if parsed.get('predicted_tokens_seconds', 0) > 0:
                self._lbl_gen_tps.config(
                    text=f'Gen: {parsed["predicted_tokens_seconds"]:.1f} tok/s')

    def _fetch_slots(self):
        if not self._server_api:
            return

        slots_data = self._server_api.slots()
        if slots_data:
            lines = []
            idle = slots_data.get('n_idle_slots', 0)
            processing = slots_data.get('n_processing_slots', 0)
            lines.append(f'Idle: {idle} | Processing: {processing}')
            lines.append('-' * 40)

            for slot in slots_data.get('slots', []):
                sid = slot.get('id', '?')
                is_proc = slot.get('is_processing', False)
                ctx = slot.get('n_past', 0)
                n_ctx = slot.get('n_ctx', 0)
                if n_ctx > 0:
                    pct = ctx / n_ctx * 100
                else:
                    pct = 0
                bar_len = 20
                filled = int(bar_len * pct / 100)
                bar = '#' * filled + '-' * (bar_len - filled)

                tps = slot.get('predicted_per_second', 0)
                state = 'PROC' if is_proc else 'IDLE'
                lines.append(f'  Slot {sid} [{state}] |{bar}| {ctx}/{n_ctx}')

            self._update_text(self._slots_text, '\n'.join(lines))
        else:
            self._update_text(self._slots_text, 'No slot data available')

    def _fetch_system_stats(self):
        if not self._sys_monitor:
            return

        snap = self._sys_monitor.get_snapshot()

        cpu = snap.get('cpu', 0)
        self._lbl_cpu.config(text=f'CPU: {cpu:.0f}%')

        mem = snap.get('memory', {})
        self._lbl_mem.config(text=f'MEM: {mem.get("used", 0):.1f} / {mem.get("total", 0):.1f} GiB')

        swap = snap.get('swap', {})
        self._lbl_swap.config(text=f'SWAP: {swap.get("used", 0):.1f} / {swap.get("total", 0):.1f} GiB')

        gpu = snap.get('gpu', {})
        if gpu.get('error'):
            self._lbl_gpu.config(text='GPU: N/A')
            self._lbl_vram.config(text='VRAM: N/A')
            self._lbl_temp.config(text='Temp: N/A')
        else:
            self._lbl_gpu.config(text=f'GPU: {gpu.get("percent", 0):.0f}%')
            self._lbl_vram.config(text=f'VRAM: {gpu.get("used", 0):.0f} / {gpu.get("total", 0):.0f} MiB')
            self._lbl_temp.config(text=f'Temp: {gpu.get("temp", 0)}C')

    def _update_text(self, text_widget, content):
        text_widget.configure(state='normal')
        text_widget.delete('1.0', tk.END)
        text_widget.insert('1.0', content)
        text_widget.configure(state='disabled')
        text_widget.see(tk.END)

    def update_from_log(self, metrics):
        """Update monitor with metrics parsed from logs."""
        if not metrics:
            return

        prompt_tps = metrics.get('prompt_per_second', 0)
        gen_tps = metrics.get('gen_per_second', 0)
        draft_rate = metrics.get('draft_acceptance_rate', 0)

        self._lbl_prompt_tps.config(text=f'Prompt: {prompt_tps:.1f} tok/s')
        self._lbl_gen_tps.config(text=f'Gen: {gen_tps:.1f} tok/s')
        self._lbl_draft.config(text=f'Draft: {draft_rate * 100:.1f}%')
        self._lbl_kv.config(text=f'KV Cache: {metrics.get("cache_size_mib", 0):.1f} MiB')
        self._lbl_graphs.config(text=f'Graphs: {metrics.get("graphs_reused", 0)} reused')

    def stop(self):
        """Stop monitoring."""
        self._stop_monitoring()
