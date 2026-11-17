"""Per-user settings store: connected working directories + the settings that used to be launch-only.

- File: <home>/.launchpad/settings.json (outside every project and out of git); env LAUNCHPAD_HOME moves the
  whole per-user folder (tests, the fake demo). path=None = in memory only (nothing persists)
- Directories: [{dir_id, path, name}], dir_id = stable hash of the resolved path; default = the last used
- Values: SPECS below; launch options override them for one launch (not saved); a change from the page is saved
  and takes effect at once (also over a launch option)
- applies: "now" = read live (next question / permission card / render); "new_sessions" = read when a planner
  session or chat starts (a planner session nobody has written to yet is reloaded with the new planner settings)
- planner_harness / planner_start_model / planner_auto_promote: also set from the planner's picker
  (app/agents/planner/choices.py)
- pilot_harness / pilot_model: also set from the CLI chat's picker (app/agents/claude_code/choices.py); pilot_harness
  None = the launch engine's CLI
- Agent use counter: agent_uses {agent name: count}; +1 each time an agent is started (app/hub.py count_use);
  starts from zero, survives restarts
- additional_dir_ids [dir_id]: folders ticked as "additional" (global; a session uses them minus its primary)
- agent_skills {agent name: "all" | [skill names]}: per-agent skill allowlist (defaults in app/skills.py)
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

# name -> (type, default, applies)
SPECS: dict[str, tuple[type, object, str]] = {
    "question_timeout_s": (float, 180.0, "now"),
    "permission_timeout_s": (float, 180.0, "now"),
    "autopilot_default": (bool, False, "new_sessions"),
    "planner_start_model": (str, "sonnet", "new_sessions"),
    "planner_top_model": (str, "opus", "new_sessions"),
    "planner_harness": (str, "claude", "new_sessions"),
    "planner_auto_promote": (bool, True, "new_sessions"),
    "promotion_window_turns": (int, 2, "new_sessions"),
    "promotion_criteria_path": (str, None, "new_sessions"),
    "pilot_model": (str, None, "new_sessions"),
    "pilot_harness": (str, None, "new_sessions"),
    "visual_model": (str, None, "now"),
}


def launchpad_home() -> Path:
    """Per-user Launchpad folder (settings, backups)."""
    env = os.environ.get("LAUNCHPAD_HOME")
    return Path(env).expanduser() if env else Path.home() / ".launchpad"


def dir_id(path: Path) -> str:
    return "d" + hashlib.sha1(str(Path(path).resolve()).lower().encode("utf-8")).hexdigest()[:8]


def coerce(name: str, value):
    """Validate one setting value -> its typed value (ValueError with a plain message)."""
    if name not in SPECS:
        raise ValueError(f"unknown setting {name!r}")
    typ, default, _ = SPECS[name]
    if value is None or value == "":
        if default is None:
            return None
        raise ValueError(f"{name} needs a value")
    if typ is bool:
        if isinstance(value, bool):
            return value
        if str(value).lower() in ("true", "1", "on", "yes"):
            return True
        if str(value).lower() in ("false", "0", "off", "no"):
            return False
        raise ValueError(f"{name} must be true or false")
    if typ in (int, float):
        try:
            v = typ(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a number") from None
        if v < (0 if typ is int else 1):
            raise ValueError(f"{name} is too small")
        return v
    return str(value).strip()


class Store:
    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None
        self.data = {"version": 1, "directories": [], "default_dir": None, "values": {}, "agent_uses": {},
                     "additional_dir_ids": [], "agent_skills": {}}
        if self.path and self.path.is_file():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update({k: loaded[k] for k in ("directories", "default_dir", "values", "agent_uses",
                                                             "additional_dir_ids", "agent_skills") if k in loaded})
                    for k, typ in (("agent_uses", dict), ("agent_skills", dict), ("additional_dir_ids", list)):
                        if not isinstance(self.data.get(k), typ):
                            self.data[k] = typ()
            except (OSError, ValueError):
                pass                                        # a broken file starts fresh (and is overwritten on save)

    @classmethod
    def default(cls) -> "Store":
        return cls(launchpad_home() / "settings.json")

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix="settings-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=1)
        os.replace(tmp, self.path)

    # ---------------------------------------------------------------- directories
    def directories(self) -> list[dict]:
        return list(self.data["directories"])

    def get(self, did: str | None) -> dict | None:
        return next((d for d in self.data["directories"] if d["dir_id"] == did), None)

    def find(self, path) -> dict | None:
        return self.get(dir_id(Path(path)))

    def add(self, path) -> dict:
        p = Path(str(path).strip().strip('"')).expanduser()
        if not str(path).strip():
            raise ValueError("give a folder path")
        if not p.is_dir():
            raise ValueError(f"not a folder: {p}")
        p = p.resolve()
        found = self.find(p)
        if found:
            return found
        entry = {"dir_id": dir_id(p), "path": str(p), "name": p.name or str(p)}
        self.data["directories"].append(entry)
        if not self.data.get("default_dir"):
            self.data["default_dir"] = entry["dir_id"]
        self.save()
        return entry

    def remove(self, did: str) -> None:
        if not self.get(did):
            raise ValueError("that folder is not in the list")
        if len(self.data["directories"]) == 1:
            raise ValueError("keep at least one folder connected")
        self.data["directories"] = [d for d in self.data["directories"] if d["dir_id"] != did]
        self.data["additional_dir_ids"] = [x for x in self.data.get("additional_dir_ids") or [] if x != did]
        if self.data.get("default_dir") == did:
            self.data["default_dir"] = self.data["directories"][0]["dir_id"]
        self.save()

    def default_id(self) -> str | None:
        did = self.data.get("default_dir")
        return did if self.get(did) else (self.data["directories"][0]["dir_id"] if self.data["directories"] else None)

    def set_default(self, did: str) -> None:
        if self.get(did) and self.data.get("default_dir") != did:
            self.data["default_dir"] = did
            self.save()

    # ---------------------------------------------------------------- additional folders
    def additional_ids(self) -> list[str]:
        """Connected folders ticked as additional (unknown ids dropped), in the connected-folders order."""
        ticked = set(self.data.get("additional_dir_ids") or [])
        return [d["dir_id"] for d in self.data["directories"] if d["dir_id"] in ticked]

    def set_additional(self, ids) -> list[str]:
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            raise ValueError("additional_dir_ids must be a list of folder ids")
        unknown = [x for x in ids if not self.get(x)]
        if unknown:
            raise ValueError("that folder is not connected")
        self.data["additional_dir_ids"] = list(dict.fromkeys(ids))
        self.save()
        return self.additional_ids()

    # ---------------------------------------------------------------- agent skills
    def agent_skills(self) -> dict:
        """Agent name -> "all" | [skill names] (only agents whose setting was changed)."""
        return dict(self.data.get("agent_skills") or {})

    def set_agent_skills(self, name: str, value) -> None:
        """value: "all" | [names] (already checked by app/skills.py clean_setting)."""
        if not str(name or "").strip():
            raise ValueError("give the agent name")
        self.data.setdefault("agent_skills", {})[str(name)] = value
        self.save()

    # ---------------------------------------------------------------- values
    def values(self) -> dict:
        out = {k: spec[1] for k, spec in SPECS.items()}
        for k, v in (self.data.get("values") or {}).items():
            if k in SPECS:
                try:
                    out[k] = coerce(k, v)
                except ValueError:
                    pass
        return out

    def set_values(self, patch: dict) -> dict:
        clean = {k: coerce(k, v) for k, v in (patch or {}).items()}
        self.data.setdefault("values", {}).update(clean)
        self.save()
        return clean

    # ---------------------------------------------------------------- agent use counter
    def uses(self) -> dict[str, int]:
        """Agent name -> times started (only agents started at least once)."""
        out = {}
        for k, v in (self.data.get("agent_uses") or {}).items():
            try:
                out[str(k)] = max(0, int(v))
            except (TypeError, ValueError):
                continue
        return out

    def add_use(self, name: str) -> int:
        """One more start of agent `name` (saved at once) -> its new count."""
        counts = self.data.setdefault("agent_uses", {})
        try:
            n = max(0, int(counts.get(name, 0))) + 1
        except (TypeError, ValueError):
            n = 1
        counts[name] = n
        self.save()
        return n
