# 1NFER agent connection tools

Public **read-only** MCP: `https://hesoyam.business/agent-tools/mcp` (Streamable HTTP).
Tools: `list_models`, `payment_terms`, `estimate_cost`, `connection_recipe`.
No API key required or accepted, no model generation, no invoice creation or payments on this public server.

Local procurement: install the pinned Python dependencies into an isolated environment and run `python server.py --stdio`.
Local-only extra tools: `register_account`, `account_status`, `create_invoice`, `invoice_status`.
`INFER_STATE_DIR` optionally selects your private local directory (default `~/.config/1nfer-client`, mode0700). Keys and saved invoice intents are0600; secrets are not tool outputs. Preserve this directory for account access. This is an API credential, not a crypto wallet seed.

Invoice creation requires an authorized amount and saved intent ID. It never signs or sends cryptocurrency. Do not start a new transfer after expiry; wait for confirmed credit. Unknown outcomes require reconciliation, not a new key/payment. Read live payment terms and your account's actual rates before use.

Installable skills are under `skills/`. Existing inference: https://1nfer.net/ . Scoped own-brand business setup: https://hesoyam.business/router . No guaranteed customers, returns, free model or full-framework compatibility. All named models are exact catalogue aliases; provider identity alone does not establish provenance.
