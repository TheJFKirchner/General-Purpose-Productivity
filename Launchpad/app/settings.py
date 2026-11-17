"""App settings (one place; CLI flags in launch.py override the defaults)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    project: Path                              # folder the app was launched for (--cwd); session folders go here
    engine: str = "claude"                     # "fake" for --fake (zero tokens)
    planner_model: str | None = None           # set = always this model (promotion off; --model)
    planner_start_model: str = "sonnet"        # every session starts here ...
    planner_top_model: str = "opus"            # ... and may be promoted here (same value = promotion off)
    planner_harness: str = "claude"            # harness new planners run on (app/agents/planner/choices.py)
    planner_auto_promote: bool = True          # off = the planner never promotes itself (by hand still works)
    promotion_window_turns: int = 2            # the planner may promote itself only in its first N turns
    promotion_criteria_path: str | None = None # replacement criteria file (default app/agents/planner/promotion.md)
    visual_model: str | None = None            # visual agent (Visualizer); None = the agent file's model (haiku)
    pilot_model: str | None = None             # CLI chat; None = the agent file's model (sonnet)
    question_timeout_s: float = 180            # timed builder questions auto-answer after this
    permission_timeout_s: float = 180          # builder permission cards are DENIED after this (separate setting)
    autopilot_default: bool = False            # new sessions start with autopilot on/off
    builder_turn_timeout_s: float | None = None    # builder turns include user waits -> no limit; Stop ends a run
    orchestrator_nudges: int = 2               # turns without run_builder/write_report before the run fails
    builder_runs_per_step: int = 2             # cap on builder runs = steps x this

    def __post_init__(self):
        self.project = Path(self.project).resolve()
