"""
Profile switching and OptionWidget tests.

Covers:
  - set_value(None) clears every widget type to produce no CLI output
  - checkbox display stays in sync with _var
  - ConfigTab._do_switch_profile leaves a clean, non-dirty state
  - Values from a previous profile do not leak into the next
  - Unsaved manual changes are discarded on profile switch
  - The Default profile always yields a pristine empty state

Run with:  python3 test_profiles.py
"""

import sys
import os
import tempfile
import shutil
import unittest
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_empty(opt):
    val = opt.get_value()
    return val is None or val == ''


# ---------------------------------------------------------------------------
# OptionWidget.set_value(None) — one test per widget type
# ---------------------------------------------------------------------------

class OptionWidgetClearTest(unittest.TestCase):
    """set_value(None) must leave every widget type producing no CLI output."""

    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def _make(self, wtype, choices=None, key='test'):
        from widget_factory import OptionWidget
        return OptionWidget(self.root, wtype, '', choices=choices,
                            option_key=key)

    # ── file ─────────────────────────────────────────────────────────────────

    def test_file_set_then_clear(self):
        opt = self._make('file', key='model')
        opt.set_value('/models/x.gguf')
        self.assertFalse(_is_empty(opt))
        opt.set_value(None)
        self.assertTrue(_is_empty(opt), f'file not cleared: {opt.get_value()!r}')

    def test_file_display_clears(self):
        opt = self._make('file', key='model')
        opt.set_value('/models/x.gguf')
        opt.set_value(None)
        self.assertEqual(opt.widget.path.get(), '')

    # ── text ─────────────────────────────────────────────────────────────────

    def test_text_set_then_clear(self):
        opt = self._make('text')
        opt.set_value('hello')
        opt.set_value(None)
        self.assertTrue(_is_empty(opt), f'text not cleared: {opt.get_value()!r}')

    # ── spin ─────────────────────────────────────────────────────────────────

    def test_spin_set_then_clear(self):
        opt = self._make('spin')
        opt.set_value('16')
        opt.set_value(None)
        self.assertTrue(_is_empty(opt), f'spin not cleared: {opt.get_value()!r}')

    # ── float_spin ───────────────────────────────────────────────────────────

    def test_float_spin_set_then_clear(self):
        opt = self._make('float_spin')
        opt.set_value('0.8')
        opt.set_value(None)
        self.assertTrue(_is_empty(opt), f'float_spin not cleared: {opt.get_value()!r}')

    # ── checkbox ─────────────────────────────────────────────────────────────

    def test_checkbox_on_clears(self):
        opt = self._make('checkbox')
        opt.set_value('on')
        self.assertEqual(opt.get_value(), 'on')
        opt.set_value(None)
        self.assertEqual(opt.get_value(), '', f'checkbox not cleared: {opt.get_value()!r}')

    def test_checkbox_off_clears(self):
        opt = self._make('checkbox')
        opt.set_value('off')
        opt.set_value(None)
        self.assertEqual(opt.get_value(), '')

    def test_checkbox_display_syncs_on(self):
        """Combobox widget display must update when set_value('on') is called."""
        opt = self._make('checkbox')
        opt.set_value('on')
        self.assertEqual(opt.widget.get(), 'on')

    def test_checkbox_display_clears(self):
        """Combobox widget display must clear when set_value(None) is called."""
        opt = self._make('checkbox')
        opt.set_value('on')
        opt.set_value(None)
        self.assertEqual(opt.widget.get(), '',
                         'checkbox display still shows old value after clear')

    # ── dropdown ─────────────────────────────────────────────────────────────

    def test_dropdown_set_then_clear(self):
        opt = self._make('dropdown', choices=['none', 'linear', 'yarn'])
        opt.set_value('linear')
        self.assertEqual(opt.get_value(), 'linear')
        opt.set_value(None)
        self.assertTrue(_is_empty(opt), f'dropdown not cleared: {opt.get_value()!r}')

    def test_dropdown_display_clears(self):
        opt = self._make('dropdown', choices=['none', 'linear', 'yarn'])
        opt.set_value('linear')
        opt.set_value(None)
        self.assertEqual(opt.widget.get(), '')

    # ── radio ─────────────────────────────────────────────────────────────────

    def test_radio_set_then_clear(self):
        opt = self._make('radio', choices=['0', '1', '2'])
        opt.set_value('1')
        opt.set_value(None)
        self.assertTrue(_is_empty(opt), f'radio not cleared: {opt.get_value()!r}')

    # ── multiline_text ────────────────────────────────────────────────────────

    def test_multiline_text_set_then_clear(self):
        opt = self._make('multiline_text')
        opt.set_value('line one\nline two')
        self.assertFalse(_is_empty(opt))
        opt.set_value(None)
        self.assertTrue(_is_empty(opt), f'multiline_text not cleared: {opt.get_value()!r}')

    # ── ordered_list_of_options ───────────────────────────────────────────────

    def test_ordered_list_set_then_clear(self):
        opt = self._make('ordered_list_of_options', choices=['a', 'b', 'c'])
        opt.set_value('a,c')
        self.assertFalse(_is_empty(opt))
        opt.set_value(None)
        self.assertTrue(_is_empty(opt), f'ordered_list not cleared: {opt.get_value()!r}')


# ---------------------------------------------------------------------------
# ConfigTab profile switching — headless integration tests
# ---------------------------------------------------------------------------

class ConfigTabProfileTest(unittest.TestCase):
    """
    Full ConfigTab integration tests for profile switching.

    Each test gets a fresh ConfigTab and an isolated temp profile directory
    so tests are independent and don't touch ~/.llama-gui.
    """

    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        from config_tab import ConfigTab
        self.tab = ConfigTab(self.root)
        # Redirect profile storage to the temp directory
        self.tab._profile_mgr._dir = self._tmpdir

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        self.tab.destroy()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _set(self, key, value):
        opt = self.tab._option_map.get(key)
        if opt is None:
            self.fail(f'option {key!r} not found in option_map')
        opt.set_value(value)

    def _get(self, key):
        opt = self.tab._option_map.get(key)
        return opt.get_value() if opt else None

    def _save_current_as(self, name):
        opts = self.tab._collect_options()
        self.tab._profile_mgr.save(name, opts)
        self.tab._refresh_profile_list()

    def _switch(self, name):
        self.tab._do_switch_profile(name)

    # ── not-dirty after switch ────────────────────────────────────────────────

    def test_not_dirty_after_switch_to_default(self):
        self._switch('Default')
        self.assertFalse(self.tab._dirty,
                         'Form must not be dirty after switching to Default')

    def test_not_dirty_after_switch_to_named_profile(self):
        self._save_current_as('P1')
        self._switch('P1')
        self.assertFalse(self.tab._dirty,
                         'Form must not be dirty after switching to a named profile')

    def test_not_dirty_after_two_switches(self):
        self._save_current_as('A')
        self._save_current_as('B')
        self._switch('A')
        self._switch('B')
        self.assertFalse(self.tab._dirty)

    # ── Default yields pristine empty state ──────────────────────────────────

    def test_default_clears_file_field(self):
        self._set('model', '/models/x.gguf')
        self._switch('Default')
        self.assertTrue(_is_empty(self.tab._option_map['model']),
                        'model must be empty after switching to Default')

    def test_default_clears_spin_field(self):
        self._set('threads', '16')
        self._switch('Default')
        self.assertTrue(_is_empty(self.tab._option_map['threads']),
                        'threads must be empty after switching to Default')

    def test_default_clears_checkbox_field(self):
        self._set('mlock', 'on')
        self._switch('Default')
        opt = self.tab._option_map['mlock']
        val = opt.get_value()
        self.assertEqual(val, '',
                         f'mlock must be empty after Default switch, got {val!r}')

    def test_default_clears_checkbox_display(self):
        self._set('mlock', 'on')
        self._switch('Default')
        displayed = self.tab._option_map['mlock'].widget.get()
        self.assertEqual(displayed, '',
                         f'mlock combobox still shows {displayed!r} after Default switch')

    def test_default_clears_text_field(self):
        self._set('alias', 'my-model')
        self._switch('Default')
        self.assertTrue(_is_empty(self.tab._option_map['alias']))

    # ── values do not leak between profiles ──────────────────────────────────

    def test_file_does_not_leak_to_profile_without_it(self):
        """mmproj set in profile A must not appear when switching to profile B."""
        self._set('mmproj', '/models/mmproj.gguf')
        self._save_current_as('WithMMProj')

        # Profile B saved with mmproj cleared
        self._set('mmproj', None)
        self._save_current_as('NoMMProj')

        # Switch to A to load mmproj, then to B
        self._switch('WithMMProj')
        self.assertFalse(_is_empty(self.tab._option_map['mmproj']),
                         'sanity: mmproj should be set in WithMMProj')

        self._switch('NoMMProj')
        self.assertTrue(_is_empty(self.tab._option_map['mmproj']),
                        'mmproj must be empty after switching to NoMMProj')

    def test_spin_does_not_leak(self):
        self._set('threads', '8')
        self._save_current_as('T8')

        self._set('threads', None)
        self._save_current_as('TDefault')

        self._switch('T8')
        self._switch('TDefault')
        self.assertTrue(_is_empty(self.tab._option_map['threads']),
                        'threads must be empty in TDefault profile')

    def test_checkbox_does_not_leak(self):
        self._set('mlock', 'on')
        self._save_current_as('Mlock')

        self._set('mlock', None)
        self._save_current_as('NoMlock')

        self._switch('Mlock')
        self.assertEqual(self._get('mlock'), 'on', 'sanity check')

        self._switch('NoMlock')
        val = self._get('mlock')
        self.assertEqual(val, '',
                         f'mlock must be empty in NoMlock, got {val!r}')

    def test_checkbox_display_does_not_leak(self):
        self._set('mlock', 'on')
        self._save_current_as('Mlock')
        self._set('mlock', None)
        self._save_current_as('NoMlock')

        self._switch('Mlock')
        self._switch('NoMlock')
        displayed = self.tab._option_map['mlock'].widget.get()
        self.assertEqual(displayed, '',
                         f'mlock combobox shows {displayed!r} after switch to NoMlock')

    def test_multiple_fields_do_not_leak(self):
        self._set('model', '/a.gguf')
        self._set('threads', '4')
        self._set('mlock', 'on')
        self._save_current_as('Full')

        # Empty profile
        self._switch('Default')
        self._save_current_as('Empty')

        self._switch('Full')
        self._switch('Empty')

        for key in ('model', 'threads', 'mlock'):
            opt = self.tab._option_map[key]
            val = opt.get_value()
            empty = val is None or val == ''
            self.assertTrue(empty,
                            f'{key} leaked into Empty profile: {val!r}')

    # ── profile values are applied correctly ──────────────────────────────────

    def test_named_profile_values_applied(self):
        self._set('model', '/models/q4.gguf')
        self._set('threads', '4')
        self._save_current_as('Config1')

        self._switch('Default')
        self._switch('Config1')

        self.assertEqual(self._get('model'), '/models/q4.gguf')
        self.assertEqual(str(self._get('threads')), '4')

    def test_profile_overwrites_previously_different_value(self):
        """When B has threads=4 and we were viewing A (threads=8), B must show 4."""
        self._set('threads', '8')
        self._save_current_as('T8')

        self._set('threads', '4')
        self._save_current_as('T4')

        self._switch('T8')
        self.assertEqual(str(self._get('threads')), '8', 'sanity')

        self._switch('T4')
        self.assertEqual(str(self._get('threads')), '4',
                         'threads must be 4 after switching to T4')

    # ── unsaved manual changes are discarded on switch ────────────────────────

    def test_unsaved_manual_change_does_not_persist(self):
        self._save_current_as('Clean1')
        self._save_current_as('Clean2')

        self._switch('Clean1')
        # Manual change — not saved
        self._set('model', '/sneaky.gguf')

        self._switch('Clean2')
        self.assertTrue(_is_empty(self.tab._option_map['model']),
                        'Unsaved manual change must not appear in Clean2')

    # ── _apply_options does not mutate the loaded dict ────────────────────────

    def test_apply_options_does_not_mutate_source(self):
        original = {'model': '/x.gguf', '_server_bin': 'my-server'}
        copy = dict(original)
        self.tab._apply_options(original)
        self.assertEqual(original, copy,
                         '_apply_options must not mutate its argument')


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main(verbosity=2)
