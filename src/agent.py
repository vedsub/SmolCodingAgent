
from pathlib import Path

from src.file_tools import apply_patch, run_tests


class TinyCodingAgent:

    ALLOWED_TOOLS = {
        "run_tests",
        "apply_patch",
    }

    def __init__(
        self,
        workspace,
        proposals,
        action_budget=4,
        test_timeout=30,
    ):
        self.workspace = Path(workspace).resolve(strict=True)

        if not self.workspace.is_dir():
            raise NotADirectoryError("Workspace must be a directory")

        if action_budget < 0:
            raise ValueError("Action budget cannot be negative")

        self.proposals = proposals
        self.action_budget = action_budget
        self.test_timeout = test_timeout

        self.actions_used = 0
        self.trace = []
        self.observations = []

        self.tests_passed = False
        self.stopped = False
        self.stop_reason = None

    def planner(self):
        """
        Deterministic planner.

        Decide the next action using previous observations.
        """

        # First action: always run tests.
        if not self.observations:
            return {"tool": "run_tests"}

        last_observation = self.observations[-1]

        # Stop immediately when tests pass.
        if last_observation.get("tool") == "run_tests":
            if last_observation.get("success"):
                return None

            error_text = (
                last_observation.get("stderr", "")
                + "\n"
                + last_observation.get("error", "")
            )

            # Select a proposal only if its failure marker matches.
            for proposal in self.proposals:
                marker = proposal.get("failure_marker")

                if marker and marker in error_text:
                    return {
                        "tool": "apply_patch",
                        "path": proposal["path"],
                        "old_text": proposal["old_text"],
                        "new_text": proposal["new_text"],
                    }

            return None

        # After a successful patch, test again.
        if last_observation.get("tool") == "apply_patch":
            if last_observation.get("success"):
                return {"tool": "run_tests"}

            return None

        return None

    def execute_action(self, action):
        """
        Validate and execute one allowed tool action.
        """

        if not isinstance(action, dict):
            raise ValueError("Action must be a dictionary")

        tool_name = action.get("tool")

        if tool_name not in self.ALLOWED_TOOLS:
            raise ValueError(f"Invalid tool: {tool_name}")

        if tool_name == "run_tests":
            result = run_tests(
                self.workspace,
                timeout=self.test_timeout,
            )

            return {
                "tool": "run_tests",
                **result,
            }

        if tool_name == "apply_patch":
            required_fields = {
                "path",
                "old_text",
                "new_text",
            }

            if not required_fields.issubset(action):
                raise ValueError("Patch action has missing fields")

            result = apply_patch(
                self.workspace,
                action["path"],
                action["old_text"],
                action["new_text"],
            )

            return {
                "tool": "apply_patch",
                "success": True,
                "message": result,
            }

    def run(self):
        """
        Execute the agent loop until a stopping condition is reached.
        """

        while self.actions_used < self.action_budget:

            action = self.planner()

            # Planner abstained.
            if action is None:
                self.stopped = True

                if self.observations and (
                    self.observations[-1].get("tool") == "run_tests"
                    and self.observations[-1].get("success")
                ):
                    self.tests_passed = True
                    self.stop_reason = "tests_passed"
                else:
                    self.stop_reason = "planner_abstained"

                break

            # Every action counts against the budget.
            self.actions_used += 1

            try:
                observation = self.execute_action(action)

            except (ValueError, KeyError, TypeError) as error:
                observation = {
                    "tool": action.get("tool"),
                    "success": False,
                    "error": str(error),
                }

                self.trace.append({
                    "action": action,
                    "observation": observation,
                })

                self.observations.append(observation)

                self.stopped = True
                self.stop_reason = "invalid_tool_call"

                break

            except Exception as error:
                observation = {
                    "tool": action.get("tool"),
                    "success": False,
                    "error": str(error),
                }

                self.trace.append({
                    "action": action,
                    "observation": observation,
                })

                self.observations.append(observation)

                self.stopped = True
                self.stop_reason = "tool_execution_failed"

                break

            # Record action and corresponding observation.
            self.trace.append({
                "action": action,
                "observation": observation,
            })

            self.observations.append(observation)

            # Stop immediately after a successful test run.
            if (
                observation.get("tool") == "run_tests"
                and observation.get("success")
            ):
                self.tests_passed = True
                self.stopped = True
                self.stop_reason = "tests_passed"
                break

        # Stop if the action budget has been exhausted.
        if not self.stopped:
            self.stopped = True
            self.stop_reason = "action_budget_exhausted"

        return {
            "success": self.tests_passed,
            "actions_used": self.actions_used,
            "action_budget": self.action_budget,
            "stop_reason": self.stop_reason,
            "trace": self.trace,
        }
