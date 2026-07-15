# Scheduling

Brainwatch is designed to run on a cadence — probe models, write evidence, and
stale out. The recommended way is systemd, but cron works too.

## systemd timer (recommended)

The shipped timer probes every six hours with up to ten minutes of randomized
delay to avoid coordinated stampedes:

```bash
mkdir -p ~/.config/systemd/user ~/.local/share/brainwatch
cp deploy/systemd/brainwatch.service deploy/systemd/brainwatch.timer \
  ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now brainwatch.timer
```

The service uses `Type=oneshot`. It has no restart policy — a transient failure
waits for the next timer tick (up to six hours). The timer uses `OnUnitActiveSec`
rather than a fixed wall-clock schedule: runs are six hours apart measured from
the end of the last run, not from midnight. This is intentional for a watchdog;
if you need a precise daily schedule, add `OnCalendar=daily` to the timer.

## Service configuration

```ini
# ~/.config/brainwatch/env
BRAINWATCH_CONFIG=$HOME/.config/brainwatch/config.toml
OPENROUTER_API_KEY=$OPENROUTER_API_KEY
EXAMPLE_PROVIDER_API_KEY=$EXAMPLE_PROVIDER_API_KEY
```

The environment file is optional. When absent, Brainwatch probes only providers
whose credentials you have exported in the shell that launched `systemctl --user`.

## Sandboxing

The shipped unit applies:

- `ProtectSystem=strict` with `ReadWritePaths` scoped to the data directory
- `ProtectHome=read-only` (the data directory must exist before launch)
- `PrivateTmp=true`
- `NoNewPrivileges=true`
- `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`
- `MemoryDenyWriteExecute=true` (CPython-only; PyPy users must disable this)
- `UMask=0077` — files created by the service are owner-only
- `TimeoutStartSec=300` — a single `brainwatch health` run is capped at five minutes

## cron

```cron
# Run every six hours with a ten-minute stagger
0 */6 * * * sleep $((RANDOM % 600)) && brainwatch health --retain 5000
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | All probed models passed |
| 1    | Internal error (config, network, disk) |
| 2    | No models passed — everything failed or was refused |
