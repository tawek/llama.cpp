import tkinter as tk


class Tooltip:
    """Hover tooltip for a widget."""

    def __init__(self, widget, text):
        self._widget = widget
        self._text = text
        self._window = None
        widget.bind('<Enter>', self._show, add='+')
        widget.bind('<Leave>', self._hide, add='+')

    def _show(self, event=None):
        if self._window or not self._text:
            return
        x = self._widget.winfo_rootx() + 18
        y = self._widget.winfo_rooty() + 22
        # Pick colors to match the active Azure theme variant
        try:
            theme = str(self._widget.tk.call('ttk::style', 'theme', 'use'))
            dark = 'dark' in theme
        except Exception:
            dark = False
        bg = '#2d2d2d' if dark else '#ffffea'
        fg = '#e0e0e0' if dark else '#333333'
        self._window = tk.Toplevel(self._widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f'+{x}+{y}')
        self._window.attributes('-topmost', True)
        label = tk.Label(self._window, text=self._text, justify='left',
                         background=bg, foreground=fg,
                         relief='solid', borderwidth=1,
                         wraplength=420,
                         padx=8, pady=6)
        label.pack()

    def _hide(self, event=None):
        if self._window:
            self._window.destroy()
            self._window = None
