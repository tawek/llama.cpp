"""
Configuration tab - uses CollapsiblePane for sections with label:value(?) rows.
"""

import os
import tkinter as tk
from tkinter import ttk

from config_registry import iter_options
from widget_factory import OptionWidget
from collapsible_pane import CollapsiblePane
from command_builder import build_command, update_preview
from profile_mgr import ProfileManager


# Section definitions: (title, [keys_or_sub_panels])
# Sub-panels: ('Sub Title', ['key1', 'key2', ...])
SECTIONS = [
    ('Model Loading', [
        'model', 'lora', 'lora_scaled', 'mmproj', 'image', 'audio',
        'mlock', 'mmap', 'direct_io', 'check_tensors',
        'tags', 'alias', 'override_kv', 'lora_init_without_apply']),
    ('GPU & Acceleration', [
        'gpu_layers', 'split_mode', 'tensor_split', 'main_gpu',
        'device', 'rpc', 'cpu_moe', 'n_cpu_moe',
        'fit', 'fit_print', 'fit_target', 'fit_ctx']),
    ('Cache & KV', [
        'cache_prompt', 'cache_reuse', 'cache_ram', 'cache_type_k',
        'cache_type_v', 'kv_unified', 'cache_idle_slots',
        'slot_save_path', 'ctx_checkpoints', 'checkpoint_every_n']),
    ('Context & Batch', [
        'ctx_size', 'batch_size', 'ubatch_size', 'predict', 'keep', 'swa_full']),
    ('CPU', [
        'threads', 'threads_batch', 'cpu_mask', 'cpu_range', 'cpu_strict',
        'prio', 'poll', 'prio_prompt', 'prio_predict', 'prio_batch', 'prio_draft']),
    ('RoPE & Scaling', [
        'rope_scaling', 'rope_scale', 'rope_freq_base', 'rope_freq_scale',
        'yarn_orig_ctx', 'yarn_ext_factor', 'yarn_attn_factor',
        'yarn_beta_fast', 'yarn_beta_slow',
        'grp_attn_n', 'grp_attn_w', 'flash_attn']),
    ('Sampling', [
        'temperature', 'top_k', 'top_p', 'min_p', 'top_n_sigma',
        'xtc_prob', 'xtc_threshold', 'typical',
        'adaptive_target', 'adaptive_decay', 'dynatemp_range', 'dynatemp_exp',
        'seed', 'samplers', 'sampler_seq']),
    ('Mirostat', [
        'mirostat', 'mirostat_lr', 'mirostat_ent']),
    ('Penalties', [
        'repeat_last_n', 'repeat_penalty', 'presence_penalty',
        'frequency_penalty', 'ignore_eos']),
    ('DRY', [
        'dry_multiplier', 'dry_base', 'dry_allowed_length',
        'dry_penalty_last_n', 'dry_sequence_breaker']),
    ('Grammar', [
        'logit_bias', 'grammar', 'grammar_file', 'json_schema', 'json_schema_file']),
    ('Speculative', [
        'spec_draft_model', 'spec_type', 'spec_draft_n_max',
        'spec_draft_n_min', 'spec_draft_p_split', 'spec_draft_p_min',
        'spec_draft_device', 'spec_draft_ngl']),
    ('Prompt/Input', [
        'prompt', 'system_prompt', 'file', 'in_file', 'binary_file',
        'reverse_prompt', 'escape', 'special',
        'interactive', 'interactive_first', 'multiline_input',
        'in_prefix', 'in_suffix', 'warmup', 'perf']),
    ('Chat', [
        'chat_template', 'chat_template_file',
        'reasoning_format', 'reasoning_budget', 'jinja', 'prefill_assistant']),
    ('Display', [
        'verbose_prompt', 'display_prompt', 'color',
        'slot_prompt_similarity', 'simple_io', 'show_timings']),
    ('Server', [
        'host', 'port', 'parallel', 'sequences', 'cont_batching',
        'timeout', 'threads_http', 'api_key',
        'ssl_key', 'ssl_cert', 'path', 'api_prefix',
        ('WebUI', ['webui', 'webui_config']),
        ('Server Features', ['tools', 'embedding', 'rerank',
                             'metrics', 'props', 'slots'])]),
    ('Embedding', [
        'pooling', 'attention']),
]


class ConfigTab(ttk.Frame):
    """Configuration tab with collapsible sections and help tooltips."""

    def __init__(self, parent, main_window=None):
        super().__init__(parent)
        self._main_window = main_window
        self._option_map = {}
        self._profile_mgr = ProfileManager()
        self._current_profile = 'Default'
        self._server_bin_var = tk.StringVar(value='llama-server')
        self._build_ui()

    def _build_ui(self):
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient='vertical',
                                  command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def _mw(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        def _b4(event):
            canvas.yview_scroll(-1, 'units')
        def _b5(event):
            canvas.yview_scroll(1, 'units')
        canvas.bind_all('<MouseWheel>', _mw)
        canvas.bind_all('<Button-4>', _b4)
        canvas.bind_all('<Button-5>', _b5)

        self._build_profile_bar(scroll_frame)
        self._build_sections(scroll_frame)
        self._build_preview(scroll_frame)
        self._bind_updates()
        self._refresh_profile_list()

    def _build_sections(self, parent):
        all_opts = dict(iter_options())

        for sec_idx, (section_title, keys) in enumerate(SECTIONS):
            pane = CollapsiblePane(parent, section_title, expanded=True)
            pane.grid(row=sec_idx + 2, column=0, sticky='ew', padx=6, pady=4)

            inner_row = 0
            for item in keys:
                if isinstance(item, tuple):
                    sub_title, sub_keys = item
                    sub_pane = CollapsiblePane(pane.content_frame,
                                               sub_title, expanded=True)
                    sub_pane.grid(row=inner_row, column=0, columnspan=3,
                                  sticky='ew', pady=(4, 0))
                    inner_row += 1
                    sub_inner = 0
                    for sk in sub_keys:
                        if sk not in all_opts:
                            continue
                        info = all_opts[sk]
                        self._add_option(pane, sk, info, sub_pane,
                                         sub_inner)
                        sub_inner += 1
                else:
                    if item not in all_opts:
                        continue
                    info = all_opts[item]
                    self._add_option(pane, item, info, None, inner_row)
                    inner_row += 1

            parent.columnconfigure(0, weight=1)

    def _add_option(self, pane, key, info, sub_pane, row):
        label, default, wtype, choices = info[0], info[1], info[2], info[3]
        help_text = info[5] if len(info) > 5 else None
        parent_frame = (sub_pane.content_frame if sub_pane
                        else pane.content_frame)
        opt = OptionWidget(parent_frame, wtype, default, choices,
                           main_window=self._main_window, option_key=key)
        self._option_map[key] = opt
        target = sub_pane if sub_pane else pane
        show_default = str(default) if default != '' and default is not None else None
        target.add_option(label, help_text, opt.widget, row, show_default)

    def _build_preview(self, parent):
        pf = ttk.LabelFrame(parent, text='Command Preview')
        pf.grid(row=len(SECTIONS) + 2, column=0, sticky='ew',
                padx=8, pady=(8, 8))

        self._cmd_preview = tk.Text(pf, height=4, wrap='word',
                                    font=('Consolas', 9), state='disabled')
        sc = ttk.Scrollbar(pf, orient='vertical',
                           command=self._cmd_preview.yview)
        self._cmd_preview.configure(yscrollcommand=sc.set)
        self._cmd_preview.pack(side='left', fill='x', expand=True)
        sc.pack(side='right', fill='y')

        btn_f = ttk.Frame(pf)
        btn_f.pack(side='right', padx=(4, 0))
        ttk.Button(btn_f, text='Copy', command=self._copy_command).pack()
        ttk.Button(btn_f, text='Use', command=self._use_command).pack()

    def _bind_updates(self):
        for key, opt in self._option_map.items():
            if hasattr(opt, '_var') and opt._var is not None:
                opt._var.trace_add('write',
                    lambda *_, k=key: self._refresh())

    def _refresh(self):
        cmd = build_command(self._option_map)
        update_preview(cmd, self._cmd_preview)

    def _copy_command(self):
        cmd = build_command(self._option_map)
        if self._main_window:
            self._main_window.clipboard_clear()
            self._main_window.clipboard_append(cmd)
            self._main_window.update()

    def _use_command(self):
        cmd = build_command(self._option_map)
        if self._main_window and hasattr(self._main_window, 'set_command'):
            self._main_window.set_command(cmd)

    def _build_profile_bar(self, parent):
        pf = ttk.Frame(parent)
        pf.grid(row=0, column=0, sticky='ew', padx=8, pady=(4, 0))
        parent.columnconfigure(0, weight=1)

        ttk.Label(pf, text='Profile:').pack(side='left')
        self._profile_var = tk.StringVar()
        self._profile_combo = ttk.Combobox(pf, textvariable=self._profile_var,
                                           state='readonly', width=24)
        self._profile_combo.pack(side='left', padx=4)
        self._profile_combo.bind('<<ComboboxSelected>>',
                                 lambda e: self._on_profile_select())

        ttk.Button(pf, text='Save', command=self._save_profile).pack(side='left', padx=1)
        ttk.Button(pf, text='Save As...', command=self._save_as_profile).pack(side='left', padx=1)
        self._btn_delete = ttk.Button(pf, text='Delete', command=self._delete_profile)
        self._btn_delete.pack(side='left', padx=1)

        ttk.Separator(parent, orient='horizontal').grid(row=1, column=0,
                          sticky='ew', padx=8, pady=(6, 2))

        # Server binary path
        bf = ttk.Frame(parent)
        bf.grid(row=2, column=0, sticky='ew', padx=8, pady=(2, 4))
        ttk.Label(bf, text='llama-server:').pack(side='left')
        ttk.Entry(bf, textvariable=self._server_bin_var, width=30).pack(
            side='left', fill='x', expand=True, padx=4)
        ttk.Button(bf, text='...', command=self._browse_server_bin).pack(side='left')

    def _refresh_profile_list(self):
        names = self._profile_mgr.list_profiles()
        all_names = ['Default'] + names
        self._profile_combo.configure(values=all_names)
        if self._current_profile in all_names:
            self._profile_var.set(self._current_profile)
        else:
            self._profile_var.set('Default')
            self._current_profile = 'Default'
        self._btn_delete.configure(state='disabled' if self._current_profile == 'Default' else 'normal')

    def _browse_server_bin(self):
        from tkinter import filedialog
        if os.name == 'nt':
            path = filedialog.askopenfilename(
                title='Select llama-server executable',
                filetypes=[('Executable files', '*.exe'), ('All files', '*.*')],
                master=self._main_window)
        else:
            path = filedialog.askopenfilename(
                title='Select llama-server executable',
                filetypes=[('All files', '*.*')],
                master=self._main_window)
        if path:
            self._server_bin_var.set(path)

    def _collect_options(self):
        result = {}
        for key, opt in self._option_map.items():
            val = opt.get_value()
            if val is not None and val != '':
                result[key] = str(val)
        bin_path = self._server_bin_var.get().strip()
        if bin_path and bin_path != 'llama-server':
            result['_server_bin'] = bin_path
        return result

    def _apply_options(self, options):
        bin_path = options.pop('_server_bin', None)
        if bin_path:
            self._server_bin_var.set(bin_path)
        for key, val in options.items():
            opt = self._option_map.get(key)
            if opt:
                opt.set_value(val)

    def _on_profile_select(self):
        name = self._profile_var.get()
        self._current_profile = name
        if name == 'Default':
            self._apply_options({})
        else:
            opts = self._profile_mgr.load(name)
            if opts:
                self._apply_options(opts)
        self._btn_delete.configure(state='disabled' if name == 'Default' else 'normal')
        self._refresh()

    def _save_profile(self):
        if self._current_profile == 'Default':
            self._save_as_profile()
            return
        opts = self._collect_options()
        self._profile_mgr.save(self._current_profile, opts)

    def _save_as_profile(self):
        import tkinter.simpledialog as simpledialog
        name = simpledialog.askstring('Save Profile', 'Profile name:',
                                       parent=self._main_window or self)
        if not name:
            return
        if not name.strip():
            return
        name = name.strip()
        opts = self._collect_options()
        self._profile_mgr.save(name, opts)
        self._current_profile = name
        self._refresh_profile_list()
        self._profile_var.set(name)
        self._refresh()

    def _delete_profile(self):
        if self._current_profile == 'Default':
            return
        from tkinter import messagebox
        ok = messagebox.askyesno('Delete Profile',
                                  f'Delete profile "{self._current_profile}"?',
                                  parent=self._main_window or self)
        if not ok:
            return
        self._profile_mgr.delete(self._current_profile)
        self._current_profile = 'Default'
        self._refresh_profile_list()
        self._apply_options({})
        self._refresh()

    def get_command(self):
        return build_command(self._option_map)

    def get_options(self):
        return self._option_map
