"""inspect_games.py: its report, its browser lookup and its time limits (the browser run itself needs Chrome, so it is
not a unit test)."""
from __future__ import annotations

import asyncio
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import inspect_games


class InspectGamesTests(unittest.TestCase):
    def test_the_report_names_every_unit_and_problem(self):
        result = {"passed": False, "problems": ["L01 Hör-Bingo: a right answer showed wrong («Hallo.»)"],
                  "units": {"L01": {"bingo": {"calls": 9, "flashes": 1}, "art": None},
                            "L02": {"paare": {"rounds": 3, "flashes": 0}}}}
        report = inspect_games.summary(result)
        self.assertIn("L01: bingo calls 9, flashes 1", report)
        self.assertIn("L02: paare rounds 3, flashes 0", report)
        self.assertIn("PROBLEM: L01 Hör-Bingo: a right answer showed wrong", report)
        self.assertTrue(report.endswith("FAIL: 2 units, 1 problems"))

    def test_a_missing_browser_says_how_to_name_one(self):
        with self.assertRaisesRegex(inspect_games.InspectError, "--browser"):
            inspect_games.find_browser("no-such-browser-for-this-test")

    def test_a_wait_that_runs_out_says_what_did_not_happen(self):
        async def never():
            await asyncio.Event().wait()
        with self.assertRaisesRegex(inspect_games.InspectError, r"^the app did not finish loading within 0\.05 s$"):
            asyncio.run(inspect_games.within(0.05, never(), "the app did not finish loading"))

    def test_a_failure_always_says_why(self):
        async def times_out(*args):
            raise asyncio.TimeoutError()               # no message, as when a computer slept during the check
        with tempfile.TemporaryDirectory() as folder:
            app = Path(folder) / "app.html"
            app.write_text("<!doctype html>", encoding="utf-8")
            with mock.patch.object(inspect_games, "inspect", times_out), \
                    mock.patch.object(inspect_games, "find_browser", lambda given=None: "chrome"), \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(inspect_games.main([str(app)]), 2)
        self.assertEqual(errors.getvalue(), "FAIL: TimeoutError\n")


if __name__ == "__main__":
    unittest.main()
