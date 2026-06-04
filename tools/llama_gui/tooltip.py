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
        self._window = tk.Toplevel(self._widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f'+{x}+{y}')
        self._window.attributes('-topmost', True)
        label = tk.Label(self._window, text=self._text, justify='left',
                         background='#ffffea', foreground='#333',
                         relief='solid', borderwidth=1,
                         wraplength=420,
                         padx=8, pady=6)
        label.pack()

    def _hide(self, event=None):
        if self._window:
            self._window.destroy()
            self._window = None
