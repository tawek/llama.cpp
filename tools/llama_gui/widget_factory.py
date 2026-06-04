"""
Widget factory - creates control widgets for config options.
"""

import tkinter as tk
from tkinter import ttk, filedialog


# Per-option file type filter presets
# None = directory dialog, empty list = all files only
_FILE_FILTERS = {
    'model': [('GGUF files', '*.gguf'), ('All files', '*.*')],
    'spec_draft_model': [('GGUF files', '*.gguf'), ('All files', '*.*')],
    'mmproj': [('GGUF files', '*.gguf'), ('All files', '*.*')],
    'lora': [('GGUF files', '*.gguf'), ('All files', '*.*')],
    'image': [('Image files', '*.png *.jpg *.jpeg *.bmp *.tiff *.webp'), ('All files', '*.*')],
    'audio': [('Audio files', '*.wav *.mp3 *.ogg *.flac *.m4a'), ('All files', '*.*')],
    'grammar_file': [('Grammar files', '*.gbnf'), ('Text files', '*.txt'), ('All files', '*.*')],
    'json_schema_file': [('JSON files', '*.json'), ('All files', '*.*')],
    'file': [('Text files', '*.txt'), ('All files', '*.*')],
    'in_file': [('Text files', '*.txt'), ('All files', '*.*')],
    'chat_template_file': [('Jinja files', '*.jinja'), ('Text files', '*.txt'), ('All files', '*.*')],
    'ssl_key': [('PEM files', '*.pem'), ('Key files', '*.key'), ('All files', '*.*')],
    'ssl_cert': [('PEM files', '*.pem'), ('Cert files', '*.crt'), ('All files', '*.*')],
    'slot_save_path': None,  # directory dialog
}


class _FileSelector(ttk.Frame):
    """File selector with browse button."""

    def __init__(self, parent, main_window, filetypes=None, is_dir=False, **kwargs):
        super().__init__(parent, **kwargs)
        self.path = tk.StringVar()
        self._main_window = main_window
        self._filetypes = filetypes if filetypes else [('All files', '*.*')]
        self._is_dir = is_dir
        ttk.Entry(self, textvariable=self.path, width=30).pack(
            side='left', fill='x', expand=True)
        ttk.Button(self, text='...', command=self._browse).pack(side='right')

    def _browse(self):
        if self._is_dir:
            path = filedialog.askdirectory(
                title='Select directory',
                master=self._main_window)
        else:
            path = filedialog.askopenfilename(
                title='Select file',
                filetypes=self._filetypes,
                master=self._main_window)
        if path:
            self.path.set(path)
            if hasattr(self, '_on_select'):
                self._on_select(path)


class _OrderedListSelector(ttk.Frame):
    """Dual-list selector for ordered comma-separated values."""

    def __init__(self, parent, items=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._all_items = list(items) if items else []
        self._value = tk.StringVar(value='')
        self._build_ui()

    def _build_ui(self):
        # Available list
        left = ttk.Frame(self)
        left.pack(side='left', fill='both', expand=True)
        ttk.Label(left, text='Available:', font=('', 8)).pack(anchor='w')
        self._avail_list = tk.Listbox(left, height=6, width=16,
                                       font=('', 9))
        self._avail_list.pack(fill='both', expand=True)
        for item in self._all_items:
            self._avail_list.insert('end', item)

        # Middle buttons
        mid = ttk.Frame(self)
        mid.pack(side='left', fill='y', padx=4)
        ttk.Button(mid, text='>>', width=3,
                    command=self._add_selected).pack(pady=(20, 2))
        ttk.Button(mid, text='<<', width=3,
                    command=self._remove_selected).pack(pady=2)

        # Selected list
        right = ttk.Frame(self)
        right.pack(side='left', fill='both', expand=True)
        ttk.Label(right, text='Selected (priority):', font=('', 8)).pack(anchor='w')
        self._sel_list = tk.Listbox(right, height=6, width=16,
                                     font=('', 9))
        self._sel_list.pack(fill='both', expand=True)

        # Up/Down buttons below selected
        btnf = ttk.Frame(right)
        btnf.pack(fill='x', pady=(2, 0))
        ttk.Button(btnf, text='Up', width=4,
                    command=self._move_up).pack(side='left', padx=1)
        ttk.Button(btnf, text='Down', width=4,
                    command=self._move_down).pack(side='left', padx=1)

    def _sync_value(self):
        items = [self._sel_list.get(i) for i in range(self._sel_list.size())]
        self._value.set(','.join(items))

    def _add_selected(self):
        sel = self._avail_list.curselection()
        if not sel:
            return
        idx = sel[0]
        item = self._avail_list.get(idx)
        self._avail_list.delete(idx)
        self._sel_list.insert('end', item)
        self._sync_value()

    def _remove_selected(self):
        sel = self._sel_list.curselection()
        if not sel:
            return
        idx = sel[0]
        item = self._sel_list.get(idx)
        self._sel_list.delete(idx)
        # Reinsert into available in sorted order
        for i, avail in enumerate(self._all_items):
            if item == avail:
                self._avail_list.insert(i, item)
                break
        self._sync_value()

    def _move_up(self):
        sel = self._sel_list.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        item = self._sel_list.get(idx)
        self._sel_list.delete(idx)
        self._sel_list.insert(idx - 1, item)
        self._sel_list.selection_set(idx - 1)
        self._sync_value()

    def _move_down(self):
        sel = self._sel_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= self._sel_list.size() - 1:
            return
        item = self._sel_list.get(idx)
        self._sel_list.delete(idx)
        self._sel_list.insert(idx + 1, item)
        self._sel_list.selection_set(idx + 1)
        self._sync_value()

    def set_items(self, items_str):
        items = [i.strip() for i in items_str.split(',') if i.strip()]
        self._avail_list.delete(0, 'end')
        self._sel_list.delete(0, 'end')
        selected_set = set(items)
        for item in self._all_items:
            if item in selected_set:
                self._sel_list.insert('end', item)
            else:
                self._avail_list.insert('end', item)
        self._sync_value()


class OptionWidget:
    """Creates and manages a control widget (no label)."""

    def __init__(self, parent, widget_type, default, choices=None,
                 main_window=None, option_key=None):
        self.parent = parent
        self.widget_type = widget_type
        self.default = default
        self.choices = choices
        self._var = None
        self.widget = None
        self._option_key = option_key or ''
        self._create(main_window)

    def _create(self, main_window):
        if self.widget_type in ('file', 'directory'):
            ft = _FILE_FILTERS.get(self._option_key)
            is_dir = ft is None and self._option_key in _FILE_FILTERS
            self.widget = _FileSelector(self.parent, main_window,
                                        filetypes=ft if not is_dir else None,
                                        is_dir=is_dir)
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

        elif self.widget_type == 'ordered_list_of_options':
            self.widget = _OrderedListSelector(self.parent,
                                                items=self.choices)
            self._var = self.widget._value

        elif self.widget_type in ('spin', 'float_spin'):
            self._var = tk.StringVar(value='')
            self.widget = tk.Entry(self.parent,
                                    textvariable=self._var, width=14)

        elif self.widget_type == 'text':
            self._var = tk.StringVar(value='')
            self.widget = tk.Entry(self.parent,
                                    textvariable=self._var, width=28)

        elif self.widget_type == 'multiline_text':
            f = ttk.Frame(self.parent)
            self._text_widget = tk.Text(f, height=4, wrap='word',
                                         font=('Consolas', 9))
            sc = ttk.Scrollbar(f, orient='vertical',
                                command=self._text_widget.yview)
            self._text_widget.configure(yscrollcommand=sc.set)
            self._text_widget.pack(side='left', fill='both', expand=True)
            sc.pack(side='right', fill='y')
            self.widget = f

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
        if self.widget_type == 'multiline_text':
            raw = self._text_widget.get('1.0', 'end-1c').strip()
            return raw if raw else None
        if self.widget_type == 'ordered_list_of_options':
            raw = self._var.get().strip()
            return raw if raw else None
        if self.widget_type == 'spin':
            raw = self._var.get().strip()
            return int(raw) if raw else None
        if self.widget_type == 'float_spin':
            raw = self._var.get().strip()
            return float(raw) if raw else None
        return self.default

    def set_value(self, value):
        if self.widget_type == 'file':
            self.widget.path.set(str(value) if value is not None else '')
        elif self.widget_type == 'checkbox':
            self._var.set(str(value) if value is not None else '')
        elif self.widget_type == 'radio':
            self._var.set(str(value) if value is not None else '')
        elif self.widget_type == 'dropdown':
            vals = self.widget.cget('values')
            if str(value) in vals:
                self.widget.set(str(value))
            elif vals:
                self.widget.set('')
        elif self.widget_type in ('text',):
            self._var.set(str(value) if value is not None else '')
        elif self.widget_type == 'multiline_text':
            self._text_widget.delete('1.0', 'end')
            if value is not None and value != '':
                self._text_widget.insert('1.0', str(value))
        elif self.widget_type == 'ordered_list_of_options':
            self.widget.set_items(str(value) if value is not None else '')
        elif self.widget_type in ('spin', 'float_spin'):
            if value is not None and value != '':
                self._var.set(str(value))
            else:
                self._var.set('')
