# Build `greet`, a tiny greeting command-line application

Deliver a small but clean Python 3.14 CLI called `greet` in the current
repository. A scripted evaluation will run the exact commands below.

## Command contract (exact)

1. `greet --name World` prints exactly `Hello, World!` on stdout; exit code 0.
2. `greet --name ""` (empty or whitespace-only name) prints a clear message on
   stderr and exits with code 2.
3. `greet --name World --shout` prints `HELLO, WORLD!`; exit code 0.

## Engineering requirements

- Python 3.14, project managed with `uv` (`pyproject.toml`); expose the CLI as
  a console script named `greet` so `uv run greet …` works from the repository
  root.
- A small automated test suite runnable with `uv run pytest` must pass.
