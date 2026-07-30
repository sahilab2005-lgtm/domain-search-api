from __future__ import annotations
from fastapi import FastAPI, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import config
import domain_config
import llm_summarizer
from search_client import search_mcp

app = FastAPI(
    title="Domain-Restricted Search API",
    version="1.0.0",
    description=(
        "Search the web through an MCP server, optionally restricted to an "
        "allowlist of domains, with a persistent blocklist always applied."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in config.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    use_allowlist: bool = True
    max_results: int = Field(default=config.MAX_RESULTS_DEFAULT, ge=1, le=20)
    synthesize_answer: bool = False


class DomainRequest(BaseModel):
    domain: str = Field(min_length=1, max_length=255)

#-----------------Endpoints-------------------------------------

@app.get("/health", tags=["System"])
def health() -> dict:
    return {"status": "ok", "mcp_enabled": config.MCP_ENABLED}


@app.post("/query", tags=["Query"])
async def query(body: QueryRequest) -> dict:
    blocked = domain_config.get_blocked_domains()

    if body.use_allowlist:
        allowed = domain_config.get_allowed_domains()
        if not allowed:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Domain search requires at least one allowed domain. "
                    "Add one via POST /allowlist, or set use_allowlist=false "
                    "for an open web search."
                ),
            )
    else:
        allowed = None  # None => no allowlist restriction (open web search)

    try:
        results = await run_in_threadpool(
            search_mcp,
            body.query.strip(),
            allowed,
            blocked,
            body.max_results,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    response = {
        "query": body.query,
        "use_allowlist": body.use_allowlist,
        "allowed_domains": allowed or [],
        "blocked_domains": blocked,
        "result_count": len(results),
        "results": results,
    }

    if body.synthesize_answer:
        # Fails soft: if Ollama isn't running / model isn't pulled, the
        # raw search results still come back — only "answer" is missing,
        # replaced with an explanation in "answer_error".
        try:
            response["answer"] = await run_in_threadpool(
                llm_summarizer.generate_answer, body.query.strip(), results
            )
        except RuntimeError as exc:
            response["answer"] = None
            response["answer_error"] = str(exc)

    return response


# ── Allowlist ────────────────────────────────────────────────────────────
@app.get("/allowlist", tags=["Allowlist"])
def list_allowlist() -> list[str]:
    return domain_config.get_allowed_domains()


@app.post("/allowlist", status_code=status.HTTP_201_CREATED, tags=["Allowlist"])
def add_allowlist(body: DomainRequest) -> dict:
    domain_config.add_allowed_domain(body.domain)
    return {"domain": body.domain.strip().lower()}


@app.delete("/allowlist/{domain}", status_code=status.HTTP_204_NO_CONTENT, tags=["Allowlist"])
def remove_allowlist(domain: str) -> None:
    domain_config.remove_allowed_domain(domain)


# ── Blocklist ────────────────────────────────────────────────────────────
@app.get("/blocklist", tags=["Blocklist"])
def list_blocklist() -> list[str]:
    return domain_config.get_blocked_domains()


@app.post("/blocklist", status_code=status.HTTP_201_CREATED, tags=["Blocklist"])
def add_blocklist(body: DomainRequest) -> dict:
    domain_config.add_blocked_domain(body.domain)
    return {"domain": body.domain.strip().lower()}


@app.delete("/blocklist/{domain}", status_code=status.HTTP_204_NO_CONTENT, tags=["Blocklist"])
def remove_blocklist(domain: str) -> None:
    domain_config.remove_blocked_domain(domain)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
