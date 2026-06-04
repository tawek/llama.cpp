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
        self._slot_widgets = {}   # slot_id -> dict of widgets
        self._build_ui()

    def set_dependencies(self, server_api, sys_monitor, process_mgr):
        """Inject dependencies."""
        self._server_api = server_api
        self._sys_monitor = sys_monitor
        self._process_mgr = process_mgr

    def _build_ui(self):
        # ── Server Metrics ────────────────────────────────────────────────
        sm_frame = ttk.LabelFrame(self, text='Server Metrics', padding=(8, 4))
        sm_frame.pack(side='left', fill='both', expand=True, padx=4, pady=4)

        self._lbl_prompt_tps = ttk.Label(sm_frame, text='Prompt: -- tok/s')
        self._lbl_prompt_tps.pack(fill='x', pady=1)
        self._lbl_gen_tps = ttk.Label(sm_frame, text='Gen: -- tok/s')
        self._lbl_gen_tps.pack(fill='x', pady=1)
        self._lbl_draft = ttk.Label(sm_frame, text='Draft: --%')
        self._lbl_draft.pack(fill='x', pady=1)
        self._lbl_kv = ttk.Label(sm_frame, text='KV Cache: -- MiB')
        self._lbl_kv.pack(fill='x', pady=1)
        self._lbl_graphs = ttk.Label(sm_frame, text='Graphs: --')
        self._lbl_graphs.pack(fill='x', pady=1)
        self._lbl_status = ttk.Label(sm_frame, text='Status: Idle',
                                      foreground='gray')
        self._lbl_status.pack(fill='x', pady=1)

        # ── Slots ─────────────────────────────────────────────────────────
        slots_frame = ttk.LabelFrame(self, text='Slots', padding=(8, 4))
        slots_frame.pack(side='left', fill='both', expand=True, padx=4, pady=4)

        self._slots_header = ttk.Label(slots_frame,
                                        text='Idle: -- | Processing: --',
                                        font=('', 9, 'bold'))
        self._slots_header.pack(fill='x', pady=(0, 4))
        ttk.Separator(slots_frame, orient='horizontal').pack(fill='x', pady=(0, 4))

        # Scrollable inner frame for slot rows
        canvas = tk.Canvas(slots_frame, highlightthickness=0)
        scroll = ttk.Scrollbar(slots_frame, orient='vertical',
                                command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        self._slots_inner = ttk.Frame(canvas)
        self._slots_inner.bind(
            '<Configure>',
            lambda e: canvas.configure(
                scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=self._slots_inner, anchor='nw')
        canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        # Column headers
        hdr = ttk.Frame(self._slots_inner)
        hdr.pack(fill='x')
        ttk.Label(hdr, text='Slot',  width=5,  anchor='w').grid(row=0, column=0)
        ttk.Label(hdr, text='State', width=6,  anchor='w').grid(row=0, column=1)
        ttk.Label(hdr, text='Context',          anchor='w').grid(row=0, column=2, sticky='ew', padx=4)
        ttk.Label(hdr, text='Tokens', width=12, anchor='e').grid(row=0, column=3)
        hdr.columnconfigure(2, weight=1)
        self._slots_hdr_frame = hdr

        # ── System Resources ──────────────────────────────────────────────
        sys_frame = ttk.LabelFrame(self, text='System Resources', padding=(8, 4))
        sys_frame.pack(side='left', fill='both', expand=True, padx=4, pady=4)

        self._lbl_cpu  = ttk.Label(sys_frame, text='CPU:  --%')
        self._lbl_cpu.pack(fill='x', pady=1)
        self._bar_cpu  = ttk.Progressbar(sys_frame, maximum=100, length=160)
        self._bar_cpu.pack(fill='x', pady=(0, 4))

        self._lbl_mem  = ttk.Label(sys_frame, text='MEM:  -- / -- GiB')
        self._lbl_mem.pack(fill='x', pady=1)
        self._bar_mem  = ttk.Progressbar(sys_frame, maximum=100, length=160)
        self._bar_mem.pack(fill='x', pady=(0, 4))

        self._lbl_swap = ttk.Label(sys_frame, text='SWAP: -- / -- GiB')
        self._lbl_swap.pack(fill='x', pady=1)
        self._bar_swap = ttk.Progressbar(sys_frame, maximum=100, length=160)
        self._bar_swap.pack(fill='x', pady=(0, 4))

        ttk.Separator(sys_frame, orient='horizontal').pack(fill='x', pady=4)

        self._lbl_gpu  = ttk.Label(sys_frame, text='GPU:  --%')
        self._lbl_gpu.pack(fill='x', pady=1)
        self._bar_gpu  = ttk.Progressbar(sys_frame, maximum=100, length=160)
        self._bar_gpu.pack(fill='x', pady=(0, 4))

        self._lbl_vram = ttk.Label(sys_frame, text='VRAM: -- / -- MiB')
        self._lbl_vram.pack(fill='x', pady=1)
        self._bar_vram = ttk.Progressbar(sys_frame, maximum=100, length=160)
        self._bar_vram.pack(fill='x', pady=(0, 4))

        self._lbl_temp = ttk.Label(sys_frame, text='Temp: --°C')
        self._lbl_temp.pack(fill='x', pady=1)

    # ── Monitoring control ────────────────────────────────────────────────

    def _start_monitoring(self):
        self._poll_once()

    def _stop_monitoring(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

    def _schedule_next(self):
        self._after_id = self.after(self._refresh_ms, self._poll_once)

    def _poll_once(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        try:
            self._fetch_server_metrics()
        except Exception as e:
            print(f'monitor: fetch_server_metrics error: {e}')

        try:
            self._fetch_slots()
        except Exception as e:
            print(f'monitor: fetch_slots error: {e}')

        try:
            self._fetch_system_stats()
        except Exception as e:
            print(f'monitor: fetch_system_stats error: {e}')

        self._schedule_next()

    # ── Fetch helpers ─────────────────────────────────────────────────────

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

        raw = self._server_api.metrics()
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
        if slots_data is None:
            self._slots_header.config(text='Idle: -- | Processing: --')
            return

        slots = slots_data if isinstance(slots_data, list) else slots_data.get('slots', [])

        idle       = sum(1 for s in slots if not s.get('is_processing', False))
        processing = sum(1 for s in slots if     s.get('is_processing', False))
        self._slots_header.config(text=f'Idle: {idle} | Processing: {processing}')

        seen = set()
        for slot in slots:
            sid = slot.get('id', 0)
            seen.add(sid)
            if sid not in self._slot_widgets:
                self._create_slot_row(sid)
            self._update_slot_row(sid, slot)

        for sid in list(self._slot_widgets):
            if sid not in seen:
                self._slot_widgets[sid]['frame'].destroy()
                del self._slot_widgets[sid]

    def _create_slot_row(self, sid):
        row = len(self._slot_widgets) + 1   # +1 for header row
        f = ttk.Frame(self._slots_inner)
        f.pack(fill='x', pady=1)

        lbl_id    = ttk.Label(f, text=f'#{sid}', width=5, anchor='w')
        lbl_id.grid(row=0, column=0)

        lbl_state = ttk.Label(f, text='IDLE', width=6, anchor='w')
        lbl_state.grid(row=0, column=1)

        bar = ttk.Progressbar(f, maximum=100, length=100, mode='determinate')
        bar.grid(row=0, column=2, sticky='ew', padx=4)

        lbl_ctx = ttk.Label(f, text='0 / 0', width=12, anchor='e')
        lbl_ctx.grid(row=0, column=3)

        f.columnconfigure(2, weight=1)

        self._slot_widgets[sid] = {
            'frame': f,
            'lbl_state': lbl_state,
            'bar': bar,
            'lbl_ctx': lbl_ctx,
        }

    def _update_slot_row(self, sid, slot):
        w = self._slot_widgets[sid]
        is_proc = slot.get('is_processing', False)
        ctx     = slot.get('n_past', 0)
        n_ctx   = slot.get('n_ctx', 0)
        pct     = ctx / n_ctx * 100 if n_ctx > 0 else 0

        w['lbl_state'].config(
            text='PROC' if is_proc else 'IDLE',
            foreground='green' if is_proc else 'gray')
        w['bar']['value'] = pct
        w['lbl_ctx'].config(text=f'{ctx} / {n_ctx}')

    def _fetch_system_stats(self):
        if not self._sys_monitor:
            return

        snap = self._sys_monitor.get_snapshot()

        cpu = snap.get('cpu', 0)
        self._lbl_cpu.config(text=f'CPU:  {cpu:.0f}%')
        self._bar_cpu['value'] = cpu

        mem = snap.get('memory', {})
        used, total = mem.get('used', 0), mem.get('total', 0)
        pct = mem.get('percent', 0)
        self._lbl_mem.config(text=f'MEM:  {used:.1f} / {total:.1f} GiB')
        self._bar_mem['value'] = pct

        swap = snap.get('swap', {})
        su, st = swap.get('used', 0), swap.get('total', 0)
        self._lbl_swap.config(text=f'SWAP: {su:.1f} / {st:.1f} GiB')
        self._bar_swap['value'] = swap.get('percent', 0)

        gpu = snap.get('gpu', {})
        if gpu.get('error'):
            self._lbl_gpu.config(text='GPU:  N/A')
            self._bar_gpu['value'] = 0
            self._lbl_vram.config(text='VRAM: N/A')
            self._bar_vram['value'] = 0
            self._lbl_temp.config(text='Temp: N/A')
        else:
            gpct = gpu.get('percent', 0)
            gu, gt = gpu.get('used', 0), gpu.get('total', 0)
            vpct  = gu / gt * 100 if gt > 0 else 0
            self._lbl_gpu.config(text=f'GPU:  {gpct:.0f}%')
            self._bar_gpu['value'] = gpct
            self._lbl_vram.config(text=f'VRAM: {gu:.0f} / {gt:.0f} MiB')
            self._bar_vram['value'] = vpct
            self._lbl_temp.config(text=f'Temp: {gpu.get("temp", 0)}°C')

    # ── Called from main.py log parser ───────────────────────────────────

    def update_from_log(self, metrics):
        if not metrics:
            return
        self._lbl_prompt_tps.config(
            text=f'Prompt: {metrics.get("prompt_per_second", 0):.1f} tok/s')
        self._lbl_gen_tps.config(
            text=f'Gen: {metrics.get("gen_per_second", 0):.1f} tok/s')
        self._lbl_draft.config(
            text=f'Draft: {metrics.get("draft_acceptance_rate", 0) * 100:.1f}%')
        self._lbl_kv.config(
            text=f'KV Cache: {metrics.get("cache_size_mib", 0):.1f} MiB')
        self._lbl_graphs.config(
            text=f'Graphs: {metrics.get("graphs_reused", 0)} reused')

    def stop(self):
        self._stop_monitoring()
