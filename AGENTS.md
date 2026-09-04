# Environment
`devenv` is used to manage the environment, and project "tasks".
The `devenv shell` is already active, there's no need for `devenv shell {command}`.
List tasks: `devenv --no-tui --quiet tasks list`
Run a task: `devenv --no-tui --quiet tasks run publish:clean 2>&1 >/dev/null`

# Coding
Never use recursion.

## Type Annotations
Prefer type inference to explicit annotations.
When a concrete type is assigned to a variable, do not annotate the type.

# Testing
Mirror the structure of the library in tests. E.g.: place all `concurrent_iterator.thread` tests in `tests.test_thread`.

List possible tests: `devenv --no-tui --quiet tasks list | rg test:`
Run one test: `devenv --no-tui --quiet tasks run test:py314`
Run all tests, checkers, and linters: `devenv --no-tui test 2>&1 | rg -v ' in \d| ignoring ' ; echo EXITS:${PIPESTATUS[0]}` (Do not truncate output)

## Efficiency
`devenv test` runs git-hooks plus tests for several interpreters.
1. Baseline: all tests once at start to capture pre-existing state.
2. Iterate fast: type-only change → `mypy` first; otherwise single interpreter, `test:py314`; single failure → that one `unittest` in isolation.
3. Verify: all tests once at the end to double-check.

## TDD
Use TDD cycle while developing:
1. Write one new test at a time.
2. Run tests and it must fail. Failure is not an error on a missing piece of the interface, but an actual failure about the missing/incorrect logic.
3. Implement simplest fix
4. Run tests and it must pass.
5. Refactor.

Be explicit about each step. Add in todowrite each step for each test.

Finally, make double-check that the wanted functionality was completely implemented.

## Tests
Organize tests into 3 paragraphs: setup, execution, assertions.
Assign the type being tested to variable `subject`.
Name tests using BDD-like style. E.g. `test_when_{escenario}_then_it_{expected outcome}`.

# Documentation
## Docstrings
Do not add redundant information. E.g. if a function has type annotations, do not document the same information.
Type annotations are better than documentation, when containing the same info.
