# Security policy

## Supported versions

Security fixes are applied to the latest released minor version.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature for this repository. Do not
open a public issue containing credentials, private provider responses, or affected
configuration files.

Include:

- the affected version or commit;
- a minimal reproduction using synthetic data;
- expected and observed behavior;
- impact and any known workaround.

## Credential model

Brainwatch configuration stores environment-variable names, not key values. Keys
are read only when a provider request is made. Reports and ledgers must not contain
credentials or authorization headers.

Error strings are bounded and redact common bearer and API-key patterns. Ledger
serialization removes secret-shaped fields recursively. These controls reduce risk;
they do not make arbitrary error text safe to publish. Review evidence before
sharing it.

## Network model

- Remote providers require HTTPS.
- Plain HTTP is accepted only for loopback hosts.
- Endpoint paths may not change the configured origin.
- Catalog and chat requests use explicit timeouts.
- Retries are bounded to transient failures.

## Spend model

Brainwatch refuses unknown-cost remote models. OpenRouter requires exact catalog
zeroes. Generic providers require exact model IDs in `free_models`.

This is a technical gate, not a billing guarantee from the provider. Provider
pricing, quotas, promotions, and account policies remain external dependencies.
Review your provider dashboard and limits.

## File writes

Evidence and backups use restrictive permissions where supported. Reports are
written through temporary files and atomic replacement. OpenClaw changes require an
explicit target, recognized schema, nonempty chain, confirmation flag, validated
JSON, and a protected backup.

Brainwatch does not restart external services or execute model output.
