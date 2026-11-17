#!/usr/bin/env python3
"""Headless, isolated writer call.

The main conversation never launches the writer. This script does: it passes
the brief as the prompt to a headless Claude Code run with

  * an explicitly empty tool list (--tools ""), no MCP servers, no skills
  * writer.md as the entire system prompt (--system-prompt-file)
  * no settings sources, so no hooks or permissions from the project
  * a fresh empty working folder, so no project CLAUDE.md loads
  * structured output enforced with --json-schema

It returns the parsed JSON plus call metadata. Only a short summary ever goes
back to the conversation that ran generate.py.

Test hook: set COMMENTARY_WRITER_CMD to a command that reads the brief on
stdin and prints output JSON on stdout to replace the real call.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SKILL_DIR  # noqa: E402

WRITER_PROMPT = SKILL_DIR / "writer.md"

NUMBER_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": "number"},
        "kind": {"type": "string", "enum": ["direct", "derived", "unverified"]},
        "ref": {"type": "string"},
        "op": {"type": "string", "enum": ["difference", "pct_change", "share", "ratio", "sum", "pp_change"]},
        "inputs": {"type": "array", "items": {"type": ["string", "number"]}},
    },
    "required": ["value", "kind"],
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "bullets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "numbers": {"type": "array", "items": NUMBER_SCHEMA},
                                "tables": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["text", "numbers"],
                        },
                    },
                    "missing": {"type": "array", "items": {"type": "string"}},
                    "source": {"type": "string"},
                },
                "required": ["id", "bullets", "missing", "source"],
            },
        }
    },
    "required": ["units"],
}


class WriterError(Exception):
    pass


def build_command(model: str) -> list[str]:
    exe = shutil.which("claude")
    if not exe:
        raise WriterError("the `claude` command is not on PATH; the headless writer cannot run")
    return [
        exe, "-p",
        "--tools", "",
        "--system-prompt-file", str(WRITER_PROMPT),
        "--setting-sources", "",
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
        "--disable-slash-commands",
        "--no-session-persistence",
        "--model", model,
        "--output-format", "json",
        "--json-schema", json.dumps(OUTPUT_SCHEMA),
    ]


def call_writer(prompt: str, model: str, timeout_s: int = 300) -> tuple[dict, dict]:
    """Return (output_json, meta). Raises WriterError on transport or parse failure."""
    t0 = time.time()
    override = os.environ.get("COMMENTARY_WRITER_CMD")
    with tempfile.TemporaryDirectory(prefix="commentary_writer_") as empty:
        if override:
            # Windows: pass the string as is (shlex would eat backslashes in paths)
            cmd = override if os.name == "nt" else shlex.split(override)
        else:
            cmd = build_command(model)
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_CODE_ADDITIONAL_DIRECTORIES")}
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                                  cwd=empty, timeout=timeout_s, env=env)
        except subprocess.TimeoutExpired as e:
            raise WriterError(f"writer timed out after {timeout_s}s") from e
    meta = {"model": model, "seconds": round(time.time() - t0, 1)}
    if proc.returncode != 0:
        raise WriterError(f"writer exited {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}")
    out = proc.stdout.strip()
    if override:
        return _parse_json(out), meta
    try:
        env_json = json.loads(out)
    except json.JSONDecodeError as e:
        raise WriterError(f"writer returned non-JSON envelope: {out[:300]}") from e
    if env_json.get("is_error"):
        raise WriterError(f"writer error: {env_json.get('result') or env_json.get('subtype')}")
    meta["cost_usd"] = env_json.get("total_cost_usd")
    used = list((env_json.get("modelUsage") or {}).keys())
    if used:
        meta["model"] = used[0]
    if isinstance(env_json.get("structured_output"), dict):
        return env_json["structured_output"], meta
    return _parse_json(env_json.get("result") or ""), meta


def _parse_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        raise WriterError(f"writer output is not JSON: {text[:300]}") from e


if __name__ == "__main__":
    # Smoke test: call_writer.py <brief.json> [model]
    brief = Path(sys.argv[1]).read_text()
    out, meta = call_writer(brief, sys.argv[2] if len(sys.argv) > 2 else "sonnet")
    print(json.dumps({"meta": meta, "output": out}, indent=1))
