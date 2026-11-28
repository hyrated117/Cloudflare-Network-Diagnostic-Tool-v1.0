#!/usr/bin/env python3
"""Self-test for the rules in Tools/check-dependabot.py.

GitHub reads `dependabot.yml` only from the default branch and reports nothing when it
is wrong, so every rule the check asserts is pinned here both ways: a config that breaks
the rule must fail, and one that satisfies it must stay quiet. The warning path is
pinned too, because keeping an unrecognized key a warning is what stops a new GitHub
key from failing a sound config.

    python3 Tools/test_check_dependabot.py

Stdlib only, and the tool imports PyYAML inside main(), so this runs without it.
"""

import contextlib
import importlib.util
import io
import pathlib
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "check-dependabot.py"
SPEC = importlib.util.spec_from_file_location("check_dependabot", TOOL)
check_dependabot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_dependabot)


def entry(**fields):
    """A sound update entry, with the given fields replacing or adding to it."""
    base = {
        "package-ecosystem": "github-actions",
        "directory": "/",
        "schedule": {"interval": "weekly"},
    }
    base.update(fields)
    return base


class Base(unittest.TestCase):
    def setUp(self):
        check_dependabot.problems.clear()

    def run_quietly(self, call, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            call(*args)
        return output.getvalue()

    def failures(self, call, *args):
        self.run_quietly(call, *args)
        return check_dependabot.problems


class EntryRule(Base):
    def failures(self, value):
        return super().failures(check_dependabot.check_entry, 0, value)

    def assert_sound(self, value):
        self.assertEqual(self.failures(value), [])

    def assert_fails(self, value, expected):
        problems = self.failures(value)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(expected, problems[0])

    def test_sound_entry_passes(self):
        self.assert_sound(entry())

    def test_directories_passes(self):
        value = entry()
        value.pop("directory")
        value["directories"] = ["/", "/installers"]
        self.assert_sound(value)

    def test_non_mapping_entry_fails(self):
        self.assert_fails("github-actions", "must be a mapping")

    def test_missing_ecosystem_fails(self):
        value = entry()
        value.pop("package-ecosystem")
        self.assert_fails(value, "package-ecosystem must be a name")

    def test_blank_ecosystem_fails(self):
        self.assert_fails(entry(**{"package-ecosystem": "  "}), "package-ecosystem must be a name")

    def test_both_paths_fail(self):
        self.assert_fails(entry(directories=["/"]), "exactly one of directory or directories")

    def test_neither_path_fails(self):
        value = entry()
        value.pop("directory")
        self.assert_fails(value, "exactly one of directory or directories")

    def test_directory_must_be_a_string(self):
        self.assert_fails(entry(directory=1), "directory must be a string")

    def test_directories_must_be_non_empty_strings(self):
        value = entry()
        value.pop("directory")
        value["directories"] = []
        self.assert_fails(value, "non-empty list of strings")

    def test_directories_with_non_string_item_fails(self):
        value = entry()
        value.pop("directory")
        value["directories"] = ["/", 1]
        self.assert_fails(value, "non-empty list of strings")

    def test_missing_schedule_fails(self):
        value = entry()
        value.pop("schedule")
        self.assert_fails(value, "needs a schedule mapping")

    def test_schedule_must_be_a_mapping(self):
        self.assert_fails(entry(schedule="weekly"), "needs a schedule mapping")

    def test_unknown_interval_fails(self):
        self.assert_fails(entry(schedule={"interval": "hourly"}), "interval must be one of")

    def test_missing_interval_fails(self):
        self.assert_fails(entry(schedule={"day": "monday"}), "interval must be one of")

    def test_cron_interval_needs_a_cronjob(self):
        self.assert_fails(entry(schedule={"interval": "cron"}), "needs a cronjob string")

    def test_cron_interval_with_a_cronjob_passes(self):
        self.assert_sound(entry(schedule={"interval": "cron", "cronjob": "0 4 * * 1"}))

    def test_unrecognized_entry_key_warns_without_failing(self):
        output = self.run_quietly(check_dependabot.check_entry, 0, entry(**{"made-up-key": True}))
        self.assertEqual(check_dependabot.problems, [])
        self.assertIn("unrecognized key(s) made-up-key", output)
        self.assertIn("warning:", output)

    def test_unrecognized_schedule_key_warns_without_failing(self):
        value = entry(schedule={"interval": "weekly", "made-up-key": 1})
        output = self.run_quietly(check_dependabot.check_entry, 0, value)
        self.assertEqual(check_dependabot.problems, [])
        self.assertIn("updates[0].schedule: unrecognized key(s) made-up-key", output)


class ConfigRule(Base):
    def failures(self, config, pinned=()):
        return super().failures(check_dependabot.check_config, config, list(pinned))

    def assert_sound(self, config, pinned):
        self.assertEqual(self.failures(config, pinned), [])

    def assert_fails(self, config, pinned, expected):
        problems = self.failures(config, pinned)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(expected, problems[0])

    def test_sound_config_passes(self):
        config = {"version": 2, "updates": [entry()]}
        self.assert_sound(config, ["ci.yml"])

    def test_version_must_be_two(self):
        self.assert_fails({"version": 1, "updates": [entry()]}, [], "version must be 2")

    def test_version_must_be_a_number(self):
        self.assert_fails({"version": "2", "updates": [entry()]}, [], "version must be 2")

    def test_missing_version_fails(self):
        self.assert_fails({"updates": [entry()]}, [], "version must be 2")

    def test_missing_updates_fails(self):
        self.assert_fails({"version": 2}, [], "updates must be a non-empty list")

    def test_empty_updates_fails(self):
        self.assert_fails({"version": 2, "updates": []}, [], "updates must be a non-empty list")

    def test_updates_must_be_a_list(self):
        self.assert_fails({"version": 2, "updates": entry()}, [], "updates must be a non-empty list")

    def test_uncovered_action_pins_fail(self):
        config = {
            "version": 2,
            "updates": [entry(**{"package-ecosystem": "npm", "directory": "/installers"})],
        }
        problems = self.failures(config, ["ci.yml", "codeql.yml"])
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("would never be updated", problems[0])
        self.assertIn("ci.yml, codeql.yml", problems[0])

    def test_github_actions_entry_elsewhere_does_not_cover(self):
        config = {
            "version": 2,
            "updates": [entry(directory="/installers"), entry(**{"package-ecosystem": "npm"})],
        }
        problems = self.failures(config, ["ci.yml"])
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("would never be updated", problems[0])

    def test_no_action_pins_need_no_github_actions_entry(self):
        config = {
            "version": 2,
            "updates": [entry(**{"package-ecosystem": "npm", "directory": "/installers"})],
        }
        self.assert_sound(config, [])

    def test_entry_problems_are_collected(self):
        broken = entry()
        broken.pop("schedule")
        problems = self.failures({"version": 2, "updates": [broken]}, [])
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("updates[0]", problems[0])

    def test_every_broken_entry_is_reported(self):
        first = entry(schedule={"interval": "hourly"})
        second = entry(**{"package-ecosystem": ""})
        problems = self.failures({"version": 2, "updates": [first, second]}, [])
        self.assertEqual(len(problems), 2, problems)
        self.assertIn("updates[0].schedule", problems[0])
        self.assertIn("updates[1]", problems[1])


if __name__ == "__main__":
    unittest.main()
