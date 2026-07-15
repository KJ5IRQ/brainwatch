# OpenClaw integration

OpenClaw support is optional. Brainwatch can inspect or update only an explicitly
provided JSON file. It never searches for an OpenClaw installation and never
restarts a process.

## Supported shape

The target must contain:

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "provider/model-id",
        "fallbacks": ["provider/another-model"]
      }
    }
  }
}
```

Unknown top-level and sibling fields are preserved. An unknown model-block shape is
refused rather than guessed.

## Check status

Run a health check first, then compare the configured chain with the latest evidence:

```bash
brainwatch health
brainwatch openclaw status --config ~/.openclaw/openclaw.json
```

Status returns `0` when every configured model appears in current evidence with
status `ok`, and `2` when any model is missing or unhealthy.

## Preview

Inspect the proposed mapping without writing:

```bash
brainwatch chain --format openclaw
```

## Apply

Applying requires all of the following:

- a nonempty proposed chain;
- an explicit target path;
- a recognized JSON shape;
- the `--yes` flag.

```bash
brainwatch openclaw apply --config ~/.openclaw/openclaw.json --yes
```

Before replacement, Brainwatch writes a timestamped mode-`0600` backup under its
runtime `backups/` directory. The generated JSON is parsed and validated before an
atomic replace. The target is written mode `0600`.

Brainwatch does not restart OpenClaw. Use the framework's documented restart or
reload procedure after reviewing the diff.

## Manual rollback

The Python API exposes strict rollback validation. The CLI intentionally does not
automate rollback in version 0.1. To restore manually:

1. Stop or quiesce the process that writes the target file.
2. Locate the backup path printed by `openclaw apply`.
3. Validate the backup JSON.
4. Copy it over the target with mode `0600`.
5. Restart or reload using OpenClaw's documented command.

Keeping rollback explicit avoids selecting the wrong backup automatically.
