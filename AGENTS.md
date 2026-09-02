# Environment
`devenv` is used to manage the environment, and project "tasks".
The `devenv shell` is already active, there's no need for `devenv shell {command}`.
List tasks: `devenv --no-tui --quiet tasks list`
Run a task: `devenv --no-tui --quiet tasks run publish:clean 2>&1 >/dev/null`

# Coding
Never use recursion.

## Type Annotations
Prefer type inference to explicit annotations.
When a concrete type is assigned to a variable, don't annotate the type.

# Testing
Mirror the structure of the library in tests. E.g.: place all `concurrent_iterator.thread` tests in `tests.test_thread`.

List possible tests: `devenv --no-tui --quiet tasks list | rg test:`
Run one test: `devenv --no-tui --quiet tasks run test:py314`
Run all tests: `devenv --no-tui --quiet test`

Running all tests also runs linters, so run it frequently.

## TDD
Use TDD cycle while developing:
1. Write one new test at a time.
2. Run tests and it must fail. Failure is not an error on a missing piece of the interface, but an actual failure about the missing/incorrect logic.
3. Implement simplest fix
4. Run tests and it must pass.
5. Refactor.

Be explicit about each step. Add in todowrite each step for each test.

Finally, make double-check that the wanted functionality was completely implemented.
