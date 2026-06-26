"""
Main entry point for llama.cpp GUI launcher.
Wires together config, monitor, logs tabs and process management.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import queue
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_tab import ConfigTab
from monitor_tab import MonitorTab
from logs_tab import LogsTab
from api_client import ServerAPI
from process_mgr import ServerProcess
from system_monitor import SystemMonitor


def _detect_system_theme() -> str:
    """Return 'dark' or 'light' by querying the OS colour-scheme preference.

    Supports Windows (registry), macOS (defaults), and Linux/freedesktop
    (gsettings org.gnome.desktop.interface color-scheme, with a fallback to
    the XDG_CURRENT_DESKTOP / GTK_THEME environment variables).
    Returns 'dark' when the preference cannot be determined.
    """
    import platform
    import subprocess

    system = platform.system()
    try:
        if system == 'Windows':
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize')
            val, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
            return 'light' if val == 1 else 'dark'

        elif system == 'Darwin':
            result = subprocess.run(
                ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                capture_output=True, text=True, timeout=2)
            return 'dark' if 'dark' in result.stdout.lower() else 'light'

        else:  # Linux / BSD / other freedesktop systems
            # Try gsettings (GNOME / KDE with gnome-settings-daemon)
            result = subprocess.run(
                ['gsettings', 'get',
                 'org.gnome.desktop.interface', 'color-scheme'],
                capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                return 'dark' if 'dark' in result.stdout.lower() else 'light'

            # Fallback: GTK_THEME env var set by the session
            gtk_theme = os.environ.get('GTK_THEME', '').lower()
            if gtk_theme:
                return 'dark' if 'dark' in gtk_theme else 'light'

    except Exception:
        pass

    return 'dark'


class MainWindow:
    """Main application window."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('llama.cpp GUI Launcher')
        self.root.geometry('1100x700')
        self._set_icon()
        self._theme_mode = 'dark'  # default; overridden by saved preferences
        self._configure_fonts()

        # Shared components
        self.process = ServerProcess()
        self.sys_monitor = SystemMonitor()
        self.api = ServerAPI()

        # State
        self._command = ''
        self._monitoring = False
        self._health_check_id = None
        self._log_queue: queue.Queue = queue.Queue()   # thread → main-thread

        # Server URL for external monitoring (must be set before _build_ui)
        self._server_url_var = tk.StringVar()

        # Setup UI
        self._build_ui()

        # Connect callbacks — background thread puts into queue; main thread
        # drains it every 50 ms.  Avoids thousands of after(0) events during
        # server startup bursts.
        self.process.on_stdout(self._log_queue.put)
        self.process.on_stopped(
            lambda: self.root.after(0, self._on_process_stopped))

        # Start log drain loop
        self._drain_log_queue()

        # Start background system monitor (needed for CPU delta calculation)
        self.sys_monitor.start(interval=2.0)

        # Load saved preferences
        self._load_preferences()

        # Start auto-monitoring on launch (connects to configured URL)
        self.root.after(500, self._start_auto_monitor)

    def _set_icon(self):
        """Set the window icon from the bundled base64 PNG."""
        try:
            import base64
            from icon import ICON_B64
            data = base64.b64decode(ICON_B64)
            img = tk.PhotoImage(data=data)
            self.root.iconphoto(True, img)
            self._icon_img = img   # keep reference — GC would blank the icon
        except Exception:
            pass   # icon is cosmetic; never crash over it

    def _configure_fonts(self):
        import tkinter.font as tkfont
        import platform

        # ── Azure ttk theme ───────────────────────────────────────────────────
        # Bundled under theme/azure/azure.tcl.  Must be sourced before any
        # widgets are created.  Use root.tk.call("set_theme", ...) to switch
        # modes — do NOT use ttk.Style.theme_use() directly after this point
        # or the palette will be incorrect on subsequent switches.
        _tcl = Path(__file__).parent / 'theme' / 'azure' / 'azure.tcl'
        try:
            self.root.tk.call('source', str(_tcl))
            self.root.tk.call('set_theme', self._theme_mode)
        except Exception as exc:
            # Fallback to clam if the TCL file is missing
            import warnings
            warnings.warn(f'Azure theme not loaded: {exc}')
            ttk.Style(self.root).theme_use('clam')

        # ── Xft hints (X11 only) ─────────────────────────────────────────────
        if platform.system() == 'Linux':
            try:
                self.root.option_add('*Xft.hintstyle', 'hintslight')
                self.root.option_add('*Xft.antialias', '1')
            except Exception:
                pass

        # ── TkFixedFont ───────────────────────────────────────────────────────
        fixed = tkfont.nametofont('TkFixedFont')
        available = set(tkfont.families())
        for candidate in ('JetBrains Mono', 'Fira Code', 'Cascadia Code',
                          'Consolas', 'DejaVu Sans Mono', 'Liberation Mono',
                          'Menlo', 'Courier New'):
            if candidate in available:
                fixed.configure(family=candidate, size=9)
                break

    def set_theme(self, mode: str):
        """Switch between 'dark', 'light', or 'system' Azure theme.

        'system' resolves the OS colour-scheme preference at call time and
        stores the *preference* as 'system' (so it re-resolves on next launch)
        while applying the resolved variant immediately.
        """
        if mode not in ('dark', 'light', 'system'):
            return
        self._theme_mode = mode
        resolved = _detect_system_theme() if mode == 'system' else mode
        try:
            self.root.tk.call('set_theme', resolved)
        except Exception:
            pass
        # Propagate to canvas-based widgets that manage their own colors
        if hasattr(self, 'monitor_tab'):
            self.monitor_tab.set_theme(resolved)

    def _build_ui(self):
        # Top toolbar
        self._build_toolbar()

        # Tab control
        self._build_tabs()

        # Bottom status bar
        self._build_statusbar()

    def _build_toolbar(self):
        # Two-row toolbar: server controls on top, connection controls below.
        # The Entry widget expands to fill available space in row 1.
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill='x', padx=4, pady=4)

        # ── Row 0: Server lifecycle controls ──────────────────────────────────
        row0 = ttk.Frame(toolbar)
        row0.pack(fill='x')

        self._btn_start = ttk.Button(row0, text='Start',
                                      command=self._start_server)
        self._btn_start.grid(row=0, column=0, padx=2, pady=2, sticky='w')

        self._btn_stop = ttk.Button(row0, text='Stop', state='disabled',
                                     command=self._stop_server)
        self._btn_stop.grid(row=0, column=1, padx=2, pady=2, sticky='w')

        self._btn_restart = ttk.Button(row0, text='Restart', state='disabled',
                                        command=self._restart_server)
        self._btn_restart.grid(row=0, column=2, padx=2, pady=2, sticky='w')

        ttk.Separator(row0, orient='vertical').grid(
            row=0, column=3, padx=8, pady=2, sticky='ns')

        self._lbl_server_status = ttk.Label(row0, text='Server: Not started',
                                             foreground='gray')
        self._lbl_server_status.grid(row=0, column=4, padx=4, pady=2, sticky='w')

        ttk.Separator(row0, orient='vertical').grid(
            row=0, column=5, padx=8, pady=2, sticky='ns')

        self._btn_settings = ttk.Button(row0, text='Settings',
                                         command=self._show_settings)
        self._btn_settings.grid(row=0, column=6, padx=2, pady=2, sticky='e')

        # ── Row 1: Connection controls ────────────────────────────────────────
        row1 = ttk.Frame(toolbar)
        row1.pack(fill='x')

        ttk.Label(row1, text='URL:').grid(row=0, column=0, padx=2, pady=2, sticky='e')

        self._entry_url = ttk.Entry(row1, textvariable=self._server_url_var, width=42)
        self._entry_url.grid(row=0, column=1, padx=2, pady=2, sticky='ew')
        self._entry_url.bind('<Return>', lambda e: self._connect_to_url())

        self._btn_connect = ttk.Button(row1, text='Connect',
                                        command=self._connect_to_url)
        self._btn_connect.grid(row=0, column=2, padx=2, pady=2, sticky='w')

        ttk.Separator(row1, orient='vertical').grid(
            row=0, column=3, padx=8, pady=2, sticky='ns')

        self._btn_open_browser = ttk.Button(row1, text='Open in Browser',
                                             command=self._open_browser,
                                             state='disabled')
        self._btn_open_browser.grid(row=0, column=4, padx=2, pady=2, sticky='e')

        row1.columnconfigure(1, weight=1)

    def _build_tabs(self):
        self._notebook = ttk.Notebook(self.root)
        self._notebook.pack(fill='both', expand=True, padx=4, pady=4)

        # Config tab
        self.config_tab = ConfigTab(self._notebook, self.root)
        self._notebook.add(self.config_tab, text='Config')

        # Monitor tab
        self.monitor_tab = MonitorTab(self._notebook, self.root)
        self._notebook.add(self.monitor_tab, text='Monitor')

        # Logs tab
        self.logs_tab = LogsTab(self._notebook, self.root)
        self._notebook.add(self.logs_tab, text='Logs')

        # Connect dependencies
        self.monitor_tab.set_dependencies(self.api, self.sys_monitor, self.process)
        self.logs_tab._on_metrics_update = None  # log-parser path replaced by /metrics + /slots

    def _build_statusbar(self):
        self._statusbar = ttk.Frame(self.root)
        self._statusbar.pack(fill='x', side='bottom')

        self._status_label = ttk.Label(self._statusbar, text='Ready',
                                        relief='sunken', anchor='w')
        self._status_label.pack(fill='x', expand=True, padx=2, pady=2)

    def set_command(self, command):
        """Set the server command from config tab."""
        self._command = command

    def _set_buttons_started(self):
        self._btn_start.config(state='disabled')
        self._btn_stop.config(state='normal')
        self._btn_restart.config(state='normal')

    def _set_buttons_stopped(self):
        self._btn_start.config(state='normal')
        self._btn_stop.config(state='disabled')
        self._btn_restart.config(state='disabled')
        self._btn_open_browser.config(state='disabled')
        self._lbl_server_status.config(text='Server: Not started',
                                        foreground='gray')

    def _ensure_directories(self):
        """Create any directories required by the current command before launch."""
        opts = self.config_tab.get_options()
        dir_keys = ('slot_save_path',)
        for key in dir_keys:
            opt = opts.get(key)
            if opt is None:
                continue
            val = opt.get_value()
            if not val:
                continue
            path = os.path.expanduser(str(val))
            if not os.path.exists(path):
                try:
                    os.makedirs(path, exist_ok=True)
                    self.logs_tab.add_log_line(f'Created directory: {path}')
                except OSError as e:
                    self.logs_tab.add_log_line(f'Warning: could not create {path}: {e}')

    def _update_api_url(self):
        """Sync api.base_url with the host/port currently configured."""
        opts = self.config_tab.get_options()

        host_opt = opts.get('host')
        port_opt = opts.get('port')

        host = host_opt.get_value() if host_opt else None
        port = port_opt.get_value() if port_opt else None

        host = str(host).strip() if host else '127.0.0.1'
        port = str(port).strip() if port else '8080'

        # Bind-all addresses: connect to loopback for health checks
        if host in ('0.0.0.0', '::'):
            host = '127.0.0.1'

        self.api.base_url = f'http://{host}:{port}'
        self.logs_tab.add_log_line(f'Health check target: {self.api.base_url}')

    def _start_server(self):
        """Start the llama-server process."""
        self._command = self.config_tab.get_command()

        if not self._command.strip():
            messagebox.showwarning('No Command',
                                    'Please configure at least the model path.')
            return

        self._update_api_url()
        self._server_url_var.set(self.api.base_url)
        self._ensure_directories()
        self.logs_tab.add_log_line(f'Invoking: {self._command}')
        self._status_label.config(text='Starting server...')
        self._lbl_server_status.config(text='Server: Starting...', foreground='orange')

        try:
            success = self.process.start(self._command)
        except Exception:
            success = False

        if not success:
            self._status_label.config(text='Failed to start server')
            self._lbl_server_status.config(text='Server: Failed', foreground='red')
            messagebox.showerror('Error', 'Failed to start server.\n'
                                 'Make sure llama-server is on PATH.')
            return

        self._set_buttons_started()
        self._status_label.config(text='Connecting...')

        # Schedule health check after server starts
        self._health_check_timeout = 120
        self._health_check_attempts = 0
        self._poll_health()

    def _poll_health(self):
        """Poll health endpoint until server is ready or timeout."""
        if not self.process.is_running:
            self._on_server_health_failed()
            return

        try:
            health = self.api.health()
            if health and health.get('status') == 'ok':
                self._on_server_health_ok(health)
                return
        except Exception:
            pass

        self._health_check_attempts += 1
        if self._health_check_attempts >= self._health_check_timeout:
            self._on_server_health_failed()
            return

        self._health_check_id = self.root.after(1000, self._poll_health)

    def _on_server_health_ok(self, health):
        self._lbl_server_status.config(text='Server: Connected', foreground='green')
        self._btn_open_browser.config(state='normal')
        self._status_label.config(text='Server running')

    def _on_server_health_failed(self):
        if self.process.is_running:
            self.process.stop()
        self._set_buttons_stopped()
        self._status_label.config(text='Server failed to start or connect')
        self._lbl_server_status.config(text='Server: Failed', foreground='red')
        messagebox.showerror('Server Error',
                              f'Server did not become healthy within {self._health_check_timeout} seconds.\n'
                              'Check the Logs tab for details.')

    def _on_process_stopped(self):
        """Called when the server process exits unexpectedly."""
        self.root.after(0, self._handle_process_stopped)

    def _handle_process_stopped(self):
        self._set_buttons_stopped()
        self._status_label.config(text='Server stopped unexpectedly')
        self._lbl_server_status.config(text='Server: Crashed', foreground='red')

    def _stop_server(self):
        """Stop the llama-server process. Monitoring continues."""
        if self._health_check_id:
            self.root.after_cancel(self._health_check_id)
            self._health_check_id = None

        self.process.stop()
        self._set_buttons_stopped()
        self._status_label.config(text='Server stopped')
        self._lbl_server_status.config(text='Server: Disconnected', foreground='gray')

    def _restart_server(self):
        """Restart the server with current command."""
        self._stop_server()
        self._command = self.config_tab.get_command()
        self.root.after(500, self._start_server)

    def _open_browser(self):
        """Open server URL in default browser."""
        import webbrowser
        webbrowser.open(self.api.base_url)

    def _show_settings(self):
        """Show the Settings dialog."""
        from tkinter import filedialog

        dlg = tk.Toplevel(self.root)
        dlg.title('Settings')
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        pad = {'padx': 8, 'pady': 4}

        # Server binary
        ttk.Label(dlg, text='Server binary:').grid(
            row=0, column=0, sticky='w', **pad)
        bin_var = tk.StringVar(
            value=self.config_tab._server_bin_var.get())
        bin_entry = ttk.Entry(dlg, textvariable=bin_var, width=42)
        bin_entry.grid(row=0, column=1, sticky='ew', **pad)

        def _browse_bin():
            path = filedialog.askopenfilename(
                title='Select llama-server executable',
                filetypes=[('All files', '*')],
                master=dlg)
            if path:
                bin_var.set(path)

        ttk.Button(dlg, text='...', command=_browse_bin).grid(
            row=0, column=2, padx=(0, 8), pady=4)

        # Health check timeout
        ttk.Label(dlg, text='Startup timeout (s):').grid(
            row=1, column=0, sticky='w', **pad)
        timeout_var = tk.StringVar(value=str(self._health_check_timeout))
        ttk.Spinbox(dlg, from_=10, to=600, increment=10,
                     textvariable=timeout_var, width=8).grid(
            row=1, column=1, sticky='w', **pad)

        # Monitor refresh interval
        ttk.Label(dlg, text='Monitor refresh (ms):').grid(
            row=2, column=0, sticky='w', **pad)
        refresh_var = tk.StringVar(value=str(self.monitor_tab._refresh_ms))
        ttk.Spinbox(dlg, from_=500, to=10000, increment=500,
                     textvariable=refresh_var, width=8).grid(
            row=2, column=1, sticky='w', **pad)

        # Prometheus metrics sample interval
        ttk.Label(dlg, text='Metrics sample (ms):').grid(
            row=3, column=0, sticky='w', **pad)
        metrics_var = tk.StringVar(value=str(self.monitor_tab._metrics_sample_ms))
        ttk.Spinbox(dlg, from_=100, to=60000, increment=100,
                     textvariable=metrics_var, width=8).grid(
            row=3, column=1, sticky='w', **pad)

        # Graph smoothing windows
        ttk.Label(dlg, text='Smooth PP (ms):').grid(
            row=4, column=0, sticky='w', **pad)
        smooth_pp_var = tk.StringVar(value=str(self.monitor_tab._graph_smooth_ms_pp))
        ttk.Spinbox(dlg, from_=100, to=30000, increment=500,
                     textvariable=smooth_pp_var, width=8).grid(
            row=4, column=1, sticky='w', **pad)
        ttk.Label(dlg, text='Smooth TG (ms):').grid(
            row=5, column=0, sticky='w', **pad)
        smooth_tg_var = tk.StringVar(value=str(self.monitor_tab._graph_smooth_ms_tg))
        ttk.Spinbox(dlg, from_=100, to=30000, increment=500,
                     textvariable=smooth_tg_var, width=8).grid(
            row=5, column=1, sticky='w', **pad)

        # Graph time window
        ttk.Label(dlg, text='Graph window (s):').grid(
            row=6, column=0, sticky='w', **pad)
        window_var = tk.StringVar(value=str(self.monitor_tab._graph_time_window_s))
        ttk.Spinbox(dlg, from_=30, to=600, increment=30,
                     textvariable=window_var, width=8).grid(
            row=6, column=1, sticky='w', **pad)

        # Theme — live preview: changing the selection immediately re-renders
        # the whole GUI.  Cancel reverts to the mode active when the dialog
        # was opened.
        _prev_theme = self._theme_mode
        ttk.Label(dlg, text='Theme:').grid(
            row=7, column=0, sticky='w', **pad)
        theme_var = tk.StringVar(value=self._theme_mode)
        theme_combo = ttk.Combobox(dlg, textvariable=theme_var,
                                   values=['dark', 'light', 'system'],
                                   state='readonly', width=10)
        theme_combo.grid(row=7, column=1, sticky='w', **pad)

        def _preview_theme(event=None):
            self.set_theme(theme_var.get())

        theme_combo.bind('<<ComboboxSelected>>', _preview_theme)

        # Per-graph visibility — live effect via BooleanVar trace
        chart = self.monitor_tab._chart
        _prev_graph_vis = dict(chart._graphs_visible)   # save for Cancel
        _graph_labels = {
            'pp':           'PP tok/s',
            'tg':           'TG tok/s',
            'draft_pct':    'Draft %',
            'draft_tokens': 'Draft tokens (gen/acc)',
        }
        ttk.Label(dlg, text='Graphs:').grid(
            row=8, column=0, sticky='nw', **pad)
        gfx_frame = ttk.Frame(dlg)
        gfx_frame.grid(row=8, column=1, columnspan=2, sticky='w', **pad)
        _graph_vars = {}
        for i, (key, lbl) in enumerate(_graph_labels.items()):
            var = tk.BooleanVar(value=chart._graphs_visible.get(key, True))
            _graph_vars[key] = var

            def _make_cb(k, v):
                def _cb(*_):
                    chart.set_graph_visible(k, v.get())
                return _cb

            var.trace_add('write', _make_cb(key, var))
            ttk.Checkbutton(gfx_frame, text=lbl, variable=var,
                            style='Switch.TCheckbutton').grid(
                row=i // 2, column=i % 2, sticky='w', padx=(0, 12), pady=2)

        ttk.Separator(dlg, orient='horizontal').grid(
            row=9, column=0, columnspan=3, sticky='ew', pady=6)

        # Buttons
        btn_frame = ttk.Frame(dlg)
        btn_frame.grid(row=10, column=0, columnspan=3, pady=(0, 8))

        def _ok():
            self.config_tab._server_bin_var.set(bin_var.get())
            try:
                self._health_check_timeout = max(10, int(timeout_var.get()))
            except ValueError:
                pass
            try:
                self.monitor_tab._refresh_ms = max(500, int(refresh_var.get()))
            except ValueError:
                pass
            try:
                self.monitor_tab._metrics_sample_ms = max(100, int(metrics_var.get()))
            except ValueError:
                pass
            try:
                self.monitor_tab._graph_smooth_ms_pp = max(100, min(30000, int(smooth_pp_var.get())))
            except ValueError:
                pass
            try:
                self.monitor_tab._graph_smooth_ms_tg = max(100, min(30000, int(smooth_tg_var.get())))
            except ValueError:
                pass
            try:
                new_win = max(30, min(600, int(window_var.get())))
                self.monitor_tab._graph_time_window_s = new_win
                self.monitor_tab._chart.set_time_window(new_win)
            except ValueError:
                pass
            # Theme already applied live; just persist the chosen value
            self._theme_mode = theme_var.get()
            # Graph visibility already applied live via traces; nothing extra needed
            self.save_preferences()
            dlg.destroy()

        def _cancel():
            self.set_theme(_prev_theme)
            # Restore graph visibility to what it was before the dialog opened
            for key, vis in _prev_graph_vis.items():
                chart.set_graph_visible(key, vis)
            dlg.destroy()

        ttk.Button(btn_frame, text='OK', command=_ok, width=10).pack(
            side='left', padx=4)
        ttk.Button(btn_frame, text='Cancel', command=_cancel,
                    width=10).pack(side='left', padx=4)

        dlg.protocol('WM_DELETE_WINDOW', _cancel)
        dlg.columnconfigure(1, weight=1)
        dlg.wait_window()

    def _drain_log_queue(self):
        """Drain the log queue — runs on the main thread every 50 ms.
        Processes up to 200 lines per tick to keep the UI responsive."""
        MAX_PER_TICK = 200
        count = 0
        while count < MAX_PER_TICK:
            try:
                line = self._log_queue.get_nowait()
            except queue.Empty:
                break
            try:
                self._on_log_line(line)
            except Exception as e:
                print(f'drain: error processing log line: {e}')
            count += 1
        self.root.after(50, self._drain_log_queue)

    def _on_log_line(self, line):
        """Handle incoming log line from server process.
        Always called on the main thread via root.after(0, ...)."""
        self.logs_tab.add_log_line(line)

        # Detect server ready
        if 'server is listening' in line.lower():
            url = line.split('server is listening')[-1].strip()
            self._lbl_server_status.config(text=f'Server: {url}', foreground='green')
            self._btn_open_browser.config(state='normal')

    def _start_auto_monitor(self):
        """Start monitoring at app launch, connecting to the configured URL."""
        url = self._server_url_var.get().strip()
        if url:
            self.api.base_url = url.rstrip('/')
        self._monitoring = True
        self.monitor_tab._start_monitoring()
        self._lbl_server_status.config(text='Monitor: waiting...', foreground='orange')

    def _connect_to_url(self):
        """Connect to the server URL entered in the toolbar."""
        url = self._server_url_var.get().strip()
        if not url:
            return
        self.api.base_url = url.rstrip('/')
        self.logs_tab.add_log_line(f'Connecting to server: {self.api.base_url}')
        self._lbl_server_status.config(text='Monitor: connecting...', foreground='orange')
        if not self._monitoring:
            self._monitoring = True
            self.monitor_tab._start_monitoring()
        # Force an immediate health check on the new URL
        self._do_health_check()

    def _do_health_check(self):
        """Single-shot health check to update status bar."""
        try:
            health = self.api.health()
            if health and health.get('status') == 'ok':
                self._lbl_server_status.config(text='Server: Connected', foreground='green')
                self._btn_open_browser.config(state='normal')
                return
        except Exception:
            pass
        self._lbl_server_status.config(text='Server: Disconnected', foreground='gray')
        self._btn_open_browser.config(state='disabled')

    def _load_preferences(self):
        """Load saved preferences from file."""
        pref_path = os.path.expanduser('~/.llama-gui/preferences.json')
        if os.path.exists(pref_path):
            try:
                import json
                with open(pref_path) as f:
                    prefs = json.load(f)
                if 'refresh_ms' in prefs:
                    self.monitor_tab._refresh_ms = int(prefs['refresh_ms'])
                if 'metrics_sample_ms' in prefs:
                    self.monitor_tab._metrics_sample_ms = int(prefs['metrics_sample_ms'])
                if 'graph_smooth_ms_pp' in prefs:
                    self.monitor_tab._graph_smooth_ms_pp = max(100, min(30000, int(prefs['graph_smooth_ms_pp'])))
                elif 'graph_smooth_ms' in prefs:
                    self.monitor_tab._graph_smooth_ms_pp = max(100, min(30000, int(prefs['graph_smooth_ms'])))
                if 'graph_smooth_ms_tg' in prefs:
                    self.monitor_tab._graph_smooth_ms_tg = max(100, min(30000, int(prefs['graph_smooth_ms_tg'])))
                elif 'graph_smooth_ms' in prefs:
                    self.monitor_tab._graph_smooth_ms_tg = max(100, min(30000, int(prefs['graph_smooth_ms'])))
                if 'graph_time_window_s' in prefs:
                    w = max(30, min(600, int(prefs['graph_time_window_s'])))
                    self.monitor_tab._graph_time_window_s = w
                    self.monitor_tab._chart.set_time_window(w)
                if 'health_timeout' in prefs:
                    self._health_check_timeout = int(prefs['health_timeout'])
                if 'theme_mode' in prefs:
                    self.set_theme(prefs['theme_mode'])
                for key in ('pp', 'tg', 'draft_pct', 'draft_tokens'):
                    pkey = f'graph_vis_{key}'
                    if pkey in prefs:
                        self.monitor_tab._chart.set_graph_visible(key, bool(prefs[pkey]))
                server_bin = prefs.get('server_bin', '')
                if server_bin and hasattr(self.config_tab, '_server_bin_var'):
                    self.config_tab._server_bin_var.set(server_bin)
                saved_url = prefs.get('server_url', '')
                if saved_url:
                    self._server_url_var.set(saved_url)
                    self.api.base_url = saved_url.rstrip('/')
                last_profile = prefs.get('last_profile', '')
                if last_profile and hasattr(self.config_tab, '_current_profile'):
                    self.config_tab._current_profile = last_profile
                    self.config_tab._refresh_profile_list()
                    self.config_tab._profile_var.set(last_profile)
                    if last_profile != 'Default':
                        opts = self.config_tab._profile_mgr.load(last_profile)
                        if opts:
                            self.config_tab._apply_options(opts)
                self.config_tab._dirty = False
            except Exception:
                pass

    def save_preferences(self):
        """Save current preferences."""
        pref_path = os.path.expanduser('~/.llama-gui/preferences.json')
        os.makedirs(os.path.dirname(pref_path), exist_ok=True)
        try:
            import json
            prefs = {
                'refresh_ms': self.monitor_tab._refresh_ms,
                'metrics_sample_ms': self.monitor_tab._metrics_sample_ms,
                'graph_smooth_ms_pp':   self.monitor_tab._graph_smooth_ms_pp,
                'graph_smooth_ms_tg':   self.monitor_tab._graph_smooth_ms_tg,
                'graph_time_window_s':  self.monitor_tab._graph_time_window_s,
                'health_timeout': self._health_check_timeout,
                'server_bin': self.config_tab._server_bin_var.get(),
                'last_profile': getattr(self.config_tab, '_current_profile', ''),
                'theme_mode': self._theme_mode,
            }
            for key in ('pp', 'tg', 'draft_pct', 'draft_tokens'):
                prefs[f'graph_vis_{key}'] = self.monitor_tab._chart._graphs_visible.get(key, True)
            prefs['server_url'] = self._server_url_var.get().strip() or 'http://127.0.0.1:8080'
            with open(pref_path, 'w') as f:
                json.dump(prefs, f)
        except Exception:
            pass

    def run(self):
        """Start the main event loop."""
        # Clean shutdown on exit
        self.root.protocol('WM_DELETE_WINDOW', self._on_closing)
        self.root.mainloop()

    def _on_closing(self):
        """Handle window close."""
        if not self.config_tab.on_close_request():
            return
        self._monitoring = False
        self.monitor_tab._stop_monitoring()
        self.sys_monitor.stop()
        if self.process.is_running:
            if messagebox.askyesno('Quit', 'Server is running. Stop and quit?'):
                self._stop_server()
                self.save_preferences()
                self.root.destroy()
        else:
            self.save_preferences()
            self.root.destroy()


def main():
    app = MainWindow()
    app.run()


if __name__ == '__main__':
    main()
