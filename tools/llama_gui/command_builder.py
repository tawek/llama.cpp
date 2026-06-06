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
    'cache_ram': '--cache-ram',     'cache_type_k': '--cache-type-k',
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
    'spec_draft_hf': '--spec-draft-hf',
    'spec_draft_threads': '--spec-draft-threads',
    'spec_draft_threads_batch': '--spec-draft-threads-batch',
    'spec_draft_cpu_mask': '--spec-draft-cpu-mask',
    'spec_draft_cpu_range': '--spec-draft-cpu-range',
    'spec_draft_cpu_strict': '--spec-draft-cpu-strict',
    'spec_draft_prio': '--spec-draft-prio',
    'spec_draft_poll': '--spec-draft-poll',
    'spec_draft_type_k': '--spec-draft-type-k',
    'spec_draft_type_v': '--spec-draft-type-v',
    'spec_draft_cpu_moe': '--spec-draft-cpu-moe',
    'spec_draft_n_cpu_moe': '--spec-draft-n-cpu-moe',
    'spec_draft_override_tensor': '--spec-draft-override-tensor',
    'ngram_min': '--ngram-min',
    'ngram_max': '--ngram-max',
    'ngram_no_alloc': '--ngram-no-alloc',
    'lookup_cache_static': '--lookup-cache-static',
    'lookup_cache_dynamic': '--lookup-cache-dynamic',
    'spec_ngram_simple_min_hits': '--spec-ngram-simple-min-hits',
    'spec_ngram_simple_size_n': '--spec-ngram-simple-size-n',
    'spec_ngram_simple_size_m': '--spec-ngram-simple-size-m',
    'spec_ngram_map_k_min_hits': '--spec-ngram-map-k-min-hits',
    'spec_ngram_map_k_size_n': '--spec-ngram-map-k-size-n',
    'spec_ngram_map_k_size_m': '--spec-ngram-map-k-size-m',
    'spec_ngram_map_k4v_min_hits': '--spec-ngram-map-k4v-min-hits',
    'spec_ngram_map_k4v_size_n': '--spec-ngram-map-k4v-size-n',
    'spec_ngram_map_k4v_size_m': '--spec-ngram-map-k4v-size-m',
    'spec_ngram_mod_n_match': '--spec-ngram-mod-n-match',
    'spec_ngram_mod_n_max': '--spec-ngram-mod-n-max',
    'spec_ngram_mod_n_min': '--spec-ngram-mod-n-min',
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
    'log_file': '--log-file', 'log_colors': '--log-colors',
    'log_verbosity': '--log-verbosity', 'log_prefix': '--log-prefix',
    'log_timestamps': '--log-timestamps', 'log_disable': '--log-disable',
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
    'log_prefix_no': '--no-log-prefix',
    'log_timestamps_no': '--no-log-timestamps',
    'log_disable_no': '--no-log-disable',
}

# Reverse map: CLI flag → config key (built from PREFIX_MAP)
REVERSE_PREFIX_MAP = {}
for _key, _flag in PREFIX_MAP.items():
    REVERSE_PREFIX_MAP[_flag] = _key

# Additional short-form aliases not stored as separate PREFIX_MAP entries
_SHORT_ALIASES = {
    '-ctk': 'cache_type_k',
    '-ctv': 'cache_type_v',
    '-fitt': 'fit_target',
}
REVERSE_PREFIX_MAP.update(_SHORT_ALIASES)

# Keys whose widget type is checkbox (boolean flags with no value argument)
_BOOLEAN_KEYS = {
    'no_mmproj', 'no_mmproj_offload', 'mlock', 'mmap', 'direct_io',
    'check_tensors', 'cpu_moe', 'cpu_strict', 'kv_unified',
    'ignore_eos', 'escape', 'special', 'interactive',
    'interactive_first', 'multiline_input', 'simple_io',
    'show_timings', 'display_prompt', 'color', 'jinja',
    'prefill_assistant', 'verbose_prompt', 'warmup', 'perf',
    'cache_prompt', 'cache_reuse', 'cache_idle_slots',
    'ctx_checkpoints', 'swa_full', 'ngram_no_alloc',
    'tools', 'embedding', 'rerank', 'metrics', 'props', 'slots',
    'cont_batching', 'webui', 'no_mmap',
    'fit', 'fit_print',
    'log_prefix', 'log_timestamps', 'log_disable',
}


def parse_cli_line(line):
    """
    Parse a llama-server CLI command string into a dict of config key → value.
    Handles quoted values and joined continuation lines.
    Returns dict of {config_key: str_value}.
    """
    tokens = _tokenize(line)
    if not tokens:
        return {}

    try:
        start = next(i for i, t in enumerate(tokens)
                     if 'llama-server' in t or 'llama-cli' in t)
        args = tokens[start + 1:]
    except StopIteration:
        return {}

    result = {}
    i = 0
    while i < len(args):
        token = args[i]
        if not token.startswith('-'):
            i += 1
            continue

        flag = token
        key = REVERSE_PREFIX_MAP.get(flag)

        if key is None and not flag.startswith('--'):
            long_form = '--' + flag.lstrip('-')
            key = REVERSE_PREFIX_MAP.get(long_form)

        if key is None:
            i += 1
            continue

        # Handle --flag=value syntax
        if '=' in flag.lstrip('-'):
            _, val = flag.split('=', 1)
            result[key] = _strip_quotes(val)
            i += 1
            continue

        # Negated flag (key ends with _no) → set base key to 'off'
        if key.endswith('_no'):
            result[key[:-3]] = 'off'
            i += 1
            continue

        # Check if next token is a value (doesn't start with -)
        i += 1
        if i < len(args) and not args[i].startswith('-'):
            result[key] = _strip_quotes(args[i])
            i += 1
        elif key in _BOOLEAN_KEYS:
            result[key] = 'on'

    return result


def _tokenize(line):
    """Tokenize a shell command line, handling quoted strings."""
    import shlex
    try:
        return shlex.split(line)
    except ValueError:
        return line.split()


def _strip_quotes(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


# Keys that are known to have no negated variant
_NO_NEGATED = {'mlock', 'check_tensors', 'cpu_moe', 'cpu_strict',
               'ignore_eos', 'special', 'interactive', 'interactive_first',
               'multiline_input', 'simple_io', 'tools', 'embedding',
               'rerank', 'metrics', 'props', 'cache_idle_slots',
               'kv_unified', 'swa_full', 'lora_init_without_apply',
               'fit', 'flash_attn', 'log_disable', 'log_prefix', 'log_timestamps'}


def _format_arg(value):
    """Quote argument if it contains spaces."""
    value = str(value)
    return f'"{value}"' if ' ' in value else value


# Which option keys belong to which spec type(s)
_SPEC_TYPE_KEY_MAP = {
    'draft-simple': {
        'spec_draft_model', 'spec_draft_hf', 'spec_draft_threads',
        'spec_draft_threads_batch', 'spec_draft_cpu_mask',
        'spec_draft_cpu_range', 'spec_draft_cpu_strict',
        'spec_draft_prio', 'spec_draft_poll',
        'spec_draft_type_k', 'spec_draft_type_v',
        'spec_draft_cpu_moe', 'spec_draft_n_cpu_moe',
        'spec_draft_override_tensor',
        'spec_draft_p_split', 'spec_draft_p_min',
        'spec_draft_device', 'spec_draft_ngl',
        'spec_draft_n_max', 'spec_draft_n_min',
    },
    'draft-eagle3': {
        'spec_draft_model', 'spec_draft_hf', 'spec_draft_threads',
        'spec_draft_threads_batch', 'spec_draft_cpu_mask',
        'spec_draft_cpu_range', 'spec_draft_cpu_strict',
        'spec_draft_prio', 'spec_draft_poll',
        'spec_draft_type_k', 'spec_draft_type_v',
        'spec_draft_cpu_moe', 'spec_draft_n_cpu_moe',
        'spec_draft_override_tensor',
        'spec_draft_p_split', 'spec_draft_p_min',
        'spec_draft_device', 'spec_draft_ngl',
        'spec_draft_n_max', 'spec_draft_n_min',
    },
    'draft-mtp': {
        'spec_draft_model', 'spec_draft_hf', 'spec_draft_threads',
        'spec_draft_threads_batch', 'spec_draft_cpu_mask',
        'spec_draft_cpu_range', 'spec_draft_cpu_strict',
        'spec_draft_prio', 'spec_draft_poll',
        'spec_draft_type_k', 'spec_draft_type_v',
        'spec_draft_cpu_moe', 'spec_draft_n_cpu_moe',
        'spec_draft_override_tensor',
        'spec_draft_p_split', 'spec_draft_p_min',
        'spec_draft_device', 'spec_draft_ngl',
        'spec_draft_n_max', 'spec_draft_n_min',
    },
    'ngram-simple': {
        'ngram_min', 'ngram_max', 'ngram_no_alloc',
        'spec_ngram_simple_size_n', 'spec_ngram_simple_size_m',
        'spec_ngram_simple_min_hits',
    },
    'ngram-map-k': {
        'ngram_min', 'ngram_max', 'ngram_no_alloc',
        'spec_ngram_map_k_size_n', 'spec_ngram_map_k_size_m',
        'spec_ngram_map_k_min_hits',
    },
    'ngram-map-k4v': {
        'ngram_min', 'ngram_max', 'ngram_no_alloc',
        'spec_ngram_map_k4v_size_n', 'spec_ngram_map_k4v_size_m',
        'spec_ngram_map_k4v_min_hits',
    },
    'ngram-mod': {
        'ngram_min', 'ngram_max', 'ngram_no_alloc',
        'spec_ngram_mod_n_match', 'spec_ngram_mod_n_max',
        'spec_ngram_mod_n_min',
    },
    'ngram-cache': {
        'lookup_cache_static', 'lookup_cache_dynamic',
    },
}

_SPEC_SPECULATIVE_PREFIXES = ('spec_', 'ngram_', 'lookup_cache_')

def _is_speculative_key(key):
    """Check if a key is a speculative option."""
    return any(key.startswith(prefix) for prefix in _SPEC_SPECULATIVE_PREFIXES)


def _get_allowed_spec_keys(option_map):
    """Return set of allowed speculative option keys based on selected spec types.

    Returns an empty set if no speculative type is selected or specified.
    """
    spec_opt = option_map.get('spec_type')
    if not spec_opt:
        return set()  # no spec_type set → no speculative options allowed

    raw = spec_opt.get_value() or ''
    selected = [t.strip() for t in raw.split(',') if t.strip()]

    if not selected:
        return set()  # empty spec type list → exclude all speculative options

    allowed = set()
    for stype in selected:
        if stype in _SPEC_TYPE_KEY_MAP:
            allowed |= _SPEC_TYPE_KEY_MAP[stype]

    return allowed


def build_command(option_map):
    """Build CLI command string from option_map {key: OptionWidget}."""
    parts = ['llama-server']

    allowed_keys = _get_allowed_spec_keys(option_map)

    for key, opt in option_map.items():
        if opt.widget_type == 'panel_header':
            continue

        # Skip speculative options not belonging to selected spec types
        if key != 'spec_type' and _is_speculative_key(key) and key not in allowed_keys:
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
            parts.extend([prefix, str(val)])

    return ' '.join(_format_arg(p) for p in parts)


def update_preview(cmd, text_widget):
    """Update a Text widget with the current command preview."""
    text_widget.configure(state='normal')
    text_widget.delete('1.0', 'end')
    text_widget.insert('1.0', cmd)
    text_widget.configure(state='disabled')
