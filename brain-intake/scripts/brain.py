#!/usr/bin/env python3
"""brain.py - script half of brain intake and BrainCite.

Standard library only. No model calls. Every path it prints is relative to
the wiki root (the one exception is `brain.py root`).
Formats it reads and writes are defined in brain-reference.md.
"""

import argparse
import fnmatch
import hashlib
import io
import json
import os
import re
import shutil
import sys
from datetime import date, datetime

# =========================================================================
# CONFIG - every setup-specific name lives here.
# Override any key with a brain-config.json file inside the wiki root
# (or pass --config PATH). Paths are relative to the wiki root and use "/".
# =========================================================================
CONFIG = {
    "wiki_root": "",                      # "" = use --wiki, $BRAIN_WIKI, or the current folder
    "personal_dir": "personal",
    "team_dir": "team",
    "personal_rules": "personal/rules.md",
    "team_rules": "team/rules.md",
    "personal_tags": "personal/tags.md",
    "team_tags": "team/tags.md",
    "templates_dir": "team/templates",
    "dictionary_patterns": ["*-dictionary.md", "*.dictionary.md"],
    "raw_dir": "personal/raw",
    "session_facts_dir": "personal/raw/session-facts",
    "processed_dir": "personal/raw/processed",
    "sources_dir": "personal/sources",
    "work_dir": "brain-work",                 # page list, packets, log
    "skip_folder_names": ["skills", "agents", "sql", "templates", "sources", "raw", "brain-work"],
    "page_line_limit": 150,
    "doubt_tags": ["#verify", "#hunch"],  # promote --show flags these; stripping one is warned
    "section_level": 2,                   # heading level indexed by `sections`
    "dictionaries_in_sections": False,    # True = sections/section may show dictionaries (read-only)
}
CONFIG_FILE_NAME = "brain-config.json"
# =========================================================================

EXIT_OK, EXIT_INVALID, EXIT_USAGE, EXIT_MISSING = 0, 1, 2, 3

TAG_RE = re.compile(r"(?<![\w&/#])#([A-Za-z][\w-]*)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
BULLET_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
REC_PAGE_RE = re.compile(r"^##\s+\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]\s*(?:>\s*(.*?))?\s*$")
REC_NEW_RE = re.compile(r"^##\s+New page:\s*(.+?)\s*$", re.I)
REC_UNPLACED_RE = re.compile(r"^##\s+Unplaced\s*$", re.I)
REC_WARN_RE = re.compile(r"^##\s+Warnings\s*$", re.I)
BAD_NAME_RE = re.compile(r'[\\/:*?"<>|\[\]#]')
STRUCK = "[struck]"
TEAM_LINK_PREFIX = "Team page:"


class BrainError(Exception):
    def __init__(self, msg, code=EXIT_INVALID):
        Exception.__init__(self, msg)
        self.msg = msg
        self.code = code


# ------------------------------------------------------------------ files

def read_lines(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read().split("\n")


def write_lines(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def parse_frontmatter(lines):
    """Return (dict, index of first body line). Simple `key: value` only."""
    fm = {}
    if not lines or lines[0].strip() != "---":
        return fm, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            for ln in lines[1:i]:
                if ":" in ln and not ln.startswith((" ", "\t", "-")):
                    k, v = ln.split(":", 1)
                    fm[k.strip().lower()] = v.strip().strip('"').strip("'")
            return fm, i + 1
    return {}, 0


def set_frontmatter(lines, key, value):
    """Set key in frontmatter (in place); create frontmatter if absent."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                for j in range(1, i):
                    if re.match(r"^%s\s*:" % re.escape(key), lines[j], re.I):
                        lines[j] = "%s: %s" % (key, value)
                        return lines
                lines.insert(i, "%s: %s" % (key, value))
                return lines
    lines[0:0] = ["---", "%s: %s" % (key, value), "---", ""]
    return lines


def headings(lines, start=0):
    """List of (index, level, text) outside fenced code blocks."""
    out, fence = [], False
    for i in range(start, len(lines)):
        s = lines[i].strip()
        if s.startswith("```") or s.startswith("~~~"):
            fence = not fence
            continue
        if fence:
            continue
        m = HEADING_RE.match(lines[i])
        if m:
            out.append((i, len(m.group(1)), m.group(2).strip()))
    return out


def section_span(lines, hs, k):
    """End index (exclusive) of heading hs[k], trailing blanks trimmed."""
    idx, level, _ = hs[k]
    end = len(lines)
    for j in range(k + 1, len(hs)):
        if hs[j][1] <= level:
            end = hs[j][0]
            break
    while end > idx + 1 and not lines[end - 1].strip():
        end -= 1
    return end


def body_count(lines, idx, end):
    """Lines in a section body (after the heading), leading blank lines not counted."""
    start = idx + 1
    while start < end and not lines[start].strip():
        start += 1
    return end - start


def tags_in(text):
    return {t.lower() for t in TAG_RE.findall(text)}


def find_heading(lines, heading):
    """Return (headings, [indexes into headings matching heading text, level 2-6])."""
    _, body = parse_frontmatter(lines)
    hs = headings(lines, body)
    want = heading.strip().lstrip("#").strip().lower()
    return hs, [k for k, h in enumerate(hs) if h[1] >= 2 and h[2].lower() == want]


def _singular(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("sses", "xes", "zes", "ches", "shes")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def name_keys(name):
    words = [_singular(w) for w in re.split(r"[^a-z0-9]+", name.lower()) if w]
    return {"".join(words), " ".join(sorted(words))}


def near_matches(name, pages):
    """Pages whose name is the same slug, or differs only by plural, hyphens/spaces or word order."""
    keys = name_keys(name)
    return [p for p in pages if p.name.lower() != name.strip().lower() and name_keys(p.name) & keys]


# ------------------------------------------------------------------- wiki

class Page(object):
    def __init__(self, name, side, rel, description, twin_of, nlines, dictionary=False):
        self.name, self.side, self.rel = name, side, rel
        self.description, self.twin_of = description, twin_of
        self.nlines, self.dictionary = nlines, dictionary


class Wiki(object):
    def __init__(self, root, cfg):
        self.root = os.path.abspath(root)
        self.cfg = cfg

    def p(self, rel):
        return os.path.join(self.root, *[x for x in rel.split("/") if x])

    def rel(self, path):
        return os.path.relpath(os.path.abspath(path), self.root).replace(os.sep, "/")

    def c(self, key):
        return self.cfg[key]

    def work(self, *parts):
        return self.p("/".join([self.c("work_dir")] + list(parts)))

    def is_dictionary_file(self, filename):
        f = filename.lower()
        return any(fnmatch.fnmatch(f, pat.lower()) for pat in self.c("dictionary_patterns"))

    def scan(self):
        """Return (pages, dictionaries)."""
        pages, dicts = [], []
        skip_paths = {self.c(k).strip("/").lower() for k in
                      ("templates_dir", "raw_dir", "sources_dir", "work_dir",
                       "processed_dir", "session_facts_dir")}
        skip_names = {n.lower() for n in self.c("skip_folder_names")}
        skip_files = {self.c(k).strip("/").lower() for k in
                      ("personal_rules", "team_rules", "personal_tags", "team_tags")}
        for side in ("personal", "team"):
            base = self.p(self.c(side + "_dir"))
            for dirpath, dirnames, filenames in os.walk(base):
                reld = self.rel(dirpath)
                dirnames[:] = sorted(
                    d for d in dirnames
                    if not d.startswith(".") and d.lower() not in skip_names
                    and (reld + "/" + d).lower() not in skip_paths)
                for fn in sorted(filenames):
                    if not fn.lower().endswith(".md"):
                        continue
                    relf = reld + "/" + fn
                    if relf.lower() in skip_files:
                        continue
                    page = self.load_page(relf, side)
                    if self.is_dictionary_file(fn):
                        page.dictionary = True
                        dicts.append(page)
                    else:
                        pages.append(page)
        return pages, dicts

    def load_page(self, rel, side):
        lines = read_lines(self.p(rel))
        fm, body = parse_frontmatter(lines)
        desc = fm.get("description", "")
        if not desc:
            for ln in lines[body:]:
                s = ln.strip()
                if s and not s.startswith("#") and not s.startswith(TEAM_LINK_PREFIX) and not s.startswith("```"):
                    desc = s.lstrip("-* ").strip()
                    break
        if len(desc) > 140:
            desc = desc[:137].rstrip() + "..."
        name = os.path.splitext(os.path.basename(rel))[0]
        n = len(lines) - (1 if lines and lines[-1] == "" else 0)
        return Page(name, side, rel, desc, fm.get("twin_of", ""), n)


def by_name(pages, name, side=None):
    n = name.strip().lower()
    return [p for p in pages if p.name.lower() == n and (side is None or p.side == side)]


def twin_map(pages):
    """team page name (lower) -> personal twin page."""
    out = {}
    for p in pages:
        if p.side == "personal" and p.twin_of:
            out[p.twin_of.strip().lower()] = p
    return out


# ----------------------------------------------------------------- config

def load_config_file(path, cfg):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except ValueError as e:
        raise BrainError("%s is not valid JSON (%s); fix the file" % (os.path.basename(path), e), EXIT_USAGE)
    if not isinstance(data, dict):
        raise BrainError("%s must hold one JSON object" % os.path.basename(path), EXIT_USAGE)
    for k, v in data.items():
        if k not in CONFIG:
            raise BrainError("%s: unknown key '%s'; allowed keys are those in the CONFIG block of brain.py"
                             % (os.path.basename(path), k), EXIT_USAGE)
        if type(v) is not type(CONFIG[k]):
            raise BrainError("%s: key '%s' must be %s" % (os.path.basename(path), k, type(CONFIG[k]).__name__),
                             EXIT_USAGE)
        cfg[k] = v
    return cfg


def open_wiki(args):
    cfg = dict(CONFIG)
    explicit = getattr(args, "config", None)
    if explicit:
        if not os.path.isfile(explicit):
            raise BrainError("config file not found: %s" % explicit, EXIT_MISSING)
        load_config_file(explicit, cfg)
        if cfg["wiki_root"] and not os.path.isabs(cfg["wiki_root"]):
            cfg["wiki_root"] = os.path.join(os.path.dirname(os.path.abspath(explicit)), cfg["wiki_root"])
    root = getattr(args, "wiki", None) or os.environ.get("BRAIN_WIKI") or cfg["wiki_root"]
    if not root:
        cwd = os.getcwd()
        if os.path.isfile(os.path.join(cwd, CONFIG_FILE_NAME)) or (
                os.path.isdir(os.path.join(cwd, cfg["personal_dir"])) and
                os.path.isdir(os.path.join(cwd, cfg["team_dir"]))):
            root = cwd
        else:
            raise BrainError("wiki root not found; pass --wiki PATH, set BRAIN_WIKI, or set wiki_root "
                             "in the CONFIG block of brain.py", EXIT_MISSING)
    if not os.path.isdir(root):
        raise BrainError("wiki root is not a folder: %s" % root, EXIT_MISSING)
    if not explicit and os.path.isfile(os.path.join(root, CONFIG_FILE_NAME)):
        load_config_file(os.path.join(root, CONFIG_FILE_NAME), cfg)
    w = Wiki(root, cfg)
    for k in ("personal_dir", "team_dir"):
        if not os.path.isdir(w.p(cfg[k])):
            raise BrainError("folder '%s' (config %s) not found under the wiki root; fix --wiki or %s"
                             % (cfg[k], k, CONFIG_FILE_NAME), EXIT_MISSING)
    return w


# ---------------------------------------------------------------- records

class RSection(object):
    def __init__(self, kind, name, lineno, section=""):
        self.kind, self.name, self.lineno, self.section = kind, name, lineno, section
        self.bullets = []  # [lineno, text, struck]

    def label(self):
        return "[[%s]]%s" % (self.name, " > " + self.section if self.section else "")

    def live(self):
        return [b for b in self.bullets if not b[2]]


class Record(object):
    def __init__(self, wiki, path):
        self.path = path
        self.rel = wiki.rel(path)
        self.stem = os.path.splitext(os.path.basename(path))[0]
        self.lines = read_lines(path)
        self.fm, body = parse_frontmatter(self.lines)
        self.status = self.fm.get("status", "").lower()
        self.origin = self.fm.get("origin", "").lower()
        self.sections, self.problems, self.summary = [], [], ""
        cur, fence = None, False
        for i in range(body, len(self.lines)):
            ln, no = self.lines[i], i + 1
            s = ln.strip()
            if s.startswith("```"):
                fence = not fence
                continue
            if fence or not s:
                continue
            if s.lower().startswith("summary:") and cur is None:
                self.summary = s[8:].strip()
                continue
            if HEADING_RE.match(ln):
                m = REC_PAGE_RE.match(ln)
                if m:
                    cur = RSection("page", m.group(1).strip(), no, (m.group(2) or "").strip().lstrip("#").strip())
                elif REC_NEW_RE.match(ln):
                    nm = REC_NEW_RE.match(ln).group(1).strip().strip("[]").strip()
                    cur = RSection("new", nm, no)
                elif REC_UNPLACED_RE.match(ln):
                    cur = RSection("unplaced", "", no)
                elif REC_WARN_RE.match(ln):
                    cur = RSection("warnings", "", no)
                else:
                    cur = RSection("bad", s, no)
                    self.problems.append((no, "bad heading '%s'; use '## [[exact page name]]', "
                                              "'## New page: name', '## Unplaced' or '## Warnings'" % s))
                self.sections.append(cur)
                continue
            m = BULLET_RE.match(ln)
            if m and cur is not None and not m.group(1):
                text = m.group(2).strip()
                struck = text.startswith(STRUCK)
                cur.bullets.append([no, text[len(STRUCK):].strip() if struck else text, struck])
            elif cur is not None and cur.bullets and (ln.startswith((" ", "\t"))):
                cur.bullets[-1][1] += " " + s
            elif cur is not None:
                self.problems.append((no, "line is not a bullet; start it with '- '"))

    def warnings_text(self):
        return [b[1] for sec in self.sections if sec.kind == "warnings" for b in sec.live()]


def record_paths(wiki):
    d = wiki.p(wiki.c("sources_dir"))
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, f) for f in sorted(os.listdir(d))
            if f.lower().endswith(".md") and os.path.isfile(os.path.join(d, f))]


def find_record(wiki, name):
    n = name.replace("\\", "/").strip()
    base = os.path.basename(n)
    stem = base[:-3] if base.lower().endswith(".md") else base
    for p in record_paths(wiki):
        if os.path.splitext(os.path.basename(p))[0].lower() == stem.lower():
            return Record(wiki, p)
    raise BrainError("record '%s' not found in %s; run `brain.py summary --status all` to list records"
                     % (name, wiki.c("sources_dir")), EXIT_MISSING)


def load_records(wiki, names=None, statuses=None):
    if names:
        recs = [find_record(wiki, n) for n in names]
    else:
        recs = [Record(wiki, p) for p in record_paths(wiki)]
    if statuses:
        recs = [r for r in recs if r.status in statuses]
    return recs


def resolve(wiki, name, pages, dicts):
    """Route a record heading name. Returns (kind, payload)."""
    n = name.strip().lower()
    hit = [d for d in dicts if d.name.lower() == n]
    if hit or wiki.is_dictionary_file(n + ".md"):
        return "dictionary", (hit[0].rel if hit else name)
    pers = by_name(pages, name, "personal")
    if len(pers) > 1:
        return "ambiguous", [p.rel for p in pers]
    if pers:
        return "personal", pers[0]
    team = by_name(pages, name, "team")
    if len(team) > 1:
        return "ambiguous", [p.rel for p in team]
    if team:
        return "twin", team[0]
    return "unknown", None


def dict_refusal(name, where, pages):
    base = re.sub(r"([-.]dictionary)$", "", name, flags=re.I)
    hint = " File table facts to the table's main page [[%s]]." % base if by_name(pages, base) else ""
    return ("REFUSED: '%s' is a data dictionary (%s). Dictionaries are off limits to brain intake, "
            "promotion and BrainCite.%s"
            % (name, where, hint))


# --------------------------------------------------------------- packets

def write_packet(path, meta, title, groups, valid_names, warnings=None, note=None):
    out = ["---"]
    for k, v in meta:
        out.append("%s: %s" % (k, v))
    out += ["---", "", "# %s" % title, ""]
    if note:
        out += [note, ""]
    out += ["## Bullets"]
    for heading, bullets in groups:
        if heading:
            out += ["", "### %s" % heading]
        out += bullets
    if warnings:
        out += ["", "## Warnings"] + ["- %s" % w for w in warnings]
    out += ["", "## Valid wikilink names", ", ".join(valid_names)]
    write_lines(path, out)


def packet_meta(path):
    fm, _ = parse_frontmatter(read_lines(path))
    return fm


def cite(text, stem):
    if re.search(r"\(src:[^)]*\)\s*$", text):
        return "- " + text
    return "- %s (src: %s)" % (text, stem)


def log_line(wiki, event, agent="-", in_chars="-", out_chars="-", note=""):
    path = wiki.work("brain-log.md")
    if not os.path.isfile(path):
        write_lines(path, ["# Brain log", "",
                           "| Time | Event | Agent | In chars | Out chars | Note |",
                           "|---|---|---|---|---|---|"])
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write("| %s | %s | %s | %s | %s | %s |\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M"), event, agent, in_chars, out_chars,
            note.replace("|", "/").replace("\n", " ")))


# --------------------------------------------------------------- commands

def write_pagelist(wiki):
    pages, dicts = wiki.scan()
    out = ["# Page list", "",
           "Generated by `brain.py pagelist`; do not edit. Use a Name exactly as `## [[Name]]` in source records.",
           "A name on both sides is a team page with a personal twin; filing always goes to the personal page.", "",
           "| Name | Side | Path | Description | Twin of |", "|---|---|---|---|---|"]
    for p in sorted(pages, key=lambda x: (x.name.lower(), x.side)):
        out.append("| %s | %s | %s | %s | %s |" % (
            p.name, p.side, p.rel, p.description.replace("|", "/"), p.twin_of))
    path = wiki.work("page-list.md")
    write_lines(path, out)
    warns = []
    for side in ("personal", "team"):
        seen = {}
        for p in pages:
            if p.side == side:
                seen.setdefault(p.name.lower(), []).append(p.rel)
        for k, v in seen.items():
            if len(v) > 1:
                warns.append("two %s pages named '%s': %s; rename one" % (side, k, ", ".join(v)))
    team_names = {p.name.lower() for p in pages if p.side == "team"}
    for p in pages:
        if p.twin_of and p.twin_of.lower() not in team_names:
            warns.append("%s has twin_of '%s' but no such team page" % (p.rel, p.twin_of))
        if p.nlines >= wiki.c("page_line_limit"):
            warns.append("%s is %d lines (limit %d)" % (p.rel, p.nlines, wiki.c("page_line_limit")))
    return path, pages, dicts, warns


def cmd_pagelist(wiki, args):
    path, pages, dicts, warns = write_pagelist(wiki)
    n_p = sum(1 for p in pages if p.side == "personal")
    print("page list: %s (%d personal, %d team; %d dictionaries excluded)"
          % (wiki.rel(path), n_p, len(pages) - n_p, len(dicts)))
    for w in warns:
        print("warn: " + w)
    if args.print_list:
        print()
        for ln in read_lines(path):
            if ln.startswith("| ") and not ln.startswith("| Name"):
                print(ln)
    return EXIT_OK


def route_label(wiki, name, pages, dicts):
    kind, pay = resolve(wiki, name, pages, dicts)
    return {"personal": "", "twin": " (new twin)", "dictionary": " REFUSED: dictionary",
            "ambiguous": " AMBIGUOUS", "unknown": " UNKNOWN PAGE"}[kind]


def section_check(wiki, sec, pages, dicts):
    """'' if the section heading exists on the target (or its team page), else a short flag."""
    if not sec.section:
        return ""
    kind, pay = resolve(wiki, sec.name, pages, dicts)
    if kind not in ("personal", "twin"):
        return ""
    cands = [pay]
    if kind == "personal" and pay.twin_of:
        cands += by_name(pages, pay.twin_of, "team")
    for p in cands:
        if len(find_heading(read_lines(wiki.p(p.rel)), sec.section)[1]) == 1:
            return ""
    return " (no such section; page level)"


def new_page_flag(name, pages):
    exact = by_name(pages, name)
    if exact:
        return " EXISTS: use [[%s]]" % exact[0].name
    near = near_matches(name, pages)
    if near:
        return " NEAR: " + ", ".join("%s (%s)" % (p.name, p.side) for p in near)
    return ""


def cmd_summary(wiki, args):
    statuses = None if args.status == "all" else [args.status]
    recs = load_records(wiki, args.records, statuses)
    if not recs:
        print("no %s records in %s" % (args.status, wiki.c("sources_dir")))
        return EXIT_OK
    pages, dicts = wiki.scan()
    tot_b = tot_p = 0
    targets = set()
    for r in recs:
        print("%s [%s, %s] %s" % (r.stem, r.origin or "?", r.status or "?", r.fm.get("origin_name", "")))
        full = r.origin == "session" or args.full
        newp, unpl, counts = [], 0, []
        for sec in r.sections:
            live = sec.live()
            if sec.kind == "page":
                targets.add(sec.name.lower())
                tot_b += len(live)
                flags = route_label(wiki, sec.name, pages, dicts) + section_check(wiki, sec, pages, dicts)
                if full:
                    print("  %s%s" % (sec.label(), flags))
                    for b in live:
                        print("    L%d %s" % (b[0], b[1]))
                else:
                    counts.append("%s %d%s" % (sec.label()[2:].replace("]]", "", 1), len(live), flags))
            elif sec.kind == "new":
                tot_p += 1
                tot_b += len(live)
                flag = new_page_flag(sec.name, pages)
                if full:
                    print("  New page: %s%s" % (sec.name, flag))
                    for b in live:
                        print("    L%d %s" % (b[0], b[1]))
                else:
                    newp.append("%s (%d)%s" % (sec.name, len(live), flag))
            elif sec.kind == "unplaced":
                unpl += len(live)
                if full:
                    print("  Unplaced")
                    for b in live:
                        print("    L%d %s" % (b[0], b[1]))
        if not full:
            if counts:
                print("  pages: " + ", ".join(counts))
            if newp:
                print("  new pages: " + ", ".join(newp))
            if unpl:
                print("  unplaced: %d" % unpl)
        warns = r.warnings_text() + ["L%d %s" % p for p in r.problems]
        if not r.fm.get("origin") or not r.fm.get("status"):
            warns.append("frontmatter needs origin and status")
        for w in warns:
            print("  warn: " + w)
    print("total: %d records, %d bullets, %d pages, %d new pages proposed"
          % (len(recs), tot_b, len(targets), tot_p))
    return EXIT_OK


def cmd_approve(wiki, args):
    if not (args.records or args.all or args.strike):
        raise BrainError("nothing to do; name records, or pass --all or --strike RECORD:LINE", EXIT_USAGE)
    strikes = {}
    for s in args.strike or []:
        if ":" not in s:
            raise BrainError("bad --strike '%s'; use RECORD:LINE, e.g. 2026-11-18-session-x:14" % s, EXIT_USAGE)
        rec, ln = s.rsplit(":", 1)
        if not ln.isdigit():
            raise BrainError("bad line number in --strike '%s'" % s, EXIT_USAGE)
        strikes.setdefault(rec, []).append(int(ln))
    # validate all strikes before writing
    plans = []
    for rec_name, lns in strikes.items():
        r = find_record(wiki, rec_name)
        if r.status == "filed":
            raise BrainError("%s is filed; filed records are citations and never change" % r.stem)
        bl = {b[0]: b for sec in r.sections for b in sec.bullets}
        for ln in lns:
            if ln not in bl:
                raise BrainError("%s line %d is not a bullet; check the L numbers in `brain.py summary`"
                                 % (r.stem, ln))
        plans.append((r, lns, bl))
    to_approve = []
    if args.records or args.all:
        to_approve = load_records(wiki, args.records or None, None if args.records else ["pending"])
    for r, lns, bl in plans:
        for ln in lns:
            if bl[ln][2]:
                print("already struck: %s L%d" % (r.stem, ln))
                continue
            m = BULLET_RE.match(r.lines[ln - 1])
            r.lines[ln - 1] = "- %s %s" % (STRUCK, m.group(2).strip())
            print("struck: %s L%d" % (r.stem, ln))
        write_lines(r.path, r.lines)
    if args.records or args.all:
        n = 0
        for r in to_approve:
            if r.status == "pending":
                lines = read_lines(r.path)
                write_lines(r.path, set_frontmatter(lines, "status", "approved"))
                print("approved: " + r.rel)
                n += 1
            else:
                print("unchanged (%s): %s" % (r.status or "no status", r.rel))
        print("%d record(s) approved" % n)
    return EXIT_OK


def cmd_collect(wiki, args):
    pages, dicts = wiki.scan()
    recs = load_records(wiki, args.records or None, ["approved"])
    if args.records:
        for r in load_records(wiki, args.records):
            if r.status != "approved":
                raise BrainError("%s is %s, not approved; run `brain.py approve %s` first"
                                 % (r.stem, r.status or "missing status", r.stem))
    if not recs:
        print("no approved records; nothing to collect")
        return EXIT_OK
    approved_new = {n.strip().lower() for n in (args.new_page or [])}
    errors, notes = [], []
    targets, order, seen_new = {}, [], set()
    page_lines = {}

    def lines_of(rel):
        if rel not in page_lines:
            page_lines[rel] = read_lines(wiki.p(rel)) if rel and os.path.isfile(wiki.p(rel)) else []
        return page_lines[rel]

    def target(key, **kw):
        if key not in targets:
            kw.update(page_bullets=[], sections={}, sec_order=[], records=[], warns=[])
            targets[key] = kw
            order.append(key)
        return targets[key]

    def add_bullets(t, r, live, section_heading):
        items = [(b[1], r.stem) for b in live]
        if section_heading:
            if section_heading.lower() not in t["sections"]:
                t["sections"][section_heading.lower()] = {"heading": section_heading, "bullets": []}
                t["sec_order"].append(section_heading.lower())
            t["sections"][section_heading.lower()]["bullets"] += items
        else:
            t["page_bullets"] += items
        if r.rel not in t["records"]:
            t["records"].append(r.rel)

    def heading_on(rel, wanted):
        """Exact heading text if wanted occurs once on the page at rel, else ''."""
        lines = lines_of(rel)
        if not lines:
            return ""
        hs, m = find_heading(lines, wanted)
        return hs[m[0]][2] if len(m) == 1 else ""

    for r in recs:
        for no, msg in r.problems:
            errors.append("%s L%d: %s" % (r.rel, no, msg))
        for sec in r.sections:
            live = sec.live()
            where = "%s L%d" % (r.rel, sec.lineno)
            if sec.kind == "page":
                kind, pay = resolve(wiki, sec.name, pages, dicts)
                if kind == "dictionary":
                    errors.append("%s: %s" % (where, dict_refusal(sec.name, pay, pages)))
                    continue
                if kind == "ambiguous":
                    errors.append("%s: page name '%s' is ambiguous (%s); rename one page"
                                  % (where, sec.name, ", ".join(pay)))
                    continue
                if kind == "unknown":
                    errors.append("%s: [[%s]] is not in the page list; change it to an exact page name, "
                                  "'New page: %s', or 'Unplaced'" % (where, sec.name, sec.name))
                    continue
                if not live:
                    continue
                if kind == "personal":
                    team = by_name(pages, pay.twin_of, "team") if pay.twin_of else []
                    t = target(pay.name.lower(), name=pay.name, rel=pay.rel, status="existing",
                               team_rel=team[0].rel if team else "", nlines=pay.nlines)
                else:  # twin to create
                    sub = pay.rel[len(wiki.c("team_dir").strip("/")) + 1:]
                    rel = wiki.c("personal_dir").strip("/") + "/" + sub
                    t = target(pay.name.lower(), name=pay.name, rel=rel, status="twin-created",
                               team_rel=pay.rel, nlines=0)
                heading = ""
                if sec.section:
                    heading = heading_on(t["rel"], sec.section) if t["status"] != "twin-created" else ""
                    if not heading and t["team_rel"]:
                        heading = heading_on(t["team_rel"], sec.section)
                    if not heading:
                        t["warns"].append("section '%s' (from %s) is not a heading on the page; its bullets "
                                          "are filed at page level" % (sec.section, r.stem))
                add_bullets(t, r, live, heading)
            elif sec.kind == "new":
                nm = sec.name
                if wiki.is_dictionary_file(nm + ".md") or by_name(dicts, nm):
                    errors.append("%s: %s" % (where, dict_refusal(nm, "new page name", pages)))
                    continue
                if BAD_NAME_RE.search(nm) or not nm.strip():
                    errors.append("%s: new page name '%s' has characters not allowed in a file name" % (where, nm))
                    continue
                mine = by_name(pages, nm, "personal")
                if len(mine) == 1 and nm.lower() in approved_new:
                    # created by an earlier collect run (or by hand): file to it
                    seen_new.add(nm.lower())
                    if live:
                        t = target(mine[0].name.lower(), name=mine[0].name, rel=mine[0].rel, status="existing",
                                   team_rel="", nlines=mine[0].nlines)
                        add_bullets(t, r, live, "")
                        notes.append("new page '%s' already exists at %s; filing to it" % (nm, mine[0].rel))
                    continue
                if by_name(pages, nm):
                    errors.append("%s: 'New page: %s' already exists as a page; use '## [[%s]]'"
                                  % (where, nm, by_name(pages, nm)[0].name))
                    continue
                near = near_matches(nm, pages)
                seen_new.add(nm.lower())
                if nm.lower() not in approved_new:
                    notes.append("skipped new page '%s' (%d bullets) in %s; pass --new-page \"%s\" to file it%s"
                                 % (nm, len(live), r.stem, nm,
                                    "; NEAR existing " + ", ".join(p.name for p in near) if near else ""))
                    continue
                if near and not args.allow_near:
                    errors.append("%s: new page '%s' is near existing page(s) %s; change the heading to "
                                  "'## [[%s]]', or pass --allow-near to create it anyway"
                                  % (where, nm, ", ".join("%s (%s)" % (p.name, p.side) for p in near),
                                     near[0].name))
                    continue
                if not live:
                    continue
                t = target(nm.lower(), name=nm, rel=wiki.c("personal_dir").strip("/") + "/" + nm + ".md",
                           status="new-page", team_rel="", nlines=0)
                add_bullets(t, r, live, "")
            elif sec.kind == "unplaced" and live:
                notes.append("unplaced: %d bullet(s) in %s stay in the record only" % (len(live), r.stem))
    for nm in sorted(approved_new - seen_new):
        notes.append("--new-page '%s' matches no 'New page:' section in the approved records" % nm)
    if errors:
        for e in errors:
            print("error: " + e, file=sys.stderr)
        raise BrainError("collect found %d problem(s); nothing was written and records stay approved. "
                         "Fix the record headings (or strike the bullets) and rerun collect." % len(errors))

    # side effects only after full validation
    pdir = wiki.work("packets")
    os.makedirs(pdir, exist_ok=True)
    for f in os.listdir(pdir):
        if f.startswith("personal-") and f.endswith(".md"):
            os.remove(os.path.join(pdir, f))
    all_names = sorted({p.name for p in pages} | {targets[k]["name"] for k in order}, key=str.lower)
    limit = wiki.c("page_line_limit")
    for key in order:
        t = targets[key]
        abs_t = wiki.p(t["rel"])
        if t["status"] == "twin-created":
            link = os.path.relpath(wiki.p(t["team_rel"]), os.path.dirname(abs_t)).replace(os.sep, "/")
            write_lines(abs_t, ["---", "twin_of: %s" % t["name"],
                                "description: Personal additions to the team page %s." % t["name"], "---", "",
                                "# %s" % t["name"], "", "%s [%s](%s)" % (TEAM_LINK_PREFIX, t["name"], link)])
            print("twin created: %s (twin of %s)" % (t["rel"], t["team_rel"]))
        elif t["status"] == "new-page":
            write_lines(abs_t, ["---", "description:", "---", "", "# %s" % t["name"]])
            print("new page created: %s" % t["rel"])
        n_b = len(t["page_bullets"]) + sum(len(s["bullets"]) for s in t["sections"].values())
        if t["nlines"] + n_b > limit:
            t["warns"].append("page is %d lines; adding %d bullets may pass the %d-line limit"
                              % (t["nlines"], n_b, limit))
        ppath = os.path.join(pdir, "personal-%s.md" % t["name"])
        mode = "page" if t["page_bullets"] or not t["sections"] else "sections"
        write_personal_packet(wiki, ppath, t, mode, all_names, lines_of)
        print("packet: %s -> %s (%s, %d bullets from %d record(s))"
              % (wiki.rel(ppath), t["rel"], mode if mode == "page" else
                 "sections: " + ", ".join(t["sections"][s]["heading"] for s in t["sec_order"]),
                 n_b, len(t["records"])))
        for w in t["warns"]:
            print("warn: %s: %s" % (t["rel"], w))
    write_lines(wiki.work("collected.md"), ["# Records collected by the last `brain.py collect`",
                                            "Read by `brain.py markfiled`; removed when they are filed.", ""]
                + [r.rel for r in recs])
    save_guard(wiki)
    for n in notes:
        print("note: " + n)
    print("%d packet(s) written" % len(order))
    return EXIT_OK


def write_personal_packet(wiki, ppath, t, mode, valid_names, lines_of):
    meta = [("packet", "personal"), ("mode", mode), ("target", t["rel"]), ("target_status", t["status"]),
            ("team_page_readonly", t["team_rel"] or "none"), ("rules", wiki.c("personal_rules")),
            ("tags", "%s, %s" % (wiki.c("personal_tags"), wiki.c("team_tags"))), ("template", "none"),
            ("records", ", ".join(t["records"])), ("page_line_limit", wiki.c("page_line_limit")),
            ("page_lines", t["nlines"])]
    out = ["---"] + ["%s: %s" % kv for kv in meta] + ["---", "", "# Packet: %s (personal)" % t["name"]]
    if mode == "page":
        out += ["", "## Bullets"] + [cite(x, s) for x, s in t["page_bullets"]]
        for key in t["sec_order"]:
            s = t["sections"][key]
            out += ["", "### Section hint: %s" % s["heading"]] + [cite(x, st) for x, st in s["bullets"]]
    else:
        for key in t["sec_order"]:
            s = t["sections"][key]
            out += ["", "## Section: %s" % s["heading"]]
            plines = lines_of(t["rel"]) if t["status"] != "twin-created" else []
            hs, m = find_heading(plines, s["heading"]) if plines else ([], [])
            if len(m) == 1:
                start, end = hs[m[0]][0], section_span(plines, hs, m[0])
                out += ["section_lines: %d-%d" % (start + 1, end), "", "### Bullets"]
                out += [cite(x, st) for x, st in s["bullets"]]
                out += ["", "### Current section text (copy; edit it on the page)", "```markdown"]
                out += plines[start:end] + ["```"]
            else:
                out += ["section_lines: none (heading not on the page yet; add it in the team page's section order)",
                        "", "### Bullets"] + [cite(x, st) for x, st in s["bullets"]]
            if t["team_rel"]:
                tl = lines_of(t["team_rel"])
                ths, tm = find_heading(tl, s["heading"]) if tl else ([], [])
                if len(tm) == 1:
                    ts, te = ths[tm[0]][0], section_span(tl, ths, tm[0])
                    out += ["", "### Team section (read-only, %s lines %d-%d)" % (t["team_rel"], ts + 1, te),
                            "```markdown"] + tl[ts:te] + ["```"]
                else:
                    out += ["", "### Team section (read-only): not on team page; read %s if needed" % t["team_rel"]]
    if t["warns"]:
        out += ["", "## Warnings"] + ["- %s" % w for w in t["warns"]]
    out += ["", "## Valid wikilink names", ", ".join(valid_names)]
    write_lines(ppath, out)


def move_input(wiki, rec):
    inp = rec.fm.get("input", "").replace("\\", "/").strip("/")
    if not inp:
        return None, "%s has no input: field; nothing moved" % rec.stem
    raw = wiki.c("raw_dir").strip("/")
    proc = wiki.c("processed_dir").strip("/")
    if not inp.lower().startswith(raw.lower() + "/") or inp.lower().startswith(proc.lower() + "/"):
        return None, None
    src = wiki.p(inp)
    if not os.path.isfile(src):
        return None, "input %s of %s not found; nothing moved" % (inp, rec.stem)
    dest_rel = proc + "/" + inp[len(raw) + 1:]
    dest = wiki.p(dest_rel)
    base, ext = os.path.splitext(dest)
    i = 1
    while os.path.exists(dest):
        dest = "%s-%d%s" % (base, i, ext)
        i += 1
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.move(src, dest)
    return wiki.rel(dest), None


def cmd_markfiled(wiki, args):
    manifest = wiki.work("collected.md")
    for name in args.promoted or []:
        if not os.path.isfile(wiki.work("packets", "team-%s.md" % name)):
            raise BrainError("no team packet for '%s' in %s/packets; check the name (nothing was changed)"
                             % (name, wiki.c("work_dir")), EXIT_MISSING)
    pdir = wiki.work("packets")
    held, failed_packets = {}, set()
    for name in args.failed or []:
        fp = os.path.join(pdir, "personal-%s.md" % name)
        if not os.path.isfile(fp):
            raise BrainError("no personal packet for failed page '%s' in %s/packets; use the page name from the "
                             "packet file name (nothing was changed)" % (name, wiki.c("work_dir")), EXIT_MISSING)
        failed_packets.add(os.path.basename(fp))
        for x in packet_meta(fp).get("records", "").split(","):
            if x.strip():
                held.setdefault(x.strip(), []).append(name)
    if args.records:
        recs = load_records(wiki, args.records)
    elif os.path.isfile(manifest):
        names = [ln.strip() for ln in read_lines(manifest)[3:] if ln.strip()]
        recs = load_records(wiki, names) if names else []
    elif args.promoted:
        recs = []
    else:
        raise BrainError("no records collected; run `brain.py collect` first, or name the records to mark filed",
                         EXIT_MISSING)
    for r in recs:
        if r.status not in ("approved", "filed"):
            raise BrainError("%s is %s; only approved records can be marked filed" % (r.stem, r.status or "unset"))
    # team-write guard: intake must not have touched team pages or dictionaries
    team_targets = {}
    if os.path.isdir(pdir):
        for f in os.listdir(pdir):
            if f.startswith("team-") and f.endswith(".md"):
                team_targets[f[5:-3]] = packet_meta(os.path.join(pdir, f)).get("target", "")
    problems = []
    if recs:
        ch = guard_changes(wiki, None, exempt=[t for t in team_targets.values() if t])
        if ch is None:
            print("note: no intake team guard found (run collect first); team check skipped")
        elif ch:
            problems.append("intake changed team or dictionary files: " + ", ".join(ch))
    for name in args.promoted or []:
        ch = guard_changes(wiki, name, exempt=[team_targets.get(name, "")])
        if ch:
            problems.append("promotion of '%s' changed files other than %s: %s"
                            % (name, team_targets.get(name, "its team page"), ", ".join(ch)))
    if problems:
        for pr in problems:
            print("error: " + pr, file=sys.stderr)
        raise BrainError("team-write guard failed; nothing was filed. Restore the listed files (e.g. from git) "
                         "and rerun markfiled.")
    n = moved = 0
    for r in recs:
        if r.status == "filed":
            print("already filed: " + r.rel)
            continue
        if r.rel in held:
            print("held (failed page %s): %s stays approved" % (", ".join(held[r.rel]), r.rel))
            continue
        new_input, warn = move_input(wiki, r)
        lines = read_lines(r.path)
        set_frontmatter(lines, "status", "filed")
        if new_input:
            set_frontmatter(lines, "input", new_input)
            print("moved: %s -> %s" % (r.fm.get("input"), new_input))
            moved += 1
        if warn:
            print("note: " + warn)
        write_lines(r.path, lines)
        print("filed: " + r.rel)
        n += 1
    if os.path.isdir(pdir):
        done = {r.rel for r in load_records(wiki, None, ["filed"])} | set(held)
        for f in sorted(os.listdir(pdir)):
            fp = os.path.join(pdir, f)
            if f.startswith("personal-") and f.endswith(".md") and f not in failed_packets:
                recl = [x.strip() for x in packet_meta(fp).get("records", "").split(",") if x.strip()]
                if recl and all(x in done for x in recl):
                    os.remove(fp)
                    print("packet removed: " + wiki.rel(fp))
    if os.path.isfile(manifest):
        left = [ln.strip() for ln in read_lines(manifest)[3:] if ln.strip()]
        filed_now = {r.rel for r in load_records(wiki, None, ["filed"])}
        left = [x for x in left if x not in filed_now]
        if left:
            write_lines(manifest, read_lines(manifest)[:3] + left)
        else:
            os.remove(manifest)
            if os.path.isfile(guard_path(wiki)):
                os.remove(guard_path(wiki))
    for name in args.promoted or []:
        fp = os.path.join(pdir, "team-%s.md" % name)
        os.remove(fp)
        if os.path.isfile(guard_path(wiki, name)):
            os.remove(guard_path(wiki, name))
        print("packet removed: " + wiki.rel(fp))
    path, _, _, warns = write_pagelist(wiki)
    print("page list regenerated: " + wiki.rel(path))
    for w in warns:
        print("warn: " + w)
    note = "%d filed, %d inputs moved" % (n, moved)
    if args.promoted:
        note += ", promoted " + ", ".join(args.promoted)
    if args.failed:
        note += ", failed " + ", ".join(args.failed) + ", held " + str(len(held))
    log_line(wiki, "markfiled", note=note)
    print("%d record(s) filed, %d input file(s) moved, %d held for failed page(s)" % (n, moved, len(held)))
    return EXIT_OK


def cmd_log(wiki, args):
    inc = args.in_chars or 0
    for f in args.in_file or []:
        cands = [f] if os.path.isabs(f) else [os.path.abspath(f), wiki.p(f)]
        fp = next((c for c in cands if os.path.isfile(c)), None)
        if not fp:
            print("warn: --in-file not found, size not counted: %s" % f)
            continue
        with open(fp, "r", encoding="utf-8-sig") as fh:
            inc += len(fh.read())
    outc = args.out_chars or 0
    if args.out_text is not None:
        outc += len(args.out_text)
    log_line(wiki, args.event, args.agent, inc, outc, args.note or "")
    print("logged: %s %s in=%d out=%d" % (args.event, args.agent, inc, outc))
    return EXIT_OK


# ------------------------------------------------------------ team guard

def team_fingerprint(wiki):
    """rel path -> sha256 for every file under the team folder and every dictionary file."""
    out = {}
    base = wiki.p(wiki.c("team_dir"))
    for dirpath, dirnames, filenames in os.walk(base):
        for f in filenames:
            p = os.path.join(dirpath, f)
            with open(p, "rb") as fh:
                out[wiki.rel(p)] = hashlib.sha256(fh.read()).hexdigest()
    for d in wiki.scan()[1]:
        with open(wiki.p(d.rel), "rb") as fh:
            out[d.rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def guard_path(wiki, promoted=None):
    return wiki.work("team-guard%s.json" % ("-" + promoted if promoted else ""))


def save_guard(wiki, promoted=None):
    path = guard_path(wiki, promoted)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(team_fingerprint(wiki), f, indent=0, sort_keys=True)


def guard_changes(wiki, promoted=None, exempt=()):
    """Changed, added or removed team/dictionary files since the guard was saved; None if no guard."""
    path = guard_path(wiki, promoted)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        old = json.load(f)
    now = team_fingerprint(wiki)
    ex = {e.lower() for e in exempt}
    return sorted(k for k in set(old) | set(now) if old.get(k) != now.get(k) and k.lower() not in ex)


def promotable(lines, body):
    """Indexes of lines that can be promoted, with their section heading."""
    out, fence, heading = [], False, ""
    for i in range(body, len(lines)):
        s = lines[i].strip()
        if s.startswith("```") or s.startswith("~~~"):
            fence = not fence
            continue
        if fence or not s:
            continue
        m = HEADING_RE.match(lines[i])
        if m:
            heading = m.group(2).strip() if len(m.group(1)) > 1 else ""
            continue
        if s.startswith(TEAM_LINK_PREFIX):
            continue
        out.append((i, heading))
    return out


def find_personal(wiki, pages, dicts, name):
    if by_name(dicts, name):
        raise BrainError(dict_refusal(name, by_name(dicts, name)[0].rel, pages))
    hits = by_name(pages, name, "personal")
    if not hits:
        raise BrainError("no personal page named '%s'; run `brain.py promote --list`" % name, EXIT_MISSING)
    if len(hits) > 1:
        raise BrainError("personal page name '%s' is ambiguous: %s" % (name, ", ".join(h.rel for h in hits)))
    return hits[0]


def parse_line_spec(spec):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^L?(\d+)(?:-L?(\d+))?$", part, re.I)
        if not m:
            raise BrainError("bad --lines '%s'; use e.g. 12,14-16" % spec, EXIT_USAGE)
        a = int(m.group(1))
        b = int(m.group(2) or a)
        out += list(range(min(a, b), max(a, b) + 1))
    return out


def cmd_promote(wiki, args):
    pages, dicts = wiki.scan()
    if args.list:
        team_names = {p.name.lower() for p in pages if p.side == "team"}
        rows = []
        for p in sorted([p for p in pages if p.side == "personal"], key=lambda x: x.name.lower()):
            lines = read_lines(wiki.p(p.rel))
            _, body = parse_frontmatter(lines)
            n = len(promotable(lines, body))
            if n == 0:
                continue
            if p.twin_of:
                rows.append("%s | twin of %s | %d lines" % (p.name, p.twin_of, n))
            elif p.name.lower() in team_names:
                rows.append("%s | same name as team page, no twin_of | %d lines" % (p.name, n))
            else:
                rows.append("%s | personal only (needs --template) | %d lines" % (p.name, n))
        print("\n".join(rows) if rows else "no personal pages with promotable lines")
        return EXIT_OK
    if not args.page:
        raise BrainError("name a personal page, or pass --list", EXIT_USAGE)
    page = find_personal(wiki, pages, dicts, args.page)
    lines = read_lines(wiki.p(page.rel))
    fm, body = parse_frontmatter(lines)
    cand = promotable(lines, body)
    team_name = page.twin_of or page.name
    if wiki.is_dictionary_file(team_name + ".md") or by_name(dicts, team_name):
        raise BrainError(dict_refusal(team_name, "promotion target", pages))
    team = by_name(pages, team_name, "team")
    if args.show:
        print("%s (%s)" % (page.rel, "twin of " + team[0].rel if team else "no team page yet"))
        last = None
        for i, h in cand:
            if h != last:
                print("## " + (h or "(top)"))
                last = h
            flags = line_flags(wiki, lines[i])
            print("  L%d %s%s" % (i + 1, "".join("[%s] " % f for f in flags), lines[i].strip()))
        return EXIT_OK
    if not (args.lines or args.text):
        raise BrainError("choose lines with --lines 12,14-16 or --text \"exact line\" (see --show)", EXIT_USAGE)
    cidx = {i: h for i, h in cand}
    chosen = []
    for n in parse_line_spec(args.lines) if args.lines else []:
        if n - 1 not in cidx:
            raise BrainError("line %d of %s cannot be promoted (blank, heading, frontmatter or team link); "
                             "see `brain.py promote %s --show`" % (n, page.rel, page.name))
        chosen.append(n - 1)
    for t in args.text or []:
        want = t.strip()
        hit = [i for i, _ in cand if lines[i].strip() == want and i not in chosen]
        if not hit:
            hit = [i for i, _ in cand if lines[i].strip().lstrip("-* ").strip() == want.lstrip("-* ").strip()
                   and i not in chosen]
        if not hit:
            raise BrainError("no line in %s matches --text \"%s\"; copy it exactly from --show" % (page.rel, t))
        chosen.append(hit[0])
    chosen = sorted(set(chosen))
    pdir = wiki.work("packets")
    ppath = os.path.join(pdir, "team-%s.md" % team_name)
    if os.path.isfile(ppath):
        raise BrainError("a team packet for '%s' is still waiting (%s); run the filer on it and "
                         "`brain.py markfiled --promoted %s` first" % (team_name, wiki.rel(ppath), team_name))
    template = "none"
    if team:
        target_rel, status = team[0].rel, "existing"
    else:
        if not args.template:
            tdir = wiki.p(wiki.c("templates_dir"))
            names = sorted(os.path.splitext(f)[0] for f in os.listdir(tdir)) if os.path.isdir(tdir) else []
            raise BrainError("no team page '%s' yet; pass --template NAME (one of: %s)"
                             % (team_name, ", ".join(names) or "none found"))
        tname = os.path.splitext(os.path.basename(args.template.replace("\\", "/")))[0]
        tpath = wiki.p(wiki.c("templates_dir") + "/" + tname + ".md")
        if not os.path.isfile(tpath):
            raise BrainError("template '%s' not in %s" % (args.template, wiki.c("templates_dir")), EXIT_MISSING)
        template = wiki.rel(tpath)
        target_rel, status = wiki.c("team_dir").strip("/") + "/" + team_name + ".md", "created-from-template"

    def tagset(key):
        fp = wiki.p(wiki.c(key))
        return tags_in("\n".join(read_lines(fp))) if os.path.isfile(fp) else set()

    team_tags = tagset("team_tags")
    personal_only = tagset("personal_tags") - team_tags
    doubt = {t.lstrip("#").lower() for t in wiki.c("doubt_tags")}
    team_page_names = {p.name.lower() for p in pages if p.side == "team"} | {team_name.lower()}
    pdir_name = wiki.c("personal_dir").strip("/")
    pers_re = re.compile(r"(^|[/\\(\s])%s[/\\]" % re.escape(pdir_name), re.I)
    promoted_cite = "(src: promoted %s)" % date.today().isoformat()
    groups, stripped, warns, doubt_warns = [], set(), [], []
    for i in chosen:
        text = lines[i].strip()
        for tg in TAG_RE.findall(text):
            if tg.lower() in personal_only:
                stripped.add(tg.lower())
                if tg.lower() in doubt:
                    doubt_warns.append("doubt tag #%s stripped from L%d; confirm the line is settled before "
                                       "the filer runs" % (tg, i + 1))
            elif tg.lower() not in team_tags:
                warns.append("tag #%s on L%d is not a team tag; filer must drop it" % (tg, i + 1))
        text = TAG_RE.sub(lambda m: "" if m.group(1).lower() in personal_only else m.group(0), text)
        # citations: no personal paths on a team page
        text = re.sub(r"\(src:[^)]*\)", lambda m: promoted_cite if pers_re.search(m.group(0)) else m.group(0), text)
        text = re.sub(r"\[([^\]]*)\]\(([^)]*)\)",
                      lambda m: m.group(1) if pers_re.search(" " + m.group(2)) else m.group(0), text)
        if "(src:" not in text:
            text = text.rstrip() + " " + promoted_cite
        text = re.sub(r"[ \t]{2,}", " ", text).rstrip()
        for ln in LINK_RE.findall(text):
            if ln.strip().lower() not in team_page_names:
                warns.append("[[%s]] on L%d is not a team page; filer must unlink it" % (ln.strip(), i + 1))
        if not BULLET_RE.match(text):
            text = "- " + text
        h = cidx[i] and "From twin section: %s" % cidx[i]
        if groups and groups[-1][0] == h:
            groups[-1][1].append(text)
        else:
            groups.append((h, [text]))
    team_names = sorted({p.name for p in pages if p.side == "team"} | {team_name}, key=str.lower)
    meta = [("packet", "team"), ("target", target_rel), ("target_status", status),
            ("team_page_readonly", "none"), ("rules", wiki.c("team_rules")), ("tags", wiki.c("team_tags")),
            ("template", template), ("records", "none"), ("promoted_from", page.rel),
            ("page_line_limit", wiki.c("page_line_limit"))]
    if status == "created-from-template":
        write_lines(wiki.p(target_rel), page_from_template(read_lines(wiki.p(template)), team_name,
                                                           os.path.splitext(os.path.basename(template))[0]))
        print("team page created from template: %s (%s)" % (target_rel, template))
    write_packet(ppath, meta, "Packet: %s (team)" % team_name, groups, team_names, warns,
                 note="Cite each bullet exactly as given: keep its (src: ...) unchanged; add no other citation.")
    for i in reversed(chosen):
        del lines[i]
    dropped = drop_empty_headings(lines)
    if not page.twin_of:
        set_frontmatter(lines, "twin_of", team_name)
        add_team_link(wiki, lines, page.rel, target_rel, team_name)
        print("twin_of set: %s -> %s (team link added)" % (page.rel, team_name))
    write_lines(wiki.p(page.rel), lines)
    print("removed %d line(s) from %s" % (len(chosen), page.rel))
    if dropped:
        print("empty headings dropped: " + ", ".join(dropped))
    if stripped:
        print("stripped personal tags: " + ", ".join("#" + s for s in sorted(stripped)))
    for w in doubt_warns + warns:
        print("warn: " + w)
    save_guard(wiki, team_name)
    print("packet: %s -> %s (%s)" % (wiki.rel(ppath), target_rel, status))
    return EXIT_OK


def line_flags(wiki, line):
    """Short markers for a line a team owner would question."""
    flags = []
    body = TAG_RE.sub("", re.sub(r"\(src:[^)]*\)", "", line))
    if re.search(r"\bI\b", body) or re.search(r"\b(?:my|we|our)\b", body, re.I):
        flags.append("first person")
    have = tags_in(line)
    for t in wiki.c("doubt_tags"):
        if t.lstrip("#").lower() in have:
            flags.append(t if t.startswith("#") else "#" + t)
    if "(src:" not in line:
        flags.append("no source")
    return flags


def page_from_template(tlines, name, tname):
    """New team page: template headings kept, placeholder text removed, description marked TODO."""
    _, body = parse_frontmatter(tlines)
    out = ["---", "description: TODO (filer: replace with a one-line description)", "template: %s" % tname,
           "---", "", "# %s" % name]
    for idx, lv, text in headings(tlines, body):
        if lv >= 2:
            out += ["", "%s %s" % ("#" * lv, text)]
    return out


def drop_empty_headings(lines):
    """Remove level 2-6 headings with no content before the next heading of the same or higher level."""
    _, body = parse_frontmatter(lines)
    dropped, changed = [], True
    while changed:
        changed = False
        for idx, lv, text in headings(lines, body):
            if lv < 2:
                continue
            j = idx + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            m = HEADING_RE.match(lines[j]) if j < len(lines) else None
            if j >= len(lines) or (m and len(m.group(1)) <= lv):
                del lines[idx:j]
                dropped.append(text)
                changed = True
                break
    return dropped


def add_team_link(wiki, lines, page_rel, team_rel, team_name):
    if any(ln.strip().startswith(TEAM_LINK_PREFIX) for ln in lines):
        return
    link = os.path.relpath(wiki.p(team_rel), os.path.dirname(wiki.p(page_rel))).replace(os.sep, "/")
    _, body = parse_frontmatter(lines)
    at = body
    for idx, lv, text in headings(lines, body):
        if lv == 1:
            at = idx + 1
            break
    lines[at:at] = ["", "%s [%s](%s)" % (TEAM_LINK_PREFIX, team_name, link)]


def side_pages(wiki, side):
    pages, dicts = wiki.scan()
    if wiki.c("dictionaries_in_sections"):
        pages = pages + dicts
    sides = ("personal", "team") if side == "both" else (side,)
    return pages, [p for p in pages if p.side in sides]


def cmd_sections(wiki, args):
    allp, pages = side_pages(wiki, args.side)
    tw = twin_map(allp)
    level = wiki.c("section_level")
    cur_side = None
    for p in sorted(pages, key=lambda x: (x.side != "team", x.name.lower())):
        if p.side != cur_side:
            print("side: " + p.side)
            cur_side = p.side
        extra = ""
        if p.twin_of:
            extra = " | twin of " + p.twin_of
        elif p.side == "team" and p.name.lower() in tw:
            extra = " | twin: " + tw[p.name.lower()].rel
        if p.dictionary:
            extra += " | dictionary, read-only"
        print("[[%s]] %s | %d lines | %s%s" % (p.name, p.rel, p.nlines, p.description or "-", extra))
        lines = read_lines(wiki.p(p.rel))
        _, body = parse_frontmatter(lines)
        hs = headings(lines, body)
        for k, (idx, lv, text) in enumerate(hs):
            if lv == level:
                end = section_span(lines, hs, k)
                print("  %s | %d | %d" % (text, idx + 1, end - idx))
    if not pages:
        print("no pages on side '%s'" % args.side)
    return EXIT_OK


def cmd_section(wiki, args):
    allp, pages = side_pages(wiki, args.side or "both")
    _, dicts = wiki.scan()
    if not wiki.c("dictionaries_in_sections") and by_name(dicts, args.page):
        raise BrainError(dict_refusal(args.page, by_name(dicts, args.page)[0].rel, allp))
    hits = by_name(pages, args.page)
    if not hits:
        raise BrainError("no page named '%s'%s; run `brain.py sections`" % (
            args.page, " on side " + args.side if args.side else ""), EXIT_MISSING)
    if len(hits) > 1:
        raise BrainError("'%s' exists on more than one side or folder (%s); pass --side personal or --side team"
                         % (args.page, ", ".join(h.rel for h in hits)))
    p = hits[0]
    lines = read_lines(wiki.p(p.rel))
    _, body = parse_frontmatter(lines)
    if not args.heading or args.heading.strip().lower() == WHOLE_PAGE:
        end = len(lines)
        while end > body and not lines[end - 1].strip():
            end -= 1
        start = body
        while start < end and not lines[start].strip():
            start += 1
        print("%s | %s" % (p.rel, WHOLE_PAGE))
        print("\n".join(lines[start:end]))
        return EXIT_OK
    hs = headings(lines, body)
    want = args.heading.strip().lstrip("#").strip().lower()
    match = [k for k, h in enumerate(hs) if h[1] >= 2 and h[2].lower() == want]
    if not match:
        avail = ", ".join(h[2] for h in hs if h[1] >= 2)
        raise BrainError("no heading '%s' in %s; headings: %s" % (args.heading, p.rel, avail or "none"),
                         EXIT_MISSING)
    if len(match) > 1:
        raise BrainError("heading '%s' appears %d times in %s; rename one" % (args.heading, len(match), p.rel))
    k = match[0]
    end = section_span(lines, hs, k)
    print("%s | %s" % (p.rel, hs[k][2]))
    print("\n".join(lines[hs[k][0]:end]))
    return EXIT_OK


WHOLE_PAGE = "(whole page)"
CITE_SIDES = (("team", "Team"), ("personal", "Personal"))
CITE_HEADER = ["| Page | Section | Lines | Why read it |", "|---|---|---|---|"]


def parse_cite_row(line, side):
    """Page | Section | Lines | Why. Section '(whole page)' = whole page (stored as '').
    Older rows with extra columns are read as page, section, ..., lines, why."""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) < 4 or cells[0].lower() == "page" or set(cells[0]) <= set("-: "):
        return None
    m = LINK_RE.search(cells[0])
    sec = cells[1]
    if len(cells) >= 5 and cells[2].lower() in ("personal", "team"):  # old Side column
        side = cells[2].lower()
    return {"page": (m.group(1) if m else cells[0]).strip(),
            "section": "" if sec.lower() in (WHOLE_PAGE, "", "-") else sec,
            "side": side or "team", "lines": cells[-2], "why": cells[-1]}


def read_cite(wiki, path):
    """Return (preamble lines or None, {side: [rows]}, [other ## blocks as line lists])."""
    groups = {"team": [], "personal": []}
    if not os.path.isfile(path):
        return None, groups, []
    pre, others, side, in_rows, cur_lines = [], [], None, False, None
    sides = {title.lower(): sd for sd, title in CITE_SIDES}
    old_groups = ("for planning", "for the work")
    for ln in read_lines(path):
        m = re.match(r"^(#{2,3})\s+(.*?)\s*$", ln)
        if m:
            title = m.group(2).lower()
            if title in sides:
                side, in_rows, cur_lines = sides[title], True, None
                continue
            if m.group(1) == "##" and title in old_groups:  # older grouped file: rows merge by side
                side, in_rows, cur_lines = None, True, None
                continue
            if m.group(1) == "##":
                side, in_rows = None, False
                cur_lines = [ln]
                others.append(cur_lines)
                continue
        is_row = ln.strip().startswith("|")
        if in_rows:
            row = parse_cite_row(ln, side) if is_row else None
            if row:
                groups[row["side"]].append(row)
        elif cur_lines is not None:
            cur_lines.append(ln)
        elif is_row:
            row = parse_cite_row(ln, None)
            if row:
                groups[row["side"]].append(row)
        else:
            pre.append(ln)
    while pre and not pre[-1].strip():
        pre.pop()
    return pre, groups, others


def cmd_candidates(wiki, args):
    path = args.cite if os.path.isabs(args.cite) else os.path.abspath(args.cite)
    if not os.path.isfile(path):
        raise BrainError("BrainCite file not found: %s; fall back to the page list (`brain.py pagelist`)"
                         % args.cite, EXIT_MISSING)
    _, groups, _ = read_cite(wiki, path)
    pages, _ = wiki.scan()
    n = 0
    for side, _title in CITE_SIDES:
        if args.side and args.side != side:
            continue
        for r in groups[side]:
            flag = "" if by_name(pages, r["page"], side) else " (page missing)"
            print("%s | %s | %s | %s%s" % (r["page"], r["section"] or WHOLE_PAGE, side, r["why"], flag))
            n += 1
    if not n:
        print("no rows; fall back to the page list")
    print("route a section row as '## [[page]] > Section' and a whole-page row as '## [[page]]'; "
          "facts that fit no row: use %s/page-list.md" % wiki.c("work_dir"))
    return EXIT_OK


def load_rows(path):
    if not os.path.isfile(path):
        raise BrainError("rows file not found: %s" % path, EXIT_MISSING)
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    if path.lower().endswith(".json") or text.lstrip().startswith(("[", "{")):
        try:
            data = json.loads(text)
        except ValueError as e:
            raise BrainError("rows file is not valid JSON (%s)" % e)
        if isinstance(data, dict):
            data = data.get("rows", [])
        if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
            raise BrainError("rows JSON must be a list of objects with page, side, why and optional section")
        return [{str(k).lower().replace("why read it", "why"): ("" if v is None else str(v)) for k, v in x.items()}
                for x in data]
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return []
    head = [h.strip().lower().replace("why read it", "why") for h in lines[0].split("\t")]
    if "page" not in head or "side" not in head:
        raise BrainError("TSV rows need a header line with tab-separated columns: page, section, side, why")
    return [dict(zip(head, [c.strip() for c in ln.split("\t")])) for ln in lines[1:]]


def cmd_cite_add(wiki, args):
    spath = args.cite if os.path.isabs(args.cite) else os.path.abspath(args.cite)
    rows = load_rows(args.rows)
    pre, groups, others = read_cite(wiki, spath)
    pages, dicts = wiki.scan()
    if wiki.c("dictionaries_in_sections"):
        pages = pages + dicts
    counts = {s: [0, 0, 0] for s, _ in CITE_SIDES}  # added, already there, rejected
    bad_side = 0
    clean = lambda v: re.sub(r"\s+", " ", v).replace("|", "/").strip()
    for i, r in enumerate(rows, 1):
        page, section = r.get("page", "").strip().strip("[]"), r.get("section", "").strip()
        if section.lower() in (WHOLE_PAGE, "-"):
            section = ""
        side = r.get("side", "").strip().lower()
        label = "row %d (%s > %s, %s)" % (i, page, section or WHOLE_PAGE, side or "?")
        if side not in ("personal", "team"):
            print("rejected: %s: side must be personal or team" % label)
            bad_side += 1
            continue
        if by_name(dicts, page) and not wiki.c("dictionaries_in_sections"):
            print("rejected: %s: %s" % (label, dict_refusal(page, by_name(dicts, page)[0].rel, pages)))
            counts[side][2] += 1
            continue
        hit = by_name(pages, page, side)
        if len(hit) != 1:
            print("rejected: %s: no single %s page with that name" % (label, side))
            counts[side][2] += 1
            continue
        pg = hit[0]
        plines = read_lines(wiki.p(pg.rel))
        if section:
            hs, m = find_heading(plines, section)
            if len(m) != 1:
                print("rejected: %s: heading not found once on %s" % (label, pg.rel))
                counts[side][2] += 1
                continue
            heading = hs[m[0]][2]
            nlines = body_count(plines, hs[m[0]][0], section_span(plines, hs, m[0]))
        else:
            heading, nlines = "", pg.nlines
        table = groups[side]
        same = [x for x in table if x["page"].lower() == pg.name.lower()]
        if any(not x["section"] for x in same):
            print("already there: %s > %s (%s)%s" % (pg.name, heading or WHOLE_PAGE, side,
                                                   " (covered by whole page)" if heading else ""))
            counts[side][1] += 1
            continue
        if heading and any(x["section"].lower() == heading.lower() for x in same):
            print("already there: %s > %s (%s)" % (pg.name, heading, side))
            counts[side][1] += 1
            continue
        new = {"page": pg.name, "section": heading, "side": side, "lines": str(nlines),
               "why": clean(r.get("why", "")) or "-"}
        if not heading and same:  # whole page replaces its section entries, at the first one's place
            at = table.index(same[0])
            for x in same:
                table.remove(x)
            table.insert(at, new)
            print("replaced: %s > %s (%s) by %s" % (pg.name, ", ".join(x["section"] for x in same), side, WHOLE_PAGE))
        else:
            table.append(new)
        counts[side][0] += 1
        print("added: %s > %s (%s)" % (pg.name, heading or WHOLE_PAGE, side))
    out = pre if pre is not None else ["# BrainCite%s" % (": " + args.title if args.title else ""), "",
                                       "Sections and whole pages worth reading for this project, by side.",
                                       "Open one with `brain.py section \"<page>\" \"<section>\" --side team|personal`;"
                                       " for a whole page leave out the section."]
    for side, title in CITE_SIDES:
        out += ["", "## " + title, ""]
        if not groups[side]:
            out.append("None.")
            continue
        out += CITE_HEADER
        for r in groups[side]:
            out.append("| [[%s]] | %s | %s | %s |" % (r["page"], r["section"] or WHOLE_PAGE, r["lines"], r["why"]))
    for block in others:
        while block and not block[-1].strip():
            block.pop()
        out += [""] + block
    write_lines(spath, out)
    for side, _t in CITE_SIDES:
        a, d, b = counts[side]
        print("table %s: added %d, already there %d, rejected %d" % (side, a, d, b))
    added = sum(c[0] for c in counts.values())
    dup = sum(c[1] for c in counts.values())
    bad = sum(c[2] for c in counts.values()) + bad_side
    print("total: %d added, %d already there, %d rejected -> %s" % (added, dup, bad, os.path.basename(spath)))
    return EXIT_INVALID if bad and not added and not dup else EXIT_OK


def cmd_root(wiki, args):
    print(wiki.root)
    return EXIT_OK


# ----------------------------------------------------------------- parser

class Fmt(argparse.RawDescriptionHelpFormatter):
    pass


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--wiki", default=argparse.SUPPRESS, metavar="PATH",
                        help="wiki root (holds the personal and team folders). Default: $BRAIN_WIKI, "
                             "CONFIG wiki_root, then the current folder")
    common.add_argument("--config", default=argparse.SUPPRESS, metavar="PATH",
                        help="config JSON to use instead of <wiki>/%s" % CONFIG_FILE_NAME)
    top = argparse.ArgumentParser(
        prog="brain.py", formatter_class=Fmt, parents=[common],
        description="Script half of brain intake and BrainCite. No model calls.\n"
                    "Formats are defined in brain-reference.md. Output paths are relative to the wiki root.",
        epilog="intake flow:  pagelist [+ candidates --cite F] -> (extractor) -> summary -> approve -> collect\n"
               "              -> (filer per packet) -> markfiled\n"
               "promote flow: promote --list -> promote PAGE --show -> promote PAGE --lines .. -> (filer)"
               " -> markfiled --promoted NAME\n"
               "braincite:   sections --side team|personal -> (analysts) -> cite-add --cite F --rows R\n"
               "              -> section PAGE [HEADING] --side ..\n\n"
               "exit codes: 0 ok | 1 invalid or refused (message says what to fix) | 2 bad arguments |"
               " 3 not found\nerrors print one line to stderr starting 'error:'.")
    sub = top.add_subparsers(dest="cmd", metavar="COMMAND")

    def add(name, func, help_, desc):
        sp = sub.add_parser(name, parents=[common], help=help_, description=desc, formatter_class=Fmt)
        sp.set_defaults(func=func)
        return sp

    sp = add("pagelist", cmd_pagelist, "write the page list",
             "Walk the personal and team folders and write <work_dir>/page-list.md: name, side, path,\n"
             "description, twin_of. Skips sources, raw, templates, rules, tags, data dictionaries, non-.md\n"
             "files and folders named in skip_folder_names. Prints the file path, counts and warnings.")
    sp.add_argument("--print", dest="print_list", action="store_true", help="also print the table rows")

    sp = add("summary", cmd_summary, "print records compactly for approval",
             "Print source records. Session records: every bullet with its file line number (L12), for\n"
             "striking. Ingest/notes records: bullet counts per page, new pages, unplaced count, warnings.\n"
             "Route marks: (new twin) = twin will be created; UNKNOWN PAGE / REFUSED: dictionary = collect\n"
             "will fail.")
    sp.add_argument("records", nargs="*", metavar="RECORD", help="record names (file stem); default all")
    sp.add_argument("--status", default="pending", choices=["pending", "approved", "filed", "all"],
                    help="which records to show (default pending)")
    sp.add_argument("--full", action="store_true", help="print bullets in full for every origin")
    sp.add_argument("--out", metavar="FILE", help="write the output to FILE (relative to the wiki root; folders are created) instead of the screen")

    sp = add("approve", cmd_approve, "approve records and strike bullets",
             "Strike bullets first (bullet becomes '- [struck] text'; line numbers do not shift), then set\n"
             "named records, or with --all every pending record, to approved. --strike alone approves nothing.")
    sp.add_argument("records", nargs="*", metavar="RECORD", help="record names to approve")
    sp.add_argument("--all", action="store_true", help="approve every pending record")
    sp.add_argument("--strike", action="append", metavar="RECORD:LINE",
                    help="strike one bullet by record and file line number (repeatable)")

    sp = add("collect", cmd_collect, "validate approved records and write one packet per page",
             "Read approved records, check every heading against the pages on disk, then write one packet\n"
             "per target page to <work_dir>/packets/personal-<name>.md (old personal packets are replaced).\n"
             "Creates a missing personal twin when a heading names a team page.\n"
             "'## [[page]] > Section': if the heading exists on the page (or, for a twin, on the team page)\n"
             "the packet is mode: sections and carries only that section's text, its line range and the\n"
             "matching team section read-only; otherwise the bullets go to the page level with a warning.\n"
             "Any page-level bullet makes the whole packet mode: page (sections become hints).\n"
             "'New page:' sections are filed only when named with --new-page; a name that is near an\n"
             "existing page (plural, hyphens, word order) fails unless --allow-near. 'Unplaced' bullets are\n"
             "never packeted. Any bad heading, unknown page or dictionary target: exit 1, nothing written,\n"
             "records stay approved.")
    sp.add_argument("records", nargs="*", metavar="RECORD", help="limit to these approved records")
    sp.add_argument("--new-page", action="append", metavar="NAME",
                    help="approve a proposed new personal page by name (repeatable)")
    sp.add_argument("--allow-near", action="store_true",
                    help="create approved new pages even when their name is near an existing page")

    sp = add("markfiled", cmd_markfiled, "mark records filed, move inputs, regenerate page list",
             "Set the records the last successful collect handled (listed in <work_dir>/collected.md), or the\n"
             "named records, to filed; move each record's input file from the raw folder to the processed\n"
             "folder (input: is updated), remove packets whose records are all filed, regenerate the page\n"
             "list and append a line to <work_dir>/brain-log.md. Run only after every filer has returned.\n"
             "Team-write guard: refuses (exit 1, nothing filed, changed files listed) if any team or dictionary\n"
             "file changed since collect; a team page with a waiting team packet is exempt. With --promoted\n"
             "NAME, refuses if anything other than that packet's team page changed since promote.\n"
             "If a filer failed (e.g. 150-line limit), pass --failed PAGE: records with any bullet for that\n"
             "page stay approved and keep their inputs, that page's packet is kept, and everything else is\n"
             "filed. Fix the page, rerun its filer on the kept packet, then run markfiled again (the held\n"
             "records are still in collected.md).")
    sp.add_argument("records", nargs="*", metavar="RECORD", help="records to mark filed (default: those in collected.md)")
    sp.add_argument("--failed", action="append", metavar="PAGE",
                    help="a page whose filer failed (repeatable): records with bullets for it stay approved, "
                         "their inputs are not moved, and its packet is kept for a retry")
    sp.add_argument("--promoted", action="append", metavar="NAME",
                    help="remove the team packet for NAME after its filer ran (repeatable)")

    sp = add("log", cmd_log, "log input/output size of one sub-agent call",
             "Append one row to <work_dir>/brain-log.md. Input size: --in-chars and/or --in-file (sizes summed;\n"
             "a path is used as given if absolute, else tried against the current folder, then the wiki root;\n"
             "a missing file prints a warning and is not counted). Output size: --out-chars and/or --out-text\n"
             "(its length is counted).")
    sp.add_argument("agent", help="agent name, e.g. brain-filer")
    sp.add_argument("--event", default="agent-call", help="event label (default agent-call)")
    sp.add_argument("--in-chars", type=int, metavar="N", help="input size in characters")
    sp.add_argument("--in-file", action="append", metavar="PATH", help="input file whose size to add (repeatable)")
    sp.add_argument("--out-chars", type=int, metavar="N", help="output size in characters")
    sp.add_argument("--out-text", metavar="TEXT", help="the agent's returned text; its length is logged")
    sp.add_argument("--note", help="short note, e.g. the packet or page name")

    sp = add("promote", cmd_promote, "move chosen twin lines into a team packet",
             "--list: personal pages with promotable lines.\n"
             "PAGE --show: those lines as 'L<n> [flag] ... line'. Flags: [first person] (I, my, we, our),\n"
             "[#verify] etc. (doubt_tags), [no source] (no '(src: ...)').\n"
             "PAGE --lines/--text: remove the lines from the personal page (headings left empty are dropped),\n"
             "strip personal-only tags (a stripped doubt tag prints a 'warn: doubt tag' line), and write\n"
             "<work_dir>/packets/team-<team name>.md (team rules, team tags only, team page names for links).\n"
             "Citations: a line keeps its '(src: record)'; a line with none, or whose src or link points into\n"
             "the personal folder, gets '(src: promoted YYYY-MM-DD)'; the filer must use them unchanged.\n"
             "No team page yet: --template NAME creates it now from the template (headings kept, placeholder\n"
             "text removed, 'description: TODO ...' for the filer), and the personal page gets twin_of plus\n"
             "a 'Team page:' link. Saves a team guard checked by `markfiled --promoted`.\n"
             "Refuses dictionaries and refuses while an earlier team packet for the page is waiting.")
    sp.add_argument("page", nargs="?", metavar="PAGE", help="personal page name")
    sp.add_argument("--list", action="store_true", help="list personal pages that have promotable lines")
    sp.add_argument("--show", action="store_true", help="print PAGE's promotable lines with line numbers")
    sp.add_argument("--lines", metavar="SPEC", help="file line numbers, e.g. 12,14-16")
    sp.add_argument("--text", action="append", metavar="LINE", help="exact line text (repeatable)")
    sp.add_argument("--template", metavar="NAME", help="team template name or path; creates the team page from it when it does not exist")

    sp = add("sections", cmd_sections, "print the section index for BrainCite",
             "One block per page: '[[name]] path | N lines | description | twin of X' or '| twin: path'\n"
             "(N = the page's total line count, to judge whole page versus sections), then one line per\n"
             "section heading at section_level: 'Heading | start | lines'. start = 1-based line of the\n"
             "heading; lines = heading through the section's last non-blank line (read with offset=start,\n"
             "limit=lines). Dictionaries are excluded unless dictionaries_in_sections is true.")
    sp.add_argument("--side", default="both", choices=["personal", "team", "both"], help="default both")
    sp.add_argument("--out", metavar="FILE", help="write the output to FILE (relative to the wiki root; "
                    "folders are created) instead of the screen")

    sp = add("section", cmd_section, "print one section of one page, or the whole page",
             "With HEADING: print one section, found by heading text (case-insensitive, any level 2-6), up\n"
             "to the next heading of the same or higher level; first line 'path | heading'.\n"
             "Without HEADING (or with '(whole page)'): print the whole page body without frontmatter;\n"
             "first line 'path | (whole page)'.")
    sp.add_argument("page", metavar="PAGE", help="page name")
    sp.add_argument("heading", metavar="HEADING", nargs="?", help="heading text, without the #s; omit for the whole page")
    sp.add_argument("--side", choices=["personal", "team"], help="needed when the page has a twin")

    sp = add("candidates", cmd_candidates, "print BrainCite rows as routing candidates",
             "Print each row of a BrainCite file as 'page | section | side | why', where section is\n"
             "'(whole page)' for a whole-page entry. Route a section row as '## [[page]] > Section' and a\n"
             "whole-page row as '## [[page]]'. Rows whose page no longer exists are marked (page missing).\n"
             "Missing file: exit 3; fall back to the page list.")
    sp.add_argument("--cite", required=True, metavar="FILE", help="BrainCite file (e.g. <project>/braincite.md)")
    sp.add_argument("--side", choices=["team", "personal"], help="only rows from this table")
    sp.add_argument("--out", metavar="FILE", help="write the output to FILE (relative to the wiki root; "
                    "folders are created) instead of the screen")

    sp = add("cite-add", cmd_cite_add, "merge analyst rows into a BrainCite file",
             "Read rows from a JSON list or a TSV file with a header (columns: page, side, why, and optional\n"
             "section; missing or empty section or '(whole page)' = whole page). Each row is checked against\n"
             "the wiki (page exists on that side, heading exists) and Lines is filled in by the script\n"
             "(section body lines, or the page's line count). An invalid row is rejected with a one-line\n"
             "reason; the rest still go in. Rows go to '## Team' or '## Personal' (columns: Page | Section |\n"
             "Lines | Why read it) in the order given; an empty table shows 'None.'.\n"
             "Already there: same page + side + section, or the page already has a whole-page entry.\n"
             "A whole-page row replaces that page's section entries (prints 'replaced: ...').\n"
             "Prints 'table team|personal: added N, already there N, rejected N', then a total.\n"
             "Creates the file if missing. Exit 1 only if every row was rejected.")
    sp.add_argument("--cite", required=True, metavar="FILE", help="BrainCite file to create or update")
    sp.add_argument("--rows", required=True, metavar="FILE", help="rows file (.json or .tsv)")
    sp.add_argument("--title", metavar="TEXT", help="project name for the title of a new file")

    add("root", cmd_root, "print the absolute wiki root",
        "Print the wiki root as an absolute path (the only absolute path brain.py prints), so a skill can\n"
        "hand sub-agents full paths.")
    return top


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        wiki = open_wiki(args)
        out = getattr(args, "out", None)
        if not out:
            return args.func(wiki, args) or EXIT_OK
        buf = io.StringIO()
        real, sys.stdout = sys.stdout, buf
        try:
            rc = args.func(wiki, args) or EXIT_OK
        finally:
            sys.stdout = real
        path = out if os.path.isabs(out) else wiki.p(out.replace("\\", "/"))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(buf.getvalue())
        print("wrote %s (%d lines)" % (out if os.path.isabs(out) else wiki.rel(path), buf.getvalue().count("\n")))
        return rc
    except BrainError as e:
        print("error: " + e.msg, file=sys.stderr)
        return e.code
    except (OSError, UnicodeDecodeError) as e:
        print("error: %s; check the file exists and is UTF-8 text" % e, file=sys.stderr)
        return EXIT_MISSING


if __name__ == "__main__":
    sys.exit(main())
