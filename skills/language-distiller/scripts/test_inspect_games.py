"""inspect_games.py: its report and its browser lookup (the browser run itself needs Chrome, so it is not a unit test)."""
from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
