"""
Logs tab - real-time log display with filtering and statistics.
Uses log_parser to extract metrics from server output.
"""

import time
import tkinter as tk
from tkinter import ttk
from log_parser import parse_line, LogMetrics


class LogsTab(ttk.Frame):
    """Log viewer with filtering and stats."""

    # Lines inserted per async-populate chunk (keeps each tick < ~20 ms)
    _POPULATE_CHUNK = 100
    # Max lines shown on first tab switch (older history is in _log_lines, not widget)
    _MAX_INITIAL = 500

    def __init__(self, parent, main_window=None):
        super().__init__(parent)
        self._main_window = main_window
        self._metrics = LogMetrics()
        self._log_lines = []             # [(level, timestamp, text), ...]
        self._max_lines = 10000
        self._widget_line_count = 0      # tracked manually to avoid O(n) index()
        self._on_metrics_update = None   # optional callback(LogMetrics)
        # Widget population state — lines are kept out of the Text widget until
        # the tab is actually visible so Tk doesn't have to paint thousands of
        # hidden lines the moment the user switches to the tab.
        self._widget_ready = False       # True once initial populate has finished
        self._populating = False         # True while async batch-insert is running
        self._build_ui()
        # Trigger async population the first time the tab becomes visible
        self.bind('<Map>', self._on_map)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.pack(fill='x', padx=4, pady=2)

        ttk.Label(ctrl_frame, text='Filter:').pack(side='left')
        self._filter_var = tk.StringVar(value='all')
        filter_frame = ttk.Frame(ctrl_frame)
        filter_frame.pack(side='left', padx=4)

        for label, value in [('All', 'all'), ('Info', 'info'),
                                ('Warn', 'warn'), ('Error', 'error')]:
            ttk.Radiobutton(filter_frame, text=label,
                            variable=self._filter_var,
                            value=value).pack(side='left', padx=2)
        self._filter_var.trace_add('write', lambda *_: self._reapply_filter())

        ttk.Button(ctrl_frame, text='Clear',
                    command=self._clear_logs).pack(side='right', padx=2)
        ttk.Button(ctrl_frame, text='Save Log',
                    command=self._save_log).pack(side='right')

        text_frame = ttk.Frame(self)
        text_frame.pack(fill='both', expand=True, padx=4, pady=4)

        self._log_text = tk.Text(text_frame, wrap='none',
                                  font=('Consolas', 8), state='disabled')
        h_scroll = ttk.Scrollbar(text_frame, orient='horizontal',
                                  command=self._log_text.xview)
        v_scroll = ttk.Scrollbar(text_frame, orient='vertical',
                                  command=self._log_text.yview)
        self._log_text.configure(xscrollcommand=h_scroll.set,
                                  yscrollcommand=v_scroll.set)
        self._log_text.pack(side='left', fill='both', expand=True)
        h_scroll.pack(side='bottom', fill='x')
        v_scroll.pack(side='right', fill='y')

    # ── Visibility / async population ─────────────────────────────────────────

    def _on_map(self, event):
        """Fires when the tab becomes visible for the first time."""
        if event.widget is not self:
            return
        if not self._widget_ready and not self._populating:
            self._populating = True
            # Take a snapshot of lines accumulated so far, capped at MAX_INITIAL
            snapshot = self._log_lines[-self._MAX_INITIAL:]
            self.after(0, self._populate_chunk, snapshot, 0)

    def _populate_chunk(self, snapshot, start):
        """Insert _POPULATE_CHUNK lines from snapshot into the widget, then
        reschedule itself until done.  Yields back to the event loop between
        chunks so the UI stays responsive."""
        end = min(start + self._POPULATE_CHUNK, len(snapshot))
        cur_filter = self._filter_var.get()

        self._log_text.configure(state='normal')
        for level, timestamp, text in snapshot[start:end]:
            if cur_filter != 'all' and level != cur_filter:
                continue
            self._log_text.insert(tk.END, f'[{timestamp}] {text}\n')
            self._widget_line_count += 1

        if end >= len(snapshot):
            # Done — scroll to tail and mark widget as ready for live updates
            self._log_text.see(tk.END)
            self._log_text.configure(state='disabled')
            self._populating = False
            self._widget_ready = True
        else:
            self._log_text.configure(state='disabled')
            self.after(10, self._populate_chunk, snapshot, end)

    # ── Patterns whose lines are silently suppressed (server polling noise) ───

    _SUPPRESS = (
        'all slots are idle',
        'update_slots: all slots',
    )

    # ── Public API ────────────────────────────────────────────────────────────

    def add_log_line(self, line):
        """Add a line.  Always stores in _log_lines and parses metrics.
        Widget update is skipped while the tab is hidden or still populating."""
        lower = line.lower()
        if any(p in lower for p in self._SUPPRESS):
            return

        level = self._detect_level(line)
        timestamp = time.strftime('%H:%M:%S')
        self._log_lines.append((level, timestamp, line))

        if len(self._log_lines) > self._max_lines:
            self._log_lines = self._log_lines[self._max_lines // 2:]

        # Parse metrics regardless of widget state
        event = parse_line(line, self._metrics)
        if event and self._on_metrics_update:
            self._on_metrics_update(self._metrics)

        # Skip widget update until the tab is visible and fully populated
        if not self._widget_ready:
            return

        cur_filter = self._filter_var.get()
        if cur_filter != 'all' and level != cur_filter:
            return

        at_bottom = self._log_text.yview()[1] >= 0.99
        self._log_text.configure(state='normal')
        self._log_text.insert(tk.END, f'[{timestamp}] {line}\n')
        self._widget_line_count += 1

        if self._widget_line_count > self._max_lines:
            trim_to = self._max_lines // 2
            self._log_text.delete('1.0', f'{trim_to + 1}.0')
            self._widget_line_count -= trim_to

        if at_bottom:
            self._log_text.see(tk.END)
        self._log_text.configure(state='disabled')

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _reapply_filter(self):
        """Rebuild widget from stored lines (used when filter radio changes)."""
        if not self._widget_ready:
            return   # not visible yet — will be applied during populate
        self._log_text.configure(state='normal')
        self._log_text.delete('1.0', tk.END)
        self._widget_line_count = 0

        cur_filter = self._filter_var.get()
        for level, timestamp, text in self._log_lines:
            if cur_filter != 'all' and level != cur_filter:
                continue
            self._log_text.insert(tk.END, f'[{timestamp}] {text}\n')
            self._widget_line_count += 1

        self._log_text.see(tk.END)
        self._log_text.configure(state='disabled')

    def _detect_level(self, line):
        upper = line.upper()
        if 'ERROR' in upper or 'FAIL' in upper:
            return 'error'
        if 'WARN' in upper:
            return 'warn'
        return 'info'

    def _clear_logs(self):
        self._log_text.configure(state='normal')
        self._log_text.delete('1.0', tk.END)
        self._log_text.configure(state='disabled')
        self._log_lines.clear()
        self._widget_line_count = 0
        self._metrics = LogMetrics()
        if self._on_metrics_update:
            self._on_metrics_update(self._metrics)

    def _save_log(self):
        import tkinter.filedialog as filedialog
        path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            title='Save Log'
        )
        if path:
            content = self._log_text.get('1.0', tk.END)
            with open(path, 'w') as f:
                f.write(content)
