# A Tiny Coding Agent

A deterministic, tool-using Python coding agent that can inspect test results, identify predefined repair proposals, modify source files safely, and rerun tests to verify its changes.

## 1. Project Overview

Tiny Coding Agent is a lightweight implementation of an autonomous coding-agent workflow.

The project demonstrates how an agent can interact with a software project through a controlled set of tools rather than directly modifying files or executing arbitrary commands.

The agent follows a structured loop:

1. Execute the existing test suite.
2. Observe the test results.
3. Identify a matching repair proposal based on the failure output.
4. Apply the proposed code change using a controlled patching mechanism.
5. Execute the tests again.
6. Stop when the tests pass, an action fails, the planner abstains, or the action budget is exhausted.

The current implementation uses a deterministic planner and predefined repair proposals. It does not depend on an LLM to make decisions.

### Example

Suppose a project contains the following function:

```python
def calculate_total(price, quantity):
    return price + quantity
```

The expected behavior is multiplication, but the implementation uses addition.

The agent executes the test suite and observes two failures:

```text
AssertionError: 10 != 21
AssertionError: 7 != 0
```

It detects the `AssertionError` failure marker, selects a matching repair proposal, and changes:

```python
price + quantity
```

to:

```python
price * quantity
```

The agent then reruns the tests and stops after both pass.

This demonstrates a complete observe-decide-act-verify cycle.

---

## 2. Problem Statement

Traditional scripts generally execute a predefined sequence of instructions. They do not necessarily adapt their next action based on the outcome of a previous operation.

An agentic workflow introduces a feedback loop:

- Actions produce observations.
- Observations influence subsequent decisions.
- Tools perform operations in the environment.
- The system evaluates whether the desired outcome has been achieved.

The objective of this project is to implement the fundamental infrastructure required for a coding agent.

The project focuses on four important engineering problems:

1. Safe workspace file access.
2. Reliable and atomic source-code modifications.
3. Controlled test execution.
4. An agent loop that coordinates tools and observations under a finite action budget.

These capabilities form a small foundation for more advanced coding agents.

---

## 3. Architecture

The project is organized into four primary layers.

### 3.1 Workspace File Tools

Responsible for interacting with files inside a trusted workspace.

Responsibilities:

- Resolve requested paths relative to a workspace.
- Reject absolute paths.
- Prevent directory traversal.
- Detect symlink escapes.
- Read files safely.
- Apply exact-match source-code patches.

### 3.2 Test Runner

Responsible for executing the project's Python unit tests.

Responsibilities:

- Use the current Python interpreter.
- Execute unittest discovery with a fixed command.
- Capture standard output and standard error.
- Disable interactive standard input.
- Enforce a timeout.
- Terminate the process group on timeout on POSIX systems.
- Validate that tests actually ran.
- Reject skipped tests.
- Return structured success or failure observations.

### 3.3 Agent and Planner

Responsible for coordinating tools and deciding what happens next.

Responsibilities:

- Select the next tool action.
- Inspect previous observations.
- Match failures against predefined proposals.
- Execute the selected tool.
- Record actions and observations.
- Enforce the action budget.
- Stop when the task succeeds or cannot proceed.

### 3.4 Workspace and Proposals

The workspace contains the code and tests being repaired.

The proposal file contains predefined repair instructions. Each proposal specifies:

- Target file.
- Failure marker.
- Expected existing text.
- Replacement text.

The planner uses these proposals to determine which repair action to execute.

---

## 4. Project Structure

```text
coding-agent/
│
├── src/
│   ├── __init__.py
│   ├── file_tools.py
│   └── agent.py
│
├── tests/
│   ├── test_file_tools.py
│   ├── test_patching.py
│   ├── test_runner.py
│   └── test_agent.py
│
├── workspace/
│   ├── basket.py
│   ├── proposals.json
│   └── tests/
│       └── test_basket.py
│
├── main.py
├── README.md
└── .gitignore
```

### Directory responsibilities

| Component | Responsibility |
|---|---|
| `src/file_tools.py` | Workspace validation, file reading, patching and test execution |
| `src/agent.py` | Planner, tool execution and agent loop |
| `tests/` | Tests for the agent infrastructure |
| `workspace/` | Example project being repaired |
| `workspace/tests/` | Tests executed by the agent |
| `workspace/proposals.json` | Predefined repair proposals |
| `main.py` | Entry point for running the example agent |

---

## 5. Key Implementation Details

### 5.1 Workspace Confinement

One of the first problems addressed is preventing the agent from accessing files outside its designated workspace.

A user or planner might request a path such as:

```text
../../etc/passwd
```

Allowing arbitrary paths would let the file tools access unrelated files on the machine.

The implementation resolves the requested path against the trusted workspace and verifies that the resulting path remains inside it.

The central operation is:

```python
resolved_path = (workspace / requested_path).resolve(strict=True)
```

After resolving the path, the implementation checks:

```python
if not resolved_path.is_relative_to(workspace):
    raise ValueError("Access outside workspace is not allowed")
```

This is important because checking string prefixes is insufficient.

For example:

```text
/workspace/project
/workspace/project-backup
```

The second path starts with the same characters as the first but is not inside it.

Using path-component-aware containment avoids this mistake.

The implementation also checks that:

- The workspace exists and is a directory.
- The requested path is not absolute.
- The target exists.
- The target is a regular file.
- Symlinks do not resolve outside the workspace.

**Security boundary:** This protects the file tools against common path traversal and symlink escape attempts. It is not a complete operating-system sandbox and does not prevent time-of-check/time-of-use races involving concurrent filesystem changes.

### 5.2 Exact-Match Patching

The agent must not blindly overwrite source code.

Consider this patch:

```python
old_text = "price + quantity"
new_text = "price * quantity"
```

Before modifying the file, the implementation counts occurrences of the old text:

```python
occurrences = original_content.count(old_text)

if occurrences != 1:
    raise ValueError(
        f"Patch rejected: expected exactly 1 occurrence, found {occurrences}"
    )
```

There are three possible outcomes:

| Occurrences | Behavior |
|---|---|
| 0 | Reject because the expected source text does not exist |
| 1 | Apply the patch |
| More than 1 | Reject because the replacement is ambiguous |

This prevents accidental modifications to multiple locations.

It also provides a basic stale-patch check. If the source code has changed since a proposal was created, the patch will be rejected rather than applied to an unexpected version of the file.

### 5.3 Atomic File Replacement

A patch should not leave a partially written source file if writing fails.

The implementation therefore uses a temporary file in the same directory as the original file.

The process is:

1. Read the original file.
2. Validate that the old text occurs exactly once.
3. Generate the updated content.
4. Capture the original permission bits.
5. Write the new content to a temporary file.
6. Flush the file and call `fsync`.
7. Restore the original permission bits.
8. Replace the original file using `os.replace`.
9. Remove the temporary file if it still exists.

The important operation is:

```python
os.replace(temp_path, target_path)
```

When the temporary file and destination are on the same filesystem, this provides atomic replacement semantics.

The original file is therefore not exposed to an intermediate partially written state.

The implementation also uses a `finally` block to clean up temporary files after failures.

**Important distinction:** Atomic replacement protects against partial replacement visibility. It does not by itself guarantee complete crash durability or protect against concurrent writers.

### 5.4 Controlled Test Execution

The test runner does not accept arbitrary shell commands from the planner.

Instead, it constructs a fixed command:

```python
command = [
    sys.executable,
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-v",
]
```

This has several advantages:

- Uses the currently active Python interpreter.
- Avoids shell command construction.
- Restricts the operation to unittest discovery.
- Keeps command selection under application control.

The subprocess is started with:

```python
process = subprocess.Popen(
    command,
    cwd=str(workspace),
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    start_new_session=(os.name == "posix"),
)
```

The runner captures output and waits for completion with a timeout:

```python
stdout, stderr = process.communicate(timeout=timeout)
```

If the deadline expires, it terminates the process group on POSIX systems.

This is important because a test process may create child processes. Killing only the parent may leave those children running.

### 5.5 Validating Test Results

A successful process exit code alone is not enough to establish that the test suite worked.

For example, a test discovery operation that executes zero tests could exit successfully.

The runner therefore checks the unittest summary in standard error:

```text
Ran 2 tests in 0.001s

OK
```

It validates that:

- Exactly one valid test summary exists.
- At least one test ran.
- No tests were skipped.
- The process returned a successful exit code.
- The output contains the expected successful unittest result.

The runner distinguishes between two types of outcomes:

**Normal test failure:** Returns a structured failure observation so the planner can inspect the failure and decide what to do.

**Execution or validation failure:** Raises an exception for situations such as timeouts, malformed test output, zero executed tests, or skipped tests.

This distinction is important for agentic systems. An ordinary failed test is useful feedback, not necessarily a reason to terminate the entire agent.

---

## 6. Agent Loop and Decision-Making

The core implementation is in `src/agent.py`.

The agent coordinates two tools:

```python
ALLOWED_TOOLS = {"run_tests", "apply_patch"}
```

The planner generates an action, and the tool executor performs it.

The agent then records the observation and uses it to determine the next action.

### 6.1 Planner

The planner follows deterministic rules.

Its behavior is:

**Initial state**

If no observations exist, execute the test suite.

**After a test failure**

Inspect the test output and search for a failure marker matching one of the supplied proposals.

If a proposal matches, generate an `apply_patch` action.

If no proposal matches, abstain.

**After a successful patch**

Execute the tests again.

**After successful tests**

Stop immediately.

This makes the decision process explicit and reproducible.

### 6.2 Tool Execution

The tool executor receives an action and determines which supported tool should execute.

For example:

```python
{"tool": "run_tests"}
```

or:

```python
{
    "tool": "apply_patch",
    "path": "basket.py",
    "old_text": "price + quantity",
    "new_text": "price * quantity"
}
```

The executor validates the tool name and required arguments before invoking the corresponding implementation.

It does not provide an arbitrary shell-execution tool.

### 6.3 Action Budget

The agent uses a finite action budget to prevent uncontrolled execution.

For example:

```python
action_budget = 4
```

Every tool action consumes one unit.

A possible execution is:

| Step | Action | Remaining budget |
|---|---|---:|
| 1 | Run tests | 3 |
| 2 | Apply patch | 2 |
| 3 | Run tests again | 1 |

The agent stops immediately after successful verification, even though one action remains.

If the budget is exhausted before success, the agent stops with:

```text
action_budget_exhausted
```

This is a basic form of execution control and resource governance.

### 6.4 Stop Conditions

The current implementation supports several stop conditions:

| Stop reason | Meaning |
|---|---|
| `tests_passed` | Tests passed after execution |
| `planner_abstained` | No matching proposal was found |
| `invalid_tool_call` | The requested tool action was invalid |
| `tool_execution_failed` | A tool encountered an execution error |
| `action_budget_exhausted` | The action limit was reached |

The agent returns an execution trace containing each action and its corresponding observation.

---

## 7. Execution Trace

The trace is an important part of the implementation.

It records what the agent attempted and what happened after each action.

A successful execution produces a result conceptually similar to:

```json
{
    "success": true,
    "actions_used": 3,
    "action_budget": 4,
    "stop_reason": "tests_passed",
    "trace": [
        {
            "action": {
                "tool": "run_tests"
            },
            "observation": {
                "tool": "run_tests",
                "success": false,
                "tests_run": 2
            }
        },
        {
            "action": {
                "tool": "apply_patch",
                "path": "basket.py",
                "old_text": "price + quantity",
                "new_text": "price * quantity"
            },
            "observation": {
                "tool": "apply_patch",
                "success": true
            }
        },
        {
            "action": {
                "tool": "run_tests"
            },
            "observation": {
                "tool": "run_tests",
                "success": true,
                "tests_run": 2
            }
        }
    ]
}
```

The actual trace also includes test output, errors, and return codes.

This is useful for:

- Debugging.
- Understanding the agent's decisions.
- Auditing tool execution.
- Reproducing failures.
- Evaluating planner behavior.

---

## 8. Example Workspace

The example project is intentionally small so that the agent's behavior can be understood clearly.

### Source file

`workspace/basket.py`

```python
def calculate_total(price, quantity):
    return price + quantity
```

### Test file

`workspace/tests/test_basket.py`

```python
import unittest
from basket import calculate_total


class TestBasket(unittest.TestCase):

    def test_calculate_total(self):
        self.assertEqual(calculate_total(7, 3), 21)

    def test_zero_quantity(self):
        self.assertEqual(calculate_total(7, 0), 0)
```

### Repair proposal

`workspace/proposals.json`

```json
[
    {
        "path": "basket.py",
        "failure_marker": "AssertionError",
        "old_text": "price + quantity",
        "new_text": "price * quantity"
    }
]
```

The proposal is selected only when the observed failure output contains its configured failure marker.

The patch is then applied only if the expected old text appears exactly once.

---

## 9. Running the Project

### Prerequisites

- Python 3.10 or later is recommended.
- No external Python packages are required by the current implementation.
- The project uses Python's standard library, including:
  - `pathlib`
  - `subprocess`
  - `tempfile`
  - `os`
  - `stat`
  - `signal`
  - `unittest`
  - `json`
  - `re`

### Run the example agent

From the repository root:

```bash
python3 main.py
```

The example runs the agent against the local `workspace/` directory.

### Run the infrastructure test suite

```bash
python3 -m unittest discover -s tests -v
```

This executes the tests for:

- Workspace confinement.
- File reading.
- Patch validation.
- Atomic replacement behavior.
- Test runner behavior.
- Agent decision-making.
- Action budget enforcement.
- Invalid tool handling.

These are the project's local tests, not an external official evaluator.

---

## 10. Testing Strategy

The project uses focused unit tests for individual components.

### Workspace tests

Verify that the file tools:

- Accept valid workspace files.
- Reject absolute paths.
- Reject parent-directory traversal.
- Reject nonexistent files.
- Reject directories.
- Reject symlink escapes.

### Patching tests

Verify that the patch mechanism:

- Applies valid replacements.
- Rejects missing old text.
- Rejects ambiguous replacements.
- Preserves file permissions.
- Cleans up temporary files.

### Test runner tests

Verify that the runner:

- Executes successful test suites.
- Rejects zero-test execution.
- Detects failed assertions.
- Rejects skipped tests.
- Enforces execution timeouts.

### Agent tests

Verify that the agent:

- Repairs a project when a matching proposal exists.
- Stops when the action budget is exhausted.
- Abstains when no failure marker matches.
- Rejects unsupported tool names.

The tests focus on both expected behavior and failure conditions.

---

## 11. Technology Choices

| Technology | Purpose |
|---|---|
| Python | Core implementation |
| `pathlib` | Path resolution and workspace validation |
| `subprocess` | Controlled test execution |
| `unittest` | Test discovery and execution |
| `tempfile` | Temporary files for patching |
| `os.replace` | Atomic file replacement |
| `json` | Repair proposals and structured output |
| `re` | Parsing unittest summaries |
| `signal` | Process-group termination on POSIX |

The project intentionally avoids external dependencies to keep the execution environment simple and make the underlying mechanisms explicit.

---

## 12. Scope and Limitations

It is important to understand what this project does and does not attempt to solve.

### What the project currently supports

- Workspace-relative file access.
- Basic path traversal and symlink escape protection.
- Safe file reading.
- Exact-match source-code replacement.
- Temporary-file-based atomic replacement.
- Permission-bit preservation.
- Controlled Python unittest execution.
- Test timeout enforcement.
- Structured test observations.
- Deterministic planning.
- Predefined repair selection.
- Finite action budgets.
- Execution trace generation.

### What it does not currently support

- Understanding arbitrary code semantics.
- Generating new fixes from natural-language instructions.
- General-purpose code generation.
- LLM-based reasoning.
- Dynamic repair proposal generation.
- Arbitrary shell command execution.
- Full operating-system sandboxing.
- Container isolation.
- Memory or CPU quotas.
- Concurrent-edit conflict resolution.
- Multi-file transactional changes.
- Git-based rollback or version control integration.
- General-purpose support for test frameworks other than the configured unittest workflow.

The current planner is deterministic. It matches known failure markers against predefined proposals; it does not independently diagnose every possible bug.

This distinction is intentional: the project establishes the tool-execution and feedback-loop foundation before introducing probabilistic planning.

---

## 13. Security Considerations

The project incorporates several basic defensive engineering practices.

**Path validation:** File operations are restricted to resolved paths inside the configured workspace.

**No arbitrary shell commands:** The planner can select only explicitly supported tools.

**Patch preconditions:** A modification is rejected unless the expected old text occurs exactly once.

**Atomic replacement:** Changes are written to a temporary file before replacing the original.

**Execution timeout:** Test execution is subject to a finite deadline.

**Process-group termination:** On POSIX systems, timeout handling attempts to terminate child processes as well as the main test process.

However, this is not a secure execution environment for hostile code.

Tests execute as subprocesses with the same operating-system privileges as the current user. Workspace confinement applies to the file tools, not to arbitrary code executed by the test runner.

A production-grade implementation would need stronger isolation, such as containers or OS-level sandboxing, along with CPU, memory, filesystem, network, and output restrictions.

---

## 14. Future Improvements

The current architecture provides a foundation for several extensions.

### 14.1 LLM-Based Planner

Replace the deterministic planner with an LLM that receives:

- Current source code.
- Test output.
- Previous observations.
- Available tool descriptions.
- Remaining action budget.

The LLM could propose a typed action, while the existing tool executor continues to enforce validation and execution rules.

The important architectural principle is to keep reasoning separate from tool execution.

### 14.2 Structured Tool Schemas

Introduce strict schemas for every action.

For example:

```json
{
    "tool": "apply_patch",
    "path": "basket.py",
    "old_text": "price + quantity",
    "new_text": "price * quantity"
}
```

Validate required fields, types, allowed values, and unexpected fields before execution.

### 14.3 Better Patch Mechanisms

Extend exact-text patching to support:

- Unified diffs.
- Multiple controlled edits.
- Context-aware patches.
- File hashes and version checks.
- Rollback mechanisms.

### 14.4 Stronger Execution Isolation

Execute untrusted tests inside an isolated environment.

Potential improvements include:

- Docker or another container runtime.
- CPU and memory limits.
- Restricted filesystem mounts.
- Network restrictions.
- Output-size limits.
- Non-root execution.

### 14.5 Git Integration

Introduce Git-based checkpoints before applying modifications.

This would make it easier to:

- Compare changes.
- Review generated patches.
- Roll back unsuccessful modifications.
- Preserve a history of agent actions.

### 14.6 Persistent Agent Memory

Store prior failures, successful repairs, and execution traces so that the agent can reuse relevant information across tasks.

### 14.7 Multiple Agent Roles

The architecture could be extended into separate components:

- Planner: determines the next action.
- Executor: invokes tools.
- Reviewer: evaluates proposed modifications.
- Verifier: checks test results and task completion.

These roles could operate through the same typed action and observation interface.

---

## 15. Interview Discussion: Key Engineering Concepts

The following concepts are particularly important when explaining the project.

### Why separate the planner from the tools?

The planner decides what should happen. The tools determine how an operation is performed.

Keeping these responsibilities separate means that the planner can eventually be replaced with an LLM without rewriting the file access, patching, and test execution infrastructure.

### Why return observations instead of only printing output?

An agent must use the result of an action to determine its next action.

A structured observation provides machine-readable information about success, failure, output, and execution details.

### Why use exact-match patches?

A patch should modify only the intended source location. Rejecting missing or ambiguous matches reduces the risk of unintended changes.

### Why use atomic replacement?

Directly writing to the original file can leave it partially written if an error occurs. Writing to a temporary file and replacing the original avoids exposing an intermediate partial file.

### Why validate the test summary?

A successful subprocess exit code does not necessarily prove that tests actually ran. Validating the test count and summary provides stronger evidence of execution.

### Why have an action budget?

An agent can otherwise continue taking actions indefinitely. A finite budget provides a simple upper bound on the number of tool invocations.

### Why is this not yet a fully autonomous coding agent?

The planner relies on predefined failure markers and repair proposals. It cannot independently understand arbitrary bugs or synthesize novel repairs. The current implementation demonstrates the infrastructure and control flow required for a more autonomous system.

---

## 16. Project Summary

Tiny Coding Agent demonstrates the core mechanics of a tool-using coding agent.

It combines workspace-constrained file operations, preconditioned source-code modifications, atomic file replacement, controlled test execution, deterministic planning, structured observations, and bounded execution.

The central design principle is that an agent should not directly perform unrestricted operations. It should reason about the next action, invoke a controlled tool, inspect the resulting observation, and decide whether another action is necessary.

The current implementation uses deterministic planning and predefined repairs, providing a transparent foundation for future LLM-based coding agents.

**Core takeaway:** This project is not primarily about fixing one Python function. It is about implementing the controlled execution loop that allows an agent to inspect a software project, take actions through tools, observe the consequences, and verify whether its objective has been achieved.