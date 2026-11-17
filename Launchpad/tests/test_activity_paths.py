"""Activity summaries never carry an absolute path: relative to the folder the file belongs to, or to the app folder."""
from pathlib import Path

from app import activity


def test_paths_are_relative_to_their_folder_or_the_app_folder(tmp_path):
    proj, other = tmp_path / "proj", tmp_path / "other"
    (proj / "a").mkdir(parents=True)
    (other / "skills").mkdir(parents=True)
    f1, f2 = proj / "a" / "x.md", other / "skills" / "s.md"
    assert activity.summarize("Read", {"file_path": str(f1)}, [proj, other]) == "a/x.md"
    assert activity.summarize("Read", {"file_path": str(f2)}, [proj, other]) == "skills/s.md"
    built_in = activity.APP_DIR / "app" / "agents" / "builder" / "agent.md"
    assert activity.summarize("Read", {"file_path": str(built_in)}, [proj]) == "app/agents/builder/agent.md"
    assert activity.summarize("Glob", {"pattern": "*.md", "path": str(other / "skills")}, [other]) == "*.md in skills"


def test_a_path_outside_every_known_folder_is_never_absolute(tmp_path):
    outside = tmp_path / "elsewhere" / "deep" / "y.md"
    s = activity.summarize("Read", {"file_path": str(outside)}, [tmp_path / "proj"])
    assert s == ".../deep/y.md"
    assert not Path(s).is_absolute() and ":" not in s
