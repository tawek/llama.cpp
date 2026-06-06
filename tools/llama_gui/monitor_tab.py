"""
Monitor tab - displays server metrics and system resources.
Polls /slots, /metrics, /props endpoints and system_monitor.
"""

import math
import time
import threading
from collections import deque
import tkinter as tk
from tkinter import ttk


# ── MetricsChart ──────────────────────────────────────────────────────────────

class MetricsChart(ttk.Frame):
    """Three stacked time-series charts: PP tok/s, TG tok/s, draft %."""

    TICK_MS    = 250              # graph tick interval (ms)
    MARGIN_L   = 46
    MARGIN_R   = 18
    MARGIN_T   = 14
    MARGIN_B   = 28
    GAP        = 18           # vertical gap between charts

    C_BG         = '#1e1e1e'
    C_PLOT_BG    = '#252525'
    C_GRID       = '#3a3a3a'
    C_AXIS       = '#666666'
    C_PROMPT     = '#4e9eff'
    C_GEN        = '#4ec94e'
    C_DRAFT      = '#ffaa44'
    C_DRAFT_GEN  = '#4e9eff'   # draft tokens generated line (matches PP blue)
    C_DRAFT_ACC  = '#ffcc00'   # draft tokens accepted line
    C_TEXT       = '#aaaaaa'
    C_RULE       = '#ffffff'   # vertical crosshair line
    C_HOVER_TEXT = '#ffffff'   # value label foreground
    C_HOVER_SHADOW = '#000000' # value label drop-shadow

    # Panel order and height weights (higher = taller)
    _PANEL_ORDER  = ('pp', 'tg', 'draft_pct')
    _PANEL_WEIGHT = {'pp': 2, 'tg': 2, 'draft_pct': 1}

    _PALETTE = {
        'dark': {
            'C_BG': '#1e1e1e', 'C_PLOT_BG': '#252525',
            'C_GRID': '#3a3a3a', 'C_AXIS': '#666666', 'C_TEXT': '#aaaaaa',
            'C_RULE': '#ffffff',
            'C_HOVER_TEXT': '#ffffff', 'C_HOVER_SHADOW': '#000000',
        },
        'light': {
            'C_BG': '#f0f0f0', 'C_PLOT_BG': '#ffffff',
            'C_GRID': '#cccccc', 'C_AXIS': '#999999', 'C_TEXT': '#444444',
            'C_RULE': '#888888',
            'C_HOVER_TEXT': '#000000', 'C_HOVER_SHADOW': '#cccccc',
        },
    }

    def __init__(self, parent, time_window_s: int = 120):
        super().__init__(parent)
        self._time_window_s  = time_window_s
        self._max_points     = time_window_s * (1000 // self.TICK_MS)
        self._prompt    = []
        self._gen       = []
        self._draft     = []   # draft acceptance %
        self._draft_gen = []   # draft tokens generated (per request)
        self._draft_acc = []   # draft tokens accepted (per request)
        self._graphs_visible = {k: True for k in self._PANEL_ORDER}
        self._hover_x = None   # canvas x of last mouse position (None = no hover)
        self._canvas = tk.Canvas(self, bg=self.C_BG, highlightthickness=0)
        self._canvas.pack(fill='both', expand=True)
        self._canvas.bind('<Configure>', lambda _e: self._redraw())
        self._canvas.bind('<Motion>', self._on_hover)
        self._canvas.bind('<Leave>',  self._on_leave)

    def add_point(self, prompt_tps: float, gen_tps: float, draft_pct: float,
                  draft_gen: float = 0.0, draft_acc: float = 0.0):
        self._prompt.append(max(0.0, prompt_tps))
        self._gen.append(max(0.0, gen_tps))
        self._draft.append(max(0.0, min(100.0, draft_pct)))
        self._draft_gen.append(max(0.0, draft_gen))
        self._draft_acc.append(max(0.0, draft_acc))
        if len(self._prompt) > self._max_points:
            self._prompt    = self._prompt[-self._max_points:]
            self._gen       = self._gen[-self._max_points:]
            self._draft     = self._draft[-self._max_points:]
            self._draft_gen = self._draft_gen[-self._max_points:]
            self._draft_acc = self._draft_acc[-self._max_points:]
        self._redraw()

    def clear(self):
        self._prompt.clear()
        self._gen.clear()
        self._draft.clear()
        self._draft_gen.clear()
        self._draft_acc.clear()
        self._redraw()

    def set_time_window(self, seconds: int):
        """Change the visible time window; trims or pads history accordingly."""
        self._time_window_s = max(10, seconds)
        new_max = self._time_window_s * (1000 // self.TICK_MS)
        if new_max < self._max_points:
            self._prompt    = self._prompt[-new_max:]
            self._gen       = self._gen[-new_max:]
            self._draft     = self._draft[-new_max:]
            self._draft_gen = self._draft_gen[-new_max:]
            self._draft_acc = self._draft_acc[-new_max:]
        self._max_points = new_max
        self._redraw()

    def set_graph_visible(self, name: str, visible: bool):
        """Show or hide a named graph panel and redraw immediately."""
        if name in self._graphs_visible:
            self._graphs_visible[name] = bool(visible)
            self._redraw()

    def set_theme(self, mode: str):
        """Switch canvas color palette to 'dark' or 'light' and redraw."""
        palette = self._PALETTE.get(mode, self._PALETTE['dark'])
        for attr, value in palette.items():
            setattr(self, attr, value)
        self._canvas.config(bg=self.C_BG)
        self._redraw()

    # ── drawing ──────────────────────────────────────────────────────────────

    def _compute_panel_rects(self, W: int, H: int) -> dict:
        """Return ordered dict of panel_key -> (x0, y0, x1, y1) for visible panels."""
        ml, mr = self.MARGIN_L, self.MARGIN_R
        mt, mb, gap = self.MARGIN_T, self.MARGIN_B, self.GAP
        visible = [k for k in self._PANEL_ORDER if self._graphs_visible.get(k, True)]
        if not visible:
            return {}
        n = len(visible)
        usable_h = H - mt - mb - gap * (n - 1)
        if usable_h < n:
            return {}
        total_weight = sum(self._PANEL_WEIGHT[k] for k in visible)
        heights = [int(usable_h * self._PANEL_WEIGHT[k] / total_weight) for k in visible]
        heights[-1] += usable_h - sum(heights)   # correct rounding
        x0, x1 = ml, W - mr
        rects, y = {}, mt
        for i, k in enumerate(visible):
            rects[k] = (x0, y, x1, y + heights[i])
            y += heights[i] + (gap if i < n - 1 else 0)
        return rects

    def _redraw(self):
        c = self._canvas
        c.delete('all')
        W = c.winfo_width()
        H = c.winfo_height()
        if W < 20 or H < 20:
            return

        ml     = self.MARGIN_L
        mr     = self.MARGIN_R
        plot_w = W - ml - mr
        n_gl   = 4

        rects = self._compute_panel_rects(W, H)
        if not rects:
            return

        # X-axis labels below the last visible panel
        last_y1 = list(rects.values())[-1][3]
        c.create_text(ml,     last_y1 + 10, text=f'−{self._time_window_s}s',
                      anchor='w', fill=self.C_TEXT, font=('Consolas', 7))
        c.create_text(W - mr, last_y1 + 10, text='now', anchor='e',
                      fill=self.C_TEXT, font=('Consolas', 7))

        # ── Panel backgrounds, grids, and axis labels ─────────────────────────
        for key, (x0, y0, x1, y1) in rects.items():
            c.create_rectangle(x0, y0, x1, y1, fill=self.C_PLOT_BG, outline=self.C_AXIS)

            if key == 'pp':
                max_val = self._nice_ceil(max(self._prompt)) if self._prompt else 10.0
                self._draw_grid(c, x0, y0, x1, y1, ml, max_val, n_gl,
                                fmt=lambda v: f'{v:.0f}' if v < 1000 else f'{v/1000:.1f}k')
                c.create_text(6, (y0 + y1) // 2, text='PP tok/s', angle=90,
                              fill=self.C_AXIS, font=('Consolas', 7))
                c.create_text(x1 - 4, y0 + 8, text='PP', anchor='e',
                              fill=self.C_PROMPT, font=('Consolas', 7))

            elif key == 'tg':
                max_val = self._nice_ceil(max(self._gen)) if self._gen else 10.0
                all_dt  = self._draft_gen + self._draft_acc + self._gen
                max_dt  = self._nice_ceil(max(all_dt)) if all_dt else 10.0
                max_val = max(max_val, max_dt)
                self._draw_grid(c, x0, y0, x1, y1, ml, max_val, n_gl,
                                fmt=lambda v: f'{v:.0f}' if v < 1000 else f'{v/1000:.1f}k')
                c.create_text(6, (y0 + y1) // 2, text='TG tok/s', angle=90,
                              fill=self.C_AXIS, font=('Consolas', 7))
                c.create_text(x1 - 4, y0 + 8, text='TG', anchor='e',
                              fill=self.C_GEN, font=('Consolas', 7))
                c.create_text(x1 - 4, y0 + 18, text='DG', anchor='e',
                              fill=self.C_DRAFT_GEN, font=('Consolas', 7))
                c.create_text(x1 - 4, y0 + 28, text='DA', anchor='e',
                              fill=self.C_DRAFT_ACC, font=('Consolas', 7))

            elif key == 'draft_pct':
                self._draw_grid(c, x0, y0, x1, y1, ml, 100.0, n_gl,
                                fmt=lambda v: f'{v:.0f}%')
                c.create_text(6, (y0 + y1) // 2, text='Draft %', angle=90,
                              fill=self.C_AXIS, font=('Consolas', 7))
                c.create_text(x1 - 4, y0 + 8, text='Draft', anchor='e',
                              fill=self.C_DRAFT, font=('Consolas', 7))

            elif key == 'draft_tokens':
                all_dt  = self._draft_gen + self._draft_acc
                max_dt  = self._nice_ceil(max(all_dt)) if all_dt else 10.0
                self._draw_grid(c, x0, y0, x1, y1, ml, max_dt, n_gl,
                                fmt=lambda v: f'{v:.0f}' if v < 1000 else f'{v/1000:.1f}k')
                c.create_text(6, (y0 + y1) // 2, text='dtok', angle=90,
                              fill=self.C_AXIS, font=('Consolas', 7))
                c.create_text(x1 - 4, y0 + 8,  text='gen', anchor='e',
                              fill=self.C_DRAFT_GEN, font=('Consolas', 7))
                c.create_text(x1 - 4, y0 + 18, text='acc', anchor='e',
                              fill=self.C_DRAFT_ACC, font=('Consolas', 7))

        # ── Draw lines ────────────────────────────────────────────────────────
        n = len(self._prompt)
        if n < 2:
            return

        offset = self._max_points - n

        def to_x(i):
            return ml + ((i + offset) / (self._max_points - 1)) * plot_w

        def make_to_y(y0, y1, max_val):
            def to_y(v):
                return y1 - (v / max_val) * (y1 - y0)
            return to_y

        def draw_line(data, color, to_y):
            coords = []
            for i, v in enumerate(data):
                coords.extend([to_x(i), to_y(v)])
            if len(coords) >= 4:
                c.create_line(*coords, fill=color, width=1.5, smooth=True)

        if 'pp' in rects:
            r = rects['pp']
            max_pp = self._nice_ceil(max(self._prompt)) if self._prompt else 10.0
            draw_line(self._prompt, self.C_PROMPT, make_to_y(r[1], r[3], max_pp))

        if 'tg' in rects:
            r = rects['tg']
            all_vals = self._gen + self._draft_gen + self._draft_acc
            max_tg = self._nice_ceil(max(all_vals)) if all_vals else 10.0
            to_y_tg = make_to_y(r[1], r[3], max_tg)
            draw_line(self._gen, self.C_GEN, to_y_tg)
            n_dt = len(self._draft_gen)
            if n_dt >= 2:
                draw_line(self._draft_gen, self.C_DRAFT_GEN, to_y_tg)
                draw_line(self._draft_acc, self.C_DRAFT_ACC, to_y_tg)

        if 'draft_pct' in rects:
            r = rects['draft_pct']
            draw_line(self._draft, self.C_DRAFT, make_to_y(r[1], r[3], 100.0))

        self._draw_hover()

    # ── hover crosshair ───────────────────────────────────────────────────────

    def _on_hover(self, event):
        self._hover_x = event.x
        self._draw_hover()

    def _on_leave(self, _event):
        self._hover_x = None
        self._canvas.delete('hover')

    def _geometry(self, W, H):
        """Return panel geometry dict — mirrors _compute_panel_rects for hover use."""
        rects = self._compute_panel_rects(W, H)
        return dict(ml=self.MARGIN_L, mr=self.MARGIN_R,
                    plot_w=W - self.MARGIN_L - self.MARGIN_R,
                    panels=rects)

    def _draw_hover(self):
        c = self._canvas
        c.delete('hover')
        if self._hover_x is None:
            return
        W = c.winfo_width()
        H = c.winfo_height()
        if W < 20 or H < 20:
            return

        g = self._geometry(W, H)
        ml, mr, plot_w = g['ml'], g['mr'], g['plot_w']
        panels = g['panels']
        if not panels:
            return
        mx = self._hover_x

        # Only show when cursor is inside the plot area
        if mx < ml or mx > W - mr:
            return

        n = len(self._prompt)
        if n < 2:
            return

        # Map canvas-x to a (possibly fractional) data index
        frac  = (mx - ml) / plot_w
        idx_f = frac * (self._max_points - 1) - (self._max_points - n)
        if idx_f < 0 or idx_f > n - 1:
            return

        i0 = int(idx_f)
        i1 = min(i0 + 1, n - 1)
        t  = idx_f - i0

        def interp(data):
            return data[i0] * (1 - t) + data[i1] * t

        # Vertical rule spanning top of first panel to bottom of last panel
        panel_list = list(panels.values())
        top = panel_list[0][1]
        bot = panel_list[-1][3]
        c.create_line(mx, top, mx, bot,
                      fill=self.C_RULE, width=1, dash=(3, 3), tags='hover')

        def draw_dot_label(val, color, fmt, x0, py0, x1, py1, max_val, y_offset=0):
            cy = py1 - (val / max_val) * (py1 - py0)
            cy = max(py0, min(py1, cy))
            r = 3
            c.create_oval(mx - r, cy - r, mx + r, cy + r,
                          fill=color, outline='', tags='hover')
            label  = fmt(val)
            lx     = mx + 6 if mx + 52 < x1 else mx - 6
            anchor = 'w'     if lx > mx      else 'e'
            ty     = cy - 14 + y_offset
            c.create_text(lx + 1, ty + 1, text=label, fill=self.C_HOVER_SHADOW,
                          anchor=anchor, font=('Consolas', 8, 'bold'), tags='hover')
            c.create_text(lx,     ty,     text=label, fill=self.C_HOVER_TEXT,
                          anchor=anchor, font=('Consolas', 8, 'bold'), tags='hover')

        for key, (x0, py0, x1, py1) in panels.items():
            if key == 'pp':
                max_pp = self._nice_ceil(max(self._prompt)) if self._prompt else 10.0
                draw_dot_label(interp(self._prompt), self.C_PROMPT,
                               lambda v: f'{v:.1f}' if v < 1000 else f'{v/1000:.2f}k',
                               x0, py0, x1, py1, max_pp)

            elif key == 'tg':
                all_vals = self._gen + self._draft_gen + self._draft_acc
                max_tg = self._nice_ceil(max(all_vals)) if all_vals else 10.0
                fmt_dt = lambda v: f'{v:.1f}' if v < 1000 else f'{v/1000:.2f}k'
                draw_dot_label(interp(self._gen), self.C_GEN,
                               fmt_dt, x0, py0, x1, py1, max_tg)
                if len(self._draft_gen) > 1:
                    draw_dot_label(interp(self._draft_gen), self.C_DRAFT_GEN,
                                   fmt_dt, x0, py0, x1, py1, max_tg, y_offset=16)
                    draw_dot_label(interp(self._draft_acc), self.C_DRAFT_ACC,
                                   fmt_dt, x0, py0, x1, py1, max_tg, y_offset=28)

            elif key == 'draft_pct':
                draw_dot_label(interp(self._draft), self.C_DRAFT,
                               lambda v: f'{v:.1f}%',
                               x0, py0, x1, py1, 100.0)

    def _draw_grid(self, c, x0, y0, x1, y1, ml, max_val, n, fmt):
        """Draw horizontal grid lines and Y-axis labels for one graph."""
        for i in range(n + 1):
            frac = i / n
            y = y1 - frac * (y1 - y0)
            c.create_line(x0, y, x1, y, fill=self.C_GRID, dash=(2, 4))
            c.create_text(ml - 4, y, text=fmt(frac * max_val), anchor='e',
                          fill=self.C_TEXT, font=('Consolas', 7))

    @staticmethod
    def _nice_ceil(value: float) -> float:
        """Round value up to a 'nice' number (1/2/5 × 10^n)."""
        if value <= 0:
            return 1.0
        exp = math.floor(math.log10(value))
        base = 10 ** exp
        for mult in (1, 2, 5, 10):
            candidate = base * mult
            if candidate >= value:
                return float(candidate)
        return float(base * 10)


# ── MonitorTab ────────────────────────────────────────────────────────────────

class MonitorTab(ttk.Frame):
    """Real-time monitoring panel."""

    def __init__(self, parent, main_window=None):
        super().__init__(parent)
        self._main_window = main_window
        self._server_api = None
        self._sys_monitor = None
        self._process_mgr = None
        self._refresh_ms = 2000
        self._metrics_sample_ms = 5000   # prometheus /metrics probe cadence
        self._after_id = None
        self._metrics_after_id = None    # independent prometheus loop
        self._metrics = {}
        self._slot_widgets = {}          # slot_id -> dict of widgets
        self._slot_last_proc: dict = {}  # slot_id -> monotonic time last seen processing
        self._slot_n_ctx: dict = {}      # slot_id -> last known n_ctx (max, from load_model log)
        self._slot_ctx_tokens: dict = {}     # slot_id -> latest print_timing n_tokens
        self._slot_ctx_checkpoint: dict = {} # slot_id -> latest create_check n_tokens
        self._n_ctx_fallback = 0         # populated from prometheus n_ctx_size / n_slots
        # Event-based rate tracking (from /metrics n_tokens_pp/tg/td/tda/tdr counters)
        self._prev_pp_total = 0.0
        self._prev_tg_total = 0.0
        self._prev_td_total = 0.0
        self._prev_tda_total = 0.0
        self._prev_tdr_total = 0.0
        self._prev_metrics_time = 0.0
        self._using_event_metrics = False
        # Raw sample buffers: (monotonic_time, value) tuples.
        # maxlen covers ~10 min at fastest realistic poll rate (1 Hz) — plenty.
        _MAX_RAW = 600
        self._raw_prompt: deque = deque(maxlen=_MAX_RAW)
        self._raw_gen:    deque = deque(maxlen=_MAX_RAW)
        self._raw_draft:  deque = deque(maxlen=_MAX_RAW)
        self._raw_draft_gen: deque = deque(maxlen=_MAX_RAW)
        self._raw_draft_acc: deque = deque(maxlen=_MAX_RAW)
        # Smoothing window in ms: average all samples within [now-window, now];
        # if none fall inside the window the most recent sample is used as-is.
        self._graph_smooth_ms:  int = 2000
        # Visible time window in seconds (controls scroll speed)
        self._graph_time_window_s:  int = 120
        self._graph_tick_id = None
        self._build_ui()

    def set_dependencies(self, server_api, sys_monitor, process_mgr):
        """Inject dependencies."""
        self._server_api = server_api
        self._sys_monitor = sys_monitor
        self._process_mgr = process_mgr

    def set_theme(self, mode: str):
        """Propagate theme change to the embedded canvas chart."""
        self._chart.set_theme(mode)

    def _build_ui(self):
        # ── Vertical paned window: info row (top) + chart (bottom, draggable) ──
        self._paned = ttk.PanedWindow(self, orient='vertical')
        self._paned.pack(fill='both', expand=True, padx=4, pady=4)

        top = ttk.Frame(self._paned)
        self._paned.add(top, weight=1)

        # ── Server Metrics ────────────────────────────────────────────────────
        sm_frame = ttk.LabelFrame(top, text='Server Metrics', padding=(8, 4))
        sm_frame.pack(side='left', fill='both', expand=True, padx=(0, 4))

        self._lbl_prompt_tps = ttk.Label(sm_frame, text='Prompt: -- tok/s')
        self._lbl_prompt_tps.pack(fill='x', pady=1)
        self._lbl_gen_tps = ttk.Label(sm_frame, text='Gen: -- tok/s')
        self._lbl_gen_tps.pack(fill='x', pady=1)
        self._lbl_draft = ttk.Label(sm_frame, text='Draft: --%')
        self._lbl_draft.pack(fill='x', pady=1)
        self._lbl_graphs = ttk.Label(sm_frame, text='Graphs: --')
        self._lbl_graphs.pack(fill='x', pady=1)
        self._lbl_status = ttk.Label(sm_frame, text='Status: Idle',
                                      foreground='gray')
        self._lbl_status.pack(fill='x', pady=1)

        # ── Slots ─────────────────────────────────────────────────────────────
        slots_frame = ttk.LabelFrame(top, text='Slots', padding=(8, 4))
        slots_frame.pack(side='left', fill='both', expand=True, padx=4)

        self._slots_header = ttk.Label(slots_frame,
                                        text='Idle: -- | Processing: --',
                                        font=('', 9, 'bold'))
        self._slots_header.pack(fill='x', pady=(0, 4))
        ttk.Separator(slots_frame, orient='horizontal').pack(fill='x', pady=(0, 4))

        canvas = tk.Canvas(slots_frame, highlightthickness=0)
        scroll = ttk.Scrollbar(slots_frame, orient='vertical',
                                command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        self._slots_inner = ttk.Frame(canvas)
        self._slots_inner.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        win_id = canvas.create_window((0, 0), window=self._slots_inner, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        # Header row — columns must match _create_slot_row exactly
        hdr = ttk.Frame(self._slots_inner)
        hdr.pack(fill='x')
        ttk.Label(hdr, text='#',     width=4,  anchor='w').grid(row=0, column=0, padx=(0, 2))
        ttk.Label(hdr, text='State', width=5,  anchor='w').grid(row=0, column=1, padx=(0, 2))
        ttk.Label(hdr, text='',                anchor='w').grid(row=0, column=2, sticky='ew', padx=(0, 4))
        ttk.Label(hdr, text='ckpt',  width=4,  anchor='e').grid(row=0, column=3, padx=2)
        ttk.Label(hdr, text='proc',  width=4,  anchor='e').grid(row=0, column=4, padx=2)
        ttk.Label(hdr, text='ctx',   width=4,  anchor='e').grid(row=0, column=5, padx=(2, 4))
        hdr.columnconfigure(2, weight=1)
        self._slots_hdr_frame = hdr

        # ── System Resources ──────────────────────────────────────────────────
        sys_frame = ttk.LabelFrame(top, text='System Resources', padding=(8, 4))
        sys_frame.pack(side='left', fill='both', expand=True, padx=(4, 0))

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
        self._bar_temp = ttk.Progressbar(sys_frame, maximum=100, length=160)
        self._bar_temp.pack(fill='x', pady=(0, 4))

        # ── Chart pane (bottom, expands, draggable sash above it) ────────────
        chart_frame = ttk.LabelFrame(self._paned, text='Performance', padding=(8, 6))
        self._paned.add(chart_frame, weight=1)

        self._chart = MetricsChart(chart_frame, time_window_s=self._graph_time_window_s)
        self._chart.pack(fill='both', expand=True)

        # Set the initial sash at 50 % on the first real <Configure> event
        # (i.e. when the tab is first shown and has actual pixel dimensions).
        # after(100) is unreliable here because the Monitor tab is not the
        # default tab, so winfo_height() returns 1 until the tab is selected.
        self._sash_set = False

        def _on_pane_configure(event):
            if self._sash_set:
                return
            h = self._paned.winfo_height()
            if h < 10:
                return
            try:
                self._paned.sashpos(0, h // 2)
                self._sash_set = True
            except Exception:
                pass

        self._paned.bind('<Configure>', _on_pane_configure)

    # ── Monitoring control ────────────────────────────────────────────────────

    def _start_monitoring(self):
        self._poll_once()
        self._poll_metrics_once()
        self._graph_tick()

    def _stop_monitoring(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        if self._metrics_after_id:
            self.after_cancel(self._metrics_after_id)
            self._metrics_after_id = None
        if self._graph_tick_id:
            self.after_cancel(self._graph_tick_id)
            self._graph_tick_id = None

    def _graph_tick(self):
        """Push one smoothed point to the chart at a fixed 4 Hz regardless of fetch state."""
        now    = time.monotonic()
        cutoff = now - self._graph_smooth_ms / 1000.0

        def _avg(buf: deque) -> float:
            if not buf:
                return 0.0
            # Collect samples within the smoothing window
            window = [v for t, v in buf if t >= cutoff]
            if window:
                return sum(window) / len(window)
            # Window is empty (no new data) — hold the last known value
            return buf[-1][1]

        self._chart.add_point(_avg(self._raw_prompt),
                              _avg(self._raw_gen),
                              _avg(self._raw_draft),
                              _avg(self._raw_draft_gen),
                              _avg(self._raw_draft_acc))
        self._graph_tick_id = self.after(250, self._graph_tick)

    def _schedule_next(self):
        self._after_id = self.after(self._refresh_ms, self._poll_once)

    def _schedule_next_metrics(self):
        self._metrics_after_id = self.after(self._metrics_sample_ms, self._poll_metrics_once)

    def _poll_metrics_once(self):
        if self._metrics_after_id:
            self.after_cancel(self._metrics_after_id)
            self._metrics_after_id = None
        if self._server_api:
            threading.Thread(target=self._bg_fetch_metrics, daemon=True).start()
        self._schedule_next_metrics()

    def _poll_once(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        # System stats are local reads — safe and fast on main thread
        try:
            self._fetch_system_stats()
        except Exception as e:
            print(f'monitor: fetch_system_stats error: {e}')

        # All HTTP calls go off-thread so a slow/busy server never blocks the UI
        if self._server_api:
            threading.Thread(target=self._bg_poll_server, daemon=True).start()

        self._schedule_next()

    # ── Background workers (run in daemon threads, NO widget access) ──────────

    def _bg_poll_server(self):
        """Fetch /health and /slots in background; dispatch results to main thread."""
        try:
            health = self._server_api.health() or self._server_api.health_v1()
            self.after(0, self._apply_health, health)
        except Exception as e:
            print(f'monitor: bg health error: {e}')
        try:
            slots_data = self._server_api.slots()
            self.after(0, self._apply_slots, slots_data)
        except Exception as e:
            print(f'monitor: bg slots error: {e}')

    def _bg_fetch_metrics(self):
        """Fetch /metrics in background; dispatch parsed dict to main thread."""
        try:
            raw = self._server_api.metrics()
            if raw:
                from api_client import parse_prometheus_metrics
                self.after(0, self._apply_metrics, parse_prometheus_metrics(raw))
        except Exception as e:
            print(f'monitor: bg metrics error: {e}')

    # ── Main-thread apply callbacks ───────────────────────────────────────────

    def _apply_health(self, health):
        if health:
            status = health.get('status', 'unknown')
            color = 'green' if status == 'ok' else 'red'
            self._lbl_status.config(text=f'Status: {status}', foreground=color)
        else:
            self._lbl_status.config(text='Status: Disconnected', foreground='gray')

    def _apply_metrics(self, parsed):
        now = time.monotonic()
        # Detect monotonic counters from /metrics Prometheus output.
        # After stripping the "llamacpp:" prefix, the server names are:
        #   prompt_tokens_total, tokens_predicted_total, n_tokens_draft, ...
        pp_total = parsed.get('prompt_tokens_total')
        tg_total = parsed.get('tokens_predicted_total')
        td_total = parsed.get('n_tokens_draft')

        if pp_total is not None and tg_total is not None and td_total is not None:
            tda_total = parsed.get('n_tokens_draft_accepted', 0)
            tdr_total = parsed.get('n_tokens_draft_rejected', 0)

            if self._prev_metrics_time > 0:
                dt = now - self._prev_metrics_time
                if dt > 0.001:
                    # Reset on counter rollover
                    if pp_total < self._prev_pp_total or tg_total < self._prev_tg_total:
                        self._prev_pp_total = 0.0
                        self._prev_tg_total = 0.0
                        self._prev_td_total = 0.0
                        self._prev_tda_total = 0.0
                        self._prev_tdr_total = 0.0

                    if pp_total >= self._prev_pp_total and tg_total >= self._prev_tg_total:
                        pp_rate  = (pp_total  - self._prev_pp_total)  / dt
                        tg_rate  = (tg_total  - self._prev_tg_total)  / dt
                        td_rate  = (td_total  - self._prev_td_total)  / dt
                        tda_rate = (tda_total - self._prev_tda_total) / dt
                        tdr_rate = (tdr_total - self._prev_tdr_total) / dt

                        self._raw_prompt.append((now, pp_rate))
                        self._raw_gen.append((now, tg_rate))
                        self._lbl_prompt_tps.config(text=f'Prompt: {pp_rate:.1f} tok/s')
                        self._lbl_gen_tps.config(text=f'Gen: {tg_rate:.1f} tok/s')

                        self._raw_draft_gen.append((now, td_rate))
                        self._raw_draft_acc.append((now, tda_rate))

                        total_rej = tda_rate + tdr_rate
                        pct = min(100.0, tda_rate / total_rej * 100) if total_rej > 0 else 0.0
                        self._raw_draft.append((now, max(0.0, pct)))

                        self._lbl_draft.config(text=f'Draft: {pct:.1f}%')

            self._prev_pp_total = pp_total
            self._prev_tg_total = tg_total
            self._prev_td_total = td_total
            self._prev_tda_total = tda_total
            self._prev_tdr_total = tdr_total
            self._prev_metrics_time = now
            self._using_event_metrics = True

        n_ctx_size = int(parsed.get('n_ctx_size', 0))
        if n_ctx_size > 0:
            n_slots = max(len(self._slot_widgets), 1)
            self._n_ctx_fallback = n_ctx_size // n_slots

    def _apply_slots(self, slots_data):
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
        f = ttk.Frame(self._slots_inner)
        f.pack(fill='x', pady=1)

        ttk.Label(f, text=f'#{sid}', width=4, anchor='w').grid(row=0, column=0, padx=(0, 2))

        lbl_state = ttk.Label(f, text='IDLE', width=5, anchor='w')
        lbl_state.grid(row=0, column=1, padx=(0, 2))

        bar = ttk.Progressbar(f, maximum=100, mode='determinate')
        bar.grid(row=0, column=2, sticky='ew', padx=(0, 4))

        lbl_ckpt  = ttk.Label(f, text='', width=4, anchor='e')
        lbl_since = ttk.Label(f, text='', width=4, anchor='e')
        lbl_max   = ttk.Label(f, text='', width=4, anchor='e')
        lbl_ckpt.grid( row=0, column=3, padx=2)
        lbl_since.grid(row=0, column=4, padx=2)
        lbl_max.grid(  row=0, column=5, padx=(2, 4))

        f.columnconfigure(2, weight=1)

        self._slot_widgets[sid] = {
            'frame':     f,
            'lbl_state': lbl_state,
            'bar':       bar,
            'lbl_ckpt':  lbl_ckpt,
            'lbl_since': lbl_since,
            'lbl_max':   lbl_max,
        }

    @staticmethod
    def _kt(v: int) -> str:
        """Integer kTokens, no suffix."""
        return str(round(v / 1000)) if v else ''

    def _set_slot_ctx_cells(self, w, ckpt: int, since: int, n_ctx: int, pct: float):
        w['lbl_ckpt'].config(text=self._kt(ckpt))
        w['lbl_since'].config(text=self._kt(since))
        w['lbl_max'].config(text=self._kt(n_ctx) if n_ctx else '?')
        w['bar']['value'] = pct

    def _update_slot_row(self, sid, slot):
        w = self._slot_widgets[sid]
        is_proc = slot.get('is_processing', False)

        # n_ctx (max): cache first non-zero; fall back to prometheus estimate
        n_ctx = slot.get('n_ctx', 0)
        if n_ctx > 0:
            self._slot_n_ctx[sid] = n_ctx
        else:
            n_ctx = self._slot_n_ctx.get(sid, self._n_ctx_fallback)

        # next_token may be [] when no task — guard before calling .get()
        raw_nt    = slot.get('next_token')
        n_decoded = raw_nt.get('n_decoded', 0) if isinstance(raw_nt, dict) else 0

        # Sticky PROC: keep showing for 5 s after last seen processing
        if is_proc:
            self._slot_last_proc[sid] = time.monotonic()
        show_proc = is_proc or (time.monotonic() - self._slot_last_proc.get(sid, 0) < 5.0)

        log_tokens = self._slot_ctx_tokens.get(sid, 0)
        log_ckpt   = self._slot_ctx_checkpoint.get(sid, 0)

        if log_tokens > 0 or log_ckpt > 0:
            # log_tokens  = tokens processed in the current PP batch (resets each task)
            # log_ckpt    = total context tokens at the last checkpoint (absolute)
            # They are in different reference frames; show each directly.
            # Bar tracks context utilisation at the last checkpoint.
            pct = log_ckpt / n_ctx * 100 if n_ctx else 0
            self._set_slot_ctx_cells(w, log_ckpt, log_tokens, n_ctx, pct)
        elif n_decoded > 0:
            pct = n_decoded / n_ctx * 100 if n_ctx else 0
            self._set_slot_ctx_cells(w, 0, n_decoded, n_ctx, pct)
        else:
            self._set_slot_ctx_cells(w, 0, 0, n_ctx, 0)

        w['lbl_state'].config(
            text='PROC' if show_proc else 'IDLE',
            foreground='green' if show_proc else 'gray')

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
            self._bar_temp['value'] = 0
        else:
            gpct = gpu.get('percent', 0)
            gu, gt = gpu.get('used', 0), gpu.get('total', 0)
            vpct  = gu / gt * 100 if gt > 0 else 0
            temp  = gpu.get('temp', 0)
            tpct  = min(temp / 90.0 * 100, 100)
            self._lbl_gpu.config(text=f'GPU:  {gpct:.0f}%')
            self._bar_gpu['value'] = gpct
            self._lbl_vram.config(text=f'VRAM: {gu:.0f} / {gt:.0f} MiB')
            self._bar_vram['value'] = vpct
            self._lbl_temp.config(text=f'Temp: {temp}°C')
            self._bar_temp['value'] = tpct

    # ── Called from main.py log parser ────────────────────────────────────────

    def update_from_log(self, metrics):
        """Update instant metrics from a single parsed log event (legacy, unused)."""
        pass

    def update_from_metrics(self, metrics):
        """Update raw sample buffers from log parser events."""
        now = time.monotonic()
        if not self._using_event_metrics and metrics.prompt_per_second > 0:
            self._raw_prompt.append((now, metrics.prompt_per_second))
            self._lbl_prompt_tps.config(
                text=f'Prompt: {metrics.prompt_per_second:.1f} tok/s')
        if not self._using_event_metrics and metrics.gen_per_second > 0:
            self._raw_gen.append((now, metrics.gen_per_second))
            self._lbl_gen_tps.config(
                text=f'Gen: {metrics.gen_per_second:.1f} tok/s')
        if not self._using_event_metrics and (metrics.draft_acceptance_rate > 0 or metrics.draft_total > 0):
            pct = metrics.draft_acceptance_rate * 100
            self._raw_draft.append((now, pct))
            self._lbl_draft.config(text=f'Draft: {pct:.1f}%')
            self._raw_draft_gen.append((now, float(metrics.draft_total)))
            self._raw_draft_acc.append((now, float(metrics.draft_accepted)))
        if metrics.graphs_reused > 0:
            self._lbl_graphs.config(
                text=f'Graphs: {metrics.graphs_reused} reused')

        # Absorb any per-slot n_ctx values sniffed from "slot launch" log lines
        for sid, n_ctx in metrics.slot_n_ctx.items():
            if n_ctx > 0:
                self._slot_n_ctx[sid] = n_ctx

        # Clear PP state for slots that just received a new task
        for sid in metrics.slot_task_started:
            self._slot_ctx_tokens.pop(sid, None)
            self._slot_ctx_checkpoint.pop(sid, None)
            self._refresh_slot_ctx(sid)

        # Absorb per-slot PP progress from print_timing lines
        for sid, n_tokens in metrics.slot_ctx_tokens.items():
            self._slot_ctx_tokens[sid] = n_tokens
            self._refresh_slot_ctx(sid)

        # Absorb per-slot checkpoint token counts from create_check lines
        for sid, n_tokens in metrics.slot_ctx_checkpoint.items():
            self._slot_ctx_checkpoint[sid] = n_tokens
            self._refresh_slot_ctx(sid)

    def _refresh_slot_ctx(self, sid):
        """Immediately update the ctx cells for a slot using log-derived data."""
        if sid not in self._slot_widgets:
            return
        w         = self._slot_widgets[sid]
        n_ctx     = self._slot_n_ctx.get(sid, self._n_ctx_fallback)
        log_tokens = self._slot_ctx_tokens.get(sid, 0)
        log_ckpt   = self._slot_ctx_checkpoint.get(sid, 0)
        if log_tokens > 0 or log_ckpt > 0:
            pct = log_ckpt / n_ctx * 100 if n_ctx else 0
            self._set_slot_ctx_cells(w, log_ckpt, log_tokens, n_ctx, pct)
        else:
            self._set_slot_ctx_cells(w, 0, 0, n_ctx, 0)

    def stop(self):
        self._stop_monitoring()
