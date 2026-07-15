# Configuration

Brainwatch reads TOML. The default path is:

```text
~/.config/brainwatch/config.toml
```

Resolution order:

1. `--config PATH`
2. `BRAINWATCH_CONFIG`
3. `$XDG_CONFIG_HOME/brainwatch/config.toml`
4. `~/.config/brainwatch/config.toml`

Runtime evidence uses `--data-dir`, then `BRAINWATCH_HOME`, then
`$XDG_DATA_HOME/brainwatch`, then `~/.local/share/brainwatch`.

## Global settings

```toml
[brainwatch]
request_timeout_seconds = 25
overall_timeout_seconds = 240
max_workers = 4
```

- `request_timeout_seconds`: positive number used for provider catalog and chat
  requests.
- `overall_timeout_seconds`: positive wall-clock budget for the probe batch.
- `max_workers`: integer from 1 through 32.
- `data_dir`: optional path override. Prefer `BRAINWATCH_HOME` for portable scripts.

## OpenRouter

```toml
[[providers]]
name = "openrouter"
kind = "openrouter"
api_key_env = "OPENROUTER_API_KEY"
```

Optional fields:

```toml
base_url = "https://openrouter.ai/api"
models_path = "/v1/models"
chat_path = "/v1/chat/completions"
```

OpenRouter eligibility comes from its catalog. `free_models` is not used.

## Generic OpenAI-compatible provider

```toml
[[providers]]
name = "remote-friend"
kind = "openai-compatible"
base_url = "https://models.example.test"
api_key_env = "EXAMPLE_PROVIDER_API_KEY"
models_path = "/v1/models"
chat_path = "/v1/chat/completions"
free_models = ["example-free-model"]
```

Every generic provider requires a nonempty `free_models` list. This is an explicit
operator assertion that the named model IDs can be probed at zero cost. Brainwatch
matches IDs exactly and refuses all other models.

## Local endpoint

Plain HTTP is accepted only for loopback hosts:

```toml
[[providers]]
name = "local-lab"
kind = "openai-compatible"
base_url = "http://127.0.0.1:8000"
api_key_env = "LOCAL_LAB_API_KEY"
free_models = ["example-small"]
```

Set a nonempty local key if the server requires one. If it does not, use a harmless
nonsecret token such as `local` in the named environment variable. Brainwatch still
requires the variable so provider configuration remains explicit.

## Credentials

Configuration contains the variable name, never its value:

```bash
read -rsp 'OpenRouter API key: ' OPENROUTER_API_KEY && export OPENROUTER_API_KEY
printf '\n'
```

For systemd, use a private environment file:

```text
OPENROUTER_API_KEY=<set-locally>
```

```bash
chmod 600 ~/.config/brainwatch/env
```

Do not commit the environment file.

## Validation rules

Brainwatch rejects:

- duplicate provider names;
- unsupported provider kinds;
- empty credential variable names;
- generic providers without an explicit free-model allowlist;
- nonpositive timeouts;
- worker counts outside 1 through 32;
- URL credentials, query strings, and fragments;
- remote plain HTTP;
- endpoint paths that could change the configured origin.

Validation occurs before provider requests.
