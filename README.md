# lightRAG-MCP (Windows Bare-Metal)

Local LightRAG setup for citation-aware academic writing with:
- LLM: DeepSeek (`deepseek-chat`)
- Embedding: Voyage AI (`voyage-4-large`)
- Storage: JSON + NanoVector + NetworkX (local default)

## Quick Start

1. Install runtime and dependencies:

```powershell
scripts\setup.bat
```

2. Create local config files:

```powershell
copy .env.example .env
```

3. Put real API keys in `.env`:

```ini
LLM_BINDING_API_KEY=REVOKE_AND_REPLACE
EMBEDDING_BINDING_API_KEY_MAIN=REVOKE_AND_REPLACE
EMBEDDING_BINDING_API_KEY_FALLBACK=REVOKE_AND_REPLACE
```

Replace `REVOKE_AND_REPLACE` with your actual keys before starting the server.

Voyage setup notes:
- Main key is tried first.
- Fallback key is optional and used only if main fails during startup preflight.
- Selected model is `voyage-4-large`.

Important after changing embedding model:
- Rebuild embeddings by clearing existing vector data in `data/rag_storage` and re-ingesting documents.

4. Start LightRAG server:

```powershell
scripts\start-server.bat
```

Startup runs provider key preflight by default. To bypass preflight for offline/debug use:

PowerShell:

$env:LIGHTRAG_SKIP_KEYCHECK='1'; scripts\start-server.bat

cmd.exe:

cmd /c "set LIGHTRAG_SKIP_KEYCHECK=1 && scripts\start-server.bat"

5. Verify health:

```powershell
scripts\healthcheck.bat
```

Validate upstream provider keys explicitly:

```powershell
scripts\check-keys.bat
```

## Ingest PDFs with APA Metadata

- PDF input folder: `data/inputs`
- Sidecar metadata folder: `data/metadata`
- Prepared text output: `data/inputs_prepared`

Prepare + upload:

```powershell
.venv\Scripts\python.exe scripts\ingest_pdfs.py --recursive --upload --server http://127.0.0.1:9621
```

Required metadata fields per sidecar JSON:
- `author`
- `title`
- `year`

## Install Writing Skill

Install the local skill for VS Code prompts and agent skills:

```powershell
scripts\install-skill.bat
```

Skill source:
- `skills/lightrag-academic-writing/SKILL.md`
- `skills/lightrag-academic-writing/pressure-scenarios.md`

## Security Notes

- Keep real keys only in `.env`.
- Do not commit `.env`, `env`, or runtime data folders.
- Rotate any previously exposed API keys immediately.
- Avoid putting raw API keys directly in shell commands; prefer environment variables.

## Common Error

- 401 Api key is invalid during embedding extraction:
	- Run `scripts\check-keys.bat`.
	- If embedding fails, replace `EMBEDDING_BINDING_API_KEY_MAIN` and `EMBEDDING_BINDING_API_KEY_FALLBACK` in `.env` with valid Voyage keys.

## Detailed Guide

For the full setup and workflow notes, see `README-SETUP.md`.
