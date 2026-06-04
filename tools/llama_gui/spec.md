# llama.cpp GUI Launcher - Specification

## 1. Overview

A Python Tkinter GUI application to launch and monitor llama.cpp server. Provides:
- **Configuration Panel** - Friendly UI for all CLI options (collapsible sections, help tooltips, command preview)
- **Live Monitoring Panel** - Real-time token rates, draft acceptance, GPU/CPU/memory stats
- **Log Analyzer** - Parses server output logs for metrics
- **Process Management** - Start/stop/restart the server process

---

## 2. CLI Options Reference

All options from `common/arg.cpp` and `tools/server/server.cpp`.

### 2.1 Option Categories

| # | Section (GUI Panel) | Key Options |
|---|---------------------|-------------|
| 1 | Model Loading | `-m/--model`, `--mmproj`, `--lora`, `--lora-scaled`, `--mlock`, `--mmap`, `--direct-io`, `--check-tensors`, `--tags`, `--alias`, `--override-kv`, `--image`, `--audio`, `--lora-init-without-apply` |
| 2 | GPU & Acceleration | `-ngl/--gpu-layers`, `-sm/--split-mode`, `-ts/--tensor-split`, `-mg/--main-gpu`, `--device`, `--rpc`, `-cmoe/--cpu-moe`, `-ncmoe/--n-cpu-moe`, `--fit`, `--fit-print`, `--fit-target`, `--fit-ctx` |
| 3 | Cache & KV | `--cache-prompt`, `--cache-reuse`, `--cache-ram`, `--cache-type-k`, `--cache-type-v`, `--kv-unified`, `--cache-idle-slots`, `--slot-save-path`, `--ctx-checkpoints`, `--checkpoint-every-n-tokens` |
| 4 | Context & Batch | `-c/--ctx-size`, `-b/--batch-size`, `-ub/--ubatch-size`, `-n/--predict`, `--keep`, `--swa-full` |
| 5 | CPU | `-t/--threads`, `-tb/--threads-batch`, `-C/--cpu-mask`, `-Cr/--cpu-range`, `--cpu-strict`, `--prio`, `--poll` + batch/draft variants |
| 6 | RoPE & Scaling | `--rope-scaling`, `--rope-scale`, `--rope-freq-base`, `--rope-freq-scale`, `--yarn-*`, `-gan/--grp-attn-n`, `-gaw/--grp-attn-w`, `-fa/--flash-attn` |
| 7 | Sampling | `--samplers`, `-s/--seed`, `--temp/--temperature`, `--top-k`, `--top-p`, `--min-p`, `--top-n-sigma`, `--xtc-*`, `--typical`, `--adaptive-*`, `--dynatemp-*` |
| 8 | Mirostat | `--mirostat`, `--mirostat-lr`, `--mirostat-ent` |
| 9 | Penalties | `--repeat-last-n`, `--repeat-penalty`, `--presence-penalty`, `--frequency-penalty`, `--ignore-eos` |
| 10 | DRY | `--dry-multiplier`, `--dry-base`, `--dry-allowed-length`, `--dry-penalty-last-n`, `--dry-sequence-breaker` |
| 11 | Grammar | `-l/--logit-bias`, `--grammar`, `--grammar-file`, `-j/--json-schema`, `-jf/--json-schema-file` |
| 12 | Speculative | `--spec-draft-model/-md`, `--spec-type`, `--spec-draft-n-max`, `--spec-draft-n-min`, `--spec-draft-p-split`, `--spec-draft-p-min`, `--spec-draft-device`, `--spec-draft-ngl` |
| 13 | Prompt/Input | `-p/--prompt`, `-sys/--system-prompt`, `-f/--file`, `--in-file`, `-bf/--binary-file`, `-e/--escape`, `-r/--reverse-prompt`, `-sp/--special`, `-i/--interactive`, `-if/--interactive-first`, `-mli/--multiline-input`, `--in-prefix`, `--in-suffix`, `--warmup`, `--perf` |
| 14 | Chat | `--chat-template`, `--chat-template-file`, `--reasoning-format`, `--reasoning-budget`, `--jinja`, `--prefill-assistant` |
| 15 | Display | `--verbose-prompt`, `--display-prompt`, `-co/--color`, `-sps/--slot-prompt-similarity`, `--simple-io`, `--show-timings` |
| 16 | Server | `-np/--parallel`, `-ns/--sequences`, `--cont-batching`, `--host`, `--port`, `--timeout`, `--threads-http`, `--api-key`, `--ssl-key`, `--ssl-cert`, `--path`, `--api-prefix` |
| 16a | Server > WebUI (sub-panel) | `--webui`, `--webui-config` |
| 16b | Server > Features (sub-panel) | `--tools`, `--embedding`, `--rerank`, `--metrics`, `--props`, `--slots` |
| 17 | Embedding | `--pooling`, `--attention` |

### 2.2 Option Type Mapping for GUI

| C++ Type | Widget Type (registry) | GUI Widget | Example |
|----------|----------------------|-----------|---------|
| bool (flag) | `checkbox` | 3-state Combobox `['', 'on', 'off']` | `--mlock`, `--mmap`/`--no-mmap` |
| int | `spin` | tk.Entry (StringVar, starts empty) | `-t 4` (threads) |
| float | `float_spin` | tk.Entry (StringVar, starts empty) | `--temperature 0.8` |
| string (path) | `file` | ttk.Entry + Browse button | `-m model.gguf` |
| string (enum) | `dropdown` | ttk.Combobox (state='readonly') | `--rope-scaling {none,linear,yarn}` |
| string (enum, shortlist) | `radio` | ttk.Radiobutton row | `--mirostat {0,1,2}` |
| string (comma-sep) | `text` | tk.Entry (StringVar) | `-ts 0.5,0.3,0.2` |
| string (free) | `text` | tk.Entry (StringVar) | `--prompt "hello"` |
| string (key=value) | `text` | tk.Entry (StringVar) | `--override-kv KEY=TYPE:VALUE` |

### 2.3 Defaults Reference

| Option | Default | Option | Default |
|--------|---------|--------|---------|
| `-t/--threads` | hardware_concurrency | `-tb/--threads-batch` | same as threads |
| `-c/--ctx-size` | 0 (model default) | `-b/--batch-size` | 2048 |
| `-ub/--ubatch-size` | 512 | `-n/--predict` | -1 (infinity) |
| `--keep` | 0 | `--temperature` | 0.80 |
| `--top-k` | 40 | `--top-p` | 0.95 |
| `--min-p` | 0.05 | `--repeat-last-n` | 64 |
| `--repeat-penalty` | 1.00 | `--presence-penalty` | 0.00 |
| `--frequency-penalty` | 0.00 | `--flash-attn` | auto |
| `--gpu-layers` | auto | `--split-mode` | layer |
| `--parallel` | 4 (auto) | `--host` | 127.0.0.1 |
| `--port` | 8080 | `--timeout` | 600 |
| `--threads-http` | -1 (auto) | `--webui` | true |
| `--slots` | true | `--cache-prompt` | true |
| `--cache-idle-slots` | true | `--warmup` | true |
| `--jinja` | true | `--mmap` | true |
| `--mirostat` | 0 | `--mirostat-lr` | 0.10 |
| `--mirostat-ent` | 5.00 | `--typical` | 1.00 |
| `--spec-draft-n-max` | 16 | `--spec-draft-n-min` | 0 |
| `--spec-draft-p-split` | 0.1 | `--spec-draft-p-min` | 0.75 |
| `--rope-freq-scale` | 1.0 | `--ctx-checkpoints` | 32 |
| `--checkpoint-every-n-tokens` | 8192 | `--cache-ram` | 8192 MiB |
| `--cache-type-k` | F16 | `--cache-type-v` | F16 |
| `--slot-prompt-similarity` | 0.1 | `--cache-reuse` | 0 |
| `--grp-attn-n` | 1 | `--grp-attn-w` | 512 |
| `--fit` | true | `--fit-ctx` | 4096 |
| `--show-timings` | true | `--display-prompt` | true |
| `--prefill-assistant` | true | `--op-offload` | true |

---

## 3. Server API Endpoints

### 3.1 HTTP Endpoints (from server.cpp line 173-207)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health`, `/v1/health` | No | Health check |
| GET | `/metrics` | Yes | Prometheus metrics |
| GET | `/props` | Yes | Server properties & defaults |
| POST | `/props` | Yes | Update global properties |
| GET | `/models`, `/v1/models` | No | List models |
| POST | `/v1/completions` | Yes | OpenAI completions |
| POST | `/v1/chat/completions` | Yes | OpenAI chat completions |
| POST | `/v1/responses` | Yes | OpenAI responses API |
| POST | `/v1/embeddings` | Yes | OpenAI embeddings |
| POST | `/v1/rerank` | Yes | Reranking |
| POST | `/v1/audio/transcriptions` | Yes | Audio transcription |
| POST | `/v1/messages` | Yes | Anthropic messages API |
| GET | `/slots` | Yes | Slot monitoring/status |
| POST | `/slots/:id` | Yes | Save/restore/erase slot |
| GET | `/lora-adapters` | Yes | List LoRA adapters |
| POST | `/lora-adapters` | Yes | Load/unload LoRA |
| POST | `/tokenize`, `/detokenize` | Yes | Tokenization |
| POST | `/apply-template` | Yes | Apply chat template |

### 3.2 Slot Monitoring Response (from server-context.cpp)

```json
{
  "n_idle_slots": 4,
  "n_processing_slots": 1,
  "t_prompt_processing": 123.45,
  "t_tokens_generation": 67.89,
  "n_busy_slots_total": 100,
  "slots": [
    {
      "id": 0,
      "n_ctx": 4096,
      "speculative": false,
      "is_processing": false,
      "n_prompt_tokens": 256,
      "n_prompt_tokens_cache": 128,
      "n_past": 384,
      "n_decoded": 10,
      "n_draft": 0,
      "n_draft_accepted": 0,
      "prompt_per_second": 1234.56,
      "predicted_per_second": 56.78,
      "has_next_token": false,
      "next_token": {"has_next_token": false, "n_remain": -1}
    }
  ]
}
```

### 3.3 Prometheus Metrics (from server-context.cpp:3702-3748)

| Metric | Type | Description |
|--------|------|-------------|
| `prompt_tokens_total` | counter | Total prompt tokens processed |
| `prompt_seconds_total` | counter | Total prompt processing time |
| `tokens_predicted_total` | counter | Total generated tokens |
| `tokens_predicted_seconds_total` | counter | Total generation time |
| `n_decode_total` | counter | Total llama_decode() calls |
| `n_tokens_max` | gauge | Largest observed n_tokens |
| `prompt_tokens_seconds` | gauge | Prompt throughput (tokens/s) |
| `predicted_tokens_seconds` | gauge | Generation throughput (tokens/s) |
| `requests_processing` | gauge | Active requests |
| `requests_deferred` | gauge | Deferred requests |
| `n_busy_slots_per_decode` | gauge | Busy slots per decode call |

---

## 4. Log Output Patterns for Parsing (server-context.cpp)

| Pattern | Location | Example |
|---------|----------|---------|
| Prompt eval time | L470 | `prompt eval time = 123.45 ms / 256 tokens (0.48 ms per token, 533.33 tokens per second)` |
| Eval time | L473 | `eval time = 67.89 ms / 10 tokens (6.79 ms per token, 147.33 tokens per second)` |
| Total time | L477 | `total time = 191.34 ms / 266 tokens` |
| Graphs reused | L481 | `graphs reused = 5` |
| Draft acceptance | L485 | `draft acceptance = 0.75000 ( 12 accepted /  16 generated)` |
| Slot draft | L3218 | `accepted 12/16 draft tokens (restore checkpoint)` |
| Checkpoint | L1888 | `created context checkpoint 1 of 32 (pos_min = 0, pos_max = 256, n_tokens = 256, size = 1.234 MiB)` |
| Cache state | L2160 | `prompt cache state: 3 prompts, 45.123 MiB (limits: 512.000 MiB, 65536 tokens, 1024 est)` |
| Prompt processing | L458 | `prompt processing, n_tokens = 256, progress = 1.00, t = 0.12 s / 2133.33 tokens per second` |

---

## 5. GUI Layout

### 5.1 Main Window

```
+----------------------------------------------------------+
| [Tab: Config] [Tab: Monitor] [Tab: Logs] [Tab: Slots]   |
+----------------------------------------------------------+
| (Tab Content)                                            |
+----------------------------------------------------------+
| [Start] [Stop] | Server: http://host:port [Open in Browser]|
+----------------------------------------------------------+
```

### 5.2 Config Tab

A scrollable canvas (tk.Canvas + ttk.Scrollbar, mouse-wheel bound) containing **18 collapsible sections** (CollapsiblePane widgets) plus a **Command Preview** frame at bottom.

Each section is a `CollapsiblePane` (extends `ttk.LabelFrame`) with:
- **⬟ arrow** (▾ expanded / ▸ collapsed) + **bold title** — both clickable
- `ttk.Separator` (always visible)
- Content grid (hidden when collapsed)

Each option row is a 3-column grid inside the content frame:

| Col | Widget | Details |
|-----|--------|---------|
| 0 | `ttk.Label` | `"Label [default]:"` — right-aligned ('e' anchor); default shown in brackets if non-empty |
| 1 | Value control | Determined by registry `widget_type` (see 2.2). `sticky='ew'`, `weight=1` |
| 2 | `"?"` label | Bold, 'dodger blue', cursor 'question_arrow'. Shows help text via `Tooltip` (top-level window, appears on `<Enter>`, hides on `<Leave>`, wraplength 420px, bg `#ffffea`). Only shown when `help_text` is defined in registry. |

Widget types per option:
- **`checkbox`** (boolean): 3-state Combobox — `['', 'on', 'off']`. Default: `''` (unset). `'on'` → emit flag, `'off'` → emit `--no-*` if negated variant exists, else omit.
- **`spin` / `float_spin`** (numeric): Plain `tk.Entry` with `StringVar`, starts **empty** (not pre-filled). Empty means "use server default". Value emitted only if non-None and differs from registry default.
- **`text`** (free string): `tk.Entry` with `StringVar`.
- **`file`** (path): Custom `_FileSelector` frame with `ttk.Entry` + `"..."` button opening `filedialog.askopenfilename`.
- **`dropdown`** (enum): `ttk.Combobox`, `state='readonly'`, values from `choices`.
- **`radio`** (short enum): `ttk.Frame` with `ttk.Radiobutton` per choice, packed side-by-side.

Sections:

1. **Model Loading** — model (file), lora, lora_scaled, mmproj (file), image, audio, mlock, mmap, direct_io, check_tensors, tags, alias, override_kv, lora_init_without_apply
2. **GPU & Acceleration** — gpu_layers, split_mode (dropdown), tensor_split, main_gpu, device, rpc, cpu_moe, n_cpu_moe, fit, fit_print, fit_target, fit_ctx
3. **Cache & KV** — cache_prompt, cache_reuse, cache_ram, cache_type_k (dropdown: F16/F32/I8/I4), cache_type_v (dropdown), kv_unified, cache_idle_slots, slot_save_path, ctx_checkpoints, checkpoint_every_n
4. **Context & Batch** — ctx_size, batch_size, ubatch_size, predict, keep, swa_full
5. **CPU** — threads, threads_batch, cpu_mask, cpu_range, cpu_strict, prio, poll, prio_prompt, prio_predict, prio_batch, prio_draft
6. **RoPE & Scaling** — rope_scaling (dropdown: none/linear/yarn), rope_scale, rope_freq_base, rope_freq_scale, yarn_orig_ctx, yarn_ext_factor, yarn_attn_factor, yarn_beta_fast, yarn_beta_slow, grp_attn_n, grp_attn_w, flash_attn (checkbox)
7. **Sampling** — temperature, top_k, top_p, min_p, top_n_sigma, xtc_prob, xtc_threshold, typical, adaptive_target, adaptive_decay, dynatemp_range, dynatemp_exp, seed, samplers, sampler_seq
8. **Mirostat** — mirostat (radio: 0/1/2), mirostat_lr, mirostat_ent
9. **Penalties** — repeat_last_n, repeat_penalty, presence_penalty, frequency_penalty, ignore_eos (checkbox)
10. **DRY** — dry_multiplier, dry_base, dry_allowed_length, dry_penalty_last_n, dry_sequence_breaker
11. **Grammar** — logit_bias, grammar (file), grammar_file, json_schema, json_schema_file
12. **Speculative** — spec_draft_model (file), spec_type (dropdown: ngram/mtp/lookup/server), spec_draft_n_max, spec_draft_n_min, spec_draft_p_split, spec_draft_p_min, spec_draft_device, spec_draft_ngl
13. **Prompt/Input** — prompt, system_prompt, file, in_file, binary_file, reverse_prompt, escape, special, interactive, interactive_first, multiline_input, in_prefix, in_suffix, warmup, perf
14. **Chat** — chat_template, chat_template_file, reasoning_format (dropdown: auto/verbose/off), reasoning_budget, jinja, prefill_assistant (checkbox)
15. **Display** — verbose_prompt, display_prompt, color (dropdown: on/off/auto), slot_prompt_similarity, simple_io, show_timings
16. **Server** (has **sub-panels**) — host, port, parallel, sequences, cont_batching, timeout, threads_http, api_key, ssl_key, ssl_cert, path, api_prefix
    - **WebUI** (sub-collapsible): webui, webui_config
    - **Server Features** (sub-collapsible): tools, embedding, rerank, metrics, props, slots
17. **Embedding** — pooling (dropdown: mean/cls/rank/step/none), attention (dropdown: causal/non-causal)

**Command Preview** (`ttk.LabelFrame`) at bottom of scroll area:
- `tk.Text` widget (height 4, wrap='word', font Consolas 9, initially disabled) + Scrollbar
- **Copy** button → clipboard
- **Use** button → pushes command to main toolbar's start button
- Auto-updates via `trace_add('write', ...)` on every option's StringVar

### 5.3 Monitor Tab

```
+----------------------------------------------------------+
|                                                          |
|  +-- Server Metrics --+  +-- Token Throughput (chart) --+|
|  | Prompt:  XXX tok/s |  |                                ||
|  | Eval:    XX.X tok/s|  | [Live bar/line chart]         ||
|  | Draft:   XX% acc.  |  |                                ||
|  | KV:      XXX MiB   |  |                                ||
|  | Graphs:  ZZZ reused|  |                                ||
|  +--------------------+  +--------------------------------+|
|                                                          |
|  +-- Slot Status --+  +-- System Resources --+           |
|  | Slot 0: [##--]  |  | CPU:  [####--] 60%  |            |
|  | Slot 1: [######]|  | MEM:  [######] 75%  |            |
|  | Slot 2: [--]    |  | SWAP: [--] 5%       |            |
|  | ...             |  | GPU:  [#######-]80% |            |
|  |                 |  | VRAM: 12GB/16GB     |            |
|  +-----------------+  | Temp: 72 C          |            |
|                       +---------------------+            |
|                                                          |
|  [Auto-Refresh: 2s] [Manual Refresh] [Export Stats]      |
+----------------------------------------------------------+
```

### 5.4 Logs Tab

```
+----------------------------------------------------------+
| Filter: [All] [Info] [Warn] [Error] [Clear]              |
+----------------------------------------------------------+
| [14:23:01] [INFO ] prompt eval time = 123.45 ms ...     |
| [14:23:02] [INFO ]        eval time = 67.89 ms ...      |
| ...                                                      |
+----------------------------------------------------------+
| Stats: Avg prompt=1234 tok/s Avg gen=56.7 tok/s         |
|        Draft=72.3% Checkpoints=15 Cache=45.1 MiB        |
+----------------------------------------------------------+
| [Save Log] [Export CSV]                                  |
+----------------------------------------------------------+
```

### 5.5 Slots Tab

Table showing all slots with:
- Slot ID, state (idle/processing), tokens processed, context usage, draft info, throughput

---

## 6. Architecture

### 6.1 Dependencies

```
Core (built-in):  tkinter, subprocess, json, urllib.request
External:         psutil (CPU/memory/swap monitoring)
Optional:         nvidia-smi (on PATH for GPU monitoring)
```

### 6.2 Module Structure

```
tools/llama_gui/
  main.py              # Entry point, window setup, preferences
  config_tab.py        # Config tab UI (collapsible sections, command preview)
  monitor_tab.py       # Monitor tab UI + MetricsPoller
  logs_tab.py          # Logs tab UI + LogParser
  slots_tab.py         # Slots tab UI
  process_mgr.py       # ServerProcessManager
  system_monitor.py    # CPU/memory/GPU monitoring
  log_parser.py        # Regex patterns + metric extraction
  api_client.py        # HTTP polling (/slots, /metrics, /props)
  collapsible_pane.py  # CollapsiblePane widget (extends ttk.LabelFrame)
  widget_factory.py    # OptionWidget factory (FileSelector, 3-state combobox, etc.)
  config_registry.py   # Option definitions (widget_type, choices, defaults, help_text)
  command_builder.py   # Builds CLI command string from option values
  tooltip.py           # Tooltip top-level widget
  assets/              # Static resources
```

### 6.3 Data Flow

1. **Config**: User sets options -> CommandBuilder generates CLI -> Preview updates
2. **Start**: ProcessManager launches llama-server with command -> Captures stdout/stderr
3. **Monitor**: Polls HTTP endpoints + system monitoring + log parsing
4. **Logs**: Real-time stdout/stderr capture + regex parsing + stats aggregation

### 6.4 Log Parser Regex (Python)

```python
PROMPT_EVAL_RE = re.compile(r'prompt eval time\s+=\s+([\d.]+)\s+ms\s+/\s+(\d+)\s+tokens(?:\s*\(.*?([\d.]+)\s+tokens per second\))?')
EVAL_RE = re.compile(r'eval time\s+=\s+([\d.]+)\s+ms\s+/\s+(\d+)\s+tokens(?:\s*\(.*?([\d.]+)\s+tokens per second\))?')
TOTAL_TIME_RE = re.compile(r'total time\s+=\s+([\d.]+)\s+ms\s+/\s+(\d+)\s+tokens')
DRAFT_RE = re.compile(r'draft acceptance\s+=\s+([\d.]+)\s+\((\d+)\s+accepted\s+/\s+(\d+)\s+generated\)')
GRAPHS_REUSED_RE = re.compile(r'graphs reused\s+=\s+(\d+)')
CHECKPOINT_RE = re.compile(r'created context checkpoint\s+(\d+)\s+of\s+(\d+)')
PROMPT_CACHE_RE = re.compile(r'prompt cache state:\s+(\d+)\s+prompts,\s+([\d.]+)\s+MiB')
```

---

## 7. Profile Management

**Not yet implemented.** The only persistence mechanism is `~/.llama-gui/preferences.json` (monitor tab refresh interval). No profile save/load UI exists in the config tab.

---

## 8. Implementation Status

- [x] **Phase 1**: Core process management + config tab with full CLI options
- [x] **Phase 2**: Monitor tab with HTTP polling + system monitoring + log parsing
- [x] **Phase 3**: Logs tab with filtering + StatsAggregation
- [x] **Phase 4**: Slots tab + Advanced options (Profile management not yet implemented)
- [ ] **Phase 5**: Polish - charts, export, presets, keyboard shortcuts
