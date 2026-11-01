"""Guards for the /habits data pipeline.

Standard library only, like everything under scripts/. Run with

    python3 -m unittest discover -s tests -v

Four things are pinned here, each of which has produced wrong numbers before:

- the one-JSON-per-habit contract that habits.astro reads;
- ``write_habit`` merging rather than overwriting (the Apple sources keep ~4 weeks,
  so an overwriting write would erase the archive);
- ``fetch_screentime.implausible`` refusing a 26-hour day and a date in 2033 (the
  tombstone-directory parse failure);
- ``import_health.implausible_sleep`` refusing a 1.5 h median (naps filed as nights).
"""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
DATA_DIR = os.path.join(ROOT, "src", "data", "habits")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import habits_common as hc  # noqa: E402
import fetch_screentime  # noqa: E402
import import_health  # noqa: E402

DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class HabitJsonContract(unittest.TestCase):
    """Every file in src/data/habits/ has the shape habits.astro expects."""

    def habit_files(self) -> list[str]:
        files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
        self.assertTrue(files, f"no habit files under {DATA_DIR}")
        return files

    def test_every_file_has_days_and_updated_at(self) -> None:
        for path in self.habit_files():
            with self.subTest(file=os.path.basename(path)):
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                self.assertIn("days", data)
                self.assertIsInstance(data["days"], dict)
                self.assertIn("updated_at", data)
                if data["days"]:
                    # A habit with history must carry a real timestamp; only an
                    # empty placeholder (sleep.json today) may hold null.
                    self.assertIsInstance(data["updated_at"], str)
                    self.assertRegex(data["updated_at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_every_day_is_a_dated_numeric_value(self) -> None:
        for path in self.habit_files():
            with open(path, encoding="utf-8") as fh:
                days = json.load(fh)["days"]
            for key, rec in days.items():
                with self.subTest(file=os.path.basename(path), day=key):
                    self.assertRegex(key, DAY_RE)
                    dt.date.fromisoformat(key)  # a real calendar date
                    self.assertIsInstance(rec, dict)
                    self.assertIn("value", rec)
                    self.assertIsInstance(rec["value"], (int, float))
                    self.assertNotIsInstance(rec["value"], bool)
                    self.assertGreaterEqual(rec["value"], 0)


class WriteHabitMerges(unittest.TestCase):
    """``write_habit`` layers new days over the file; earlier days survive."""

    def setUp(self) -> None:
        quiet = mock.patch.object(hc, "log", lambda msg: None)  # keep stderr clean
        quiet.start()
        self.addCleanup(quiet.stop)

    def test_earlier_days_survive_a_later_write(self) -> None:
        first = {"2026-01-01": hc.day(1.0, note="old"), "2026-01-02": hc.day(2.0)}
        second = {"2026-01-02": hc.day(2.5), "2026-01-03": hc.day(3.0)}
        with tempfile.TemporaryDirectory() as tmp:
            hc.write_habit("t", "T", "test", "u", first, data_dir=tmp)
            hc.write_habit("t", "T", "test", "u", second, data_dir=tmp)
            written = hc.load_habit("t", data_dir=tmp)

        self.assertEqual(sorted(written["days"]), ["2026-01-01", "2026-01-02", "2026-01-03"])
        self.assertEqual(written["days"]["2026-01-01"], first["2026-01-01"])  # untouched
        self.assertEqual(written["days"]["2026-01-02"]["value"], 2.5)  # newer wins
        self.assertEqual(written["days"]["2026-01-03"]["value"], 3.0)

    def test_merge_false_is_the_only_way_to_lose_history(self) -> None:
        first = {"2026-01-01": hc.day(1.0)}
        second = {"2026-01-02": hc.day(2.0)}
        with tempfile.TemporaryDirectory() as tmp:
            hc.write_habit("t", "T", "test", "u", first, data_dir=tmp)
            hc.write_habit("t", "T", "test", "u", second, data_dir=tmp, merge=False)
            written = hc.load_habit("t", data_dir=tmp)
        self.assertEqual(sorted(written["days"]), ["2026-01-02"])


class ScreenTimeGuard(unittest.TestCase):
    """``implausible()`` refuses data that cannot be describing real usage."""

    def test_clean_days_pass(self) -> None:
        days = {"2026-10-30": hc.day(3.2, iphone_h=1.1), "2026-10-31": hc.day(4.0, iphone_h=2.0)}
        self.assertEqual(fetch_screentime.implausible(days), [])

    def test_rejects_a_26_hour_day(self) -> None:
        days = {"2026-10-30": hc.day(26.0, iphone_h=1.0)}
        problems = fetch_screentime.implausible(days)
        self.assertTrue(any("over 24h" in p for p in problems), problems)

    def test_rejects_a_2033_date(self) -> None:
        days = {"2033-01-15": hc.day(2.0, iphone_h=1.0)}
        problems = fetch_screentime.implausible(days)
        self.assertTrue(any("in the future" in p for p in problems), problems)


class SleepGuard(unittest.TestCase):
    """``implausible_sleep()`` refuses naps filed as nights."""

    def test_rejects_a_1_5_hour_median(self) -> None:
        days = {
            "2026-10-29": hc.day(1.3),
            "2026-10-30": hc.day(1.5),
            "2026-10-31": hc.day(1.7),
        }
        problems = import_health.implausible_sleep(days)
        self.assertTrue(any("nap length" in p for p in problems), problems)

    def test_a_real_week_passes(self) -> None:
        days = {f"2026-10-{d:02d}": hc.day(7.5) for d in range(20, 27)}
        self.assertEqual(import_health.implausible_sleep(days), [])


if __name__ == "__main__":
    unittest.main()
