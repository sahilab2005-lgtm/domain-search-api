# Domain-Restricted Search API

A standalone FastAPI service that searches the web through a custom **MCP
server**, optionally restricted to a domain allowlist, with a persistent
blocklist always applied. This is the search-only slice of the larger
`ddgs_domain_search` project — no UI, no Postgres, no Qdrant, no
embeddings/LLM. Just: query in → MCP search → filtered results out.

## How it fits together

```
Client ──POST /query──▶ FastAPI (main.py)
                              │
                              ├─ reads allowlist/blocklist from config.json (domain_config.py)
                              │
                              └─ search_client.py spawns mcp_server.py over stdio
                                     and calls its "search" tool
                                        │
                                        └─ mcp_server.py queries DuckDuckGo,
                                           filters by allowed/blocked domains,
                                           scrapes each result page, returns JSON
```

`mcp_server.py` is **not** run separately — `search_client.py` launches it
as a subprocess (via `MCP_SERVER_COMMAND` / `MCP_SERVER_ARGS`) the first
time a query needs it, communicating over stdio per the MCP protocol.

## Files

| File               | Purpose                                                            |
|--------------------|---------------------------------------------------------------------|
| `main.py`          | FastAPI app (entry point) — `/query`, `/allowlist`, `/blocklist`   |
| `search_client.py` | Sync wrapper around the async MCP client session                   |
| `mcp_server.py`    | The MCP server itself — DuckDuckGo search + domain filtering       |
| `domain_config.py` | Reads/writes `config.json` (allowlist/blocklist), atomic writes    |
| `llm_summarizer.py`| Optional — local LLM (Ollama) synthesis of one answer from results|
| `config.py`        | Env var loading for MCP + LLM connection settings                  |
| `config.json`      | Persisted allowed/blocked domains                                   |
| `.env.example`     | Copy to `.env` and adjust                                           |
| `requirements.txt` | Dependencies                                                        |

## Setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
```

## Run

Either of these works, from any directory (paths to `mcp_server.py` and
`config.json` are resolved relative to the project folder, not to wherever
you launch from):

```bash
python main.py
# or
uvicorn main:app --reload --port 8000
```

Interactive docs: http://127.0.0.1:8000/docs

## Endpoints

### `POST /query` — run a search

```json
{
  "query": "MahaAgri-AI objectives",
  "use_allowlist": true,
  "max_results": 5,
  "synthesize_answer": false
}
```

- `use_allowlist: true` → search is restricted to domains in the allowlist
  (`config.json` → `allowed_domains`). Returns HTTP 422 if the allowlist is
  empty.
- `use_allowlist: false` → open web search. The **blocklist still applies**
  either way — it's a hard exclusion, not a toggle.
- `synthesize_answer: true` → also generates one synthesized answer from
  the results using a local LLM via Ollama (see `llm_summarizer.py`). Off
  by default. If Ollama isn't running or the model isn't pulled, the raw
  `results` still come back — `answer` is `null` and `answer_error`
  explains why.

Example:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "MahaAgri-AI objectives", "use_allowlist": true}'
```

Response shape:

```json
{
  "query": "MahaAgri-AI objectives",
  "use_allowlist": true,
  "allowed_domains": ["maharashtra.nic.in"],
  "blocked_domains": ["youtube.com"],
  "result_count": 3,
  "results": [
    {"title": "...", "url": "https://maharashtra.nic.in/...", "content": "..."}
  ]
}
```

With `"synthesize_answer": true`, the response also includes:

```json
{
  "answer": "MahaAgri-AI is a sovereign, on-premises AI platform developed by NIC Maharashtra... [Source 2]",
  "answer_error": null
}
```

### Allowlist / Blocklist management

```bash
curl http://127.0.0.1:8000/allowlist
curl -X POST http://127.0.0.1:8000/allowlist -H "Content-Type: application/json" -d '{"domain": "gov.in"}'
curl -X DELETE http://127.0.0.1:8000/allowlist/gov.in

curl http://127.0.0.1:8000/blocklist
curl -X POST http://127.0.0.1:8000/blocklist -H "Content-Type: application/json" -d '{"domain": "youtube.com"}'
curl -X DELETE http://127.0.0.1:8000/blocklist/youtube.com
```

Your existing Streamlit UI's "Internet allowlist" sidebar panel and the
"Domain search / Open web search" radio button map directly onto these
endpoints — `use_allowlist` in `/query` is the same toggle as that radio.

## Optional: local LLM answer synthesis

`llm_summarizer.py` is a separate module that turns the raw search results
into one synthesized answer, using a locally running [Ollama](https://ollama.com)
model. It's off by default and completely optional — the search endpoint
works fully without it, so if you (or the people reviewing this) already
have your own LLM step, you can ignore or delete this file.

To use it:

```bash
# 1. Install and start Ollama, then pull a model:
ollama pull llama3.1

# 2. Install the optional dependency:
pip install ollama

# 3. Set LLM_MODEL in .env if you're using a different model name.

# 4. Send synthesize_answer: true on /query:
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "MahaAgri-AI objectives", "use_allowlist": true, "synthesize_answer": true}'
```

If Ollama isn't running or the model isn't pulled, the request doesn't
fail — you still get `results`, with `answer: null` and an `answer_error`
explaining what went wrong.

## Notes

- No LLM/answer-synthesis step is required by default, since the brief was
  "search only" — `/query` returns raw scraped results (title, url,
  content) unless `synthesize_answer: true` is set.
- `config.json` writes are atomic (temp file + `os.replace`), so concurrent
  requests updating the allowlist won't corrupt it.
