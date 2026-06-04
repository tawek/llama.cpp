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
        'model', 'lora', 'lora_scaled', 'mmproj', 'no_mmproj',
        'no_mmproj_offload', 'image', 'audio',
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
    ('Speculative', '__speculative__'),
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
        self._dirty = False
        self._ready = False
        self._server_bin_var = tk.StringVar(value='llama-server')
        self._build_ui()
        self._ready = True

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
        self._build_server_note(scroll_frame)
        self._build_sections(scroll_frame)
        self._build_preview(scroll_frame)
        self._bind_updates()
        self._refresh_profile_list()

    def _build_sections(self, parent):
        all_opts = dict(iter_options())
        self._section_panes = {}   # title -> (pane, flat_keys_set)

        for sec_idx, (section_title, keys) in enumerate(SECTIONS):
            pane = CollapsiblePane(parent, section_title, expanded=True)
            pane.grid(row=sec_idx + 2, column=0, sticky='ew', padx=6, pady=4)

            flat_keys = self._flatten_keys(keys)
            self._section_panes[section_title] = (pane, flat_keys)

            if keys == '__speculative__':
                self._build_speculative_section(pane, all_opts)
                parent.columnconfigure(0, weight=1)
                continue

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

    @staticmethod
    def _flatten_keys(keys):
        """Return the flat set of option keys from a section's key list."""
        if keys == '__speculative__':
            return set()   # speculative: never auto-collapse
        result = set()
        for item in keys:
            if isinstance(item, tuple):
                _, sub_keys = item
                result.update(sub_keys)
            else:
                result.add(item)
        return result

    def _collapse_empty_sections(self):
        """Collapse sections whose options are all unset; expand those with data."""
        opts_set = set(self._collect_options().keys())
        for title, (pane, flat_keys) in self._section_panes.items():
            if not flat_keys:
                continue   # skip speculative — managed by its own toggle
            has_data = bool(flat_keys & opts_set)
            if has_data:
                pane.expand()
            else:
                pane.collapse()

    # (type_name_prefix_match, title, [option_keys])
    _SPEC_TYPE_PANELS = [
        (('draft-simple', 'draft-eagle3', 'draft-mtp'), 'Draft Model', [
            'spec_draft_model', 'spec_draft_hf', 'spec_draft_threads',
            'spec_draft_threads_batch', 'spec_draft_cpu_mask',
            'spec_draft_cpu_range', 'spec_draft_cpu_strict',
            'spec_draft_prio', 'spec_draft_poll',
            'spec_draft_type_k', 'spec_draft_type_v',
            'spec_draft_cpu_moe', 'spec_draft_n_cpu_moe',
            'spec_draft_override_tensor',
            'spec_draft_p_split', 'spec_draft_p_min',
            'spec_draft_device', 'spec_draft_ngl']),
        ('ngram-simple', 'Ngram Simple', [
            'ngram_min', 'ngram_max', 'ngram_no_alloc',
            'spec_ngram_simple_size_n', 'spec_ngram_simple_size_m',
            'spec_ngram_simple_min_hits']),
        ('ngram-map-k', 'Ngram Map-k', [
            'ngram_min', 'ngram_max', 'ngram_no_alloc',
            'spec_ngram_map_k_size_n', 'spec_ngram_map_k_size_m',
            'spec_ngram_map_k_min_hits']),
        ('ngram-map-k4v', 'Ngram Map-k4v', [
            'ngram_min', 'ngram_max', 'ngram_no_alloc',
            'spec_ngram_map_k4v_size_n', 'spec_ngram_map_k4v_size_m',
            'spec_ngram_map_k4v_min_hits']),
        ('ngram-mod', 'Ngram Mod', [
            'ngram_min', 'ngram_max', 'ngram_no_alloc',
            'spec_ngram_mod_n_match', 'spec_ngram_mod_n_max',
            'spec_ngram_mod_n_min']),
        ('ngram-cache', 'Ngram Cache', [
            'lookup_cache_static', 'lookup_cache_dynamic']),
    ]

    def _build_speculative_section(self, pane, all_opts):
        """Build the Speculative section with per-type sub-panels."""
        always_visible = ['spec_type', 'spec_draft_n_max', 'spec_draft_n_min']
        for row, key in enumerate(always_visible):
            if key not in all_opts:
                continue
            info = all_opts[key]
            self._add_option(pane, key, info, None, row)

        self._spec_panel_map = {}
        for idx, (trigger, title, keys) in enumerate(self._SPEC_TYPE_PANELS):
            trigger_set = {trigger} if isinstance(trigger, str) else set(trigger)
            sub = CollapsiblePane(pane.content_frame, title, expanded=True)
            sub.grid(row=3 + idx, column=0, columnspan=3,
                     sticky='ew', pady=(4, 0))
            for i, key in enumerate(keys):
                if key not in all_opts:
                    continue
                info = all_opts[key]
                self._add_option(pane, key, info, sub, i)
            sub.grid_remove()
            self._spec_panel_map[title] = (sub, trigger_set)

        spec_opt = self._option_map.get('spec_type')
        self._toggle_spec_subpanes()
        if spec_opt and hasattr(spec_opt, '_var') and spec_opt._var is not None:
            spec_opt._var.trace_add('write',
                                    lambda *_: self._toggle_spec_subpanes())

    def _toggle_spec_subpanes(self):
        selected = self._option_map.get('spec_type')
        if not selected:
            return
        raw = selected.get_value() or ''
        types = set(t.strip() for t in raw.split(',') if t.strip())

        for title, (sub, triggers) in self._spec_panel_map.items():
            if types & triggers:
                sub.grid()
            else:
                sub.grid_remove()

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
                # checkbox, radio, spin, float_spin, text, ordered_list_of_options
                opt._var.trace_add('write',
                    lambda *_, k=key: self._refresh())
            elif opt.widget_type == 'multiline_text':
                opt._text_widget.bind('<KeyRelease>',
                    lambda *_, k=key: self._refresh())
            elif opt.widget_type == 'file':
                opt.widget.path.trace_add('write',
                    lambda *_, k=key: self._refresh())
            elif opt.widget_type == 'dropdown':
                opt.widget.bind('<<ComboboxSelected>>',
                    lambda *_, k=key: self._refresh())

    def _build_full_command(self):
        cmd = build_command(self._option_map)
        bin_path = self._server_bin_var.get().strip()
        if bin_path and bin_path != 'llama-server':
            parts = cmd.split(' ', 1)
            rest = parts[1] if len(parts) > 1 else ''
            cmd = f'{bin_path} {rest}'
        return cmd

    def _refresh(self):
        if self._ready:
            self._dirty = True
        cmd = self._build_full_command()
        update_preview(cmd, self._cmd_preview)

    def _copy_command(self):
        cmd = self._build_full_command()
        if self._main_window:
            self._main_window.clipboard_clear()
            self._main_window.clipboard_append(cmd)
            self._main_window.update()

    def _use_command(self):
        cmd = self._build_full_command()
        if self._main_window and hasattr(self._main_window, 'set_command'):
            self._main_window.set_command(cmd)

    def get_command(self):
        return self._build_full_command()

    def on_close_request(self):
        """Called before app closes. Returns True to proceed, False to cancel."""
        if not self._dirty:
            return True
        ans = self._prompt_unsaved()
        if ans is None:
            return False
        if ans:
            self._save_profile()
        return True

    def get_options(self):
        return self._option_map

    def _build_profile_bar(self, parent):
        pf = ttk.Frame(parent)
        pf.grid(row=0, column=0, sticky='ew', padx=8, pady=(2, 0))
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
        ttk.Button(pf, text='Rename', command=self._rename_profile).pack(side='left', padx=1)
        self._btn_delete = ttk.Button(pf, text='Delete', command=self._delete_profile)
        self._btn_delete.pack(side='left', padx=1)

    def _build_server_note(self, parent):
        ttk.Separator(parent, orient='horizontal').grid(
            row=1, column=0, sticky='ew', padx=8, pady=(6, 2))

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
        bin_path = options.get('_server_bin')
        if bin_path:
            self._server_bin_var.set(bin_path)
        for key, val in options.items():
            if key == '_server_bin':
                continue
            opt = self._option_map.get(key)
            if opt:
                opt.set_value(val)

    def _reset_all_options(self):
        """Clear every option widget to empty (None = no value set)."""
        for opt in self._option_map.values():
            opt.set_value(None)

    def _on_profile_select(self):
        name = self._profile_var.get()
        if name == self._current_profile:
            return
        if self._dirty:
            ans = self._prompt_unsaved()
            if ans is None:
                self._profile_var.set(self._current_profile)
                return
            if ans:
                self._save_profile()
        self._do_switch_profile(name)

    def _do_switch_profile(self, name):
        self._current_profile = name
        # Suppress dirty-marking for the entire reset+apply sequence so that
        # none of the widget traces can set _dirty=True during the switch.
        self._ready = False
        try:
            self._reset_all_options()
            if name != 'Default':
                opts = self._profile_mgr.load(name)
                if opts:
                    self._apply_options(opts)
            self._collapse_empty_sections()
        finally:
            self._ready = True
        self._dirty = False
        self._btn_delete.configure(state='disabled' if name == 'Default' else 'normal')
        # Update command preview directly — calling _refresh() would set _dirty=True.
        cmd = self._build_full_command()
        update_preview(cmd, self._cmd_preview)

    def _prompt_unsaved(self):
        from tkinter import messagebox
        return messagebox.askyesnocancel(
            'Unsaved Changes',
            f'Save changes to profile "{self._current_profile}"?',
            parent=self._main_window or self)

    def _save_profile(self):
        if self._current_profile == 'Default':
            self._save_as_profile()
            return
        opts = self._collect_options()
        self._profile_mgr.save(self._current_profile, opts)
        self._dirty = False

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
        self._dirty = False
        self._refresh_profile_list()
        self._profile_var.set(name)
        self._refresh()

    def _rename_profile(self):
        if self._current_profile == 'Default':
            return
        import tkinter.simpledialog as simpledialog
        new_name = simpledialog.askstring('Rename Profile',
                                          f'Rename "{self._current_profile}" to:',
                                          parent=self._main_window or self)
        if not new_name or not new_name.strip():
            return
        new_name = new_name.strip()
        if new_name == self._current_profile:
            return
        if not self._profile_mgr.rename(self._current_profile, new_name):
            from tkinter import messagebox
            messagebox.showerror('Rename Failed',
                                 f'Could not rename to "{new_name}". Name may already exist.',
                                 parent=self._main_window or self)
            return
        self._current_profile = new_name
        self._refresh_profile_list()
        self._profile_var.set(new_name)
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
        self._do_switch_profile('Default')
        self._refresh_profile_list()
