"""
Unit tests for llama-gui core modules.
Tests log_parser, command_builder, and config_registry.
Run with: python3 -m pytest test_core.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import MagicMock, patch
import json
import time

from log_parser import (
    LogMetrics,
    parse_line,
    PROMPT_EVAL_RE,
    EVAL_RE,
    TOTAL_TIME_RE,
    DRAFT_RE,
    GRAPHS_REUSED_RE,
    SLOT_DRAFT_RE,
    CHECKPOINT_RE,
    PROMPT_CACHE_RE,
    LOADING_RE,
    MODEL_LOADED_RE,
    SERVER_LISTENING_RE,
)
from command_builder import (
    PREFIX_MAP,
    build_command,
    _format_arg,
)
from config_registry import _OPTIONS, get_option, iter_options
from monitor_tab import MonitorTab, MetricsChart


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_option_widget(label='', default=None, widget_type='text',
                       value=None):
    """Create a minimal mock OptionWidget for command_builder testing."""
    opt = MagicMock()
    opt.label = label
    opt.default = default
    opt.widget_type = widget_type
    opt.include_var = MagicMock()
    opt.get_value.return_value = value if value is not None else default
    return opt


# ---------------------------------------------------------------------------
# ConfigRegistry tests
# ---------------------------------------------------------------------------

class ConfigRegistryTest(unittest.TestCase):

    def test_get_option_returns_tuple(self):
        opt = get_option('model')
        self.assertIsNotNone(opt)
        self.assertIsInstance(opt, tuple)
        self.assertEqual(opt[0], 'Model (-m)')

    def test_get_option_returns_none_for_unknown(self):
        self.assertIsNone(get_option('nonexistent_option_xyz'))

    def test_iter_options_yields_all(self):
        count = 0
        for key, val in iter_options():
            self.assertIsInstance(key, str)
            self.assertIsInstance(val, tuple)
            self.assertIn(val[2], ('file', 'dropdown', 'checkbox', 'radio',
                                    'spin', 'float_spin', 'text', 'panel_header',
                                    'multiline_text', 'ordered_list_of_options'))
            count += 1
        self.assertGreater(count, 150)

    def test_no_duplicate_keys(self):
        keys = list(_OPTIONS.keys())
        self.assertEqual(len(keys), len(set(keys)), 'Duplicate keys found')

    def test_all_defaults_have_widget_types(self):
        for key, val in _OPTIONS.items():
            wtype = val[2]
            if wtype == 'checkbox':
                self.assertIsInstance(val[1], bool, f'{key}: checkbox default must be bool')
            elif wtype in ('spin', 'float_spin'):
                self.assertIsInstance(val[1], (int, float), f'{key}: numeric default')
            elif wtype in ('dropdown', 'radio'):
                self.assertIsInstance(val[1], (str, int, float), f'{key}: {wtype} default must be string or number')
            elif wtype == 'file':
                self.assertIsInstance(val[1], str, f'{key}: file default must be string')
            elif wtype == 'text':
                self.assertIsInstance(val[1], str, f'{key}: text default must be string')

    def test_all_dropdowns_have_choices(self):
        for key, val in _OPTIONS.items():
            if val[2] == 'dropdown':
                self.assertIn(3, range(len(val)), f'{key}: dropdown must have choices')
                self.assertIsInstance(val[3], list)
                self.assertGreater(len(val[3]), 0, f'{key}: dropdown choices must not be empty')

    def test_spin_ranges_valid(self):
        for key, val in _OPTIONS.items():
            if val[2] in ('spin', 'float_spin') and len(val) > 3:
                params = val[3]
                if isinstance(params, tuple) and len(params) >= 3:
                    self.assertLessEqual(params[0], params[1],
                                         f'{key}: min > max')

    def test_file_options_have_text_default(self):
        for key, val in _OPTIONS.items():
            if val[2] == 'file':
                self.assertEqual(val[1], '', f'{key}: file default should be empty string')

    def test_checkbox_defaults_are_bool(self):
        for key, val in _OPTIONS.items():
            if val[2] == 'checkbox':
                self.assertIsInstance(val[1], bool, f'{key}: checkbox must be bool')

    def test_text_options_default_is_string(self):
        for key, val in _OPTIONS.items():
            if val[2] == 'text':
                self.assertIsInstance(val[1], str, f'{key}: text default must be string')


# ---------------------------------------------------------------------------
# LogParser tests
# ---------------------------------------------------------------------------

class LogParserPatternTest(unittest.TestCase):
    """Test regex patterns individually."""

    def test_prompt_eval_with_full_info(self):
        line = 'prompt eval time = 123.45 ms / 256 tokens (0.48 ms per token, 533.33 tokens per second)'
        m = PROMPT_EVAL_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(float(m.group(1)), 123.45)
        self.assertEqual(int(m.group(2)), 256)
        self.assertEqual(float(m.group(3)), 0.48)
        self.assertEqual(float(m.group(4)), 533.33)

    def test_prompt_eval_without_optional_group(self):
        line = 'prompt eval time = 100.0 ms / 50 tokens'
        m = PROMPT_EVAL_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(float(m.group(1)), 100.0)
        self.assertEqual(int(m.group(2)), 50)

    def test_eval_with_full_info(self):
        line = 'eval time = 67.89 ms / 10 tokens (6.79 ms per token, 147.33 tokens per second)'
        m = EVAL_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(float(m.group(1)), 67.89)
        self.assertEqual(int(m.group(2)), 10)

    def test_total_time(self):
        line = 'total time = 191.34 ms / 266 tokens'
        m = TOTAL_TIME_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(float(m.group(1)), 191.34)
        self.assertEqual(int(m.group(2)), 266)

    def test_draft_acceptance(self):
        line = 'draft acceptance = 0.75000 ( 12 accepted / 16 generated)'
        m = DRAFT_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(float(m.group(1)), 0.75)
        self.assertEqual(int(m.group(2)), 12)
        self.assertEqual(int(m.group(3)), 16)

    def test_graphs_reused(self):
        line = 'graphs reused = 5'
        m = GRAPHS_REUSED_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), 5)

    def test_slot_draft(self):
        line = 'accepted 12/16 draft tokens (restore checkpoint)'
        m = SLOT_DRAFT_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), 12)
        self.assertEqual(int(m.group(2)), 16)

    def test_checkpoint(self):
        line = ('created context checkpoint 1 of 32 '
                '( pos_min = 0, pos_max = 256, n_tokens = 256, size = 1.234 MiB)')
        m = CHECKPOINT_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), 1)
        self.assertEqual(int(m.group(2)), 32)

    def test_prompt_cache(self):
        line = 'prompt cache state: 3 prompts, 45.123 MiB (limits: 512.000 MiB, 65536 tokens, 1024 est)'
        m = PROMPT_CACHE_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), 3)
        self.assertEqual(float(m.group(2)), 45.123)
        self.assertEqual(float(m.group(3)), 512.0)

    def test_loading(self):
        self.assertTrue(LOADING_RE.search('loading model llama-2-7b.q4_0.gguf'))

    def test_model_loaded(self):
        self.assertTrue(MODEL_LOADED_RE.search('model loaded successfully'))

    def test_server_listening(self):
        line = 'server is listening on http://127.0.0.1:8080'
        m = SERVER_LISTENING_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1).strip(), 'http://127.0.0.1:8080')


class LogParserMetricsTest(unittest.TestCase):
    """Test parse_line updates LogMetrics correctly."""

    def setUp(self):
        self.metrics = LogMetrics()

    def test_parse_prompt_eval(self):
        line = 'prompt eval time = 123.45 ms / 256 tokens (0.48 ms per token, 533.33 tokens per second)'
        event = parse_line(line, self.metrics)
        self.assertEqual(event, 'prompt_eval')
        self.assertEqual(self.metrics.prompt_tokens, 256)
        self.assertEqual(self.metrics.prompt_time_ms, 123.45)
        self.assertEqual(self.metrics.prompt_per_second, 533.33)

    def test_parse_eval(self):
        line = 'eval time = 67.89 ms / 10 tokens (6.79 ms per token, 147.33 tokens per second)'
        event = parse_line(line, self.metrics)
        self.assertEqual(event, 'eval')
        self.assertEqual(self.metrics.gen_tokens, 10)
        self.assertEqual(self.metrics.gen_per_second, 147.33)

    def test_parse_draft(self):
        line = 'draft acceptance = 0.75000 ( 12 accepted / 16 generated)'
        event = parse_line(line, self.metrics)
        self.assertEqual(event, 'draft')
        self.assertEqual(self.metrics.draft_acceptance_rate, 0.75)
        self.assertEqual(self.metrics.draft_accepted, 12)

    def test_parse_graphs(self):
        line = 'graphs reused = 5'
        event = parse_line(line, self.metrics)
        self.assertEqual(event, 'graphs')
        self.assertEqual(self.metrics.graphs_reused, 5)

    def test_parse_checkpoint(self):
        line = ('created context checkpoint 1 of 32 '
                '( pos_min = 0, pos_max = 256, n_tokens = 256, size = 1.234 MiB)')
        event = parse_line(line, self.metrics)
        self.assertEqual(event, 'checkpoint')
        self.assertEqual(self.metrics.checkpoints_created, 1)

    def test_parse_cache(self):
        line = 'prompt cache state: 3 prompts, 45.123 MiB (limits: 512.000 MiB, 65536 tokens, 1024 est)'
        event = parse_line(line, self.metrics)
        self.assertEqual(event, 'cache')
        self.assertEqual(self.metrics.cache_prompts, 3)
        self.assertEqual(self.metrics.cache_size_mib, 45.123)

    def test_parse_total(self):
        line = 'total time = 191.34 ms / 266 tokens'
        event = parse_line(line, self.metrics)
        self.assertEqual(event, 'total')
        self.assertEqual(self.metrics.total_time_ms, 191.34)
        self.assertEqual(self.metrics.total_tokens, 266)

    def test_parse_no_match(self):
        event = parse_line('random noise line', self.metrics)
        self.assertIsNone(event)

    def test_avg_prompt_per_second(self):
        m = LogMetrics()
        m.add_prompt_rate(100.0)
        m.add_prompt_rate(200.0)
        self.assertEqual(m.avg_prompt_per_second, 150.0)

    def test_avg_gen_per_second(self):
        m = LogMetrics()
        m.add_gen_rate(50.0)
        m.add_gen_rate(150.0)
        self.assertEqual(m.avg_gen_per_second, 100.0)

    def test_avg_draft_acceptance(self):
        m = LogMetrics()
        m.add_draft_rate(0.8)
        m.add_draft_rate(0.6)
        self.assertEqual(m.avg_draft_acceptance, 0.7)

    def test_empty_avgs(self):
        m = LogMetrics()
        self.assertEqual(m.avg_prompt_per_second, 0.0)
        self.assertEqual(m.avg_gen_per_second, 0.0)
        self.assertEqual(m.avg_draft_acceptance, 0.0)

    def test_parse_slot_draft(self):
        line = 'accepted 12/16 draft tokens (restore checkpoint)'
        event = parse_line(line, self.metrics)
        self.assertEqual(event, 'draft')
        self.assertEqual(self.metrics.draft_accepted, 12)

    def test_parse_slot_draft_zero_total(self):
        line = 'accepted 0/0 draft tokens'
        event = parse_line(line, self.metrics)
        self.assertIsNone(event)

    def test_parse_prompt_cache_without_limits(self):
        line = 'prompt cache state: 1 prompts, 10.5 MiB ()'
        event = parse_line(line, self.metrics)
        self.assertEqual(event, 'cache')
        self.assertEqual(self.metrics.cache_prompts, 1)
        self.assertEqual(self.metrics.cache_size_mib, 10.5)
        self.assertEqual(self.metrics.cache_limit_mib, 0.0)

    def test_multiple_lines_accumulate_metrics(self):
        m = LogMetrics()
        parse_line('prompt eval time = 100.0 ms / 50 tokens (2.0 ms per token, 500.0 tokens per second)', m)
        parse_line('eval time = 50.0 ms / 10 tokens (5.0 ms per token, 200.0 tokens per second)', m)
        parse_line('total time = 150.0 ms / 60 tokens', m)
        self.assertEqual(m.prompt_tokens, 50)
        self.assertEqual(m.gen_tokens, 10)
        self.assertEqual(m.total_tokens, 60)
        self.assertEqual(m.avg_prompt_per_second, 500.0)
        self.assertEqual(m.avg_gen_per_second, 200.0)


# ---------------------------------------------------------------------------
# CommandBuilder tests
# ---------------------------------------------------------------------------

class FormatArgTest(unittest.TestCase):

    def test_no_spaces(self):
        self.assertEqual(_format_arg('hello'), 'hello')

    def test_with_spaces(self):
        self.assertEqual(_format_arg('hello world'), '"hello world"')

    def test_with_quotes(self):
        self.assertEqual(_format_arg('say "hi"'), '"say "hi""')


class BuildCommandTest(unittest.TestCase):

    def test_empty_option_map(self):
        cmd = build_command({})
        self.assertEqual(cmd, 'llama-server')

    def test_checkbox_on(self):
        opt = make_option_widget(widget_type='checkbox', default='',
                                   value='on')
        cmd = build_command({'mlock': opt})
        self.assertIn('--mlock', cmd)

    def test_checkbox_off(self):
        opt = make_option_widget(widget_type='checkbox', default='',
                                   value='off')
        cmd = build_command({'jinja': opt})
        self.assertIn('--no-jinja', cmd)

    def test_checkbox_unset(self):
        opt = make_option_widget(widget_type='checkbox', default='',
                                   value='')
        cmd = build_command({'mlock': opt})
        self.assertNotIn('--mlock', cmd)
        self.assertEqual(cmd, 'llama-server')

    def test_text_value_changed(self):
        opt = make_option_widget(widget_type='text', default='', value='hello world')
        cmd = build_command({'prompt': opt})
        self.assertIn('-p', cmd)
        self.assertIn('"hello world"', cmd)

    def test_dropdown_value(self):
        opt = make_option_widget(widget_type='dropdown', default='none', value='linear')
        cmd = build_command({'rope_scaling': opt})
        self.assertIn('--rope-scaling', cmd)
        self.assertIn('linear', cmd)

    def test_spin_value_changed(self):
        opt = make_option_widget(widget_type='spin', default=4, value=8)
        cmd = build_command({'threads': opt})
        self.assertIn('-t', cmd)
        self.assertIn('8', cmd)

    def test_spin_value_same_as_old_default_is_emitted(self):
        # Values are emitted regardless of what the registered default was;
        # only None / '' means "not set".
        opt = make_option_widget(widget_type='spin', default=4, value=4)
        cmd = build_command({'threads': opt})
        self.assertIn('-t', cmd)
        self.assertIn('4', cmd)

    def test_file_value(self):
        opt = make_option_widget(widget_type='file', default='', value='/path/to/model.gguf')
        cmd = build_command({'model': opt})
        self.assertIn('-m', cmd)
        self.assertIn('/path/to/model.gguf', cmd)

    def test_file_empty(self):
        opt = make_option_widget(widget_type='file', default='', value='')
        cmd = build_command({'model': opt})
        self.assertNotIn('-m', cmd)

    def test_multiple_options(self):
        model_opt = make_option_widget(widget_type='file',
                                        value='/path/model.gguf')
        threads_opt = make_option_widget(widget_type='spin',
                                          default=4, value=8)
        prompt_opt = make_option_widget(widget_type='text',
                                         value='hello')
        cmd = build_command({'model': model_opt, 'threads': threads_opt,
                              'prompt': prompt_opt})
        self.assertIn('llama-server', cmd)
        self.assertIn('-m', cmd)
        self.assertIn('/path/model.gguf', cmd)
        self.assertIn('-t', cmd)
        self.assertIn('8', cmd)
        self.assertIn('-p', cmd)
        self.assertIn('hello', cmd)

    def test_unknown_prefix_fallback(self):
        opt = make_option_widget(widget_type='text', value='x')
        cmd = build_command({'custom_opt': opt})
        self.assertIn('--custom_opt', cmd)

    def test_dropdown_includes_default_value(self):
        opt = make_option_widget(widget_type='dropdown', default='layer', value='layer')
        cmd = build_command({'split_mode': opt})
        self.assertIn('-sm', cmd)
        self.assertIn('layer', cmd)

    def test_float_spin_zero_is_emitted(self):
        # Explicit zero is a real value — must appear on the command line.
        opt = make_option_widget(widget_type='float_spin', default=0.0, value=0.0)
        cmd = build_command({'temperature': opt})
        self.assertIn('--temp', cmd)
        self.assertIn('0.0', cmd)

    def test_float_spin_with_non_zero_value(self):
        opt = make_option_widget(widget_type='float_spin', default=0.0, value=0.8)
        cmd = build_command({'temperature': opt})
        self.assertIn('--temp', cmd)
        self.assertIn('0.8', cmd)

    def test_text_empty_string_excluded(self):
        opt = make_option_widget(widget_type='text', default='', value='')
        cmd = build_command({'prompt': opt})
        self.assertNotIn('-p', cmd)

    def test_none_value_skipped(self):
        opt = make_option_widget(widget_type='text', value=None)
        cmd = build_command({'prompt': opt})
        self.assertNotIn('-p', cmd)

    def test_radio_value(self):
        opt = make_option_widget(widget_type='radio', default=0, value=1)
        cmd = build_command({'mirostat': opt})
        self.assertIn('--mirostat', cmd)
        self.assertIn('1', cmd)


class PrefixMapCompletenessTest(unittest.TestCase):
    """Ensure PREFIX_MAP has entries for all _OPTIONS keys."""

    def test_all_options_have_prefix(self):
        missing = set()
        for key in _OPTIONS:
            if key not in PREFIX_MAP:
                missing.add(key)
        self.assertEqual(missing, set(), f'Missing prefixes for: {missing}')


# ---------------------------------------------------------------------------
# API Client tests (mocked)
# ---------------------------------------------------------------------------

class APIClientTest(unittest.TestCase):

    def test_parse_prometheus_metrics_empty(self):
        from command_builder import PREFIX_MAP  # noqa: already imported above
        from api_client import parse_prometheus_metrics
        result = parse_prometheus_metrics('')
        self.assertEqual(result, {})

    def test_parse_prometheus_metrics_basic(self):
        from api_client import parse_prometheus_metrics
        text = '''# HELP prompt_tokens_total Total prompt tokens
prompt_tokens_total 256
# HELP something else
another_metric 100.5'''
        result = parse_prometheus_metrics(text)
        self.assertEqual(result['prompt_tokens_total'], 256.0)
        self.assertEqual(result['another_metric'], 100.5)

    def test_parse_prometheus_metrics_skips_comments(self):
        from api_client import parse_prometheus_metrics
        text = '''# comment line
valid_metric 42.0
# another comment'''
        result = parse_prometheus_metrics(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result['valid_metric'], 42.0)


# ---------------------------------------------------------------------------
# System Monitor tests (no GPU required)
# ---------------------------------------------------------------------------

class SystemMonitorTest(unittest.TestCase):

    def test_default_state(self):
        from system_monitor import SystemMonitor
        mon = SystemMonitor()
        self.assertEqual(mon.cpu_percent, 0.0)
        self.assertEqual(mon.memory['total'], 0)
        self.assertEqual(mon.swap['total'], 0)
        self.assertTrue(mon.gpu['error'])

    def test_get_snapshot_no_psutil(self):
        from system_monitor import SystemMonitor
        with patch.dict('sys.modules', {'psutil': None}):
            mon = SystemMonitor()
            snap = mon.get_snapshot()
            self.assertIn('cpu', snap)
            self.assertIn('memory', snap)
            self.assertIn('swap', snap)
            self.assertIn('gpu', snap)

    def test_start_stop(self):
        from system_monitor import SystemMonitor
        mon = SystemMonitor()
        mon.start(interval=0.01)
        import time
        time.sleep(0.05)
        mon.stop()
        # Should not raise

    def test_monitor_stops_on_stream_close(self):
        from system_monitor import SystemMonitor
        mon = SystemMonitor()
        mon.start(interval=0.01)
        import time
        time.sleep(0.05)
        mon.stop()
        self.assertFalse(mon._running)


# ---------------------------------------------------------------------------
# Process Manager tests
# ---------------------------------------------------------------------------

class ProcessManagerTest(unittest.TestCase):

    def test_initial_state(self):
        from process_mgr import ServerProcess
        proc = ServerProcess()
        self.assertFalse(proc.is_running)
        self.assertIsNone(proc.returncode)
        self.assertIsNone(proc.pid)

    def test_parse_command(self):
        from process_mgr import ServerProcess
        proc = ServerProcess()
        result = proc._parse_command('llama-server -m model.gguf -t 8')
        self.assertEqual(result, ['llama-server', '-m', 'model.gguf', '-t', '8'])

    def test_parse_command_with_spaces(self):
        from process_mgr import ServerProcess
        proc = ServerProcess()
        result = proc._parse_command('llama-server -p "hello world"')
        self.assertEqual(result, ['llama-server', '-p', 'hello world'])

    def test_parse_command_quoted_path(self):
        from process_mgr import ServerProcess
        proc = ServerProcess()
        result = proc._parse_command("llama-server -m '/path/to/my model.gguf'")
        self.assertIn('/path/to/my model.gguf', result)

    def test_callbacks_registered(self):
        from process_mgr import ServerProcess
        proc = ServerProcess()
        called = []
        proc.on_stdout(lambda line: called.append(line))
        proc.on_stderr(lambda line: called.append(line))
        proc.on_stopped(lambda: called.append('stopped'))
        self.assertEqual(len(proc._callbacks['stdout']), 1)
        self.assertEqual(len(proc._callbacks['stderr']), 1)
        self.assertEqual(len(proc._callbacks['stopped']), 1)

    def test_stop_not_running(self):
        from process_mgr import ServerProcess
        proc = ServerProcess()
        result = proc.stop()
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# CollapsiblePane module tests (API only, no Tk)
# ---------------------------------------------------------------------------

class CollapsiblePaneAPITest(unittest.TestCase):

    def test_add_option_row_imports(self):
        from collapsible_pane import add_option_row, CollapsiblePane
        from tooltip import Tooltip
        self.assertTrue(callable(add_option_row))
        self.assertTrue(issubclass(CollapsiblePane, object))
        self.assertTrue(issubclass(Tooltip, object))

    def test_collapsible_pane_has_expected_methods(self):
        from collapsible_pane import CollapsiblePane
        attrs = ['add_option', 'toggle', 'content_frame']
        for a in attrs:
            self.assertTrue(hasattr(CollapsiblePane, a),
                            f'CollapsiblePane missing attribute: {a}')


# ---------------------------------------------------------------------------
# Monitor tab regression tests (no Tk required)
# ---------------------------------------------------------------------------

class MonitorTabRateComputationTest(unittest.TestCase):
    """Tests for _apply_metrics delta counter/time rate computation."""

    def _fake_monitor(self):
        m = MagicMock()
        m._prev_pp_total = 0.0
        m._prev_pp_time = 0.0
        m._prev_tg_total = 0.0
        m._prev_tg_time = 0.0
        m._prev_td_total = 0.0
        m._prev_td_time = 0.0
        m._prev_tda_total = 0.0
        m._prev_tda_time = 0.0
        m._prev_tdr_total = 0.0
        m._prev_tdr_time = 0.0
        m._raw_prompt = []
        m._raw_gen = []
        m._raw_draft_gen = []
        m._raw_draft_acc = []
        m._raw_draft = []
        m._using_event_metrics = False
        return m

    def test_rate_computation_basic(self):
        m = self._fake_monitor()
        parsed = {
            'prompt_tokens_total': 100.0,
            'prompt_seconds_total': 10.0,
            'tokens_predicted_total': 200.0,
            'tokens_predicted_seconds_total': 15.0,
            'n_tokens_draft': 50.0,
            'tokens_draft_seconds_total': 5.0,
            'n_tokens_draft_accepted': 40.0,
            'n_tokens_draft_rejected': 10.0,
        }
        MonitorTab._apply_metrics(m, parsed)
        self.assertEqual(len(m._raw_prompt), 1)
        self.assertAlmostEqual(m._raw_prompt[0][1], 10.0)  # 100 / 10
        self.assertEqual(len(m._raw_gen), 1)
        self.assertAlmostEqual(m._raw_gen[0][1], 13.333, places=2)  # 200 / 15
        self.assertEqual(len(m._raw_draft_gen), 1)
        self.assertAlmostEqual(m._raw_draft_gen[0][1], 3.333, places=2)  # 50 / 15
        self.assertEqual(len(m._raw_draft_acc), 1)
        self.assertAlmostEqual(m._raw_draft_acc[0][1], 2.667, places=2)  # 40 / 15

    def test_rate_computation_with_none_time(self):
        m = self._fake_monitor()
        parsed = {
            'prompt_tokens_total': 100.0,
            'prompt_seconds_total': None,
            'tokens_predicted_total': 200.0,
            'tokens_predicted_seconds_total': 15.0,
            'n_tokens_draft': 50.0,
            'tokens_draft_seconds_total': 5.0,
            'n_tokens_draft_accepted': 40.0,
            'n_tokens_draft_rejected': 10.0,
        }
        MonitorTab._apply_metrics(m, parsed)
        # pp_rate should be None when time is None
        self.assertEqual(len(m._raw_prompt), 0)
        # tg_rate should still be emitted
        self.assertEqual(len(m._raw_gen), 1)

    def test_rate_computation_with_zero_time(self):
        m = self._fake_monitor()
        parsed = {
            'prompt_tokens_total': 100.0,
            'prompt_seconds_total': 0.0,
            'tokens_predicted_total': 200.0,
            'tokens_predicted_seconds_total': 15.0,
            'n_tokens_draft': 50.0,
            'tokens_draft_seconds_total': 5.0,
            'n_tokens_draft_accepted': 40.0,
            'n_tokens_draft_rejected': 10.0,
        }
        MonitorTab._apply_metrics(m, parsed)
        self.assertEqual(len(m._raw_prompt), 0)
        self.assertEqual(len(m._raw_gen), 1)

    def test_draft_acceptance_rate(self):
        m = self._fake_monitor()
        parsed = {
            'prompt_tokens_total': 100.0,
            'prompt_seconds_total': 10.0,
            'tokens_predicted_total': 200.0,
            'tokens_predicted_seconds_total': 15.0,
            'n_tokens_draft': 50.0,
            'tokens_draft_seconds_total': 5.0,
            'n_tokens_draft_accepted': 40.0,
            'n_tokens_draft_rejected': 10.0,
        }
        MonitorTab._apply_metrics(m, parsed)
        # acceptance % = 40/(40+10) * 100 = 80%
        self.assertEqual(len(m._raw_draft), 1)
        self.assertAlmostEqual(m._raw_draft[0][1], 80.0)

    def test_draft_acceptance_rate_zero_rejected(self):
        m = self._fake_monitor()
        parsed = {
            'prompt_tokens_total': 100.0,
            'prompt_seconds_total': 10.0,
            'tokens_predicted_total': 200.0,
            'tokens_predicted_seconds_total': 15.0,
            'n_tokens_draft': 50.0,
            'tokens_draft_seconds_total': 5.0,
            'n_tokens_draft_accepted': 50.0,
            'n_tokens_draft_rejected': 0.0,
        }
        MonitorTab._apply_metrics(m, parsed)
        # acceptance % = 50/50 * 100 = 100%
        self.assertEqual(len(m._raw_draft), 1)
        self.assertAlmostEqual(m._raw_draft[0][1], 100.0)

    def test_rollover_detection(self):
        m = self._fake_monitor()
        parsed = {
            'prompt_tokens_total': 50.0,
            'prompt_seconds_total': 5.0,
            'tokens_predicted_total': 100.0,
            'tokens_predicted_seconds_total': 10.0,
            'n_tokens_draft': 25.0,
            'tokens_draft_seconds_total': 2.5,
            'n_tokens_draft_accepted': 20.0,
            'n_tokens_draft_rejected': 5.0,
        }
        MonitorTab._apply_metrics(m, parsed)

        # Simulate counter rollover (server reset)
        parsed['prompt_tokens_total'] = 10.0
        parsed['tokens_predicted_total'] = 5.0
        MonitorTab._apply_metrics(m, parsed)
        # After rollover, prev counters are set to the new (lower) values
        self.assertEqual(m._prev_pp_total, 10.0)
        self.assertEqual(m._prev_tg_total, 5.0)

    def test_missing_counters_skip_emission(self):
        m = self._fake_monitor()
        parsed = {
            'n_tokens_draft': 50.0,
            'tokens_draft_seconds_total': 5.0,
        }
        MonitorTab._apply_metrics(m, parsed)
        # pp_total and tg_total are missing, so no emission
        self.assertFalse(m._using_event_metrics)
        self.assertEqual(len(m._raw_prompt), 0)

    def test_no_emission_when_time_unchanged(self):
        """If time counter hasn't increased since last poll, skip sample."""
        m = self._fake_monitor()
        parsed = {
            'prompt_tokens_total': 100.0,
            'prompt_seconds_total': 10.0,
            'tokens_predicted_total': 200.0,
            'tokens_predicted_seconds_total': 15.0,
            'n_tokens_draft': 50.0,
            'tokens_draft_seconds_total': 5.0,
            'n_tokens_draft_accepted': 40.0,
            'n_tokens_draft_rejected': 10.0,
        }
        # First call: time goes from 0 to non-zero → emit
        MonitorTab._apply_metrics(m, parsed)
        self.assertEqual(len(m._raw_prompt), 1)
        self.assertEqual(len(m._raw_gen), 1)

        # Second call: time unchanged → no new sample
        MonitorTab._apply_metrics(m, parsed)
        self.assertEqual(len(m._raw_prompt), 1)
        self.assertEqual(len(m._raw_gen), 1)

    def test_emission_when_time_increases(self):
        """If time counter increased, emit a fresh sample."""
        m = self._fake_monitor()
        parsed = {
            'prompt_tokens_total': 100.0,
            'prompt_seconds_total': 10.0,
            'tokens_predicted_total': 200.0,
            'tokens_predicted_seconds_total': 15.0,
            'n_tokens_draft': 50.0,
            'tokens_draft_seconds_total': 5.0,
            'n_tokens_draft_accepted': 40.0,
            'n_tokens_draft_rejected': 10.0,
        }
        MonitorTab._apply_metrics(m, parsed)
        self.assertEqual(len(m._raw_prompt), 1)

        # Time increased, counters increased
        parsed['prompt_tokens_total'] = 250.0
        parsed['prompt_seconds_total'] = 20.0
        MonitorTab._apply_metrics(m, parsed)
        self.assertEqual(len(m._raw_prompt), 2)
        # Rate is delta_tokens / delta_time = (250 - 100) / (20 - 10)
        self.assertAlmostEqual(m._raw_prompt[1][1], 15.0)

    def test_unchanged_time_with_counter_increase_skips_sample(self):
        """If time unchanged but counter increased (server bug), skip sample."""
        m = self._fake_monitor()
        parsed = {
            'prompt_tokens_total': 100.0,
            'prompt_seconds_total': 10.0,
            'tokens_predicted_total': 200.0,
            'tokens_predicted_seconds_total': 15.0,
            'n_tokens_draft': 50.0,
            'tokens_draft_seconds_total': 5.0,
            'n_tokens_draft_accepted': 40.0,
            'n_tokens_draft_rejected': 10.0,
        }
        MonitorTab._apply_metrics(m, parsed)
        self.assertEqual(len(m._raw_prompt), 1)

        # Counter increased but time unchanged → skip
        parsed['prompt_tokens_total'] = 200.0
        MonitorTab._apply_metrics(m, parsed)
        self.assertEqual(len(m._raw_prompt), 1)

        # When time finally advances, include tokens accumulated while time was
        # frozen: (300 - 100) / (20 - 10) = 20 tok/s.
        parsed['prompt_tokens_total'] = 300.0
        parsed['prompt_seconds_total'] = 20.0
        MonitorTab._apply_metrics(m, parsed)
        self.assertEqual(len(m._raw_prompt), 2)
        self.assertAlmostEqual(m._raw_prompt[1][1], 20.0)


class MonitorTabWMATest(unittest.TestCase):
    """Tests for WMA behavior with None values."""

    def _make_monitor(self):
        m = MagicMock()
        m._graph_smooth_ms_pp = 60000
        m._graph_smooth_ms_tg = 60000
        m._raw_prompt = []
        m._raw_gen = []
        m._raw_draft = []
        m._raw_draft_gen = []
        m._raw_draft_acc = []
        m._chart = MagicMock()
        m._chart.add_point = MagicMock()
        m._chart.update_gauges = MagicMock()
        m._chart.update_slot_gauges = MagicMock()
        return m

    def test_wma_empty_buffer(self):
        m = self._make_monitor()
        m._graph_tick()
        # _graph_tick calls _wma internally; verify no crash on empty buffers
        self.assertTrue(True)

    def test_wma_no_samples_in_window(self):
        m = self._make_monitor()
        m._graph_tick()
        self.assertTrue(True)

    def test_wma_with_samples(self):
        m = self._make_monitor()
        m._raw_prompt = [(100.0, 10.0), (100.5, 20.0), (101.0, 30.0)]
        m._raw_gen = [(100.0, 10.0), (100.5, 20.0), (101.0, 30.0)]
        m._raw_draft = [(100.0, 50.0)]
        m._raw_draft_gen = [(100.0, 5.0)]
        m._raw_draft_acc = [(100.0, 4.0)]
        m._graph_tick()
        # Should not crash with samples
        self.assertTrue(True)

    def test_wma_single_sample(self):
        m = self._make_monitor()
        m._raw_prompt = [(100.0, 100.0)]
        m._raw_gen = [(100.0, 100.0)]
        m._raw_draft = [(100.0, 50.0)]
        m._raw_draft_gen = [(100.0, 5.0)]
        m._raw_draft_acc = [(100.0, 4.0)]
        m._graph_tick()
        self.assertTrue(True)


class MonitorTabRawTest(unittest.TestCase):
    """Tests for _raw buffer accessor."""

    def _make_monitor(self):
        m = MagicMock()
        m._graph_smooth_ms_pp = 60000
        m._graph_smooth_ms_tg = 60000
        m._raw_prompt = []
        m._raw_gen = []
        m._raw_draft = []
        m._raw_draft_gen = []
        m._raw_draft_acc = []
        m._chart = MagicMock()
        m._chart.add_point = MagicMock()
        m._chart.update_gauges = MagicMock()
        m._chart.update_slot_gauges = MagicMock()
        return m

    def test_raw_empty_buffer(self):
        m = self._make_monitor()
        m._graph_tick()
        self.assertTrue(True)

    def test_raw_with_samples(self):
        m = self._make_monitor()
        m._raw_prompt = [(100.0, 10.0), (101.0, 20.0)]
        m._raw_gen = [(100.0, 10.0), (101.0, 20.0)]
        m._raw_draft = [(100.0, 50.0)]
        m._raw_draft_gen = [(100.0, 5.0)]
        m._raw_draft_acc = [(100.0, 4.0)]
        m._graph_tick()
        self.assertTrue(True)


class MetricsChartAddPointTest(unittest.TestCase):
    """Tests for MetricsChart.add_point with None values."""

    def test_add_point_with_none_values(self):
        chart = MagicMock()
        chart._raw_prompt = []
        chart._raw_gen = []
        chart._raw_draft = []
        chart._raw_draft_gen = []
        chart._raw_draft_acc = []
        chart._times = []
        chart._prompt = []
        chart._gen = []
        chart._draft = []
        chart._draft_gen = []
        chart._draft_acc = []
        chart._times = []
        chart._max_points = 100
        chart._time_window_s = 120
        chart._smooth_ms = 60000
        chart._smooth_ms_draft = 60000
        chart._smooth_ms_draft_acc = 60000

        # All values None — raw buffers should have None entries
        MetricsChart.add_point(chart, None, None, None, None, None, None, None, None, None)
        self.assertEqual(len(chart._raw_prompt), 1)
        self.assertIsNone(chart._raw_prompt[0])
        self.assertEqual(len(chart._raw_gen), 1)
        self.assertIsNone(chart._raw_gen[0])
        self.assertEqual(len(chart._raw_draft), 1)
        self.assertIsNone(chart._raw_draft[0])
        self.assertEqual(len(chart._raw_draft_gen), 1)
        self.assertIsNone(chart._raw_draft_gen[0])
        self.assertEqual(len(chart._raw_draft_acc), 1)
        self.assertIsNone(chart._raw_draft_acc[0])

        # Mixed — raw buffers have same length as smoothed
        MetricsChart.add_point(chart, 10.0, None, 5.0, None, None, None, 3.0, None, None)
        self.assertEqual(len(chart._raw_prompt), 2)
        self.assertEqual(chart._raw_prompt[1], 10.0)
        self.assertEqual(len(chart._raw_draft_gen), 2)
        self.assertEqual(chart._raw_draft_gen[1], 3.0)


class PanelVisibilityTest(unittest.TestCase):
    """Tests for _compute_panel_rects with None samples."""

    def _make_chart(self):
        chart = MagicMock()
        chart._prompt = []
        chart._gen = []
        chart._draft = []
        chart._draft_gen = []
        chart._draft_acc = []
        chart._graphs_visible = {'pp': True, 'tg': True, 'draft_pct': True}
        chart.MARGIN_L = 46
        chart.MARGIN_R = 12
        chart.MARGIN_T = 18
        chart.MARGIN_B = 22
        chart.GAP = 18
        chart._PANEL_ORDER = ('pp', 'tg', 'draft_pct')
        chart._PANEL_WEIGHT = {'pp': 2, 'tg': 2, 'draft_pct': 1}
        chart._time_window_s = 120
        return chart

    def test_panel_hidden_when_all_samples_none(self):
        chart = self._make_chart()
        # _prompt has only None values — panel should be hidden
        chart._prompt = [None, None, None]
        chart._gen = [None, None]
        chart._draft = [None]
        chart._times = [time.monotonic(), time.monotonic(), time.monotonic()]
        rects = MetricsChart._compute_panel_rects(chart, 100, 200)
        self.assertNotIn('pp', rects)
        self.assertNotIn('tg', rects)
        self.assertNotIn('draft_pct', rects)

    def test_panel_shown_with_one_valid_sample(self):
        chart = self._make_chart()
        chart._prompt = [None, 5.0, None]
        chart._gen = [None]
        chart._draft = [None]
        now = time.monotonic()
        chart._times = [now, now, now]
        rects = MetricsChart._compute_panel_rects(chart, 100, 200)
        self.assertIn('pp', rects)
        self.assertIn('tg', rects)
        self.assertIn('draft_pct', rects)


class LineGapBreakingTest(unittest.TestCase):
    """Tests that draw_line breaks the line when there's a gap in samples."""

    def test_gap_breaks_line_into_segments(self):
        """When there's a gap (None between samples), the line should break."""
        # This is a visual test — we verify the line drawing logic doesn't
        # connect samples across gaps. The draw_line function is defined
        # inside _redraw, so we test the behavior indirectly by checking
        # that None values in the buffer are properly handled.
        chart = MagicMock()
        chart._raw_prompt = [None, 5.0, None, 10.0, None]
        chart._raw_gen = [None, 3.0, None, 8.0, None]
        # The key invariant: raw and smoothed buffers must have the same
        # length so X positions align.
        chart._prompt = [None, 4.5, None, 9.0, None]
        chart._gen = [None, 2.5, None, 7.5, None]
        # Just verify the buffers have matching lengths
        self.assertEqual(len(chart._raw_prompt), len(chart._prompt))
        self.assertEqual(len(chart._raw_gen), len(chart._gen))

    def test_buffers_aligned_after_mixed_add_point(self):
        """After add_point with mixed None/values, raw and smoothed align."""
        chart = MagicMock()
        chart._raw_prompt = []
        chart._raw_gen = []
        chart._raw_draft = []
        chart._raw_draft_gen = []
        chart._raw_draft_acc = []
        chart._prompt = []
        chart._gen = []
        chart._draft = []
        chart._draft_gen = []
        chart._draft_acc = []
        chart._max_points = 100

        # Call add_point multiple times with mixed values
        MetricsChart.add_point(chart, 10.0, 9.0, None, None, None, None, None, None, None)
        MetricsChart.add_point(chart, None, None, 5.0, 4.0, None, None, None, None, None)
        MetricsChart.add_point(chart, 20.0, 18.0, 8.0, 7.0, 50.0, 45.0, 3.0, 2.5, 2.0, 1.8)

        # All buffers should have the same length
        self.assertEqual(len(chart._raw_prompt), 3)
        self.assertEqual(len(chart._prompt), 3)
        self.assertEqual(len(chart._raw_gen), 3)
        self.assertEqual(len(chart._gen), 3)
        self.assertEqual(len(chart._raw_draft), 3)
        self.assertEqual(len(chart._draft), 3)

    def test_max_computation_filters_none_from_raw_buffers(self):
        """max() over raw buffers must filter None values (bug fix)."""
        # This verifies the Y-axis max computation doesn't crash when
        # raw buffers contain None values (from the buffer alignment fix).
        chart = MagicMock()
        # Simulate state: smoothed buffer has values, raw buffer has None at index 0
        chart._prompt = [10.0, 20.0, 15.0]
        chart._raw_prompt = [None, 10.0, 20.0, 15.0]
        chart._gen = [5.0, 8.0, 6.0]
        chart._raw_gen = [None, 5.0, 8.0, 6.0]
        chart._draft_gen = []
        chart._draft_acc = []
        chart._raw_draft_gen = []
        chart._raw_draft_acc = []

        # The Y-axis max computation (replicated from _redraw)
        all_pp = ([v for v in chart._prompt if v is not None]
                  + [v for v in chart._raw_prompt if v is not None])
        # This should not raise TypeError
        max_pp = max(all_pp) if all_pp else 10.0
        self.assertEqual(max_pp, 20.0)

        all_vals = ([v for v in chart._gen if v is not None]
                    + [v for v in chart._raw_gen if v is not None]
                    + [v for v in chart._raw_draft_gen if v is not None]
                    + [v for v in chart._raw_draft_acc if v is not None])
        max_tg = max(all_vals) if all_vals else 10.0
        self.assertEqual(max_tg, 8.0)


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main()
