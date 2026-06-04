"""CollapsiblePane widget and option row helper."""

import tkinter as tk
from tkinter import ttk
from tooltip import Tooltip


def add_option_row(parent, label, widget, help_text, row, default=None):
    """Add a label: value (?) row to the parent grid."""
    if default is not None:
        display = f'{label} [{default}]:'
    else:
        display = label + ':'
    lbl = ttk.Label(parent, text=display, anchor='e')
    lbl.grid(row=row, column=0, padx=(4, 8), pady=2, sticky='e')
    widget.grid(row=row, column=1, padx=(0, 4), pady=2, sticky='ew')
    if help_text:
        tip = ttk.Label(parent, text='?', font=('', 8, 'bold'),
                        foreground='dodger blue', cursor='question_arrow')
        tip.grid(row=row, column=2, padx=(0, 6), pady=2)
        Tooltip(tip, help_text)
    parent.columnconfigure(1, weight=1)


class CollapsiblePane(ttk.LabelFrame):
    """A labeled frame with clickable toggle to show/hide content.

    The header (arrow + title) is always visible. Clicking on it
    expands or collapses the content area below the separator.
    """

    def __init__(self, parent, title, expanded=True):
        super().__init__(parent, text='', padding=(2, 2, 2, 4))
        self._expanded = expanded
        self.columnconfigure(1, weight=1)

        # Header row
        self._arrow = ttk.Label(self, text='▾', font=('', 8), cursor='hand2')
        self._arrow.grid(row=0, column=0, padx=(4, 2), pady=(4, 0))

        self._title = ttk.Label(self, text=title, font=('', 9, 'bold'),
                                cursor='hand2')
        self._title.grid(row=0, column=1, padx=(0, 4), pady=(4, 0),
                         sticky='w')
        self.columnconfigure(1, weight=1)

        for w in (self._arrow, self._title):
            w.bind('<Button-1>', lambda e: self.toggle())

        self._sep = ttk.Separator(self, orient='horizontal')
        self._sep.grid(row=1, column=0, columnspan=2, sticky='ew',
                       padx=4, pady=(4, 2))

        self._content = ttk.Frame(self)
        self._content.columnconfigure(1, weight=1)

        self._update()

    def toggle(self):
        self._expanded = not self._expanded
        self._update()

    def _update(self):
        self._arrow.configure(text='▾' if self._expanded else '▸')
        if self._expanded:
            self._content.grid(row=2, column=0, columnspan=2, sticky='ew',
                               padx=4, pady=(0, 4))
        else:
            self._content.grid_forget()

    def add_option(self, label, help_text, widget, row, default=None):
        """Add a label:value(?) row to this pane's content."""
        add_option_row(self._content, label, widget, help_text, row, default)

    @property
    def content_frame(self):
        return self._content
