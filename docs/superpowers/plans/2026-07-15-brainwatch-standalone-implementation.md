# Brainwatch Standalone Implementation Plan

> **Execution mode:** Subagent-assisted development in this session. The lead implements against the approved design; independent agents review security, packaging, and usability. Every behavior change follows red-green-refactor and every completion claim requires fresh verification.

**Goal:** Turn the internal Brainwatch experiment into a clean, installable, multi-provider private repository that can be shared without exposing private infrastructure or weakening the zero-spend guarantee.

**Architecture:** A `src/brainwatch` Python package with provider adapters, normalized data models, provider-independent ranking/reporting, XDG configuration and storage, and an optional explicit OpenClaw integration. OpenRouter verifies zero pricing from its catalog. Generic OpenAI-compatible providers probe only model IDs explicitly marked free.

**Tech stack:** Python 3.11+, requests, hatchling, pytest, pytest-cov, ruff, build, twine, GitHub Actions, user-level systemd.

**Approved design:** `docs/superpowers/specs/2026-07-15-brainwatch-standalone-design.md`

---

## Task 1: Scaffold the distributable package

**Files:**
- Create: `pyproject.toml`
- Create: `src/brainwatch/__init__.py`
- Create: `src/brainwatch/__main__.py`
- Create: `src/brainwatch/cli.py`
- Create: `tests/test_cli.py`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `LICENSE`

**Step 1: Write the failing console-entry test**

Create `tests/test_cli.py` asserting that `brainwatch.cli.main(["--version"])` returns zero and prints `brainwatch 0.1.0`, while `main(["--help"])` exits cleanly.

**Step 2: Run the focused test and observe the import failure**

Run: `uv run --extra dev pytest tests/test_cli.py -q`
Expected: FAIL because `brainwatch` is not installed.

**Step 3: Add packaging and the minimum CLI**

Use hatchling with a `src/` layout, Python `>=3.11`, `requests>=2.31,<3`, a `dev` extra containing pytest, pytest-cov, ruff, build, and twine, and the console entry point `brainwatch = brainwatch.cli:main`.

`main(argv=None)` must parse `--version`, expose subparser placeholders without network access, and return integer exit codes. `__main__.py` must raise `SystemExit(main())`.

**Step 4: Run the focused test**

Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml src tests/test_cli.py .gitignore .env.example LICENSE
git commit -m "build: scaffold installable Brainwatch package"
```

## Task 2: Add validated configuration, paths, and security primitives

**Files:**
- Create: `src/brainwatch/config.py`
- Create: `src/brainwatch/storage.py`
- Create: `src/brainwatch/security.py`
- Create: `src/brainwatch/models.py`
- Create: `tests/test_config.py`
- Create: `tests/test_security.py`
- Create: `tests/test_storage.py`
- Create: `config.example.toml`

**Step 1: Write failing tests**

Cover:
- XDG defaults without creating directories on import.
- `BRAINWATCH_CONFIG` and `BRAINWATCH_HOME` overrides.
- TOML loading for one OpenRouter provider and multiple generic providers.
- Duplicate provider names, missing `base_url`, missing `api_key_env`, and an empty explicit free list rejected with clear `ConfigError` messages.
- HTTP remote base URLs rejected; HTTP loopback accepted; HTTPS remote accepted.
- `redact_text` removes bearer tokens and configured secret values and truncates output.
- Atomic text writes and mode-0600 protected writes.
- Frozen normalized `ModelCandidate` and `ProbeRecord` dataclasses serialize without credentials or headers.

**Step 2: Run focused tests and observe failures**

Run: `uv run --extra dev pytest tests/test_config.py tests/test_security.py tests/test_storage.py -q`
Expected: FAIL due to missing modules.

**Step 3: Implement the minimum behavior**

Key interfaces:

```python
@dataclass(frozen=True)
class ProviderConfig:
    name: str
    kind: Literal["openrouter", "openai-compatible"]
    base_url: str
    api_key_env: str
    models_path: str
    chat_path: str
    free_models: tuple[str, ...]

@dataclass(frozen=True)
class Settings:
    config_path: Path
    data_dir: Path
    providers: tuple[ProviderConfig, ...]
    request_timeout_seconds: float
    overall_timeout_seconds: float
    max_workers: int
```

`load_settings(path=None, data_dir=None, environ=None)` loads TOML with `tomllib`. OpenRouter defaults may be supplied when explicitly configured, but no provider is silently enabled.

`validate_base_url` permits HTTPS or loopback HTTP only. `get_secret(env_name, environ=None)` raises a named error without displaying values. `redact_text` recognizes bearer tokens and OpenAI/OpenRouter-style keys.

`StoragePaths.from_root(root)` returns ledger, report, and backup paths. `ensure_writable_dirs()` creates them only at command execution time.

**Step 4: Run focused tests and lint changed files**

Expected: PASS.

**Step 5: Commit**

```bash
git add src/brainwatch tests config.example.toml
git commit -m "feat: add safe configuration and storage"
```

## Task 3: Implement provider adapters and the zero-spend gate

**Files:**
- Create: `src/brainwatch/providers/__init__.py`
- Create: `src/brainwatch/providers/base.py`
- Create: `src/brainwatch/providers/openrouter.py`
- Create: `src/brainwatch/providers/openai_compatible.py`
- Create: `src/brainwatch/providers/probe.py`
- Create: `tests/test_openrouter_provider.py`
- Create: `tests/test_openai_compatible_provider.py`
- Create: `tests/test_probe.py`

**Step 1: Write failing adapter tests**

Cover:
- OpenRouter catalog normalization.
- Exact-zero prompt and completion pricing required.
- Missing or malformed pricing refused.
- Non-text output models excluded.
- Generic providers discover models but mark only exact configured IDs eligible.
- Unknown remote models never trigger a chat request.
- A configured free model sends a bounded JSON probe with a bearer token from the named environment variable.
- Local HTTP providers are allowed but still require an explicit free model list.
- Normal content, reasoning-only content, and multipart text parsing.
- Non-JSON responses, 401, 402, 429, 5xx, timeouts, and connection failures mapped to stable statuses.
- One retry only for timeout, 429, and 5xx.
- Error text redacted and bounded.
- Provider URL joining cannot escape the configured origin.

**Step 2: Run the focused tests and observe failures**

Expected: FAIL due to missing provider modules.

**Step 3: Implement the protocol and adapters**

```python
class Provider(Protocol):
    name: str
    def discover_models(self) -> list[ModelCandidate]: ...
    def probe(self, candidate: ModelCandidate) -> ProbeRecord: ...
```

Use a shared `requests.Session`, tuple connect/read timeouts, a small structured-output prompt, and bounded response extraction. Never persist raw headers or full bodies.

`OpenRouterProvider.discover_models()` uses catalog prices to set `cost_verified=True` only when both prices are exactly zero. `OpenAICompatibleProvider.discover_models()` sets `cost_verified=True` only for exact IDs in `free_models`.

`probe_candidate(provider, candidate)` must return `refused_unverified_cost` before calling `provider.probe` when cost is not verified.

**Step 4: Run focused tests and lint**

Expected: PASS.

**Step 5: Commit**

```bash
git add src/brainwatch/providers tests/test_*provider.py tests/test_probe.py
git commit -m "feat: add guarded multi-provider probing"
```

## Task 4: Port ledgers, trends, ranking, and reports to normalized identities

**Files:**
- Create: `src/brainwatch/ledger.py`
- Create: `src/brainwatch/trend.py`
- Create: `src/brainwatch/ranking.py`
- Create: `src/brainwatch/reporting.py`
- Create: `tests/test_ledger.py`
- Create: `tests/test_trend.py`
- Create: `tests/test_ranking.py`
- Create: `tests/test_reporting.py`

**Step 1: Write failing tests**

Cover:
- JSONL append strips secret-shaped fields.
- Retention keeps the newest records and rewrites atomically.
- Stability keys use `provider:model`, avoiding collisions between providers.
- Stable models outrank equally fast flaky models.
- Persistently failed models are excluded from chains.
- Provider failures appear in reports without aborting successful providers.
- Latest JSON and human status are written atomically.
- Reports use neutral wording and contain no internal experiment terms.
- No-passing-model reports explain that unverified or paid models were not used.
- Proposed chain entries preserve provider and native model IDs.

**Step 2: Run focused tests and observe failures**

Expected: FAIL due to missing modules.

**Step 3: Implement provider-independent evidence processing**

Use `model_key = f"{provider}:{model_id}"` consistently. Keep ranking weights explicit. Reports include `generated_at`, provider summaries, candidate counts, pass/fail/refusal counts, zero-spend policy, proposed chain, and sanitized results.

**Step 4: Run focused tests and lint**

Expected: PASS.

**Step 5: Commit**

```bash
git add src/brainwatch/{ledger,trend,ranking,reporting}.py tests/test_{ledger,trend,ranking,reporting}.py
git commit -m "feat: add provider-neutral evidence and ranking"
```

## Task 5: Build the health orchestration and complete CLI

**Files:**
- Create: `src/brainwatch/health.py`
- Modify: `src/brainwatch/cli.py`
- Modify: `tests/test_cli.py`
- Create: `tests/test_health.py`
- Create: `tests/fixtures/`

**Step 1: Write failing orchestration tests**

Cover:
- One provider discovery failure does not stop another provider.
- `--provider` selects exactly one configured provider.
- Bounded worker count.
- All ineligible models produce exit code 2 and no chat calls.
- At least one passing eligible model produces exit code 0.
- Configuration/internal errors produce exit code 1.
- `providers`, `health`, `status`, `trend`, and `chain` work against temporary fixtures.
- `--json` output is parseable and stderr contains diagnostics only.
- Missing API environment variable names the variable but never a value.

**Step 2: Run focused tests and observe failures**

Expected: FAIL.

**Step 3: Implement orchestration**

`run_health(settings, provider_names=None, top=3, retain=None)` creates storage directories, instantiates adapters through a provider factory, discovers independently, filters before probing, probes with a bounded `ThreadPoolExecutor`, records evidence, computes stability, ranks results, and writes reports.

CLI commands must remain import-safe and return integer codes rather than calling `sys.exit` internally.

**Step 4: Run all tests and lint**

Expected: PASS.

**Step 5: Commit**

```bash
git add src/brainwatch tests
git commit -m "feat: add health workflow and complete CLI"
```

## Task 6: Add explicit, reversible OpenClaw integration

**Files:**
- Create: `src/brainwatch/integrations/__init__.py`
- Create: `src/brainwatch/integrations/openclaw.py`
- Modify: `src/brainwatch/cli.py`
- Create: `tests/test_openclaw_integration.py`

**Step 1: Write failing safety tests**

Cover:
- Missing `--config` rejected.
- Apply without `--yes` rejected before file access.
- Empty chain rejected.
- Provider/model references map deterministically to OpenClaw IDs.
- Unknown config shapes rejected instead of falling back to unrelated keys.
- Backup created beside Brainwatch state with mode 0600.
- Invalid backup refused during rollback.
- Apply preserves unrelated JSON, validates output, writes atomically, and returns the backup path.
- Status compares current OpenClaw chain with normalized latest evidence.

**Step 2: Run focused test and observe failures**

Expected: FAIL.

**Step 3: Implement the integration**

Expose pure helpers for mapping, validation, status, backup, apply, and rollback. Require `agents.defaults.model` to be a dictionary with a string primary and list fallbacks. Do not guess alternate schemas.

**Step 4: Run focused and full tests**

Expected: PASS.

**Step 5: Commit**

```bash
git add src/brainwatch/integrations src/brainwatch/cli.py tests/test_openclaw_integration.py
git commit -m "feat: add gated OpenClaw integration"
```

## Task 7: Add deployment templates, examples, and friend-facing documentation

**Files:**
- Create: `README.md`
- Create: `CHANGELOG.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `docs/configuration.md`
- Create: `docs/providers.md`
- Create: `docs/openclaw.md`
- Create: `docs/scheduling.md`
- Create: `deploy/systemd/brainwatch.service`
- Create: `deploy/systemd/brainwatch.timer`
- Create: `deploy/systemd/brainwatch.env.example`
- Create: `examples/ledger/availability.jsonl`
- Create: `examples/ledger/usage.jsonl`
- Create: `examples/reports/latest.json`
- Create: `examples/reports/status.txt`
- Create: `tests/test_examples.py`
- Create: `tests/test_deployment.py`

**Step 1: Write failing artifact tests**

Cover:
- JSON and JSONL examples parse.
- Every example is marked synthetic.
- systemd units have no `/root`, usernames, private paths, or credential values.
- service uses `%h`, `UMask=0077`, `NoNewPrivileges=true`, a bounded timeout, and an environment file.
- timer runs every six hours and is persistent.
- shipping files contain no internal experiment terminology or private identifiers.
- README commands match actual CLI help.

**Step 2: Run artifact tests and observe failures**

Expected: FAIL because artifacts do not exist.

**Step 3: Write the artifacts**

README sections: purpose, zero-spend guarantee, quick start with `uv tool install` and `pipx`, configuration, provider examples, commands, output, scheduling, OpenClaw integration, privacy, limitations, sharing a private repository, and development.

The systemd service runs `%h/.local/bin/brainwatch health --retain 2000`, reads `%h/.config/brainwatch/brainwatch.env`, uses a runtime lock, and has a five-minute timeout. The timer starts five minutes after boot and every six hours thereafter.

**Step 4: Run artifact tests, all tests, and lint**

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md CHANGELOG.md CONTRIBUTING.md SECURITY.md docs deploy examples tests
git commit -m "docs: add secure deployment and sharing guide"
```

## Task 8: Add CI and perform release-grade verification

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/dependabot.yml`
- Create: `scripts/check-sanitization.py`
- Modify: `pyproject.toml`

**Step 1: Write the sanitization checker and its tests**

The checker scans tracked shipping files for credential patterns, private absolute paths, host/IP patterns, operational identifiers, and forbidden internal terminology while excluding the historical design/plan records that define the boundary.

**Step 2: Add CI**

CI matrix: Python 3.11, 3.12, 3.13. Each run installs the `dev` extra, runs Ruff and pytest. A packaging job builds sdist/wheel, runs `twine check`, installs the wheel in a clean venv, and smoke-tests `brainwatch --version`, `--help`, and `providers` with a synthetic config. A sanitization job runs the checker against tracked files.

**Step 3: Run local release verification**

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest -q
uv run pytest --cov=brainwatch --cov-report=term-missing
rm -rf dist build
uv run python -m build
uv run twine check dist/*
python3 -m venv /tmp/brainwatch-smoke
/tmp/brainwatch-smoke/bin/pip install dist/*.whl
/tmp/brainwatch-smoke/bin/brainwatch --version
/tmp/brainwatch-smoke/bin/brainwatch --help
BRAINWATCH_CONFIG="$PWD/config.example.toml" /tmp/brainwatch-smoke/bin/brainwatch providers
uv run python scripts/check-sanitization.py
```

Also parse all JSON/JSONL examples and run `git diff --check` plus `git status --short`.

**Step 4: Commit**

```bash
git add .github scripts pyproject.toml uv.lock
git commit -m "ci: verify tests packaging and sanitization"
```

## Task 9: Independent review and remediation

**Files:** All shipping files.

**Step 1: Dispatch independent reviewers**

- Security/privacy reviewer.
- Python packaging/API reviewer.
- Friend onboarding/documentation reviewer.

**Step 2: Verify every finding against source**

Fix confirmed high/medium issues with a failing regression test first. Reject incorrect findings with evidence.

**Step 3: Re-run the complete release verification**

Expected: all checks pass from a clean state.

**Step 4: Commit only if remediation changed files**

```bash
git add -A
git commit -m "fix: address standalone release review"
```

## Task 10: Create and verify the private GitHub repository

**Prerequisite:** Local verification is fully green and the worktree is clean.

**Step 1: Confirm the repository name is available**

Check `KJ5IRQ/brainwatch` through authenticated GitHub tooling.

**Step 2: Create the repository**

Create `KJ5IRQ/brainwatch` with private visibility. Do not auto-initialize because local history already exists.

**Step 3: Add the remote and push main**

```bash
git remote add origin https://github.com/KJ5IRQ/brainwatch.git
git push -u origin main
```

**Step 4: Verify remote state**

- Repository visibility is private.
- Default branch is `main`.
- Remote tree contains required files.
- Local HEAD equals `refs/heads/main` on GitHub.
- GitHub Actions workflow is visible; if a run has started, inspect its status and report truthfully without claiming success before completion.

**Step 5: Report sharing requirements**

Provide the repository link. Explain that private access requires each friend’s GitHub username; do not add collaborators without those identifiers.
