# llama-gui — Agent Orientation Guide

This file is written for AI agents working on this tool. Read it before touching any code.

---

## What this tool is

`tools/llama_gui` is a **desktop GUI launcher** for `llama-server` (the HTTP inference server built by llama.cpp). It is written in pure Python using `tkinter`/`ttk` — no external UI frameworks, no web stack. It runs standalone via `python -m llama_gui` or `uv run llama-gui`.

The goal is to let users configure, start, stop, and monitor a local llama-server instance without touching the command line.

---

## Module map — read before editing anything

| File | What it owns | Key class/function |
|---|---|---|
| `main.py` | App entry point, top-level wiring | `MainWindow`, `main()` |
| `config_tab.py` | Config tab UI, profile toolbar, command preview | `ConfigTab` |
| `monitor_tab.py` | Monitor tab: server metrics, slots, system resources, chart | `MonitorTab`, `MetricsChart` |
| `logs_tab.py` | Logs tab: filtered text view | `LogsTab` |
| `widget_factory.py` | Per-option widget creation | `OptionWidget`, `_FileSelector`, `_OrderedListSelector` |
| `collapsible_pane.py` | Collapsible section panels | `CollapsiblePane` |
| `tooltip.py` | Hover tooltip popup | `Tooltip` |
| `api_client.py` | HTTP client to llama-server | `ServerAPI`, `parse_prometheus_metrics()` |
| `system_monitor.py` | CPU/MEM/GPU polling via /proc + nvidia-smi | `SystemMonitor` |
| `process_mgr.py` | subprocess wrapper for llama-server | `ServerProcess` |
| `profile_mgr.py` | JSON profiles in `~/.llama-gui/profiles/` | `ProfileManager` |
| `command_builder.py` | Builds CLI string from widget values | `build_command()`, `parse_cli_line()` |
| `config_registry.py` | All ~150 llama-server CLI option definitions | `_OPTIONS` dict |
| `log_parser.py` | Regex-based server log parsing | `LogMetrics`, `parse_line()` |
| `test_core.py` | Unit tests (no Tk, no live server) | `pytest test_core.py` |
| `test_regression.py` | Integration tests (needs server on :11435) | `pytest test_regression.py` |

Supporting docs in this directory:
- `UI_DESIGN.md` — current styling details, theme plans, color palette reference
- `spec.md` — full feature specification

---

## Architecture rules

1. **No blocking on the main thread.** All HTTP polling (`ServerAPI`) and long-running work runs via background threads or `root.after()` loops. Never call `time.sleep()` on the Tk thread.
2. **No external dependencies.** Only stdlib. `urllib` for HTTP, `subprocess` for the server process, `json` for profiles.
3. **Preferences** persist to `~/.llama-gui/preferences.json`. Keys: `refresh_ms`, `metrics_sample_ms`, `graph_smooth_ms`, `graph_time_window_s`, `health_timeout`, `server_bin`, `last_profile`, `theme_mode`.
4. **Profiles** are JSON files in `~/.llama-gui/profiles/`. Managed by `ProfileManager`.
5. **Options registry** (`config_registry.py`) is the single source of truth for all CLI options. If a new llama-server flag needs to be exposed, add it there — the widget, command builder, and profile system all derive from it.

---

## Thread model

```
Main thread (Tk event loop)
  └── root.after(50ms)  → _drain_log_queue()  [pipes server stdout/stderr into LogsTab]
  └── root.after(250ms) → MetricsChart._tick() [redraws performance graph]
  └── root.after(Nms)   → MonitorTab._poll()  [polls /metrics, /slots, /props]

Background threads (daemon, never touch Tk widgets directly)
  └── SystemMonitor     [reads /proc/stat, /proc/meminfo, nvidia-smi every 2s]
  └── ServerProcess     [reads stdout/stderr via readline(), pushes to queue.Queue]
```

**Rule**: background threads only write to `queue.Queue` or call thread-safe callbacks. All Tk widget updates happen in `after()` callbacks on the main thread.

---

## Theme

The tool uses the **Azure ttk theme** (https://github.com/rdbende/Azure-ttk-theme, MIT).

Theme files live at:
```
tools/llama_gui/theme/azure/
├── azure.tcl        ← source this file to load the theme
└── theme/           ← PNG assets (light/ and dark/ subdirectories)
```

Loading in `main.py`:
```python
tcl_path = Path(__file__).parent / "theme" / "azure" / "azure.tcl"
root.tk.call("source", str(tcl_path))
root.tk.call("set_theme", "dark")   # or "light"
```

Toggle at runtime (e.g. from Settings dialog):
```python
root.tk.call("set_theme", "light")   # switches without color artifacts
```

The theme name string used internally is `"azure-dark"` or `"azure-light"`. Check with:
```python
root.tk.call("ttk::style", "theme", "use")
```

### Extra styles provided by Azure theme
| Style string | Applied to | Effect |
|---|---|---|
| `Accent.TButton` | `ttk.Button` | Primary/highlighted button (blue accent) |
| `Toggle.TButton` | `ttk.Checkbutton` | Toggle button appearance |
| `Switch.TCheckbutton` | `ttk.Checkbutton` | iOS-style toggle switch |
| `Tick.TScale` | `ttk.Scale` | Solid tick thumb |
| `Card.TFrame` | `ttk.Frame` | Bordered card panel |

### MetricsChart canvas colors
The chart is a raw `tk.Canvas` — it does not inherit ttk theme colors. Colors are selected based on the active theme mode:

| Token | Dark | Light |
|---|---|---|
| `C_BG` | `#1e1e1e` | `#f0f0f0` |
| `C_PLOT_BG` | `#252525` | `#ffffff` |
| `C_GRID` | `#3a3a3a` | `#cccccc` |
| `C_AXIS` | `#666666` | `#999999` |
| `C_TEXT` | `#aaaaaa` | `#444444` |
| PP line | `#4e9eff` | `#4e9eff` |
| TG line | `#4ec94e` | `#4ec94e` |
| Draft% | `#ffaa44` | `#ffaa44` |

### Tooltip colors
- Dark mode: `bg=#2d2d2d`, `fg=#e0e0e0`
- Light mode: `bg=#ffffea`, `fg=#333333`

---

## Task tracking policy (for agents)

- Every user comment or request — even casual ones during UI testing — is a todo item. Capture it immediately with `TodoWrite`.
- Prioritize: bugs and crashes first, then broken UX, then new features, then polish.
- Stay focused: finish the current highest-priority item before starting the next one. Do not jump between tasks.
- Mark completed only after the fix is verified in code, not just intended.
- Never lose a request. If the user mentions something in passing while reporting a bug, add it to the list.

## Working style

- One logical change per edit. Prefer surgical edits over full-file rewrites.
- All HTTP polling and long-running work must happen off the main Tk thread or via `after()` loops. Never block the event loop.
- When a fix requires restarting the app, say so explicitly.

---

## Running tests

```bash
# Unit tests (no server needed)
cd tools/llama_gui
python -m pytest test_core.py -v

# Integration tests (requires llama-server on localhost:11435)
python -m pytest test_regression.py -v
```

---

## Common pitfalls

- **Do not call `ttk.Style.theme_use(...)` directly** after Azure is loaded — use `root.tk.call("set_theme", ...)` instead, otherwise colors will be wrong on subsequent switches.
- **`CollapsiblePane` uses `grid_forget()` to hide content** — don't use `pack_forget()` on its children.
- **`ConfigTab` scroll frame** binds `<MouseWheel>`, `<Button-4>`, `<Button-5>` globally on the root — be careful adding competing bindings.
- **`config_registry.py` option tuples** have the shape `(label, default, widget_type, choices, sub_keys, help_text)`. Always use the named accessors or index constants, not raw integers.
- **Profiles are saved on every "Save"** — they do not auto-save. The last used profile name is stored in preferences.
