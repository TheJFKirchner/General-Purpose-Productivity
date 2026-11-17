"""The planner's harness-and-model choices (the picker under the planner's chat box).

- HARNESSES: harness -> the agentlib engine that runs it, its label and the models offered. A harness is available
  when agentlib says its engine is (get_engine(name).capabilities.available; the Cursor engine is still a stub, so its
  entries are listed but disabled with "not available yet"). A new engine = one row here, no front-end change.
  The CLI chat's picker uses the same table (harness_options, engine_for; app/agents/claude_code/choices.py)
- The configured start / top models (settings planner_start_model / planner_top_model) are always listed for the
  default harness, so a launch option such as --planner-start haiku shows up as a choice
- planner_engine(settings): the engine a new planner is loaded on = the chosen harness's engine; the fake demo
  (settings.engine == "fake") forces the fake engine for everything
- choice_event(settings): the planner_choice event (options with availability, the remembered choice, auto-promote,
  the top model's name, the promotion rules text read-only)
"""
from __future__ import annotations

DEFAULT_HARNESS = "claude"
NOT_AVAILABLE = "not available yet"

# harness id -> engine (agentlib), label, models offered (model id for Agent(model=), label)
HARNESSES: tuple[dict, ...] = (
    {"harness": "claude", "engine": "claude", "label": "Claude", "models": (("sonnet", "Sonnet"), ("opus", "Opus"))},
    {"harness": "cursor", "engine": "cursor", "label": "Cursor", "models": (("sonnet", "Sonnet"), ("opus", "Opus"))},
)
MODEL_LABELS = {"sonnet": "Sonnet", "opus": "Opus", "haiku": "Haiku"}
PLANNER_SETTINGS = ("planner_start_model", "planner_top_model", "planner_harness", "planner_auto_promote",
                    "promotion_window_turns", "promotion_criteria_path")


def model_label(model: str | None) -> str:
    m = str(model or "").strip()
    return MODEL_LABELS.get(m.lower(), m)


def harness(name: str | None) -> dict | None:
    return next((h for h in HARNESSES if h["harness"] == name), None)


def harness_label(name: str | None) -> str:
    h = harness(name)
    return h["label"] if h else str(name or "")


def engine_available(engine: str) -> bool:
    """agentlib's own answer: the engine is registered and not a stub."""
    try:
        from agentlib import get_engine
        return bool(get_engine(engine).capabilities.available)
    except Exception:  # noqa: BLE001 -- unknown engine, missing package: not available
        return False


def harness_available(name: str | None) -> bool:
    h = harness(name)
    return bool(h) and engine_available(h["engine"])


def option_id(harness_name: str, model: str) -> str:
    return f"{harness_name}:{model}"


def label(harness_name: str | None, model: str | None) -> str:
    return f"{harness_label(harness_name)} · {model_label(model)}"


def launch_harness(engine: str | None) -> str:
    """The harness whose engine this launch runs on; the default harness when none matches (the fake demo)."""
    return next((h["harness"] for h in HARNESSES if h["engine"] == engine), DEFAULT_HARNESS)


def engine_for(harness_name: str | None, launch_engine: str) -> str:
    """The agentlib engine for a harness: fake in the demo (launch engine "fake" forces it for everything); else the
    harness's engine while agentlib says it is available, otherwise the launch's engine (a stale or hand-edited choice
    never breaks a session)."""
    if launch_engine == "fake":
        return "fake"
    h = harness(harness_name)
    return h["engine"] if h and engine_available(h["engine"]) else launch_engine


def harness_options(extra: dict[str, list] | None = None) -> list[dict]:
    """Every harness-and-model pair of HARNESSES, with availability (agentlib) and a note when it cannot be picked.
    extra = {harness: [model ids]} also listed for that harness (configured models outside the table). Shared by the
    planner picker and the CLI chat's picker (app/agents/claude_code/choices.py)."""
    out = []
    for h in HARNESSES:
        ok = engine_available(h["engine"])
        models = list(h["models"])
        for m in (extra or {}).get(h["harness"], ()):
            if m and m not in [x[0] for x in models]:
                models.append((m, model_label(m)))
        for m, mlabel in models:
            out.append({"id": option_id(h["harness"], m), "harness": h["harness"], "harness_label": h["label"],
                        "model": m, "model_label": mlabel, "label": f"{h['label']} · {mlabel}", "available": ok,
                        "note": None if ok else NOT_AVAILABLE})
    return out


def options(settings) -> list[dict]:
    """The planner's options: every harness-and-model pair; the configured start / top models are always listed for
    the default harness."""
    extra = [m for m in (getattr(settings, "planner_start_model", None), getattr(settings, "planner_top_model", None)) if m]
    return harness_options({DEFAULT_HARNESS: extra})


def find(oid: str, settings) -> dict | None:
    return next((o for o in options(settings) if o["id"] == oid), None)


def chosen_harness(settings) -> str:
    """The remembered harness when it is known, else the default."""
    h = getattr(settings, "planner_harness", None) or DEFAULT_HARNESS
    return h if harness(h) else DEFAULT_HARNESS


def planner_engine(settings) -> str:
    """The agentlib engine a new planner runs on: fake in the demo; else the chosen harness's engine while agentlib
    says it is available, otherwise the launch's engine (a stale or hand-edited choice never breaks a session)."""
    return engine_for(chosen_harness(settings), settings.engine)


def choice_event(settings, rules: dict | None = None, overridden=()) -> dict:
    """planner_choice: what the picker shows. choice = what the next new plan starts on (per user)."""
    from .planner import planner_models
    start, top = planner_models(settings)
    h = chosen_harness(settings)
    return {"type": "planner_choice", "options": options(settings),
            "choice": {"option_id": option_id(h, start), "harness": h, "model": start, "label": label(h, start)},
            "auto_promote": bool(getattr(settings, "planner_auto_promote", True)),
            "top_model": top, "top_label": model_label(top), "promotion_off": start == top,
            "pinned": getattr(settings, "planner_model", None) or None,
            "overridden": sorted(k for k in overridden if k in PLANNER_SETTINGS),
            "rules": rules or {"markdown": "", "path": None}}
