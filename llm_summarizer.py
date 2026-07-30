import config

def _build_context(results: list[dict], max_chars_per_result: int = 1200) -> str:
    blocks = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("url", "")
        content = (r.get("content") or "")[:max_chars_per_result]
        blocks.append(f"[Source {i}: {title} ({url})]\n{content}")
    return "\n\n---\n\n".join(blocks)


def generate_answer(query: str, results: list[dict]) -> str:
    """
    Synthesizes a single, direct answer from a list of search results
    (each shaped like {"title", "url", "content"}) using a local Ollama
    model. Returns "" if there are no results to work from.

    Raises RuntimeError with a clear message if Ollama isn't installed,
    isn't running, or the configured model isn't pulled — callers (see
    main.py) should catch this and still return the raw search results
    rather than fail the whole request.
    """
    if not results:
        return ""

    try:
        import ollama
    except ImportError as e:
        raise RuntimeError(
            "The 'ollama' Python package is not installed. "
            "Install with: pip install ollama"
        ) from e

    context = _build_context(results)

    prompt = f"""You are a helpful assistant. Multiple web pages have been retrieved to answer a query.
Carefully synthesize information across ALL the sources below and provide a direct, factual answer.
Identify and combine all distinct points relevant to the query — do not skip or summarize vaguely.
Use bullet points when listing multiple items, or short paragraphs when explaining concepts.
Every factual statement must reference at least one source inline like [Source 1].
Keep the answer concise but complete — aim for 6–10 bullet points or 4–6 sentences maximum.

Query: {query}

Sources:
{context}

Answer:"""

    chat_kwargs = {
        "model": config.LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }
    if config.LLM_NUM_CTX:
        chat_kwargs["options"] = {"num_ctx": config.LLM_NUM_CTX}

    try:
        response = ollama.chat(**chat_kwargs)
    except Exception as e:
        raise RuntimeError(
            f"Local LLM (Ollama) call failed: {e}. "
            f"Is Ollama running, and is model '{config.LLM_MODEL}' pulled? "
            f"(ollama pull {config.LLM_MODEL})"
        ) from e

    return response["message"]["content"].strip()
