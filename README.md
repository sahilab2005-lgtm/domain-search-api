# Domain-Restricted Search API

A FastAPI service that searches the web through an MCP (Model Context Protocol)
server, optionally restricted to an allowlist of domains, with a persistent
blocklist always applied. Optionally synthesizes a direct answer from the
search results using a local LLM (via Ollama).

## Features

- 🔍 Web search via DuckDuckGo (`ddgs`), run through a local MCP server over stdio
- ✅ Domain **allowlist** — restrict results to specific domains (e.g. only `.gov.in` sites)
- 🚫 Domain **blocklist** — always excluded, regardless of the allowlist
- 🧠 Optional answer synthesis using a local Ollama model — no external LLM API required
- ⚙️ Fully config-driven — nothing hardcoded (domains, model, timeouts all come from `.env` / `config.json`)

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed locally, **only if** you plan to use answer synthesis
- Git

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/sahilab2005-lgtm/domain-search-api.git
cd domain-search-api
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Copy the example file and adjust as needed:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Open `.env` and review the values — the defaults work out of the box for local
development. See [Environment Variables](#environment-variables) below for what
each one does.

### 5. (Optional) Set up Ollama for answer synthesis

Only needed if you want `/query` to return a synthesized answer instead of just
raw search results.

```bash
ollama pull llama3.2:3b
ollama serve
```

Make sure `LLM_MODEL` in `.env` matches the model you pulled.

### 6. Run the API

```bash
python main.py
```

or with uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be live at `http://localhost:8000`. Interactive docs are auto-generated
at `http://localhost:8000/docs`.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MCP_ENABLED` | `true` | Whether MCP-backed search is enabled |
| `MCP_SERVER_COMMAND` | `python` | Command used to launch the MCP server subprocess |
| `MCP_SERVER_ARGS` | `["mcp_server.py"]` | Args passed to the MCP server (JSON list) |
| `MCP_SERVER_ENV` | `{}` | Extra env vars for the MCP server subprocess (JSON object) |
| `MCP_SEARCH_TOOL_NAME` | `search` | Name of the tool exposed by `mcp_server.py` |
| `MCP_TIMEOUT_SECONDS` | `25` | Timeout for MCP calls |
| `MAX_RESULTS_DEFAULT` | `5` | Default number of results per query |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed browser origins |
| `DOMAIN_CONFIG_PATH` | `config.json` | Where the allow/block list is stored |
| `LLM_MODEL` | `llama3.2:3b` | Ollama model used for answer synthesis |
| `LLM_NUM_CTX` | `0` | Context window override for Ollama (`0` = model default) |

## API Reference

### `GET /health`
Health check. Returns `{"status": "ok", "mcp_enabled": true}`.

### `POST /query`
Run a search, optionally domain-restricted and/or synthesized into an answer.

```json
{
  "query": "renewable energy policy",
  "use_allowlist": true,
  "max_results": 5,
  "synthesize_answer": false
}
```

- `use_allowlist: true` requires at least one domain in the allowlist (add via `POST /allowlist`), otherwise the request returns a 422.
- `use_allowlist: false` runs an open, unrestricted web search.
- `synthesize_answer: true` fails soft — if Ollama isn't running or the model isn't pulled, you still get raw results back, with `answer: null` and an `answer_error` explaining why.

### Allowlist

| Method | Path | Description |
|---|---|---|
| `GET` | `/allowlist` | List allowed domains |
| `POST` | `/allowlist` | Add a domain: `{"domain": "example.gov.in"}` |
| `DELETE` | `/allowlist/{domain}` | Remove a domain |

### Blocklist

| Method | Path | Description |
|---|---|---|
| `GET` | `/blocklist` | List blocked domains |
| `POST` | `/blocklist` | Add a domain: `{"domain": "spam-site.com"}` |
| `DELETE` | `/blocklist/{domain}` | Remove a domain |

A blocked domain is always excluded, even if it would otherwise match the allowlist.

## Project Structure

```
.
├── main.py              # FastAPI app and route definitions
├── config.py            # Loads and validates environment variables
├── domain_config.py     # Allowlist/blocklist read/write (backed by config.json)
├── search_client.py      # Spawns and talks to the MCP server over stdio
├── mcp_server.py         # MCP server exposing the `search` tool (DuckDuckGo + scraping)
├── llm_summarizer.py     # Optional Ollama-based answer synthesis
├── config.json           # Persisted allowlist/blocklist state
├── requirements.txt
├── .env.example          # Template — copy to .env and fill in
└── .gitignore
```

## Notes

- The allowlist is treated as a security boundary: if a domain-restricted query
  returns no matches, it does **not** silently fall back to an open web search.
- Never commit your real `.env` — it's already excluded via `.gitignore`. Use
  `.env.example` as the reference for what variables are needed.