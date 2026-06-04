"""
Logs tab - real-time log display with filtering and statistics.
Uses log_parser to extract metrics from server output.
"""

import tkinter as tk
from tkinter import ttk
from log_parser import parse_line, LogMetrics


class LogsTab(ttk.Frame):
    """Log viewer with filtering and stats."""

    def __init__(self, parent, main_window=None):
        super().__init__(parent)
        self._main_window = main_window
        self._metrics = LogMetrics()
        self._filter_level = 'all'
        self._build_ui()

    def _build_ui(self):
        # Filter controls
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

        ttk.Button(ctrl_frame, text='Clear', command=self._clear_logs).pack(side='right', padx=2)
        ttk.Button(ctrl_frame, text='Save Log', command=self._save_log).pack(side='right')

        # Log text area
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

        # Stats bar
        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill='x', padx=4, pady=2)

        self._stats_label = ttk.Label(stats_frame, text='No logs yet',
                                       relief='sunken', anchor='w')
        self._stats_label.pack(fill='x')

    def add_log_line(self, line):
        """Add a line to the log display."""
        self._log_text.configure(state='normal')

        # Apply filter
        level = self._detect_level(line)
        if self._filter_var.get() != 'all' and level != self._filter_var.get():
            self._log_text.configure(state='disabled')
            return

        # Add timestamp
        import time
        timestamp = time.strftime('%H:%M:%S')
        display_line = f'[{timestamp}] {line}\n'
        self._log_text.insert(tk.END, display_line)

        # Parse metrics
        event = parse_line(line, self._metrics)
        if event:
            self._update_stats()

        # Auto-scroll
        self._log_text.see(tk.END)
        self._log_text.configure(state='disabled')

        # Limit lines to prevent memory issues
        max_lines = 10000
        line_count = int(self._log_text.index('end-1c').split('.')[0])
        if line_count > max_lines:
            self._log_text.delete('1.0', f'{max_lines // 2}.0')

    def _detect_level(self, line):
        """Detect log level from line content."""
        upper = line.upper()
        if 'ERROR' in upper or 'FAIL' in upper:
            return 'error'
        if 'WARN' in upper:
            return 'warn'
        if 'INFO' in upper:
            return 'info'
        return 'info'

    def _update_stats(self):
        """Update statistics display."""
        avg_prompt = self._metrics.avg_prompt_per_second
        avg_gen = self._metrics.avg_gen_per_second
        avg_draft = self._metrics.avg_draft_acceptance

        parts = [
            f'Avg Prompt: {avg_prompt:.1f} tok/s',
            f'Avg Gen: {avg_gen:.1f} tok/s',
            f'Draft: {avg_draft * 100:.1f}%',
            f'Checkpoints: {self._metrics.checkpoints_created}',
            f'Cache: {self._metrics.cache_size_mib:.1f} MiB',
        ]
        self._stats_label.config(text=' | '.join(parts))

    def _clear_logs(self):
        """Clear all logs and reset metrics."""
        self._log_text.configure(state='normal')
        self._log_text.delete('1.0', tk.END)
        self._log_text.configure(state='disabled')
        self._metrics = LogMetrics()
        self._stats_label.config(text='Cleared')

    def _save_log(self):
        """Save logs to file."""
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

    def set_metrics(self, metrics):
        """Set metrics from external parser."""
        self._metrics = metrics
        self._update_stats()
