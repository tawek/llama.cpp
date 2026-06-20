# llama-gui UI Design Notes

## Current Architecture

### Widget Toolkit
- **Python standard library only**: `tkinter` + `tkinter.ttk`
- No external theme libraries (as of initial implementation)
- Platform theme: `ttk.Style.theme_use('default')` on Linux; native on other platforms

### Layout Overview

```
MainWindow (tk.Tk, 1100x700)
├── Toolbar (ttk.Frame, fill='x')
│   ├── Start / Stop / Restart (ttk.Button × 3)
│   ├── Status label (ttk.Label — gray/orange/green/red foreground)
│   ├── Open in Browser (ttk.Button)
│   └── Settings (ttk.Button → modal Toplevel)
├── Notebook (ttk.Notebook)
│   ├── Config tab (ConfigTab)
│   ├── Monitor tab (MonitorTab)
│   └── Logs tab (LogsTab)
└── Status bar (ttk.Frame + ttk.Label, relief='sunken')
```

### Config Tab
- `tk.Canvas` + `ttk.Scrollbar` containing a `ttk.Frame` (virtual scrollable area)
- Profile toolbar: `ttk.Combobox` + Save / Save As / Rename / Delete buttons
- 18 `CollapsiblePane` sections (ttk.LabelFrame subclass), grid-stacked
- Command Preview: `ttk.LabelFrame` with `tk.Text(height=4)` + Copy + Use buttons

### Monitor Tab
- `ttk.PanedWindow(orient='vertical')`
  - Top pane: Server Metrics + Slots + System Resources (3 × `ttk.LabelFrame`)
  - Bottom pane: `MetricsChart` (custom `tk.Canvas`, dark bg `#1e1e1e`)

### Server Metrics Panel (fixed-width left column)
Each metric is a label above a `ttk.Progressbar`, same layout as System Resources:

| Gauge | Key | Unit | Adaptive max |
|-------|-----|------|-------------|
| PP tok/s | `pp` | tok/s | dynamic (initial 10000) |
| TG tok/s | `tg` | tok/s | dynamic (initial 5000) |
| TD tok/s | `td` | tok/s | dynamic (initial 5000) |
| TA tok/s | `ta` | tok/s | dynamic (initial 5000) |
| DA %    | `da` | % | 100 (fixed) |

Values are read from the same smoothed rate buffers used by `MetricsChart`
(4 Hz update via `_graph_tick()`). The bar ceiling auto-expands when the
current value exceeds 80 % of the current ceiling; ceiling = 1.2 × max_seen.

A grey LED diode + text label at the bottom show connection status:
- Connected + green LED when `/health` returns `"ok"`
- Disconnected + grey LED when no health response

### Logs Tab
- Filter bar: 4 `ttk.Radiobutton` (All/Info/Warn/Error) + Clear + Save
- `tk.Text(wrap='none', font=('Consolas', 8))` + H/V scrollbars
- Lazy population: batched inserts via `after(10, ...)` on tab `<Map>`

---

## Current Styling

| Element | Current approach |
|---|---|
| Global theme | `ttk.Style.theme_use('default')` (Linux) |
| Monospace font | JetBrains Mono → Cascadia Code → … → Courier New, size 9 |
| Xft rendering | `hintslight` + `antialias=1` via `root.option_add` |
| MetricsChart bg | `#1e1e1e` (hardcoded dark canvas) |
| Chart plot bg | `#252525` |
| Chart grid | `#3a3a3a` |
| Chart axis | `#666666` |
| Chart text | `#aaaaaa` |
| Chart PP line | `#4e9eff` |
| Chart TG line | `#4e9eff` (blue, shares PP color) |
| Chart DG line | `#4ec94e` (green, formerly TG color) |
| Chart Draft% | `#ffaa44` |
| Chart DA line | `#ffcc00` |
| Tooltip | `bg=#ffffea`, `fg=#333`, `relief=solid` |
| Help `?` label | `foreground='dodger blue'`, `font=('', 8, 'bold')` |
| Section header | `font=('', 9, 'bold')`, `cursor='hand2'` |
| Status colors | green / red / orange / gray (direct `.config(foreground=...)`) |

---

## Planned Theme: Azure-ttk-theme

**Source**: https://github.com/rdbende/Azure-ttk-theme  
**License**: MIT  
**Style**: Fluent Design inspired, supports light and dark modes

### Integration approach
- Bundle `azure.tcl` + `theme/` directory inside `tools/llama_gui/theme/azure/`
- Load at startup via `root.tk.call("source", "<path>/azure.tcl")`
- Apply with `root.tk.call("set_theme", "dark")` or `"light"`
- Expose dark/light toggle in the Settings dialog
- Persist choice in `~/.llama-gui/preferences.json` as `"theme_mode": "dark"|"light"`

### New style elements available (Azure theme)
| Style | Applied to | Effect |
|---|---|---|
| `Accent.TButton` | `ttk.Button` | Highlighted/primary action button |
| `Toggle.TButton` | `ttk.Checkbutton` | Toggle button appearance |
| `Switch.TCheckbutton` | `ttk.Checkbutton` | iOS-style toggle switch |
| `Tick.TScale` | `ttk.Scale` | Solid tick instead of circle thumb |
| `Card.TFrame` | `ttk.Frame` | Bordered card panel |

### MetricsChart dark palette — dark mode (keep as-is)
The `MetricsChart` canvas uses hardcoded dark colors. These remain valid in dark mode.  
For light mode, chart colors should adapt:

| Token | Dark mode | Light mode (proposed) |
|---|---|---|
| `C_BG` | `#1e1e1e` | `#f0f0f0` |
| `C_PLOT_BG` | `#252525` | `#ffffff` |
| `C_GRID` | `#3a3a3a` | `#cccccc` |
| `C_AXIS` | `#666666` | `#999999` |
| `C_TEXT` | `#aaaaaa` | `#444444` |

### Tooltip colors
- Dark mode: `bg=#2d2d2d`, `fg=#e0e0e0`, `relief=solid`
- Light mode: `bg=#ffffea`, `fg=#333333`, `relief=solid` (unchanged)

### Status label colors (keep semantic meaning)
- Running/healthy → `green` / `#4ec94e`
- Starting → `orange`
- Stopped/error → `red`
- Idle → `gray`

---

## File Layout (after integration)

```
tools/llama_gui/
├── theme/
│   └── azure/
│       ├── azure.tcl          # main theme script (sources set_theme proc)
│       └── theme/             # PNG assets (light + dark variants)
│           ├── light/
│           └── dark/
├── main.py                    # loads theme, exposes set_theme()
└── ...
```
