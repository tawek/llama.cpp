"""
Section builder - creates collapsible sections for config tab.
"""

import tkinter as tk
from tkinter import ttk


class SectionBuilder:
    """Creates a collapsible section within a parent frame."""

    def __init__(self, parent, title):
        self.parent = parent
        self.title = title
        self.content_frame = None
        self._create_ui()

    def _create_ui(self):
        # Section header with toggle
        header = ttk.Frame(self.parent)
        header.pack(fill='x', padx=2, pady=(4, 0))

        self.toggle_var = tk.BooleanVar(value=True)
        cb = tk.Checkbutton(header, variable=self.toggle_var,
                            command=self._toggle, width=1)
        cb.pack(side='left')
        ttk.Label(header, text=self.title,
                  font=('Segoe UI', 9, 'bold')).pack(side='left')

        # Content frame (initially visible)
        self.content_frame = ttk.LabelFrame(self.parent, text='', padding=(4, 2))
        self.content_frame.pack(fill='x', padx=4, pady=2)
        self.content_frame.columnconfigure(0, weight=1)
        self._next_row = 0

    def _toggle(self):
        if self.toggle_var.get():
            self.content_frame.pack(fill='x', padx=4, pady=2)
        else:
            self.content_frame.pack_forget()

    def add_widget(self, widget, row=None, sticky='ew', **grid_kwargs):
        """Add a widget to this section's content frame."""
        if row is None:
            row = self._next_row
        else:
            self._next_row = max(self._next_row, row + 1)
        widget.grid(row=row, column=0, sticky=sticky, **grid_kwargs)
        self._next_row = max(self._next_row, row + 1)

    def add_collapsible_pane(self, pane):
        """Add a CollapsiblePane widget to this section using grid."""
        self.add_widget(pane, sticky='ew')

    def pack(self, **kwargs):
        """Pack the content frame."""
        self.content_frame.pack(**kwargs)

    @property
    def frame(self):
        """Return the content frame for direct access."""
        return self.content_frame

    @property
    def frame(self):
        """Return the content frame for direct access."""
        return self.content_frame

    @property
    def frame(self):
        """Return the content frame for direct access."""
        return self.content_frame


class CollapsiblePane(ttk.Frame):
    """A collapsible panel that contains toggle + separator + content frame.

    Uses grid internally so content stays at a fixed position within the panel,
    not repositioned in the parent when shown/hidden.
    """

    def __init__(self, parent, title, expanded=True, **kwargs):
        super().__init__(parent, **kwargs)
        self._expanded = expanded
        self.columnconfigure(1, weight=1)

        # Arrow label (clickable)
        self._arrow = ttk.Label(self, text='▾', cursor='hand2',
                                style='PanelArrow.TLabel')
        self._arrow.grid(row=0, column=0, sticky='w', padx=(4, 0), pady=(8, 2))
        self._arrow.bind('<Button-1>', lambda e: self.toggle())

        # Title
        self._title = ttk.Label(self, text=title,
                                font=('Segoe UI', 9, 'bold'))
        self._title.grid(row=0, column=1, sticky='w', padx=(4, 0))

        # Separator
        self._sep = ttk.Separator(self, orient='horizontal')
        self._sep.grid(row=0, column=2, sticky='ew', padx=(8, 0))

        # Content frame
        self.content_frame = ttk.Frame(self)
        self.content_frame.columnconfigure(0, weight=1)
        self._update_display()

    def _update_display(self):
        self._arrow.configure(text='▾' if self._expanded else '▸')
        if self._expanded:
            self.content_frame.grid(row=1, column=0, columnspan=3,
                                    sticky='ew', padx=4, pady=(0, 4))
        else:
            self.content_frame.grid_forget()

    def toggle(self):
        self._expanded = not self._expanded
        self._update_display()

    def add_option(self, widget, **kw):
        """Add an OptionWidget to this panel's content frame."""
        widget.grid(in_=self.content_frame, **kw)
