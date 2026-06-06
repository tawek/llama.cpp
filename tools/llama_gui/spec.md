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
| 12 | Speculative | `--spec-type` (ordered list: ngram-simple/ngram-map-k/ngram-map-k4v/ngram-mod/ngram-cache/draft-simple/draft-eagle3/draft-mtp), `--spec-draft-n-max`, `--spec-draft-n-min`, draft model flags (`--spec-draft-model`, `--spec-draft-hf`, `--spec-draft-ngl`, etc.), ngram flags per type (`--spec-ngram-*`), lookup cache (`--lookup-cache-static/dynamic`) |
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
| string (path) | `file` | ttk.Entry + Browse button (per-key filters) | `-m model.gguf` |
| string (directory) | `directory` | ttk.Entry + Browse button (folder dialog) | `--slot-save-path /path/to/cache` |
| string (enum) | `dropdown` | ttk.Combobox (state='readonly') | `--rope-scaling {none,linear,yarn}` |
| string (enum, shortlist) | `radio` | ttk.Radiobutton row | `--mirostat {0,1,2}` |
| string (comma-sep) | `text` | tk.Entry (StringVar) | `-ts 0.5,0.3,0.2` |
| string (free) | `text` | tk.Entry (StringVar) | `--prompt "hello"` |
| string (key=value) | `text` | tk.Entry (StringVar) | `--override-kv KEY=TYPE:VALUE` |
| ordered enum list | `ordered_list_of_options` | `_OrderedListSelector` dual-list widget | `--spec-type ngram-simple,draft-mtp` |

`ordered_list_of_options` widget: two `tk.Listbox` columns (Available / Selected) with `>>` / `<<` transfer buttons and Up / Down reorder buttons. Internal `StringVar` holds comma-joined selection. Available choices come from `choices` in the registry entry.

File picker filters by option key:

| Key | Dialog Type | Filters |
|-----|-------------|---------|
| `model`, `spec_draft_model`, `mmproj`, `lora` | file | `*.gguf` |
| `image` | file | `*.png *.jpg *.jpeg *.bmp *.tiff *.webp` |
| `audio` | file | `*.wav *.mp3 *.ogg *.flac *.m4a` |
| `grammar_file` | file | `*.gbnf`, `*.txt` |
| `json_schema_file` | file | `*.json` |
| `ssl_key` | file | `*.pem`, `*.key` |
| `ssl_cert` | file | `*.pem`, `*.crt` |
| `chat_template_file` | file | `*.jinja`, `*.txt` |
| `file` (prompt), `in_file` | file | `*.txt` |
| `slot_save_path` | **directory** | folder picker |

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
| `--cache-type-k` | f16 | `--cache-type-v` | f16 |
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
| `n_tokens_pp_total` | counter | Total prompt tokens processed (event-based) |
| `n_tokens_tg_total` | counter | Total generated tokens (event-based) |
| `n_tokens_td_total` | counter | Total tokens drafted (event-based) |
| `n_tokens_tda_total` | counter | Total draft tokens accepted (event-based) |
| `n_tokens_tdr_total` | counter | Total draft tokens rejected (event-based) |

### 3.4 Event-Based Metrics (from server_context.cpp:server_event_metrics)

A new monotonic counter system collects per-token events via a 256K entry ring buffer. The server appends events at the C++ level; the GUI polls `/metrics` every 5s and computes rates by differencing successive samples.

| Counter | Source | Notes |
|---------|--------|-------|
| `n_tokens_pp_total` | `EVT_TOKEN_PP` | Prompt processing tokens |
| `n_tokens_tg_total` | `EVT_TOKEN_TG` | All generated tokens (speculative + non-speculative) |
| `n_tokens_td_total` | `EVT_TOKEN_TD` | Total draft tokens generated by the draft model |
| `n_tokens_tda_total` | `EVT_TOKEN_TDA` | Draft tokens accepted by the target model |
| `n_tokens_tdr_total` | `EVT_TOKEN_TDR` | Draft tokens rejected (rollback count) |

Detection heuristic: presence of all five counters (`n_tokens_pp_total`, `n_tokens_tg_total`, `n_tokens_td_total`, `n_tokens_tda_total`, `n_tokens_tdr_total`) in the parsed `/metrics` response. Once detected, the GUI switches to event-based rate computation for **all** per-second values and suppresses log-parser data entirely.

Rate computation:
```
pp_rate  = (pp_total_now  - pp_total_prev)  / dt
tg_rate  = (tg_total_now  - tg_total_prev)  / dt
td_rate  = (td_total_now  - td_total_prev)  / dt
tda_rate = (tda_total_now - tda_total_prev) / dt
tdr_rate = (tdr_total_now - tdr_total_prev) / dt
draft_accept  = tda_rate / (tda_rate + tdr_rate) * 100  (or 0 if both 0)
```

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

A scrollable canvas (tk.Canvas + ttk.Scrollbar, mouse-wheel bound) containing:
- **Profile toolbar** at top (row 0) — profile dropdown, Save / Save As... / Rename / Delete buttons
- **18 collapsible sections** (CollapsiblePane widgets)
- **Command Preview** frame at bottom

The **llama-server binary path** and **startup health-check timeout** are no longer per-profile settings — they live in the **Settings dialog** (toolbar button, section 9).

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
3. **Cache & KV** — cache_prompt, cache_reuse, cache_ram, cache_type_k (dropdown: f16/f32/bf16/q8_0/q4_0/q4_1/iq4_nl/q5_0/q5_1), cache_type_v (same dropdown), kv_unified, cache_idle_slots, slot_save_path, ctx_checkpoints, checkpoint_every_n
4. **Context & Batch** — ctx_size, batch_size, ubatch_size, predict, keep, swa_full
5. **CPU** — threads, threads_batch, cpu_mask, cpu_range, cpu_strict, prio, poll, prio_prompt, prio_predict, prio_batch, prio_draft
6. **RoPE & Scaling** — rope_scaling (dropdown: none/linear/yarn), rope_scale, rope_freq_base, rope_freq_scale, yarn_orig_ctx, yarn_ext_factor, yarn_attn_factor, yarn_beta_fast, yarn_beta_slow, grp_attn_n, grp_attn_w, flash_attn (dropdown: auto/on/off, default auto)
7. **Sampling** — temperature, top_k, top_p, min_p, top_n_sigma, xtc_prob, xtc_threshold, typical, adaptive_target, adaptive_decay, dynatemp_range, dynatemp_exp, seed, samplers, sampler_seq
8. **Mirostat** — mirostat (radio: 0/1/2), mirostat_lr, mirostat_ent
9. **Penalties** — repeat_last_n, repeat_penalty, presence_penalty, frequency_penalty, ignore_eos (checkbox)
10. **DRY** — dry_multiplier, dry_base, dry_allowed_length, dry_penalty_last_n, dry_sequence_breaker
11. **Grammar** — logit_bias, grammar (file), grammar_file, json_schema, json_schema_file
12. **Speculative** — layout differs from other sections (sentinel `'__speculative__'` in SECTIONS):
    - **Always-visible** top rows: spec_type (`ordered_list_of_options`, choices: ngram-simple / ngram-map-k / ngram-map-k4v / ngram-mod / ngram-cache / draft-simple / draft-eagle3 / draft-mtp), spec_draft_n_max, spec_draft_n_min
    - **Per-type sub-panels** (`CollapsiblePane`) — shown/hidden based on which types appear in spec_type value:
      - **Draft Model** (shown for any of draft-simple, draft-eagle3, draft-mtp): spec_draft_model, spec_draft_hf, spec_draft_threads, spec_draft_threads_batch, spec_draft_cpu_mask, spec_draft_cpu_range, spec_draft_cpu_strict, spec_draft_prio, spec_draft_poll, spec_draft_type_k, spec_draft_type_v, spec_draft_cpu_moe, spec_draft_n_cpu_moe, spec_draft_override_tensor, spec_draft_p_split, spec_draft_p_min, spec_draft_device, spec_draft_ngl
      - **Ngram Simple** (ngram-simple): ngram_min, ngram_max, ngram_no_alloc, spec_ngram_simple_size_n, spec_ngram_simple_size_m, spec_ngram_simple_min_hits
      - **Ngram Map-k** (ngram-map-k): ngram_min, ngram_max, ngram_no_alloc, spec_ngram_map_k_size_n, spec_ngram_map_k_size_m, spec_ngram_map_k_min_hits
      - **Ngram Map-k4v** (ngram-map-k4v): ngram_min, ngram_max, ngram_no_alloc, spec_ngram_map_k4v_size_n, spec_ngram_map_k4v_size_m, spec_ngram_map_k4v_min_hits
      - **Ngram Mod** (ngram-mod): ngram_min, ngram_max, ngram_no_alloc, spec_ngram_mod_n_match, spec_ngram_mod_n_max, spec_ngram_mod_n_min
      - **Ngram Cache** (ngram-cache): lookup_cache_static, lookup_cache_dynamic
    - Sub-panels are toggled by a `trace_add('write', ...)` on the spec_type `_var`
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
|  | Draft:   XX% acc.  |  | [TG + dg (draft gen) + da     ||
|  +--------------------+  | [draft accepted) lines]       ||
|                          |                                |
|                          |  +-- Slot Status --+          |
|                          |  | Slot 0: [##--]  |          |
|                          |  | Slot 1: [######]|          |
|                          |  | ...             |          |
|                          |  +-----------------+          |
|                          |                                |
|                          |  +-- System Resources --+      |
|                          |  | CPU:  [####--] 60%  |      |
|                          |  | MEM:  [######] 75%  |      |
|                          |  | GPU:  [#######-]80% |      |
|                          |  | VRAM: 12GB/16GB     |      |
|                          |  | Temp: 72 C          |      |
|                          |  +---------------------+      |
|                                                          |
|  [Auto-Refresh: 2s] [Manual Refresh] [Export Stats]      |
+----------------------------------------------------------+
```

TG chart panels:
- **PP tok/s** — prompt processing rate (blue)
- **TG tok/s** — generation rate (green) + overlay: draft gen (lightgray) + draft acc (yellow)
- **Draft %** — acceptance percentage (orange)

**Metrics data source** (hierarchical, auto-switching):

When event-based counters are **not** detected (old server versions):
- Prompt/Gen rates from `prompt_tokens_seconds` / `predicted_tokens_seconds` gauges
- Draft data from log-parser fallback

When event-based counters **are** detected:
- All per-second rates (prompt, generation, draft) computed from deltas of the 5 monotonic counters
- Log-parser data fully suppressed

### 5.4 Logs Tab

```
+----------------------------------------------------------+
| Filter: [All] [Info] [Warn] [Error]          [Clear]     |
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

**Internal storage**: `_log_lines: list[tuple[str, str, str]]` — `(level, timestamp_str, text)`. Timestamps are captured at `add_log_line()` time via `time.strftime('%H:%M:%S')`. Filter radio buttons call `_reapply_filter()` on write, which rebuilds the text widget from stored tuples using original timestamps.

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

### 7.1 Overview

Profiles provide named presets of all configuration option values, persisted across sessions. A toolbar/combobox at the top of the Config tab allows creating, loading, saving, and deleting profiles.

### 7.2 Profile Toolbar

```
[ Profile: [Default  v] ] [Save] [Save As...] [Rename] [Delete]
```

- **Profile dropdown**: `ttk.Combobox` listing all profile names + `"Default"` (built-in)
- **Save**: overwrites current profile with current option values
- **Save As...**: prompts for new name, copies current values
- **Rename**: prompts for new name, renames profile file on disk; disabled for `"Default"`
- **Delete**: removes profile file (disabled for `"Default"`)

### 7.3 Storage Format

- **Directory**: `~/.llama-gui/profiles/`
- **Extension**: `.json`
- **Schema**:
  ```json
  {
    "name": "my-preset",
    "options": {
      "model": "/path/to/model.gguf",
      "temperature": 0.7,
      "mlock": "on",
      ...
    }
  }
  ```
- Option keys use the internal underscore names (e.g. `gpu_layers`), values match the widget's internal representation (`''`, `'on'`, `'off'` for checkboxes, empty string for unset numerics, etc.)

### 7.4 Behaviors

| Operation | Behavior |
|-----------|----------|
| **Load** (dropdown selection) | Prompts to save unsaved changes first (Yes/No/Cancel). All widget values are set from the profile's `options` dict; command preview refreshes; `_dirty` cleared |
| **Save** | Current widget values are serialized to the selected profile's file; `_dirty` cleared |
| **Save As** | Dialog prompts for name; new file created; dropdown selects it; `_dirty` cleared |
| **Rename** | `simpledialog.askstring` prompts for new name; `ProfileManager.rename()` does atomic rename (write new, remove old); dropdown + `_current_profile` updated |
| **Delete** | File removed from disk; switches to `"Default"` via `_do_switch_profile()`; `_dirty` cleared |
| **Auto-restore** | Last active profile name saved in `preferences.json`; restored on launch |
| **Close window** | `on_close_request()` checks `_dirty`; if set, shows Yes/No/Cancel unsaved-changes dialog before allowing close |

#### Dirty Tracking

- `_dirty: bool` — set `True` whenever any widget `StringVar` fires its `trace_add('write')` callback via `_refresh()`.
- `_ready: bool` — initialized `False`; set `True` after `_build_ui()` completes. `_refresh()` only sets `_dirty = True` when `_ready` is `True`, preventing startup construction from marking the session dirty.
- `_load_preferences()` also calls `_apply_options()` after `_build_ui()`, so it explicitly sets `config_tab._dirty = False` after loading.

### 7.5 llama-server Binary Path

Configured in the **Settings dialog** (toolbar button, see section 9). No longer a per-profile Config tab row.

- **Widget**: `ttk.Entry` + `"..."` Browse button (file dialog) inside a `Toplevel` modal
- **Storage**: Saved in `preferences.json` under key `server_bin`
- **Usage**: When starting, `main.py` prefixes the built command with the configured binary path
- **Scope**: Global — one setting shared across all profiles

### 7.6 Implementation

- `profile_mgr.py` — `ProfileManager` class: `list_profiles()`, `load(name)`, `save(name, options)`, `delete(name)`, `rename(old, new)` (atomic: write new, remove old)
- `config_tab.py` — profile toolbar with Combobox + Save/Save As.../Rename/Delete buttons; `_dirty`/`_ready` guard; `on_close_request()`; `_do_switch_profile()` centralises load + dirty-clear + button-state update; `_prompt_unsaved()` → `messagebox.askyesnocancel`
- `main.py` — `_show_settings()` modal; `save_preferences()` includes `server_bin` + `health_timeout`; `_load_preferences()` restores both and clears `_dirty`
- `widget_factory.py` — `set_value(value)` on `OptionWidget` for profile loading; `_OrderedListSelector` for `ordered_list_of_options`

---

## 9. Settings Dialog

Opened via a **Settings** button in the main toolbar (right of the browser button, separated by a vertical separator).

```
+-------------------------------------+
| Settings                            |
+-------------------------------------+
| Server binary: [llama-server  ] [...] |
| Startup timeout (s): [120   ↕ ]     |
+-------------------------------------+
|        [  OK  ]  [ Cancel ]         |
+-------------------------------------+
```

- **Server binary**: `ttk.Entry` (width 42) + `"..."` Browse button. Pre-filled from `config_tab._server_bin_var`. On OK, writes back to `_server_bin_var`.
- **Startup timeout**: `ttk.Spinbox` (10–600, step 10). Controls `self._health_check_timeout` in `main.py`.
- **OK**: applies values, calls `save_preferences()`, destroys dialog.
- **Cancel**: destroys dialog without changes.
- Modal: `dlg.transient(root)` + `dlg.grab_set()`.

Storage in `preferences.json`:

```json
{
  "server_bin": "llama-server",
  "health_timeout": 120,
  "refresh_ms": 2000,
  "last_profile": "my-preset"
}
```

---

## 10. Implementation Status

- [x] **Phase 1**: Core process management + config tab with full CLI options
- [x] **Phase 2**: Monitor tab with HTTP polling + system monitoring + log parsing
- [x] **Phase 3**: Logs tab with filtering + StatsAggregation
- [x] **Phase 4**: Slots tab + Advanced options
- [x] **Phase 4b**: Profiles — save/load/copy/delete config presets (section 7)
- [x] **Phase 4c**: Process robustness — error handling, health check, crash detection
- [x] **Phase 4d**: Monitoring completeness — `/metrics` polling, log filter fix
- [x] **Phase 4e**: Cleanup — remove dead code (`section_builder.py`, unused functions)
- [x] **Phase 4f**: Speculative section revamp — `ordered_list_of_options` for spec_type, per-type sub-panels, all ngram/draft flags wired in registry + command builder
- [x] **Phase 4g**: Profile improvements — Rename button, dirty tracking with unsaved-changes prompt on switch and close, delete fix
- [x] **Phase 4h**: Settings dialog — server binary + health timeout moved out of config tab into toolbar modal; server_bin + health_timeout persisted in preferences.json
- [x] **Phase 4i**: Bug fixes — KV cache types corrected to ggml type names (`f16/f32/bf16/q8_0/…`), flash_attn changed to dropdown, fit_target changed to text, log line timestamps captured at receipt time, `~` expansion in subprocess args, dirty false-positive on startup fixed
- [ ] **Phase 5**: Polish — charts, export, presets, keyboard shortcuts
