"""
Main entry point for llama.cpp GUI launcher.
Wires together config, monitor, logs tabs and process management.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_tab import ConfigTab
from monitor_tab import MonitorTab
from logs_tab import LogsTab
from api_client import ServerAPI
from process_mgr import ServerProcess
from system_monitor import SystemMonitor


class MainWindow:
    """Main application window."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('llama.cpp GUI Launcher')
        self.root.geometry('1100x700')
        self._configure_fonts()

        # Shared components
        self.process = ServerProcess()
        self.sys_monitor = SystemMonitor()
        self.api = ServerAPI()

        # State
        self._command = ''
        self._monitoring = False
        self._health_check_id = None

        # Setup UI
        self._build_ui()

        # Connect callbacks
        self.process.on_stdout(self._on_log_line)
        self.process.on_stopped(self._on_process_stopped)

        # Load saved preferences
        self._load_preferences()

    def _configure_fonts(self):
        import tkinter.font as font
        f = font.nametofont('TkDefaultFont')
        f.configure(family='Segoe UI', size=9)
        f = font.nametofont('TkTextFont')
        f.configure(family='Segoe UI', size=9)
        f = font.nametofont('TkFixedFont')
        f.configure(family='Consolas', size=9)

    def _build_ui(self):
        # Top toolbar
        self._build_toolbar()

        # Tab control
        self._build_tabs()

        # Bottom status bar
        self._build_statusbar()

    def _build_toolbar(self):
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill='x', padx=4, pady=4)

        self._btn_start = ttk.Button(toolbar, text='Start',
                                      command=self._start_server)
        self._btn_start.pack(side='left', padx=2)

        self._btn_stop = ttk.Button(toolbar, text='Stop', state='disabled',
                                     command=self._stop_server)
        self._btn_stop.pack(side='left', padx=2)

        self._btn_restart = ttk.Button(toolbar, text='Restart', state='disabled',
                                        command=self._restart_server)
        self._btn_restart.pack(side='left', padx=2)

        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=8)

        self._lbl_server_status = ttk.Label(toolbar, text='Server: Not started',
                                             foreground='gray')
        self._lbl_server_status.pack(side='left', padx=4)

        self._btn_open_browser = ttk.Button(toolbar, text='Open in Browser',
                                              command=self._open_browser,
                                              state='disabled')
        self._btn_open_browser.pack(side='left', padx=4)

        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=8)
        ttk.Button(toolbar, text='Settings',
                    command=self._show_settings).pack(side='left', padx=2)

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

    def _start_server(self):
        """Start the llama-server process."""
        self._command = self.config_tab.get_command()

        if not self._command.strip():
            messagebox.showwarning('No Command',
                                    'Please configure at least the model path.')
            return

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
        self._monitoring = True
        self.monitor_tab._start_monitoring()

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
        if self._monitoring:
            self._monitoring = False
            self.monitor_tab._stop_monitoring()
        self._set_buttons_stopped()
        self._status_label.config(text='Server stopped unexpectedly')
        self._lbl_server_status.config(text='Server: Crashed', foreground='red')

    def _stop_server(self):
        """Stop the llama-server process."""
        if self._health_check_id:
            self.root.after_cancel(self._health_check_id)
            self._health_check_id = None

        self.process.stop()
        self._monitoring = False
        self.monitor_tab._stop_monitoring()
        self._set_buttons_stopped()
        self._status_label.config(text='Server stopped')

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

        ttk.Separator(dlg, orient='horizontal').grid(
            row=2, column=0, columnspan=3, sticky='ew', pady=6)

        # Buttons
        btn_frame = ttk.Frame(dlg)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=(0, 8))

        def _ok():
            self.config_tab._server_bin_var.set(bin_var.get())
            try:
                self._health_check_timeout = max(10, int(timeout_var.get()))
            except ValueError:
                pass
            self.save_preferences()
            dlg.destroy()

        ttk.Button(btn_frame, text='OK', command=_ok, width=10).pack(
            side='left', padx=4)
        ttk.Button(btn_frame, text='Cancel', command=dlg.destroy,
                    width=10).pack(side='left', padx=4)

        dlg.columnconfigure(1, weight=1)
        dlg.wait_window()

    def _on_log_line(self, line):
        """Handle incoming log line from server process."""
        # Update logs tab
        self.logs_tab.add_log_line(line)

        # Update monitor with parsed metrics
        from log_parser import parse_line, LogMetrics
        temp_metrics = LogMetrics()
        event = parse_line(line, temp_metrics)
        if event in ('prompt_eval', 'eval', 'draft', 'cache', 'graphs'):
            self.monitor_tab.update_from_log({
                'prompt_per_second': temp_metrics.prompt_per_second,
                'gen_per_second': temp_metrics.gen_per_second,
                'draft_acceptance_rate': temp_metrics.draft_acceptance_rate,
                'cache_size_mib': temp_metrics.cache_size_mib,
                'graphs_reused': temp_metrics.graphs_reused,
            })

        # Detect server ready
        if 'server is listening' in line.lower():
            url = line.split('server is listening')[-1].strip()
            self._lbl_server_status.config(text=f'Server: {url}', foreground='green')
            self._btn_open_browser.config(state='normal')

    def _load_preferences(self):
        """Load saved preferences from file."""
        pref_path = os.path.expanduser('~/.llama-gui/preferences.json')
        if os.path.exists(pref_path):
            try:
                import json
                with open(pref_path) as f:
                    prefs = json.load(f)
                if 'refresh_ms' in prefs:
                    self.monitor_tab._refresh_var.set(str(prefs['refresh_ms']))
                if 'health_timeout' in prefs:
                    self._health_check_timeout = int(prefs['health_timeout'])
                server_bin = prefs.get('server_bin', '')
                if server_bin and hasattr(self.config_tab, '_server_bin_var'):
                    self.config_tab._server_bin_var.set(server_bin)
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
                'health_timeout': self._health_check_timeout,
                'server_bin': self.config_tab._server_bin_var.get(),
                'last_profile': getattr(self.config_tab, '_current_profile', ''),
            }
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
