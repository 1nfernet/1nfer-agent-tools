# 1NFER agent connection tools

The previous public HTTP MCP on the development host has been retired. Use the local stdio client below. Production machine instructions: https://1nfer.net/llms.txt . No replacement public HTTP endpoint is advertised.

Local procurement: install the pinned Python dependencies into an isolated environment and run `python server.py --stdio`.
Local-only extra tools: `register_account`, `account_status`, `create_invoice`, `invoice_status`.
`INFER_STATE_DIR` optionally selects your private local directory (default `~/.config/1nfer-client`, mode0700). Keys and saved invoice intents are0600; secrets are not tool outputs. Preserve this directory for account access. This is an API credential, not a crypto wallet seed.

Invoice creation requires an authorized amount and saved intent ID. It never signs or sends cryptocurrency. Do not start a new transfer after expiry; wait for confirmed credit. Unknown outcomes require reconciliation, not a new key/payment. Read live payment terms and your account's actual rates before use.

Installable skills are under `skills/`. Existing inference: https://1nfer.net/ . Scoped own-brand business setup: https://1nfer.net/guides/launch-your-service.html . No guaranteed customers, returns, free model or full-framework compatibility. All named models are exact catalogue aliases; provider identity alone does not establish provenance.
