"""The fake engine's Claude Code permission-rule matcher (agentlib/fake/rules.py)."""
from pathlib import Path

import pytest

from agentlib.fake.rules import allowed, command_matches, denied, domain_matches, path_matches


@pytest.mark.parametrize("pattern, command, ok", [
    ("npm run build", "npm run build", True),
    ("npm run build", "npm run build --watch", False),
    ("npm run *", "npm run test --watch", True),
    ("npm run *", "npm run", True),
    ("npm run *", "npm install", False),
    ("git log * main", "git log --oneline main", True),
    ("git log * main", "git log main", False),
    ("* --version", "node --version", True),
    ("* --version", "node -v", False),
    ("ls *", "lsof", False),
    ("ls*", "lsof", True),
    ("ls:*", "ls", True),
    ("* --help *", "npm --help", False),
    ("git:* push", "git status push", False),          # ':*' is only special at the end
])
def test_command_patterns(pattern, command, ok):
    assert command_matches(pattern, command) is ok


def test_path_anchors(tmp_path):
    cwd = tmp_path
    (cwd / "src").mkdir()
    assert path_matches("src/**", str(cwd / "src" / "a.ts"), cwd)
    assert not path_matches("src/**", str(cwd / "vendor" / "src" / "a.ts"), cwd)
    assert path_matches("src/**", str(cwd / "vendor" / "src" / "a.ts"), cwd, deny=True)
    assert path_matches("/src/**", "src/a.ts", cwd)                      # relative input -> from cwd
    assert path_matches(".env", str(cwd / "a" / "b" / ".env"), cwd)     # no slash: any depth
    assert path_matches("*.py", str(cwd / "pkg" / "m.py"), cwd)
    assert not path_matches("*.py", str(cwd.parent / "m.py"), cwd)      # outside the anchor
    assert path_matches("secrets", str(cwd / "secrets" / "k.txt"), cwd) # directory covers its contents
    assert path_matches("~/notes/*.md", str(Path.home() / "notes" / "x.md"), cwd)
    absolute = "//" + Path(cwd).resolve().as_posix().lstrip("/")
    if absolute[3:4] == ":":                                             # Windows: //C:/x -> //c/x
        absolute = "//" + absolute[2].lower() + absolute[4:]
    assert path_matches(absolute + "/**", str(cwd / "deep" / "f"), cwd)


def test_read_and_edit_rule_coverage(tmp_path):
    f = {"file_path": str(tmp_path / "docs" / "a.md")}
    assert allowed(["Edit(docs/**)"], "Write", f, tmp_path)
    assert allowed(["Edit(docs/**)"], "NotebookEdit", {"notebook_path": f["file_path"]}, tmp_path)
    assert not allowed(["Write(docs/**)"], "Write", f, tmp_path)         # Write(path) rules never match
    assert not allowed(["Grep(docs/**)"], "Grep", {"path": str(tmp_path / "docs")}, tmp_path)
    assert allowed(["Read(docs/**)"], "Grep", {"path": str(tmp_path / "docs")}, tmp_path)
    assert denied(["Read(docs/**)"], "Edit", f, tmp_path)                 # Read deny also blocks edits
    assert not allowed(["Read(docs/**)"], "Edit", f, tmp_path)
    assert allowed(["Read"], "Read", f, tmp_path) and not allowed(["Read"], "Grep", f, tmp_path)


@pytest.mark.parametrize("spec, url, ok", [
    ("domain:example.com", "https://example.com/x", True),
    ("domain:example.com", "https://api.example.com/x", False),
    ("domain:*.example.com", "https://a.b.example.com", True),
    ("domain:*.example.com", "https://example.com", False),
    ("domain:example.*", "https://example.org", True),
    ("domain:example.*", "https://example.evil.com", False),
    ("domain:*", "https://anything.test", True),
    ("domain:EXAMPLE.com.", "https://example.COM", True),
])
def test_webfetch_domains(spec, url, ok):
    assert domain_matches(spec, url) is ok


def test_mcp_rules():
    t = "mcp__db__get_rows"
    assert allowed(["mcp__db"], t, {}) and allowed(["mcp__db__*"], t, {}) and allowed(["mcp__db__get_*"], t, {})
    assert allowed([t], t, {}) and not allowed(["mcp__other__*"], t, {}) and not allowed(["mcp__db__put_*"], t, {})


def test_deny_parameter_rules():
    assert denied(["Bash(run_in_background:true)"], "Bash", {"command": "sleep 9", "run_in_background": True})
    assert not denied(["Bash(run_in_background:true)"], "Bash", {"command": "sleep 9"})
    assert denied(["Bash(rm *)"], "Bash", {"command": "cd x && rm -rf y"})    # any subcommand
