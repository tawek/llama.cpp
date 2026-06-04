"""
Widget factory - creates control widgets for config options.
"""

import tkinter as tk
from tkinter import ttk, filedialog


class _FileSelector(ttk.Frame):
    """File selector with browse button."""

    def __init__(self, parent, main_window, **kwargs):
        super().__init__(parent, **kwargs)
        self.path = tk.StringVar()
        self._main_window = main_window
        ttk.Entry(self, textvariable=self.path, width=30).pack(
            side='left', fill='x', expand=True)
        ttk.Button(self, text='...', command=self._browse).pack(side='right')

    def _browse(self):
        path = filedialog.askopenfilename(
            title='Select file',
            filetypes=[('All files', '*.*'), ('GGUF files', '*.gguf')],
            master=self._main_window)
        if path:
            self.path.set(path)
            if hasattr(self, '_on_select'):
                self._on_select(path)


class OptionWidget:
    """Creates and manages a control widget (no label)."""

    def __init__(self, parent, widget_type, default, choices=None,
                 main_window=None):
        self.parent = parent
        self.widget_type = widget_type
        self.default = default
        self.choices = choices
        self._var = None
        self.widget = None
        self._create(main_window)

    def _create(self, main_window):
        if self.widget_type == 'file':
            self.widget = _FileSelector(self.parent, main_window)
            self.widget._on_select = lambda p: None

        elif self.widget_type == 'dropdown':
            self.widget = ttk.Combobox(self.parent, values=self.choices or [],
                                       state='readonly', width=28)

        elif self.widget_type == 'checkbox':
            self._var = tk.StringVar(value='')
            self.widget = ttk.Combobox(self.parent,
                                       values=['', 'on', 'off'],
                                       state='readonly', width=10)

        elif self.widget_type == 'radio':
            self._var = tk.StringVar(value='')
            f = ttk.Frame(self.parent)
            for choice in self.choices or []:
                rb = ttk.Radiobutton(f, text=str(choice), variable=self._var,
                                     value=str(choice))
                rb.pack(side='left', padx=(0, 8))
            self.widget = f

        elif self.widget_type in ('spin', 'float_spin'):
            self._var = tk.StringVar(value='')
            self.widget = tk.Entry(self.parent,
                                   textvariable=self._var, width=14)

        elif self.widget_type == 'text':
            self._var = tk.StringVar(value='')
            self.widget = tk.Entry(self.parent,
                                   textvariable=self._var, width=28)

    def get_value(self):
        if self.widget_type == 'file':
            return self.widget.path.get()
        if self.widget_type == 'checkbox':
            return self._var.get()
        if self.widget_type == 'radio':
            raw = self._var.get().strip()
            return raw if raw else None
        if self.widget_type == 'dropdown':
            return self.widget.get()
        if self.widget_type == 'text':
            raw = self._var.get().strip()
            return raw if raw else None
        if self.widget_type == 'spin':
            raw = self._var.get().strip()
            return int(raw) if raw else None
        if self.widget_type == 'float_spin':
            raw = self._var.get().strip()
            return float(raw) if raw else None
        return self.default
