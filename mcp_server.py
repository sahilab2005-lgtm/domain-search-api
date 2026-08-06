import json
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    raise SystemExit(
        "Could not import FastMCP from the 'mcp' package. "
        "Make sure to have a recent version installed: pip install -U mcp"
    ) from e

# Support both duckduckgo-search v5 and v6+ ('ddgs')
try:
    from ddgs import DDGS  # v6+
except ImportError:
    try:
        from ddgs import DDGS  # v5 and below
    except ImportError as e:
        raise SystemExit(
            "No DuckDuckGo search package found. Run: pip install -U ddgs"
        ) from e

mcp = FastMCP("allowlist-search")


def _host_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _domain_matches(url: str, allowed_domains: list[str] | None) -> bool:
    """True if url's host equals or is a subdomain of one of allowed_domains.
    An empty/None allowlist means "no restriction" (open web)."""
    if not allowed_domains:
        return True
    host = _host_of(url)
    if not host:
        return False
    for d in allowed_domains:
        d = d.lower().strip()
        if d.startswith("www."):
            d = d[4:]
        if not d:
            continue
        if host == d or host.endswith("." + d):
            return True
    return False


def _domain_blocked(url: str, blocked_domains: list[str] | None) -> bool:
    """True if url's host equals or is a subdomain of one of blocked_domains.
    Checked independently of (and after) the allowlist — a blocked domain
    stays excluded even if it would otherwise pass the allowlist, since a
    block is a more specific, deliberate signal than a broad allow."""
    if not blocked_domains:
        return False
    host = _host_of(url)
    if not host:
        return False
    for d in blocked_domains:
        d = d.lower().strip()
        if d.startswith("www."):
            d = d[4:]
        if not d:
            continue
        if host == d or host.endswith("." + d):
            return True
    return False


def _scrape(url: str) -> str:
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:3000]
    except Exception:
        return ""


@mcp.tool()
def search(
    query: str,
    max_results: int = 5,
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
) -> str:
    """Search the web (optionally restricted to allowed_domains, always
    excluding blocked_domains) and return scraped page content as JSON."""
    results: list[dict] = []
    seen_urls: set[str] = set()

    # Build one query per allowed domain so DuckDuckGo's site: filter applies.
    # If allowed_domains is empty/None, this is a single open-web query.
    search_queries = (
        [f"site:{d} {query}" for d in allowed_domains] if allowed_domains else [query]
    )

    with DDGS() as ddgs:
        for sq in search_queries:
            try:
                raw = list(ddgs.text(sq, max_results=max_results))
            except Exception:
                raw = []

            for r in raw:
                url = r.get("href", "")
                if not url or url in seen_urls:
                    continue
                if not _domain_matches(url, allowed_domains):
                    continue
                if _domain_blocked(url, blocked_domains):
                    continue
                seen_urls.add(url)

                title = r.get("title", "")
                snippet = r.get("body", "")
                page = _scrape(url)
                content = f"{snippet}\n{page}".strip()
                results.append({"title": title, "url": url, "content": content[:3000]})

                if len(results) >= max_results:
                    break

            if len(results) >= max_results:
                break

    # An allowlist is a security boundary: no matching result means no result.
    # Never retry without it, or a domain-restricted request can leak into an
    # unrestricted web search.
    return json.dumps(results)


if __name__ == "__main__":
    print("MCP search server is running…")
    mcp.run(transport="stdio")
