"""
Minimal configuration for the domain-restricted search API.
Only the settings actually needed to spawn/talk to the MCP search server.
"""
import json
import os
import shutil
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Directory this file lives in — used to build an absolute default path to
# mcp_server.py, so launching main.py works the same way regardless of the
# current working directory the process happens to be started from.
_PROJECT_DIR = Path(__file__).resolve().parent

_dotenv_path = find_dotenv()
if _dotenv_path:
    print(f"✔ Loaded environment from: {_dotenv_path}")
else:
    print("⚠ No .env file found — relying on real OS environment variables / defaults.")
load_dotenv(_dotenv_path)


def _optional_env(name: str, default, cast=str):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return cast(value)
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"Environment variable '{name}'='{value}' could not be parsed: {e}")


# ── MCP server connection (spawned over stdio) ──
MCP_ENABLED = os.getenv("MCP_ENABLED", "true").strip().lower() in ("1", "true", "yes")

MCP_SERVER_COMMAND_RAW = _optional_env("MCP_SERVER_COMMAND", "python")
# Resolve python/python3/py to this process's own interpreter so the MCP
# child process uses the same virtualenv, regardless of what's on PATH.
if MCP_SERVER_COMMAND_RAW.strip().lower() in {"python", "python3", "py"}:
    MCP_SERVER_COMMAND = sys.executable
else:
    MCP_SERVER_COMMAND = shutil.which(MCP_SERVER_COMMAND_RAW) or MCP_SERVER_COMMAND_RAW

_DEFAULT_MCP_SERVER_SCRIPT = str(_PROJECT_DIR / "mcp_server.py")
MCP_SERVER_ARGS_RAW = _optional_env("MCP_SERVER_ARGS", "")
if MCP_SERVER_ARGS_RAW.strip():
    try:
        MCP_SERVER_ARGS = json.loads(MCP_SERVER_ARGS_RAW)
        if not isinstance(MCP_SERVER_ARGS, list):
            raise ValueError("MCP_SERVER_ARGS must be a JSON list")
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(f"MCP_SERVER_ARGS='{MCP_SERVER_ARGS_RAW}' is not a valid JSON list: {e}")
else:
    # No override given — point at mcp_server.py next to this file, so
    # `python main.py` / `uvicorn main:app` works from any working directory.
    MCP_SERVER_ARGS = [_DEFAULT_MCP_SERVER_SCRIPT]

MCP_SERVER_ENV_RAW = _optional_env("MCP_SERVER_ENV", "{}")
try:
    MCP_SERVER_ENV = json.loads(MCP_SERVER_ENV_RAW) or None
    if MCP_SERVER_ENV is not None and not isinstance(MCP_SERVER_ENV, dict):
        raise ValueError("MCP_SERVER_ENV must be a JSON object")
except (json.JSONDecodeError, ValueError) as e:
    raise RuntimeError(f"MCP_SERVER_ENV='{MCP_SERVER_ENV_RAW}' is not a valid JSON object: {e}")

MCP_SEARCH_TOOL_NAME = _optional_env("MCP_SEARCH_TOOL_NAME","search")
MCP_TIMEOUT_SECONDS = _optional_env("MCP_TIMEOUT_SECONDS",25, int)
MAX_RESULTS_DEFAULT = _optional_env("MAX_RESULTS_DEFAULT", 5,int)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# ── Optional local LLM synthesis (llm_summarizer.py) ──
# Only used when a /query request sets "synthesize_answer": true.
# Leave the defaults if you don't plan on using this feature.
LLM_MODEL = _optional_env("LLM_MODEL","llama3.2:3b")
LLM_NUM_CTX = _optional_env("LLM_NUM_CTX", 0, int)  # 0 = let Ollama use its own default
