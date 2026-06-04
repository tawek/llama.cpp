"""
CLI command builder - generates llama-server command from OptionWidget values.
"""

PREFIX_MAP = {
    'model': '-m', 'lora': '--lora', 'lora_scaled': '--lora-scaled',
    'mmproj': '--mmproj', 'image': '--image', 'audio': '--audio',
    'mlock': '--mlock', 'mmap': '--mmap', 'direct_io': '--direct-io',
    'no_mmproj': '--no-mmproj', 'no_mmproj_offload': '--no-mmproj-offload',
    'check_tensors': '--check-tensors', 'tags': '--tags',
    'alias': '--alias', 'override_kv': '--override-kv',
    'lora_init_without_apply': '--lora-init-without-apply',
    'gpu_layers': '-ngl', 'split_mode': '-sm', 'tensor_split': '-ts',
    'main_gpu': '-mg', 'device': '--device', 'rpc': '--rpc',
    'cpu_moe': '--cpu-moe', 'n_cpu_moe': '--n-cpu-moe',
    'fit': '--fit', 'fit_print': '--fit-print',
    'fit_target': '--fit-target', 'fit_ctx': '--fit-ctx',
    'cache_prompt': '--cache-prompt', 'cache_reuse': '--cache-reuse',
    'cache_ram': '--cache-ram', 'cache_type_k': '--cache-type-k',
    'cache_type_v': '--cache-type-v', 'kv_unified': '--kv-unified',
    'cache_idle_slots': '--cache-idle-slots',
    'slot_save_path': '--slot-save-path',
    'ctx_checkpoints': '--ctx-checkpoints',
    'checkpoint_every_n': '--checkpoint-every-n-tokens',
    'ctx_size': '-c', 'batch_size': '-b', 'ubatch_size': '-ub',
    'predict': '-n', 'keep': '--keep', 'swa_full': '--swa-full',
    'threads': '-t', 'threads_batch': '-tb', 'cpu_mask': '-C',
    'cpu_range': '-Cr', 'cpu_strict': '--cpu-strict',
    'prio': '--prio', 'poll': '--poll',
    'prio_prompt': '--prio-prompt', 'prio_predict': '--prio-predict',
    'prio_batch': '--prio-batch', 'prio_draft': '--prio-draft',
    'rope_scaling': '--rope-scaling', 'rope_scale': '--rope-scale',
    'rope_freq_base': '--rope-freq-base', 'rope_freq_scale': '--rope-freq-scale',
    'yarn_orig_ctx': '--yarn-orig-ctx', 'yarn_ext_factor': '--yarn-ext-factor',
    'yarn_attn_factor': '--yarn-attn-factor',
    'yarn_beta_fast': '--yarn-beta-fast', 'yarn_beta_slow': '--yarn-beta-slow',
    'grp_attn_n': '-gan', 'grp_attn_w': '-gaw', 'flash_attn': '-fa',
    'temperature': '--temp', 'top_k': '--top-k', 'top_p': '--top-p',
    'min_p': '--min-p', 'top_n_sigma': '--top-n-sigma',
    'xtc_prob': '--xtc-prob', 'xtc_threshold': '--xtc-threshold',
    'typical': '--typical', 'adaptive_target': '--adaptive-target',
    'adaptive_decay': '--adaptive-decay',
    'dynatemp_range': '--dynatemp-range', 'dynatemp_exp': '--dynatemp-exp',
    'seed': '-s', 'samplers': '--samplers', 'sampler_seq': '--sampler-seq',
    'mirostat': '--mirostat', 'mirostat_lr': '--mirostat-lr',
    'mirostat_ent': '--mirostat-ent',
    'repeat_last_n': '--repeat-last-n', 'repeat_penalty': '--repeat-penalty',
    'presence_penalty': '--presence-penalty',
    'frequency_penalty': '--frequency-penalty', 'ignore_eos': '--ignore-eos',
    'dry_multiplier': '--dry-multiplier', 'dry_base': '--dry-base',
    'dry_allowed_length': '--dry-allowed-length',
    'dry_penalty_last_n': '--dry-penalty-last-n',
    'dry_sequence_breaker': '--dry-sequence-breaker',
    'logit_bias': '-l', 'grammar': '--grammar', 'grammar_file': '--grammar-file',
    'json_schema': '-j', 'json_schema_file': '-jf',
    'spec_draft_model': '--spec-draft-model', 'spec_type': '--spec-type',
    'spec_draft_n_max': '--spec-draft-n-max',
    'spec_draft_n_min': '--spec-draft-n-min',
    'spec_draft_p_split': '--spec-draft-p-split',
    'spec_draft_p_min': '--spec-draft-p-min',
    'spec_draft_device': '--spec-draft-device',
    'spec_draft_ngl': '--spec-draft-ngl',
    'prompt': '-p', 'system_prompt': '-sys', 'file': '-f',
    'in_file': '--in-file', 'binary_file': '-bf',
    'reverse_prompt': '-r', 'escape': '-e', 'special': '-sp',
    'interactive': '-i', 'interactive_first': '-if',
    'multiline_input': '-mli', 'in_prefix': '--in-prefix',
    'in_suffix': '--in-suffix', 'warmup': '--warmup', 'perf': '--perf',
    'chat_template': '--chat-template', 'chat_template_file': '--chat-template-file',
    'reasoning_format': '--reasoning-format', 'reasoning_budget': '--reasoning-budget',
    'jinja': '--jinja', 'prefill_assistant': '--prefill-assistant',
    'verbose_prompt': '--verbose-prompt', 'display_prompt': '--display-prompt',
    'color': '-co', 'slot_prompt_similarity': '--slot-prompt-similarity',
    'simple_io': '--simple-io', 'show_timings': '--show-timings',
    'host': '--host', 'port': '--port', 'parallel': '-np',
    'sequences': '-ns', 'timeout': '--timeout',
    'threads_http': '--threads-http', 'api_key': '--api-key',
    'ssl_key': '--ssl-key', 'ssl_cert': '--ssl-cert',
    'path': '--path', 'api_prefix': '--api-prefix',
    'webui': '--webui', 'webui_config': '--webui-config',
    'tools': '--tools', 'embedding': '--embedding', 'rerank': '--rerank',
    'metrics': '--metrics', 'props': '--props', 'slots': '--slots',
    'cont_batching': '--cont-batching',
    'pooling': '--pooling', 'attention': '--attention',
    # Panel headers (UI-only, not used in command building)
    'spec_panel': '--spec-panel',
    'chat_panel': '--chat-panel',
    'display_panel': '--display-panel',
    'webui_panel': '--webui-panel',
    'server_features_panel': '--server-features-panel',
    # Negated prefixes for tristate checkbox 'false' state
    'jinja_no': '--no-jinja',
    'prefill_assistant_no': '--no-prefill-assistant',
    'mmap_no': '--no-mmap',
    'display_prompt_no': '--no-display-prompt',
    'show_timings_no': '--no-show-timings',
    'escape_no': '--no-escape',
    'warmup_no': '--no-warmup',
    'perf_no': '--no-perf',
    'cont_batching_no': '--no-cont-batching',
    'cache_prompt_no': '--no-cache-prompt',
    'slots_no': '--no-slots',
    'direct_io_no': '--no-direct-io',
    'webui_no': '--no-webui',
}

# Keys that are known to have no negated variant
_NO_NEGATED = {'mlock', 'check_tensors', 'cpu_moe', 'cpu_strict',
               'ignore_eos', 'special', 'interactive', 'interactive_first',
               'multiline_input', 'simple_io', 'tools', 'embedding',
               'rerank', 'metrics', 'props', 'cache_idle_slots',
               'kv_unified', 'swa_full', 'lora_init_without_apply',
               'fit', 'flash_attn'}


def _format_arg(value):
    """Quote argument if it contains spaces."""
    value = str(value)
    return f'"{value}"' if ' ' in value else value


def build_command(option_map):
    """Build CLI command string from option_map {key: OptionWidget}."""
    parts = ['llama-server']

    for key, opt in option_map.items():
        if opt.widget_type == 'panel_header':
            continue
        val = opt.get_value()
        if val is None or val == '':
            continue

        prefix = PREFIX_MAP.get(key, f'--{key}')

        if opt.widget_type == 'checkbox':
            if val == 'on':
                parts.append(prefix)
            elif val == 'off':
                no_prefix = PREFIX_MAP.get(key + '_no')
                if no_prefix:
                    parts.append(no_prefix)
        elif opt.widget_type == 'file':
            val_str = str(val).strip()
            if val_str:
                parts.extend([prefix, val_str])
        elif opt.widget_type in ('dropdown', 'radio'):
            parts.extend([prefix, str(val)])
        else:
            if val != opt.default:
                parts.extend([prefix, str(val)])

    return ' '.join(_format_arg(p) for p in parts)


def update_preview(cmd, text_widget):
    """Update a Text widget with the current command preview."""
    text_widget.configure(state='normal')
    text_widget.delete('1.0', 'end')
    text_widget.insert('1.0', cmd)
    text_widget.configure(state='disabled')
