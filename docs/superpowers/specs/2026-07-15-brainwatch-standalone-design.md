# Brainwatch Standalone Design

**Date:** 2026-07-15
**Status:** Approved
**Owner:** KJ5IRQ
**Initial version:** 0.1.0
**Repository visibility:** Private
**License:** MIT

## Purpose

Brainwatch is a local command-line watchdog for free large-language-model endpoints. It discovers or reads configured models, sends tiny bounded probes, records availability and latency, ranks models using current and historical evidence, and proposes a resilient model chain without silently spending money.

The standalone repository must be safe to share with technical friends. It must contain no LEO, HAG, Operation Lifeline, private infrastructure, live operational records, credentials, hostnames, usernames, or historical provider responses.

## Product Positioning

**Why this matters:** Advertised free model endpoints frequently disappear, time out, return malformed responses, or quietly stop being free. Brainwatch replaces catalog trust with measured evidence.

**Who it is for:** Technical users running local agents, OpenClaw, scripts, or other LLM tooling who depend on free OpenRouter or OpenAI-compatible endpoints and need a bounded, auditable health check.

**Demonstration:**

1. Configure OpenRouter and a local or remote OpenAI-compatible provider.
2. Run `brainwatch health`.
3. See which models actually returned the expected structured response, how long they took, and which zero-cost fallback chain Brainwatch recommends.
4. Run `brainwatch trend` later to distinguish transient failures from persistently unreliable models.

## Scope

Version 0.1.0 includes:

- OpenRouter model discovery and exact-zero-price enforcement.
- Configurable OpenAI-compatible providers.
- Explicit free-model allowlists for providers that do not publish trustworthy pricing.
- Provider-independent model normalization, probing, ranking, ledgers, and reports.
- A local CLI with `providers`, `health`, `status`, `trend`, `chain`, and optional OpenClaw integration commands.
- Generic user-level systemd scheduling.
- Packaging, CI, tests, security documentation, synthetic examples, and installation smoke tests.

Version 0.1.0 excludes:

- Paid model probing or a nonzero spending cap.
- A web dashboard or hosted service.
- PyPI publication.
- Automatic support for agent frameworks other than the explicit OpenClaw integration.
- Public GitHub visibility.
- Automatic friend invitations without GitHub usernames supplied by the owner.

## Trust Boundaries and Threat Model

### Assets

- Provider API keys.
- User configuration.
- Model availability and latency history.
- Optional OpenClaw configuration.
- The guarantee that unknown-cost remote models are not probed.

### External inputs

- Provider catalog responses.
- Chat completion responses.
- Provider URLs and model IDs from user configuration.
- Existing OpenClaw JSON configuration.
- Environment variables containing credentials.

### Required controls

- Credentials are read from environment variables only and are never serialized.
- Remote provider URLs require HTTPS. HTTP is accepted only for loopback hosts.
- Provider responses are treated as untrusted data.
- Response bodies and errors are bounded, truncated, and secret-redacted before recording.
- Requests have connection, read, and wall-clock limits.
- Retries are bounded and limited to transient failures.
- Model output is parsed as data only. It is never executed, interpolated into a shell command, or used as a file path.
- Unknown-cost remote models are refused unless their exact IDs are explicitly marked free in configuration.
- OpenRouter models are eligible only when both published prompt and completion prices parse to exactly zero.
- OpenClaw writes require an explicit path, `--yes`, a protected backup, JSON validation, and atomic replacement.

## Architecture

### Package layout

```text
src/brainwatch/
  __init__.py
  __main__.py
  cli.py
  config.py
  models.py
  storage.py
  ledger.py
  ranking.py
  reporting.py
  security.py
  providers/
    __init__.py
    base.py
    openrouter.py
    openai_compatible.py
  integrations/
    __init__.py
    openclaw.py
```

Tests mirror these responsibilities under `tests/`.

### Provider interface

Every provider adapter implements the same interface:

```python
class Provider(Protocol):
    name: str
    def discover_models(self) -> list[ModelCandidate]: ...
    def probe(self, candidate: ModelCandidate) -> ProbeRecord: ...
```

`ModelCandidate` carries a provider name, provider-native model ID, display name, context length, capability tags, pricing evidence, and whether zero cost has been verified.

`ProbeRecord` carries provider and model identity, timestamp, status, latency, bounded usage fields, response mode, retry count, recovery flag, HTTP status, and sanitized error information. It never carries request headers, credentials, or full response bodies.

### OpenRouter adapter

- Uses `https://openrouter.ai/api/v1/models` for discovery.
- Uses `https://openrouter.ai/api/v1/chat/completions` for probes.
- Reads `OPENROUTER_API_KEY` unless the provider configuration names a different environment variable.
- Accepts a model only when prompt and completion prices both parse to exactly zero.
- Filters to text-output models.

### Generic OpenAI-compatible adapter

Each configured provider has:

- A unique name.
- A base URL.
- An optional models path, defaulting to `/v1/models`.
- A chat-completions path, defaulting to `/v1/chat/completions`.
- The name of an environment variable containing its API key.
- An explicit list of model IDs authorized as free.
- Optional static model metadata when its catalog is incomplete.

Remote endpoints require HTTPS. Loopback addresses may use HTTP. A discovered model not present in the explicit free list is recorded as ineligible and is never probed.

### Configuration

Default configuration path:

```text
~/.config/brainwatch/config.toml
```

Override order, highest priority first:

1. CLI flags.
2. `BRAINWATCH_CONFIG` and `BRAINWATCH_HOME`.
3. TOML configuration.
4. Platform defaults.

Configuration stores environment-variable names, not credential values.

A committed `config.example.toml` demonstrates OpenRouter, a local server, and a remote OpenAI-compatible server using fictitious endpoints and model IDs.

### Runtime storage

Default runtime root:

```text
~/.local/share/brainwatch/
```

The root contains:

```text
ledger/availability.jsonl
ledger/usage.jsonl
reports/latest.json
reports/status.txt
reports/trend.txt
reports/proposed-chain.json
backups/
```

`BRAINWATCH_HOME` or `--data-dir` overrides the root. Importing the package must not create directories. Directories are created only when a command writes data.

### Core workflow

`brainwatch health`:

1. Load and validate configuration.
2. Select all providers or the requested provider.
3. Discover and normalize candidates.
4. Refuse unverified-cost candidates before any chat request.
5. Probe eligible candidates with bounded concurrency and timeouts.
6. Append sanitized availability and usage records.
7. Calculate stability from historical evidence.
8. Rank successful models.
9. Write machine-readable and human-readable reports atomically.
10. Exit zero when at least one eligible model passes; exit two when no usable chain remains; exit one for configuration or internal errors.

A provider failure does not abort other providers. The final report distinguishes discovery failure, authentication failure, timeout, malformed response, HTTP failure, and spend-guard refusal.

### Ranking

Ranking remains deterministic and provider-independent. It uses:

- Successful structured-output parsing.
- Latency.
- Context length.
- Capability tags.
- Response mode.
- Historical pass rate.
- Current failure streak.

A model that failed every recorded probe is excluded even if a single current response appears successful. A transient failure is penalized but does not automatically remove a historically reliable model.

### CLI

```text
brainwatch providers
brainwatch health [--provider NAME] [--top N] [--retain N] [--data-dir PATH]
brainwatch status [--data-dir PATH]
brainwatch trend [--data-dir PATH]
brainwatch chain [--format json|openclaw] [--data-dir PATH]
brainwatch openclaw status --config PATH [--data-dir PATH]
brainwatch openclaw apply --config PATH --yes [--data-dir PATH]
```

CLI output uses neutral terms such as provider, model, chain, healthy, degraded, unavailable, and refused. It contains no LEO, HAG, military-operation, or tonight-specific language.

### OpenClaw integration

OpenClaw support is an optional adapter over Brainwatch’s proposed chain.

- `status` compares a specified OpenClaw primary/fallback chain with current Brainwatch evidence.
- `apply` converts provider/model IDs to OpenClaw model references, writes a mode-0600 timestamped backup, validates the new JSON, and atomically replaces the specified configuration.
- No default OpenClaw path is assumed.
- No write occurs without `--yes`.
- Rollback instructions are documented and tested against temporary fixtures.

## Packaging and Tooling

- PEP 517 build using `hatchling`.
- `src/` layout.
- Runtime dependency: `requests` with a bounded compatible version range.
- Development extras: `pytest`, `pytest-cov`, `ruff`, `build`, and `twine`.
- Console entry point: `brainwatch = brainwatch.cli:main`.
- Python support: 3.11, 3.12, and 3.13.
- Version source: `src/brainwatch/__init__.py`.

## Scheduling

The repository provides a user-level systemd service and timer:

- `%h` paths rather than `/root` or a named user.
- Optional environment file under `%h/.config/brainwatch/brainwatch.env`.
- `NoNewPrivileges=true`, `UMask=0077`, bounded service timeout, and non-overlap locking.
- Default cadence every six hours after a five-minute boot delay.
- Scheduling is optional. Manual CLI use remains fully supported.

## Repository Contents

```text
.github/workflows/ci.yml
.github/dependabot.yml
.gitignore
.env.example
LICENSE
README.md
CHANGELOG.md
CONTRIBUTING.md
SECURITY.md
config.example.toml
pyproject.toml
src/brainwatch/...
tests/...
docs/configuration.md
docs/providers.md
docs/openclaw.md
docs/scheduling.md
deploy/systemd/...
examples/ledger/...
examples/reports/...
```

All example records are synthetic and marked as such.

## Verification Requirements

Before the first push:

- Existing behavior retained where provider-independent.
- New tests are written before each behavior change and observed failing for the expected reason.
- Unit and integration tests pass on the working Python version.
- CI matrix covers Python 3.11, 3.12, and 3.13.
- Ruff reports no errors.
- Source distribution and wheel build successfully.
- Wheel installs in a clean virtual environment.
- Installed `brainwatch --help`, `brainwatch providers`, and an offline fixture-based command execute successfully.
- `twine check` passes.
- Secret scan covers files and git history.
- Synthetic examples parse as JSON/JSONL.
- Shipping source, user documentation, examples, and deployment artifacts contain none of the forbidden internal terms or operational identifiers. This historical design record may name them only to define the sanitization boundary.
- Local commit and GitHub `main` commit match after push.

## Sharing Model

The repository is private. Friends can access it only after the owner adds their GitHub usernames as collaborators. The README will explain cloning and installation after access is granted. Making it public is a separate future decision after the owner reviews the repository and license implications.
