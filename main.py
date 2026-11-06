
import json
from pathlib import Path

from src.agent import TinyCodingAgent


def main():

    workspace = Path("workspace").resolve()

    proposals_path = workspace / "proposals.json"

    proposals = json.loads(
        proposals_path.read_text(encoding="utf-8")
    )

    agent = TinyCodingAgent(
        workspace=workspace,
        proposals=proposals,
        action_budget=4,
        test_timeout=30,
    )

    result = agent.run()

    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    main()
