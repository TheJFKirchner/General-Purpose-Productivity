"""Repos panel back end (app/gitrepos.py + the hub's git_* messages): temporary repos only, never a real one.
Skipped as a whole when git is not installed."""
import asyncio
import subprocess
from pathlib import Path

import pytest

from app import gitrepos
from app.gitrepos import GitRepos, find_repos, parse_remote
from app.hub import Hub
from app.settings import Settings
from app.store import Store
from conftest import Client

pytestmark = pytest.mark.skipif(not gitrepos.available(), reason="git is not installed")


def git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args],
                       capture_output=True, text=True, check=True)
    return p.stdout.strip()


def make_repo(path: Path, files: dict | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")
    git(path, "config", "commit.gpgsign", "false")
    for rel, text in (files or {"a.txt": "one\ntwo\nthree\n", "b.txt": "b1\n", "c.txt": "c1\n"}).items():
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).write_text(text, encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "first")
    return path


def link(repo: Path, bare: Path) -> None:
    bare.mkdir(parents=True)
    git(bare, "init", "-q", "--bare", "-b", "main")
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "-q", "-u", "origin", "main")


def service(*folders: Path) -> GitRepos:
    return GitRepos(lambda: [{"dir_id": f"d{i}", "path": str(f), "name": f.name} for i, f in enumerate(folders)])


def only(svc: GitRepos, folder_repo: Path | None = None) -> dict:
    ev = svc.scan()
    assert ev["available"] is True
    assert len(ev["repos"]) == 1, ev
    return ev["repos"][0]


def paths(repo: dict) -> dict:
    return {f["path"]: f for f in repo["files"]}


# ------------------------------------------------------------------ status
def test_clean_repo_not_linked(tmp_path):
    r = make_repo(tmp_path / "proj")
    repo = only(service(r))
    assert repo["clean"] and repo["files"] == [] and repo["branch"] == "main"
    assert repo["remote"] is None and repo["upstream"] is None and repo["linked"] is False
    assert (repo["ahead"], repo["behind"], repo["added"], repo["removed"]) == (0, 0, 0, 0)
    assert repo["rel"] == "." and repo["name"] == "proj" and repo["error"] is None


def test_modified_untracked_deleted_counts(tmp_path):
    r = make_repo(tmp_path / "proj")
    (r / "a.txt").write_text("one\nTWO\nthree\nfour\n", encoding="utf-8")        # +2 -1
    (r / "new.txt").write_text("x\ny\nz", encoding="utf-8")                      # untracked: 3 lines, no final newline
    (r / "b.txt").unlink()                                                       # deleted: -1
    (r / "blob.bin").write_bytes(b"\x00\x01\x02binary")                          # untracked binary
    repo = only(service(r))
    f = paths(repo)
    assert not repo["clean"]
    assert (f["a.txt"]["status"], f["a.txt"]["added"], f["a.txt"]["removed"]) == ("M", 2, 1)
    assert (f["new.txt"]["status"], f["new.txt"]["added"], f["new.txt"]["removed"]) == ("?", 3, 0)
    assert (f["b.txt"]["status"], f["b.txt"]["added"], f["b.txt"]["removed"]) == ("D", 0, 1)
    assert f["blob.bin"]["binary"] is True and f["blob.bin"]["added"] == 0
    assert (repo["added"], repo["removed"]) == (5, 2)


def test_staged_new_file_and_tracked_binary(tmp_path):
    r = make_repo(tmp_path / "proj", {"a.txt": "a\n", "img.bin": "x"})
    (r / "img.bin").write_bytes(b"\x00\x00new")
    (r / "staged.txt").write_text("s1\ns2\n", encoding="utf-8")
    git(r, "add", "staged.txt")
    f = paths(only(service(r)))
    assert (f["staged.txt"]["status"], f["staged.txt"]["added"]) == ("A", 2)
    assert f["img.bin"]["binary"] is True and f["img.bin"]["added"] == 0


def test_repo_without_commits(tmp_path):
    r = tmp_path / "fresh"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    (r / "n.txt").write_text("1\n2\n", encoding="utf-8")
    repo = only(service(r))
    assert repo["error"] is None and paths(repo)["n.txt"]["added"] == 2


def test_remote_display_has_no_credentials(tmp_path):
    r = make_repo(tmp_path / "proj")
    git(r, "remote", "add", "origin", "https://user:s3cret@github.com/acme/widgets.git")
    repo = only(service(r))
    assert repo["remote"] == {"name": "origin", "host": "github.com", "owner": "acme", "repo": "widgets"}
    assert "s3cret" not in str(repo) and repo["linked"] is False          # a remote but no upstream branch yet


def test_parse_remote_forms():
    assert parse_remote("o", "git@github.com:acme/widgets.git") == {"name": "o", "host": "github.com", "owner": "acme", "repo": "widgets"}
    assert parse_remote("o", "ssh://git@host.example:2222/grp/sub/proj.git")["owner"] == "grp/sub"
    assert parse_remote("o", "https://tok@gitlab.com/a/b")["host"] == "gitlab.com"
    local = parse_remote("o", "C:\\data\\remotes\\shop.git")
    assert local["host"] == "" and local["repo"] == "shop" and "data" not in str(local)


def test_error_text_loses_credentials():
    t = gitrepos.clean_text("fatal: unable to access 'https://me:pw@example.com/x.git/': boom\n")
    assert "pw" not in t and "me:" not in t and "example.com" in t


# ------------------------------------------------------------------ detection
def test_detection_rules(tmp_path):
    root = tmp_path / "work"
    make_repo(root / "top")                                   # level 1
    make_repo(root / "group" / "deep")                        # level 2
    make_repo(root / "a" / "b" / "too-deep")                  # level 3: not found
    make_repo(root / "node_modules" / "dep")                  # skipped
    make_repo(root / ".venv" / "pkg")
    make_repo(root / "env" / "pkg")
    make_repo(root / ".launchpad" / "s")
    make_repo(root / "top" / "inner")                         # inside a repo: never entered
    found = sorted(p.relative_to(root).as_posix() for p in find_repos(root))
    assert found == ["group/deep", "top"]


def test_folder_that_is_a_repo_is_itself_and_not_descended(tmp_path):
    r = make_repo(tmp_path / "proj")
    make_repo(r / "sub")
    assert find_repos(r) == [r]


def test_same_repo_in_two_connected_folders_listed_once(tmp_path):
    root = tmp_path / "work"
    r = make_repo(root / "shop")
    ev = service(root, r).scan()                              # the parent folder and the repo itself
    assert len(ev["repos"]) == 1
    assert ev["repos"][0]["dir_id"] == "d0" and ev["repos"][0]["rel"] == "shop"


def test_ids_are_stable_and_unknown_ids_refused(tmp_path):
    r = make_repo(tmp_path / "proj")
    svc = service(r)
    a, b = only(svc), only(svc)
    assert a["repo_id"] == b["repo_id"]
    res = svc.run("commit", {"repo_id": str(r), "message": "x", "paths": ["a.txt"]})     # a path is not an id
    assert res["ok"] is False and res["repo"] is None
    assert svc.run("refresh", {"repo_id": "nope"})["ok"] is False


# ------------------------------------------------------------------ commit
def test_commit_subset_leaves_the_rest_uncommitted(tmp_path):
    r = make_repo(tmp_path / "proj")
    (r / "a.txt").write_text("changed\n", encoding="utf-8")
    (r / "new.txt").write_text("fresh\n", encoding="utf-8")
    (r / "b.txt").unlink()
    git(r, "add", "c.txt")                                    # an unrelated staged state must stay as it is
    (r / "c.txt").write_text("c2\n", encoding="utf-8")
    git(r, "add", "c.txt")
    svc = service(r)
    rid = only(svc)["repo_id"]
    res = svc.run("commit", {"repo_id": rid, "message": "  Change a and drop b  ", "paths": ["a.txt", "b.txt"]})
    assert res["ok"] and res["committed"], res
    assert git(r, "log", "-1", "--format=%s") == "Change a and drop b"
    assert sorted(git(r, "show", "--name-only", "--format=", "HEAD").split()) == ["a.txt", "b.txt"]
    left = paths(res["repo"])
    assert set(left) == {"new.txt", "c.txt"}
    assert git(r, "diff", "--cached", "--name-only") == "c.txt"                 # still staged, not committed


def test_failed_commit_leaves_the_index_as_it_was_and_identity_message_is_short(tmp_path, monkeypatch):
    r = make_repo(tmp_path / "proj")
    git(r, "config", "--unset", "user.name")
    git(r, "config", "--unset", "user.email")
    git(r, "config", "user.useConfigOnly", "true")            # no identity anywhere: the commit must fail
    nothing = tmp_path / "empty-gitconfig"
    nothing.write_text("", encoding="utf-8")
    for k, v in {"HOME": str(tmp_path), "USERPROFILE": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path),
                 "GIT_CONFIG_GLOBAL": str(nothing), "GIT_CONFIG_NOSYSTEM": "1"}.items():
        monkeypatch.setenv(k, v)
    for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL"):
        monkeypatch.delenv(k, raising=False)
    (r / "c.txt").write_text("c2\n", encoding="utf-8")
    git(r, "add", "c.txt")                                    # staged by the user: stays staged
    (r / "a.txt").write_text("changed\n", encoding="utf-8")
    (r / "new.txt").write_text("fresh\n", encoding="utf-8")
    svc = service(r)
    rid = only(svc)["repo_id"]
    head = git(r, "rev-parse", "HEAD")
    res = svc.run("commit", {"repo_id": rid, "message": "msg", "paths": ["a.txt", "new.txt"]})
    assert not res["ok"] and not res["committed"], res
    assert res["message"] == gitrepos.IDENTITY_MSG
    assert git(r, "diff", "--cached", "--name-only") == "c.txt"               # a.txt / new.txt unstaged again
    state = git(r, "status", "--porcelain=v1", "--untracked-files=all")        # (git() strips the first column)
    assert sorted(l for l in state.splitlines() if "b.txt" not in l) == ["?? new.txt", "M  c.txt", "M a.txt"]
    assert git(r, "rev-parse", "HEAD") == head


def test_commit_needs_message_and_paths(tmp_path):
    r = make_repo(tmp_path / "proj")
    (r / "a.txt").write_text("changed\n", encoding="utf-8")
    svc = service(r)
    rid = only(svc)["repo_id"]
    assert svc.run("commit", {"repo_id": rid, "message": "   ", "paths": ["a.txt"]})["ok"] is False
    assert svc.run("commit", {"repo_id": rid, "message": "m", "paths": []})["ok"] is False
    assert svc.run("commit", {"repo_id": rid, "message": "m", "paths": "a.txt"})["ok"] is False
    assert git(r, "rev-list", "--count", "HEAD") == "1"


def test_paths_outside_the_repo_or_not_changed_are_refused(tmp_path):
    r = make_repo(tmp_path / "proj")
    (tmp_path / "secret.txt").write_text("outside\n", encoding="utf-8")
    (r / "a.txt").write_text("changed\n", encoding="utf-8")
    svc = service(r)
    rid = only(svc)["repo_id"]
    for bad in ("../secret.txt", str(tmp_path / "secret.txt"), "sub/../../secret.txt", "*", ":/", "b.txt", ".git/config"):
        res = svc.run("commit", {"repo_id": rid, "message": "m", "paths": ["a.txt", bad]})
        assert res["ok"] is False and "Refused" in res["message"], (bad, res)
    assert git(r, "rev-list", "--count", "HEAD") == "1"
    assert git(r, "diff", "--cached", "--name-only") == ""                       # nothing was staged either


def test_first_commit_in_an_empty_repo(tmp_path):
    r = tmp_path / "fresh"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.name", "T")
    git(r, "config", "user.email", "t@example.invalid")
    (r / "n.txt").write_text("1\n", encoding="utf-8")
    svc = service(r)
    res = svc.run("commit", {"repo_id": only(svc)["repo_id"], "message": "start", "paths": ["n.txt"]})
    assert res["ok"], res
    assert res["repo"]["clean"] is True


def test_git_error_text_is_passed_back(tmp_path):
    r = make_repo(tmp_path / "proj")
    hook = r / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'blocked by test hook' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    (r / "a.txt").write_text("changed\n", encoding="utf-8")
    svc = service(r)
    res = svc.run("commit", {"repo_id": only(svc)["repo_id"], "message": "m", "paths": ["a.txt"]})
    assert res["ok"] is False and res["committed"] is False
    assert res["repo"] is not None


# ------------------------------------------------------------------ remote: ahead / behind / fetch / push
def test_ahead_behind_fetch_and_push(tmp_path):
    r = make_repo(tmp_path / "proj")
    link(r, tmp_path / "remote.git")
    svc = service(r)
    repo = only(svc)
    rid = repo["repo_id"]
    assert repo["linked"] and repo["upstream"] == "origin/main" and (repo["ahead"], repo["behind"]) == (0, 0)
    assert repo["remote"]["repo"] == "remote" and repo["remote"]["host"] == ""

    (r / "a.txt").write_text("mine\n", encoding="utf-8")                          # ahead by one
    res = svc.run("commit", {"repo_id": rid, "message": "mine", "paths": ["a.txt"]})
    assert res["ok"] and res["repo"]["ahead"] == 1
    # a second clone pushes one commit: behind is only known after "Check remote" (fetch)
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(tmp_path / "remote.git"), str(other))
    (other / "o.txt").write_text("o\n", encoding="utf-8")
    git(other, "add", "o.txt")
    git(other, "commit", "-q", "-m", "other")
    git(other, "push", "-q", "origin", "main")
    assert svc.run("refresh", {"repo_id": rid})["repo"]["behind"] == 0
    fetched = svc.run("fetch", {"repo_id": rid})
    assert fetched["ok"] and (fetched["repo"]["ahead"], fetched["repo"]["behind"]) == (1, 1)
    # diverged: a plain push is refused by git, its text comes back, and nothing is forced
    refused = svc.run("push", {"repo_id": rid})
    assert refused["ok"] is False and refused["message"]
    assert git(tmp_path / "remote.git", "log", "-1", "--format=%s", "main") == "other"
    # catch up by hand (the app never pulls), then push alone
    git(r, "pull", "-q", "--no-rebase", "--no-edit", "origin", "main")
    pushed = svc.run("push", {"repo_id": rid})
    assert pushed["ok"] and pushed["repo"]["ahead"] == 0
    assert svc.run("push", {"repo_id": rid})["message"] == "Nothing to push."


def test_commit_and_push(tmp_path):
    r = make_repo(tmp_path / "proj")
    link(r, tmp_path / "remote.git")
    (r / "a.txt").write_text("v2\n", encoding="utf-8")
    (r / "keep.txt").write_text("stay\n", encoding="utf-8")
    svc = service(r)
    rid = only(svc)["repo_id"]
    res = svc.run("commit", {"repo_id": rid, "message": "ship it", "paths": ["a.txt"], "push": True})
    assert res["ok"] and res["committed"] and res["message"].startswith("Committed.")
    assert git(tmp_path / "remote.git", "log", "-1", "--format=%s", "main") == "ship it"
    assert set(paths(res["repo"])) == {"keep.txt"} and res["repo"]["ahead"] == 0


def test_commit_and_push_failure_keeps_the_commit(tmp_path):
    r = make_repo(tmp_path / "proj")
    link(r, tmp_path / "remote.git")
    git(r, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    (r / "a.txt").write_text("v2\n", encoding="utf-8")
    svc = service(r)
    res = svc.run("commit", {"repo_id": only(svc)["repo_id"], "message": "m", "paths": ["a.txt"], "push": True})
    assert res["ok"] is False and res["committed"] is True and res["message"].startswith("Committed, but the push failed")


def test_not_linked_refuses_fetch_and_push(tmp_path):
    r = make_repo(tmp_path / "proj")
    svc = service(r)
    rid = only(svc)["repo_id"]
    for op in ("fetch", "push"):
        res = svc.run(op, {"repo_id": rid})
        assert res["ok"] is False and "not linked" in res["message"]


def test_git_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(gitrepos, "git_path", lambda: None)
    svc = service(tmp_path)
    assert svc.scan() == {"type": "git_repos", "available": False, "repos": []}
    res = svc.run("refresh", {"repo_id": "x"})
    assert res["ok"] is False and "not installed" in res["message"]


# ------------------------------------------------------------------ through the hub
def test_hub_messages(tmp_path):
    root = tmp_path / "work"
    r = make_repo(root / "shop")
    (r / "a.txt").write_text("hub\n", encoding="utf-8")

    async def go():
        store = Store(tmp_path / "home" / "settings.json")
        store.add(root)
        hub = Hub(Settings(project=root, engine="fake"), store=store)
        c = Client(hub)
        await hub.connect(c)
        await hub.handle({"type": "git_scan"})
        scan = c.of("git_repos")[-1]
        assert scan["available"] and [x["name"] for x in scan["repos"]] == ["shop"]
        rid = scan["repos"][0]["repo_id"]
        await hub.handle({"type": "git_commit", "repo_id": rid, "message": "via hub", "paths": ["a.txt"]})
        res = c.of("git_result")[-1]
        assert res["op"] == "commit" and res["ok"] and res["repo"]["clean"]
        await hub.handle({"type": "git_refresh", "repo_id": "bogus"})
        assert c.of("git_result")[-1]["ok"] is False
        await hub.close()

    asyncio.run(go())
    assert git(r, "log", "-1", "--format=%s") == "via hub"
