# Contributing

## Development setup

```bash
git clone https://github.com/KJ5IRQ/brainwatch.git
cd brainwatch
uv sync --extra dev
uv run pytest -q
```

Python 3.11 or newer is required.

## Change process

1. Open or identify a focused issue.
2. Add a failing test that demonstrates the required behavior.
3. Make the smallest implementation change that passes the test.
4. Run the focused test, full suite, Ruff, and a package build.
5. Update user documentation when commands, configuration, or evidence schemas
   change.

Required local checks:

```bash
uv run ruff check src tests
uv run pytest -q
uv build
```

## Provider changes

Provider changes require tests for:

- the exact zero-cost eligibility rule;
- unknown-cost refusal before a chat request;
- authentication and timeout behavior;
- malformed catalog and completion responses;
- secret redaction;
- provider isolation.

Never classify a model as free from its name alone.

## Security-sensitive changes

OpenClaw writes, credential handling, URL validation, file permissions, and ledger
serialization are security-sensitive. Include negative tests and preserve fail-closed
behavior.

## Repository hygiene

Do not commit:

- API keys, tokens, cookies, or private environment files;
- live ledgers or provider responses;
- hostnames, usernames, or machine-specific paths;
- generated wheels, virtual environments, coverage data, or runtime state.

Use only fabricated evidence in examples and tests.

## Style

- Keep modules small and typed.
- Prefer standard-library code when it is clear and auditable.
- Bound network waits and stored error text.
- Use provider-qualified model identities.
- Explain operator-facing failure modes plainly.
