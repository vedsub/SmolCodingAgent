
import json
import tempfile
import unittest

from pathlib import Path

from src.agent import TinyCodingAgent


class TestTinyCodingAgent(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

        (self.workspace / "tests").mkdir()

        (self.workspace / "basket.py").write_text(
            "def calculate_total(price, quantity):\n"
            "    return price + quantity\n",
            encoding="utf-8",
        )

        (self.workspace / "tests" / "test_basket.py").write_text(
            "import unittest\n"
            "from basket import calculate_total\n"
            "\n"
            "class BasketTests(unittest.TestCase):\n"
            "    def test_total(self):\n"
            "        self.assertEqual(calculate_total(7, 3), 21)\n"
            "\n"
            "    def test_zero_quantity(self):\n"
            "        self.assertEqual(calculate_total(7, 0), 0)\n",
            encoding="utf-8",
        )

        self.proposals = [
            {
                "path": "basket.py",
                "failure_marker": "AssertionError",
                "old_text": "price + quantity",
                "new_text": "price * quantity",
            }
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_agent_repairs_basket(self):

        agent = TinyCodingAgent(
            workspace=self.workspace,
            proposals=self.proposals,
            action_budget=4,
        )

        result = agent.run()

        self.assertTrue(result["success"])
        self.assertEqual(result["actions_used"], 3)
        self.assertEqual(result["stop_reason"], "tests_passed")

    def test_agent_stops_when_budget_exhausted(self):

        agent = TinyCodingAgent(
            workspace=self.workspace,
            proposals=self.proposals,
            action_budget=1,
        )

        result = agent.run()

        self.assertFalse(result["success"])
        self.assertEqual(
            result["stop_reason"],
            "action_budget_exhausted",
        )

    def test_agent_stops_if_marker_does_not_match(self):

        proposals = [
            {
                "path": "basket.py",
                "failure_marker": "SomeOtherError",
                "old_text": "price + quantity",
                "new_text": "price * quantity",
            }
        ]

        agent = TinyCodingAgent(
            workspace=self.workspace,
            proposals=proposals,
            action_budget=4,
        )

        result = agent.run()

        self.assertFalse(result["success"])
        self.assertEqual(result["stop_reason"], "planner_abstained")

    def test_invalid_tool_is_rejected(self):

        agent = TinyCodingAgent(
            workspace=self.workspace,
            proposals=self.proposals,
        )

        with self.assertRaises(ValueError):
            agent.execute_action({"tool": "execute_shell"})


if __name__ == "__main__":
    unittest.main()
