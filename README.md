# Brainwatch

Brainwatch is a local, zero-spend model availability watchdog. It discovers models,
refuses unverified-cost remote models, runs a tiny structured-output probe against
eligible models, keeps JSONL evidence, and proposes a ranked fallback chain.

It supports:

- OpenRouter, using catalog pricing as the zero-cost proof.
- Generic OpenAI-compatible endpoints, using an explicit `free_models` allowlist.
- Optional, reversible OpenClaw model-chain updates.
- User-level systemd scheduling.

Brainwatch is a CLI, not a hosted service. Evidence and configuration stay on your
machine.

## Spend guarantee

Brainwatch probes only models with verified zero cost:

- OpenRouter models must advertise prompt price `0` and completion price `0`.
- Generic remote providers must list the exact model ID in `free_models`.
- Unknown, malformed, or nonzero pricing is refused before a chat request.
- Paid fallback behavior is not implemented.

Provider pricing and policies can change. Brainwatch rechecks OpenRouter pricing on
every discovery run. You remain responsible for the provider account you connect.

## Requirements

- Python 3.11 or newer
- A provider API key in an environment variable
- Linux, macOS, or Windows with a POSIX-like shell for the documented commands

## Install

Using [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/KJ5IRQ/brainwatch.git
brainwatch --version
```

From a local clone:

```bash
git clone https://github.com/KJ5IRQ/brainwatch.git
cd brainwatch
uv tool install .
brainwatch --version
```

For development:

```bash
git clone https://github.com/KJ5IRQ/brainwatch.git
cd brainwatch
uv sync --extra dev
uv run pytest -q
```

## Configure

```bash
mkdir -p ~/.config/brainwatch
cp config.example.toml ~/.config/brainwatch/config.toml
chmod 600 ~/.config/brainwatch/config.toml
```

Edit the copied file. Remove providers you do not use. Then export only the keys
needed by the enabled providers:

```bash
read -rsp 'OpenRouter API key: ' OPENROUTER_API_KEY && export OPENROUTER_API_KEY
printf '\n'
```

Do not put key values in `config.toml`. Configuration stores environment-variable
names only.

See [Configuration](docs/configuration.md) and [Providers](docs/providers.md).

## First run

```bash
brainwatch providers
brainwatch health
brainwatch status
brainwatch trend
brainwatch chain --format json
```

Use a non-default configuration or evidence directory with global options before
the command:

```bash
brainwatch --config ./config.example.toml --data-dir ./scratch-state providers
```

`health` returns:

- `0` when at least one verified-free model passed.
- `2` when no verified-free model passed.
- `1` for configuration, local I/O, or command errors.

A provider failure is isolated. Other configured providers continue.

## Commands

### `brainwatch providers`

Lists configured provider names, kinds, base URLs, and credential variable names.
It does not read credential values or contact the provider.

### `brainwatch health`

Discovers models, verifies eligibility, probes candidates concurrently with bounded
workers and timeouts, records evidence, ranks current survivors, and writes reports.

```bash
brainwatch health --provider openrouter --top 3 --retain 5000
brainwatch health --json
```

### `brainwatch status`

Reads the last report without contacting a provider.

```bash
brainwatch status
brainwatch status --json
```

### `brainwatch trend`

Summarizes historical probe pass rates and current failure streaks.

### `brainwatch chain`

Prints the latest proposed chain as normalized JSON or OpenClaw-shaped JSON.

### `brainwatch openclaw`

Compares evidence with an explicit OpenClaw config or applies the proposed chain.
Writes require `--yes`, create a mode-`0600` backup, validate JSON, and replace the
file atomically.

```bash
brainwatch openclaw status --config ~/.openclaw/openclaw.json
brainwatch openclaw apply --config ~/.openclaw/openclaw.json --yes
```

Read [OpenClaw integration](docs/openclaw.md) before applying a chain.

## Data layout

Default configuration:

```text
~/.config/brainwatch/config.toml
```

Default evidence:

```text
~/.local/share/brainwatch/
├── backups/
├── ledger/
│   ├── availability.jsonl
│   └── usage.jsonl
└── reports/
    ├── latest.json
    ├── proposed-chain.json
    ├── status.txt
    └── trend.txt
```

Override these paths with `BRAINWATCH_CONFIG`, `BRAINWATCH_HOME`, XDG variables, or
CLI flags. Reports and ledgers are created with restrictive permissions where the
platform permits it.

## Scheduling

Generic user-level systemd units are in `deploy/systemd/`:

```bash
mkdir -p ~/.config/systemd/user ~/.local/share/brainwatch
cp deploy/systemd/brainwatch.service deploy/systemd/brainwatch.timer \
  ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now brainwatch.timer
systemctl --user list-timers brainwatch.timer
```

Put required environment assignments in `~/.config/brainwatch/env`, set mode
`0600`, and never commit that file.

## Security model

Brainwatch treats provider responses as untrusted data. It does not execute model
output, use output as a command or path, or silently enable paid models. Error text
is bounded and redacted. Ledger writers remove secret-shaped fields. Remote HTTP is
refused; plain HTTP is allowed only for loopback endpoints.

Read [Security](SECURITY.md) for reporting and operational details.

## Synthetic examples

`examples/` contains fabricated evidence and report files. They are safe to inspect,
copy, and use in tests. They are not provider measurements.

## Development

```bash
uv sync --extra dev
uv run ruff check src tests
uv run pytest -q
uv build
```

Contributions should add a failing test before changing behavior. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
