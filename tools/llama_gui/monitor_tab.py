"""
Monitor tab - displays server metrics and system resources.
Polls /slots, /metrics, /props endpoints and system_monitor.
"""

import math
import re
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
    C_GEN        = '#4e9eff'   # TG tokens per second line (now blue)
    C_DRAFT      = '#ffaa44'
    C_DRAFT_GEN  = '#ffcc00'   # draft tokens generated line
    C_DRAFT_ACC  = '#4ec94e'   # draft tokens accepted line (now green)
    C_PROMPT_RAW     = '#274f80'
    C_GEN_RAW        = '#274f80'
    C_DRAFT_RAW      = '#805522'
    C_DRAFT_GEN_RAW  = '#806611'
    C_DRAFT_ACC_RAW  = '#276427'
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
        self._times         = []
        self._raw_prompt    = []
        self._raw_gen       = []
        self._raw_draft     = []
        self._raw_draft_gen = []
        self._raw_draft_acc = []
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

    def add_point(self, prompt_tps_raw, prompt_tps,
                  gen_tps_raw, gen_tps,
                  draft_pct_raw, draft_pct,
                  draft_gen_raw=0.0, draft_gen=0.0,
                  draft_acc_raw=0.0, draft_acc=0.0,
                  sample_t=None):
        sample_t = time.monotonic() if sample_t is None else sample_t
        self._times.append(sample_t)
        self._raw_prompt.append(max(0.0, prompt_tps_raw) if prompt_tps_raw is not None else None)
        self._raw_gen.append(max(0.0, gen_tps_raw) if gen_tps_raw is not None else None)
        self._raw_draft.append(max(0.0, min(100.0, draft_pct_raw)) if draft_pct_raw is not None else None)
        self._raw_draft_gen.append(max(0.0, draft_gen_raw) if draft_gen_raw is not None else None)
        self._raw_draft_acc.append(max(0.0, draft_acc_raw) if draft_acc_raw is not None else None)

        self._prompt.append(prompt_tps if prompt_tps is not None else None)
        self._gen.append(gen_tps if gen_tps is not None else None)
        self._draft.append(draft_pct if draft_pct is not None else None)
        self._draft_gen.append(draft_gen if draft_gen is not None else None)
        self._draft_acc.append(draft_acc if draft_acc is not None else None)

        cutoff = sample_t - self._time_window_s
        drop = 0
        while drop < len(self._times) and self._times[drop] < cutoff:
            drop += 1
        if drop:
            self._times         = self._times[drop:]
            self._raw_prompt    = self._raw_prompt[drop:]
            self._raw_gen       = self._raw_gen[drop:]
            self._raw_draft     = self._raw_draft[drop:]
            self._raw_draft_gen = self._raw_draft_gen[drop:]
            self._raw_draft_acc = self._raw_draft_acc[drop:]
            self._prompt        = self._prompt[drop:]
            self._gen           = self._gen[drop:]
            self._draft         = self._draft[drop:]
            self._draft_gen     = self._draft_gen[drop:]
            self._draft_acc     = self._draft_acc[drop:]
        self._redraw()

    def clear(self):
        self._raw_prompt.clear()
        self._raw_gen.clear()
        self._raw_draft.clear()
        self._raw_draft_gen.clear()
        self._raw_draft_acc.clear()
        self._times.clear()
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
        now = time.monotonic()
        t_min = now - self._time_window_s

        def has_visible_data(data):
            return any(t >= t_min and t <= now and v is not None
                       for t, v in zip(self._times, data))

        any_data = (
            has_visible_data(self._prompt) or
            has_visible_data(self._gen) or
            has_visible_data(self._draft) or
            has_visible_data(self._draft_gen) or
            has_visible_data(self._draft_acc)
        )
        if not any_data:
            return {}

        visible = []
        for k in self._PANEL_ORDER:
            if not self._graphs_visible.get(k, True):
                continue
            visible.append(k)

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
        now    = time.monotonic()
        t_min  = now - self._time_window_s

        rects = self._compute_panel_rects(W, H)
        if not rects:
            c.create_text(W // 2, H // 2, text='No data',
                          fill=self.C_TEXT, font=('Consolas', 10))
            return

        def visible_values(data):
            return [v for t, v in zip(self._times, data)
                    if t >= t_min and t <= now and v is not None]

        # X-axis labels below the last visible panel
        last_y1 = list(rects.values())[-1][3]
        c.create_text(ml,     last_y1 + 10, text=f'−{self._time_window_s}s',
                      anchor='w', fill=self.C_TEXT, font=('Consolas', 7))
        c.create_text(W - mr, last_y1 + 10, text='now', anchor='e',
                      fill=self.C_TEXT, font=('Consolas', 7))

        # ── Compute max values for each panel (from all visible data) ──────────
        maxs = {}
        for key in rects:
            if key == 'pp':
                all_pp = visible_values(self._prompt) + visible_values(self._raw_prompt)
                maxs[key] = self._nice_ceil(max(all_pp)) if all_pp else 10.0
            elif key == 'tg':
                all_vals = (visible_values(self._gen) + visible_values(self._draft_gen)
                            + visible_values(self._draft_acc) + visible_values(self._raw_gen)
                            + visible_values(self._raw_draft_gen) + visible_values(self._raw_draft_acc))
                maxs[key] = self._nice_ceil(max(all_vals)) if all_vals else 10.0
            elif key == 'draft_pct':
                maxs[key] = 100.0
            elif key == 'draft_tokens':
                all_dt = visible_values(self._draft_gen) + visible_values(self._draft_acc)
                maxs[key] = self._nice_ceil(max(all_dt)) if all_dt else 10.0

        # ── Panel backgrounds, grids, and axis labels ─────────────────────────
        for key, (x0, y0, x1, y1) in rects.items():
            c.create_rectangle(x0, y0, x1, y1, fill=self.C_PLOT_BG, outline=self.C_AXIS)
            panel_has_data = False

            if key == 'pp':
                valid = visible_values(self._prompt)
                panel_has_data = bool(valid)
                max_val = maxs.get(key, 10.0)
                self._draw_grid(c, x0, y0, x1, y1, ml, max_val, n_gl,
                                fmt=lambda v: f'{v:.0f}' if v < 1000 else f'{v/1000:.1f}k')
                c.create_text(6, (y0 + y1) // 2, text='PP tok/s', angle=90,
                              fill=self.C_AXIS, font=('Consolas', 7))
                c.create_text(x1 - 4, y0 + 8, text='PP', anchor='e',
                              fill=self.C_PROMPT, font=('Consolas', 7))

            elif key == 'tg':
                valid_gen = visible_values(self._gen)
                valid_dg = visible_values(self._draft_gen)
                valid_da = visible_values(self._draft_acc)
                panel_has_data = bool(valid_gen or valid_dg or valid_da)
                max_val = maxs.get(key, 10.0)
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
                panel_has_data = bool(visible_values(self._draft))
                self._draw_grid(c, x0, y0, x1, y1, ml, 100.0, n_gl,
                                fmt=lambda v: f'{v:.0f}%')
                c.create_text(6, (y0 + y1) // 2, text='Draft %', angle=90,
                              fill=self.C_AXIS, font=('Consolas', 7))
                c.create_text(x1 - 4, y0 + 8, text='Draft', anchor='e',
                              fill=self.C_DRAFT, font=('Consolas', 7))

            elif key == 'draft_tokens':
                all_dt = visible_values(self._draft_gen) + visible_values(self._draft_acc)
                panel_has_data = bool(all_dt)
                max_val = maxs.get(key, 10.0)
                self._draw_grid(c, x0, y0, x1, y1, ml, max_val, n_gl,
                                fmt=lambda v: f'{v:.0f}' if v < 1000 else f'{v/1000:.1f}k')
                c.create_text(6, (y0 + y1) // 2, text='dtok', angle=90,
                              fill=self.C_AXIS, font=('Consolas', 7))
                c.create_text(x1 - 4, y0 + 8,  text='gen', anchor='e',
                              fill=self.C_DRAFT_GEN, font=('Consolas', 7))
                c.create_text(x1 - 4, y0 + 18, text='acc', anchor='e',
                              fill=self.C_DRAFT_ACC, font=('Consolas', 7))

            if not panel_has_data:
                c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text='No data',
                              fill=self.C_TEXT, font=('Consolas', 10))

        # ── Draw lines ────────────────────────────────────────────────────────
        n = len(self._times)
        if n < 2:
            return

        def to_x(t):
            return ml + ((t - t_min) / self._time_window_s) * plot_w

        def make_to_y(y0, y1, max_val):
            def to_y(v):
                return y1 - (v / max_val) * (y1 - y0)
            return to_y

        def draw_line(data, color, to_y, width=1.5, smooth=True):
            coords = []
            for t, v in zip(self._times, data):
                if t < t_min or t > now:
                    continue
                if v is None:
                    if len(coords) >= 4:
                        c.create_line(*coords, fill=color, width=width, smooth=smooth)
                    coords = []
                    continue
                coords.extend([to_x(t), to_y(v)])
            if len(coords) >= 4:
                c.create_line(*coords, fill=color, width=width, smooth=smooth)

        if 'pp' in rects:
            r = rects['pp']
            max_pp = maxs['pp']
            to_y_pp = make_to_y(r[1], r[3], max_pp)
            draw_line(self._raw_prompt, self.C_PROMPT_RAW, to_y_pp, width=0.7, smooth=False)
            draw_line(self._prompt, self.C_PROMPT, to_y_pp)

        if 'tg' in rects:
            r = rects['tg']
            max_tg = maxs['tg']
            to_y_tg = make_to_y(r[1], r[3], max_tg)
            draw_line(self._raw_gen, self.C_GEN_RAW, to_y_tg, width=0.7, smooth=False)
            n_rdt = len(self._raw_draft_gen)
            if n_rdt >= 2:
                draw_line(self._raw_draft_gen, self.C_DRAFT_GEN_RAW, to_y_tg, width=0.7, smooth=False)
                draw_line(self._raw_draft_acc, self.C_DRAFT_ACC_RAW, to_y_tg, width=0.7, smooth=False)
            draw_line(self._gen, self.C_GEN, to_y_tg)
            n_dt = len(self._draft_gen)
            if n_dt >= 2:
                draw_line(self._draft_gen, self.C_DRAFT_GEN, to_y_tg)
                draw_line(self._draft_acc, self.C_DRAFT_ACC, to_y_tg)

        if 'draft_pct' in rects:
            r = rects['draft_pct']
            to_y_da = make_to_y(r[1], r[3], 100.0)
            draw_line(self._raw_draft, self.C_DRAFT_RAW, to_y_da, width=0.7, smooth=False)
            draw_line(self._draft, self.C_DRAFT, to_y_da)

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
        now = time.monotonic()
        t_min = now - self._time_window_s

        # Only show when cursor is inside the plot area
        if mx < ml or mx > W - mr:
            return

        n = len(self._times)
        if n < 2:
            return

        t_hover = t_min + ((mx - ml) / plot_w) * self._time_window_s
        if t_hover < self._times[0] or t_hover > self._times[-1]:
            return

        i1 = None
        for i, sample_t in enumerate(self._times):
            if sample_t >= t_hover:
                i1 = i
                break
        if i1 is None or i1 == 0:
            return
        i0 = i1 - 1
        t0 = self._times[i0]
        t1 = self._times[i1]
        if t1 <= t0:
            return
        frac = (t_hover - t0) / (t1 - t0)

        def interp(data):
            v0, v1 = data[i0], data[i1]
            if v0 is None or v1 is None:
                return None
            return v0 * (1 - frac) + v1 * frac

        def visible_values(data):
            return [v for sample_t, v in zip(self._times, data)
                    if sample_t >= t_min and sample_t <= now and v is not None]

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
                pp_vals = visible_values(self._prompt)
                max_pp = self._nice_ceil(max(pp_vals)) if pp_vals else 10.0
                val = interp(self._prompt)
                if val is not None:
                    draw_dot_label(val, self.C_PROMPT,
                                   lambda v: f'{v:.1f}' if v < 1000 else f'{v/1000:.2f}k',
                                   x0, py0, x1, py1, max_pp)

            elif key == 'tg':
                all_vals = visible_values(self._gen) + visible_values(self._draft_gen) + visible_values(self._draft_acc)
                max_tg = self._nice_ceil(max(all_vals)) if all_vals else 10.0
                fmt_dt = lambda v: f'{v:.1f}' if v < 1000 else f'{v/1000:.2f}k'
                val_gen = interp(self._gen)
                if val_gen is not None:
                    draw_dot_label(val_gen, self.C_GEN, fmt_dt, x0, py0, x1, py1, max_tg)
                if len(self._draft_gen) > 1:
                    val_dg = interp(self._draft_gen)
                    val_da = interp(self._draft_acc)
                    if val_dg is not None:
                        draw_dot_label(val_dg, self.C_DRAFT_GEN, fmt_dt, x0, py0, x1, py1, max_tg, y_offset=16)
                    if val_da is not None:
                        draw_dot_label(val_da, self.C_DRAFT_ACC, fmt_dt, x0, py0, x1, py1, max_tg, y_offset=28)

            elif key == 'draft_pct':
                val = interp(self._draft)
                if val is not None:
                    draw_dot_label(val, self.C_DRAFT,
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
        self._metrics_sample_ms = 2000   # prometheus /metrics probe cadence (matches /slots)
        self._after_id = None
        self._metrics_after_id = None    # independent prometheus loop
        self._metrics = {}
        self._slot_widgets = {}          # slot_id -> dict of widgets
        self._slot_last_proc: dict = {}  # slot_id -> monotonic time last seen processing
        self._slot_n_ctx: dict = {}      # slot_id -> last known n_ctx
        self._slot_bar_data: dict = {}   # slot_id -> {n_prompt_length, n_prompt_tokens_processed, n_decoded, n_ctx}
        self._slot_prompt_length: dict = {}  # slot_id -> cached original prompt length (persists across polls)
        self._n_ctx_fallback = 0         # populated from prometheus n_ctx_size / n_slots
        # Gauge state
        self._gauge_max_seen = {
            'pp': 0.0,
            'tg': 0.0,
            'td': 0.0,
            'ta': 0.0,
            'da': 100.0,
        }
        # Accumulated rate tracking (counter and time counters).
        self._prev_pp_total = 0.0
        self._prev_pp_time = 0.0
        self._prev_tg_total = 0.0
        self._prev_tg_time = 0.0
        self._prev_td_total = 0.0
        self._prev_td_time = 0.0
        self._prev_tda_total = 0.0
        self._prev_tda_time = 0.0
        self._prev_tdr_total = 0.0
        self._prev_tdr_time = 0.0
        self._using_event_metrics = False
        self._gauge_last = {}
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
        self._graph_smooth_ms_pp: int = 2000
        self._graph_smooth_ms_tg: int = 2000
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
        sm_frame.pack(side='left', fill='y', padx=(0, 4))

        self._gauges = {}
        gauge_specs = [
            ('pp', 'PP',  'tok/s'),
            ('tg', 'TG',  'tok/s'),
            ('td', 'TD',  'tok/s'),
            ('ta', 'TA',  'tok/s'),
            ('da', 'DA%', '%'),
        ]
        for key, label, unit in gauge_specs:
            f = ttk.Frame(sm_frame)
            f.pack(fill='x', pady=1)
            lbl = ttk.Label(f, text=f'{label}:  -- {unit}', anchor='w', width=22)
            lbl.pack(fill='x')
            bar = ttk.Progressbar(f, maximum=100, length=160)
            bar.pack(fill='x', pady=(0, 2))
            self._gauges[key] = {'lbl': lbl, 'bar': bar}

        ttk.Separator(sm_frame, orient='horizontal').pack(fill='x', pady=4)

        # Connection status — LED diode + text label
        status_frame = ttk.Frame(sm_frame)
        status_frame.pack(fill='x', pady=1)
        self._status_led = tk.Canvas(status_frame, width=16, height=16,
                                      highlightthickness=0)
        self._status_led.pack(side='right')
        self._status_led.create_oval(2, 2, 14, 14, fill='gray', outline='')
        self._lbl_status = ttk.Label(status_frame, text='Disconnected',
                                      foreground='gray', anchor='w')
        self._lbl_status.pack(side='left', fill='x')

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
        ttk.Label(hdr, text='pp',  width=4,  anchor='e').grid(row=0, column=3, padx=2)
        ttk.Label(hdr, text='gen', width=4,  anchor='e').grid(row=0, column=4, padx=2)
        ttk.Label(hdr, text='max', width=4,  anchor='e').grid(row=0, column=5, padx=(2, 4))
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
        self._stop_monitoring()
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
        """Redraw the chart so timestamped samples move with real time."""
        self._chart._redraw()
        self._graph_tick_id = self.after(250, self._graph_tick)

    def _push_graph_point(self, raw, extra_sample_t=None,
                          wma_pp=None, wma_tg=None, wma_da=None,
                          wma_td=None, wma_ta=None,
                          wma_pp_e=None, wma_tg_e=None, wma_da_e=None,
                          wma_td_e=None, wma_ta_e=None):
        """Push one or two aligned graph points for a single /metrics probe.

        WMA values are precomputed by the caller before appending new samples
        to the raw buffers, so the WMA reflects only samples that existed
        before this poll.
        """
        now = time.monotonic()

        fresh = {key: value is not None for key, value in raw.items()}

        pp_raw = raw.get('pp')
        pp     = wma_pp if wma_pp is not None else None
        tg_raw = raw.get('tg')
        tg     = wma_tg if wma_tg is not None else None
        da_raw = raw.get('da')
        da     = wma_da if wma_da is not None else None
        td_raw = raw.get('td')
        td     = wma_td if wma_td is not None else None
        ta_raw = raw.get('ta')
        ta     = wma_ta if wma_ta is not None else None

        if extra_sample_t is not None:
            pp_raw_e = pp_raw
            pp_e     = wma_pp_e if wma_pp_e is not None else None
            tg_raw_e = tg_raw
            tg_e     = wma_tg_e if wma_tg_e is not None else None
            da_raw_e = da_raw
            da_e     = wma_da_e if wma_da_e is not None else None
            td_raw_e = td_raw
            td_e     = wma_td_e if wma_td_e is not None else None
            ta_raw_e = ta_raw
            ta_e     = wma_ta_e if wma_ta_e is not None else None
            self._chart.add_point(pp_raw_e, pp_e, tg_raw_e, tg_e, da_raw_e, da_e, td_raw_e, td_e, ta_raw_e, ta_e, sample_t=extra_sample_t)
        self._chart.add_point(pp_raw, pp, tg_raw, tg, da_raw, da, td_raw, td, ta_raw, ta, sample_t=now)
        self._update_gauges({'pp': pp, 'tg': tg, 'td': td, 'ta': ta, 'da': da}, fresh)

    def _update_gauges(self, values, fresh):
        """Update gauge labels and progress bars from smoothed graph values."""
        for key, fmt, bright, dim in [
            ('pp', 'PP:  {:.1f} tok/s', MetricsChart.C_PROMPT, MetricsChart.C_PROMPT_RAW),
            ('tg', 'TG:  {:.1f} tok/s', MetricsChart.C_GEN, MetricsChart.C_GEN_RAW),
            ('td', 'TD:  {:.1f} tok/s', MetricsChart.C_DRAFT_GEN, MetricsChart.C_DRAFT_GEN_RAW),
            ('ta', 'TA:  {:.1f} tok/s', MetricsChart.C_DRAFT_ACC, MetricsChart.C_DRAFT_ACC_RAW),
            ('da', 'DA:  {:.1f}%', MetricsChart.C_DRAFT, MetricsChart.C_DRAFT_RAW),
        ]:
            g = self._gauges.get(key)
            if not g:
                continue

            val = values.get(key)
            if val is None:
                val = self._gauge_last.get(key)
                if val is None:
                    g['lbl'].config(text='N/A')
                    g['bar']['value'] = 0
                    continue
            else:
                self._gauge_last[key] = val

            v = max(val, 0.0)
            g['lbl'].config(text=fmt.format(v), foreground=bright if fresh.get(key) else dim)

            # Adaptive max — expand when value exceeds 80 % of current ceiling
            max_seen = self._gauge_max_seen.get(key, 100.0)
            if v > max_seen:
                max_seen = v
                self._gauge_max_seen[key] = max_seen
            ceiling = max_seen * 1.2
            g['bar']['maximum'] = max(ceiling, 1.0)
            g['bar']['value'] = v

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
            led_color = 'green' if status == 'ok' else 'red'
            self._lbl_status.config(text='Connected' if status == 'ok' else status,
                                    foreground='green' if status == 'ok' else 'red')
        else:
            led_color = 'gray'
            self._lbl_status.config(text='Disconnected', foreground='gray')
        self._set_led(led_color)

    def _set_led(self, color):
        self._status_led.delete('all')
        self._status_led.create_oval(2, 2, 14, 14, fill=color, outline='')

    def _apply_metrics(self, parsed):
        now = time.monotonic()
        # Detect monotonic counters from /metrics Prometheus output.
        pp_total = parsed.get('prompt_tokens_total')
        pp_time  = parsed.get('prompt_seconds_total')
        tg_total = parsed.get('tokens_predicted_total')
        tg_time  = parsed.get('tokens_predicted_seconds_total')
        td_total = parsed.get('n_tokens_draft')
        td_time  = tg_time
        tda_total = parsed.get('n_tokens_draft_accepted', 0)
        tda_time  = td_time
        tdr_total = parsed.get('n_tokens_draft_rejected', 0)
        tdr_time  = td_time

        if pp_total is not None and tg_total is not None and td_total is not None:
            # Detect rollover (server reset) and reset accumulated values.
            if pp_total < self._prev_pp_total or tg_total < self._prev_tg_total:
                self._prev_pp_total = 0.0
                self._prev_pp_time = 0.0
                self._prev_tg_total = 0.0
                self._prev_tg_time = 0.0
                self._prev_td_total = 0.0
                self._prev_td_time = 0.0
                self._prev_tda_total = 0.0
                self._prev_tda_time = 0.0
                self._prev_tdr_total = 0.0
                self._prev_tdr_time = 0.0

            # Compute rates as counter deltas over time-counter deltas.
            # Only emit a sample when the time counter has increased since
            # the last poll; unchanged counters become gaps in the chart.
            pp_changed  = pp_time  is not None and pp_time  > self._prev_pp_time
            tg_changed  = tg_time  is not None and tg_time  > self._prev_tg_time
            td_changed  = td_time  is not None and td_time  > self._prev_td_time
            tda_changed = tda_time is not None and tda_time > self._prev_tda_time
            tdr_changed = tdr_time is not None and tdr_time > self._prev_tdr_time

            def _rate(total, prev_total, time_total, prev_time, changed):
                if not changed:
                    return None
                dt = time_total - prev_time
                if dt <= 0:
                    return None
                return max(0.0, total - prev_total) / dt

            pp_rate  = _rate(pp_total, self._prev_pp_total, pp_time, self._prev_pp_time, pp_changed)
            tg_rate  = _rate(tg_total, self._prev_tg_total, tg_time, self._prev_tg_time, tg_changed)
            td_rate  = _rate(td_total, self._prev_td_total, td_time, self._prev_td_time, td_changed)
            tda_rate = _rate(tda_total, self._prev_tda_total, tda_time, self._prev_tda_time, tda_changed)
            tdr_rate = _rate(tdr_total, self._prev_tdr_total, tdr_time, self._prev_tdr_time, tdr_changed)

            raw = {'pp': pp_rate, 'tg': tg_rate, 'td': td_rate, 'ta': tda_rate, 'da': None}

            # Compute WMA values from existing buffer (before appending new samples)
            cutoff_pp = now - self._graph_smooth_ms_pp / 1000.0
            cutoff_tg = now - self._graph_smooth_ms_tg / 1000.0

            def _wma(buf, cutoff, max_t=None):
                if not buf:
                    return None
                if not isinstance(cutoff, (int, float)):
                    return None
                window = [v for t, v in buf if t >= cutoff and (max_t is None or t <= max_t)]
                if not window:
                    return None
                n = len(window)
                weights = [i + 1 for i in range(n)]
                return sum(v * w for v, w in zip(window, weights)) / sum(weights)

            # Draft acceptance % — compute whenever rates are available.
            if tda_rate is not None and tdr_rate is not None:
                total_rej = tda_rate + tdr_rate
                if total_rej > 0:
                    pct = min(100.0, tda_rate / total_rej * 100)
                    raw['da'] = max(0.0, pct)

            fresh = {key: value is not None for key, value in raw.items()}
            wma_pp_now   = _wma(self._raw_prompt, cutoff_pp, now) if fresh['pp'] else None
            wma_tg_now   = _wma(self._raw_gen, cutoff_tg, now) if fresh['tg'] else None
            wma_da_now   = _wma(self._raw_draft, cutoff_tg, now) if fresh['da'] else None
            wma_td_now   = _wma(self._raw_draft_gen, cutoff_tg, now) if fresh['td'] else None
            wma_ta_now   = _wma(self._raw_draft_acc, cutoff_tg, now) if fresh['ta'] else None

            # Determine extra_sample_t from the smallest dt among changed metrics
            extra_sample_t = None
            min_dt = None
            if pp_rate is not None and pp_changed:
                dt = pp_time - self._prev_pp_time
                if min_dt is None or dt < min_dt:
                    min_dt = dt
            if tg_rate is not None and tg_changed:
                dt = tg_time - self._prev_tg_time
                if min_dt is None or dt < min_dt:
                    min_dt = dt
            if td_rate is not None and td_changed:
                dt = td_time - self._prev_td_time
                if min_dt is None or dt < min_dt:
                    min_dt = dt
            if tda_rate is not None and tda_changed:
                dt = tda_time - self._prev_tda_time
                if min_dt is None or dt < min_dt:
                    min_dt = dt
            if min_dt is not None:
                extra_sample_t = now - min_dt

            # Compute extra-sample WMA from pre-existing buffer (before appending new samples)
            wma_pp_e = _wma(self._raw_prompt, extra_sample_t - self._graph_smooth_ms_pp / 1000.0, extra_sample_t) if fresh.get('pp') else None
            wma_tg_e = _wma(self._raw_gen, extra_sample_t - self._graph_smooth_ms_tg / 1000.0, extra_sample_t) if fresh.get('tg') else None
            wma_da_e = _wma(self._raw_draft, extra_sample_t - self._graph_smooth_ms_tg / 1000.0, extra_sample_t) if fresh.get('da') else None
            wma_td_e = _wma(self._raw_draft_gen, extra_sample_t - self._graph_smooth_ms_tg / 1000.0, extra_sample_t) if fresh.get('td') else None
            wma_ta_e = _wma(self._raw_draft_acc, extra_sample_t - self._graph_smooth_ms_tg / 1000.0, extra_sample_t) if fresh.get('ta') else None

            # Append new samples to buffers
            if pp_rate is not None and pp_changed:
                self._raw_prompt.append((now, pp_rate))
            if tg_rate is not None and tg_changed:
                self._raw_gen.append((now, tg_rate))
            if td_rate is not None and td_changed:
                self._raw_draft_gen.append((now, td_rate))
            if tda_rate is not None and tda_changed:
                self._raw_draft_acc.append((now, tda_rate))

            # Draft acceptance raw samples — only when draft time has advanced.
            if raw.get('da') is not None and tda_changed:
                self._raw_draft.append((now, raw['da']))

            self._push_graph_point(raw, extra_sample_t=extra_sample_t,
                                   wma_pp=wma_pp_now, wma_tg=wma_tg_now,
                                   wma_da=wma_da_now, wma_td=wma_td_now,
                                   wma_ta=wma_ta_now,
                                   wma_pp_e=wma_pp_e, wma_tg_e=wma_tg_e,
                                   wma_da_e=wma_da_e, wma_td_e=wma_td_e,
                                   wma_ta_e=wma_ta_e)

            if pp_rate is not None:
                self._prev_pp_total = pp_total
                self._prev_pp_time = pp_time
            if tg_rate is not None:
                self._prev_tg_total = tg_total
                self._prev_tg_time = tg_time
            if td_rate is not None:
                self._prev_td_total = td_total
                self._prev_td_time = td_time
            if tda_rate is not None:
                self._prev_tda_total = tda_total
                self._prev_tda_time = tda_time
            if tdr_rate is not None:
                self._prev_tdr_total = tdr_total
                self._prev_tdr_time = tdr_time
            self._using_event_metrics = True

        n_ctx_size = int(parsed.get('n_ctx_size', 0))
        if n_ctx_size > 0:
            n_slots = max(len(self._slot_widgets), 1)
            self._n_ctx_fallback = n_ctx_size // n_slots

        # ── Per-slot values from labeled Prometheus metrics ──────────────────
        # Keys look like:  slot_prompt_tokens_processed{id_slot="3"}
        slot_label_pat = re.compile(r'^slot_(\w+)\{id_slot="(\d+)"\}$')
        slot_values = {}  # sid -> {metric_name: int_value}
        for key, value in parsed.items():
            m = slot_label_pat.match(key)
            if m:
                metric = m.group(1)
                sid = int(m.group(2))
                slot_values.setdefault(sid, {})[metric] = int(value)

        for sid, vals in slot_values.items():
            if sid not in self._slot_widgets:
                self._create_slot_row(sid)

            pp   = vals.get('prompt_tokens_processed', 0)
            plen = vals.get('prompt_length', 0)
            gen  = vals.get('tokens_predicted', 0)
            n_ctx = self._slot_n_ctx.get(sid, self._n_ctx_fallback) or 1

            # Cache prompt length so it survives task release
            if plen > 0:
                self._slot_prompt_length[sid] = plen
            cached_plen = self._slot_prompt_length.get(sid, 0)

            self._slot_bar_data[sid] = {
                'n_prompt_length':          max(cached_plen, plen),
                'n_prompt_tokens_processed': pp,
                'n_decoded':                gen,
                'n_ctx':                    n_ctx,
            }
            self._redraw_slot_bar(sid)

            w = self._slot_widgets[sid]
            self._set_slot_ctx_cells(w, pp, gen, n_ctx)

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

            # Cache n_ctx per slot
            n_ctx = slot.get('n_ctx', 0)
            if n_ctx > 0:
                self._slot_n_ctx[sid] = n_ctx

            # Sticky PROC: keep showing for 5 s after last seen processing
            is_proc = slot.get('is_processing', False)
            if is_proc:
                self._slot_last_proc[sid] = time.monotonic()
            show_proc = is_proc or (time.monotonic() - self._slot_last_proc.get(sid, 0) < 5.0)

            w = self._slot_widgets[sid]
            w['lbl_state'].config(
                text='PROC' if show_proc else 'IDLE',
                foreground='green' if show_proc else 'gray')

        for sid in list(self._slot_widgets):
            if sid not in seen:
                self._slot_widgets[sid]['frame'].destroy()
                del self._slot_widgets[sid]
                self._slot_bar_data.pop(sid, None)
                self._slot_prompt_length.pop(sid, None)
                self._slot_last_proc.pop(sid, None)
                self._slot_n_ctx.pop(sid, None)

    def _create_slot_row(self, sid):
        f = ttk.Frame(self._slots_inner)
        f.pack(fill='x', pady=1)

        ttk.Label(f, text=f'#{sid}', width=4, anchor='w').grid(row=0, column=0, padx=(0, 2))

        lbl_state = ttk.Label(f, text='IDLE', width=5, anchor='w')
        lbl_state.grid(row=0, column=1, padx=(0, 2))

        canvas = tk.Canvas(f, height=20, highlightthickness=0)
        canvas.grid(row=0, column=2, sticky='ew', padx=(0, 4))
        canvas.bind('<Configure>', lambda e, s=sid: self._redraw_slot_bar(s))

        lbl_pp   = ttk.Label(f, text='', width=4, anchor='e')
        lbl_gen  = ttk.Label(f, text='', width=4, anchor='e')
        lbl_max  = ttk.Label(f, text='', width=4, anchor='e')
        lbl_pp.grid( row=0, column=3, padx=2)
        lbl_gen.grid(row=0, column=4, padx=2)
        lbl_max.grid( row=0, column=5, padx=(2, 4))

        f.columnconfigure(2, weight=1)

        self._slot_widgets[sid] = {
            'frame':     f,
            'lbl_state': lbl_state,
            'canvas':    canvas,
            'lbl_pp':    lbl_pp,
            'lbl_gen':   lbl_gen,
            'lbl_max':   lbl_max,
        }

    @staticmethod
    def _kt(v: int) -> str:
        """Integer in kTokens as a fixed-width 4-char label."""
        return str(round(v / 1000))

    def _set_slot_ctx_cells(self, w, n_pp: int, n_gen: int, n_max: int):
        w['lbl_pp' ].config(text=self._kt(n_pp))
        w['lbl_gen'].config(text=self._kt(n_gen))
        w['lbl_max'].config(text=self._kt(n_max))

    def _redraw_slot_bar(self, sid):
        """Redraw the multi-colored slot progress bar on the slot's canvas."""
        w = self._slot_widgets.get(sid)
        if not w:
            return
        canvas = w.get('canvas')
        if not canvas:
            return

        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 10 or ch < 5:
            return

        data = self._slot_bar_data.get(sid, {})
        n_prompt_length           = data.get('n_prompt_length', 0)
        n_prompt_tokens_processed = data.get('n_prompt_tokens_processed', 0)
        n_decoded                 = data.get('n_decoded', 0)
        n_ctx                     = data.get('n_ctx', 0) or self._n_ctx_fallback

        # Scale is always n_ctx (the fixed per-slot context size).
        # This keeps the bar consistent across requests.
        scale = max(n_ctx, 1)

        # Colours — match the chart palette
        bg       = '#3a3a3a'
        c_pp     = '#4e9eff'   # blue — pre-processed prompt
        c_tg     = '#4ec94e'   # green — generated tokens
        c_marker = '#ffffff'   # prompt-length reference line

        canvas.delete('all')

        # Bar background
        canvas.create_rectangle(0, 0, cw, ch, fill=bg, outline='')

        # Pre-processed segment (blue)
        x_pp = int(n_prompt_tokens_processed / scale * cw)
        if x_pp > 0:
            canvas.create_rectangle(0, 0, min(x_pp, cw), ch, fill=c_pp, outline='')

        # Generated segment (green, starts where pre-processed ends)
        x_tg = int((n_prompt_tokens_processed + n_decoded) / scale * cw)
        if x_tg > x_pp:
            canvas.create_rectangle(x_pp, 0, min(x_tg, cw), ch, fill=c_tg, outline='')

        # Prompt-length reference marker (thin vertical line)
        x_ref = int(n_prompt_length / scale * cw)
        if 0 < x_ref < cw:
            canvas.create_line(x_ref, 0, x_ref, ch, fill=c_marker, width=1)

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

    def stop(self):
        self._stop_monitoring()
