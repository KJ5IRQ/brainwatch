# Providers

Brainwatch normalizes provider catalogs and probe evidence into provider-qualified
model identities:

```text
provider:model-id
```

This prevents identical model IDs from colliding across providers.

## OpenRouter

OpenRouter discovery requests `/v1/models` and accepts only text-output models whose
catalog prompt and completion prices both parse to decimal zero. Missing, malformed,
or nonzero pricing fails closed.

The probe uses the provider's chat-completions endpoint with a tiny deterministic
prompt. The response must contain `{"ok": true, "n": 42}` in normal content,
multipart text, or a reasoning field.

## OpenAI-compatible endpoints

The generic adapter expects:

- `GET /v1/models` returning an object with a `data` list;
- each model object containing an `id` string;
- `POST /v1/chat/completions` returning OpenAI-compatible `choices` and optional
  `usage` fields.

Only exact IDs in the provider's `free_models` list are eligible. Catalog presence
alone is not cost proof.

## Failure isolation

Each provider has an independent discovery boundary. Authentication failures,
timeouts, malformed catalogs, and network errors are recorded for that provider
without preventing other providers from running.

Probe statuses include:

- `ok`
- `refused_unverified_cost`
- `auth_error`
- `payment_required`
- `rate_limited`
- `server_error`
- `timeout`
- `connection_error`
- `bad_format`
- `overall_timeout`
- `probe_error`

Only timeout, rate-limit, and server errors receive one bounded retry. Raw response
bodies are not stored.

## Adding a provider adapter

New adapters implement the `Provider` protocol in
`src/brainwatch/providers/base.py`:

```python
class Provider(Protocol):
    name: str

    def discover_models(self) -> list[ModelCandidate]: ...
    def probe(self, candidate: ModelCandidate) -> ProbeRecord: ...
```

A provider must define a verifiable zero-cost rule. If a trustworthy cost signal is
not available, require an exact operator allowlist. Do not infer free status from a
model name.
