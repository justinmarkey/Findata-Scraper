import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from findata.settings import DEFAULT_SETTINGS, load_settings, report_settings, screen_rules
from findata.screening import screen
from test_pipeline import snapshot


class SettingsTests(unittest.TestCase):
    def test_editing_pe_threshold_changes_results_without_code_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.toml'
            path.write_text(DEFAULT_SETTINGS.read_text().replace('threshold = 20.0', 'threshold = 5.0'))
            settings = load_settings(path)
            rules = screen_rules(settings, 'value_pe')
            self.assertEqual(len(rules), 5)
            self.assertFalse(screen({'X': snapshot()}, 'value_pe', rules=rules).iloc[0]['passed'])
            self.assertTrue(screen({'X': snapshot()}, 'value_pe').iloc[0]['passed'])

    def test_secrets_environment_overrides_local_file(self):
        with patch.dict(os.environ, {'REPORT_TO': 'configured@example.com'}):
            self.assertEqual(report_settings()['recipient'], 'configured@example.com')

    def test_schedule_sync_follows_settings(self):
        from findata.scheduling import sync_schedule
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / 'workflow.yml'
            workflow.write_text('on:\n  schedule:\n    # BEGIN CONFIGURED SCHEDULE\n    # END CONFIGURED SCHEDULE\n')
            settings = load_settings()
            settings['reports']['morning_time'] = '08:15'
            sync_schedule(settings, workflow)
            self.assertIn("cron: '15 8 * * *'", workflow.read_text())
            self.assertIn('timezone: America/New_York', workflow.read_text())

    def test_invalid_rules_and_inheritance_fail_early(self):
        settings = load_settings()
        settings['screens']['value']['rules'][0]['threshold'] = float('nan')
        with self.assertRaises(ValueError): screen_rules(settings, 'value')
        settings['screens']['cycle'] = {'extends': 'cycle', 'rules': []}
        with self.assertRaises(ValueError): screen_rules(settings, 'cycle')


if __name__ == '__main__':
    unittest.main()
