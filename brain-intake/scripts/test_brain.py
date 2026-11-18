#!/usr/bin/env python3
"""Tests for brain.py. Standard library only.

Every test copies test-wiki/ to a temp folder and works on the copy.
Run: python scripts/test_brain.py
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "brain.py")
SOURCE_WIKI = os.path.join(os.path.dirname(HERE), "test-wiki")


def tree_hash(root):
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for f in sorted(filenames):
            p = os.path.join(dirpath, f)
            h.update(os.path.relpath(p, root).replace(os.sep, "/").encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


SOURCE_HASH = tree_hash(SOURCE_WIKI)


def slurp(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def cite_tables(text):
    """{side title: ['T1 [[page]] | Section', ...] or ['None.']} in file order."""
    out, side = {}, None
    for ln in text.splitlines():
        if ln.startswith("## "):
            side = ln[3:].strip()
            out[side] = []
        elif side and re.match(r"^\| [TP]\d+ \|", ln):
            cells = [c.strip() for c in ln.strip("|").split("|")]
            out[side].append("%s %s | %s" % (cells[0], cells[1], cells[2]))
        elif side and ln.strip() == "None.":
            out[side].append("None.")
    return out


class BrainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="brain-test-")
        self.wiki = os.path.join(self.tmp, "wiki")
        shutil.copytree(SOURCE_WIKI, self.wiki)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # helpers
    def run_brain(self, *args, ok=True):
        p = subprocess.run([sys.executable, BRAIN, "--wiki", self.wiki] + list(args), cwd=self.tmp,
                           capture_output=True, text=True, encoding="utf-8")
        if ok is True:
            self.assertEqual(p.returncode, 0, "brain.py %s failed:\n%s%s" % (" ".join(args), p.stdout, p.stderr))
        elif ok is not None:
            self.assertEqual(p.returncode, ok, "expected exit %s:\n%s%s" % (ok, p.stdout, p.stderr))
        return p

    def path(self, rel):
        return os.path.join(self.wiki, *rel.split("/"))

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as f:
            return f.read()

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def record(self, name, body, status="approved", origin="session"):
        self.write("personal/sources/%s.md" % name,
                   "---\norigin: %s\norigin_name: %s\nuser: analyst\ndate: 2026-11-18\nstatus: %s\n"
                   "input: personal/raw/%s.md\n---\n\nSummary: test record.\n\n%s" % (origin, name, status, name, body))

    def only_records(self, *keep):
        d = self.path("personal/sources")
        for f in os.listdir(d):
            if os.path.splitext(f)[0] not in keep:
                os.remove(os.path.join(d, f))

    def packets(self):
        d = self.path("brain-work/packets")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    # ---------------------------------------------------------- page list
    def test_pagelist_correct_and_dictionary_absent(self):
        out = self.run_brain("pagelist").stdout
        self.assertIn("5 personal, 8 team; 1 dictionaries excluded", out)
        text = self.read("brain-work/page-list.md")
        rows = [ln for ln in text.splitlines() if ln.startswith("| ") and not ln.startswith("| Name")]
        names = sorted((r.split("|")[1].strip(), r.split("|")[2].strip()) for r in rows)
        expected = sorted([(n, "team") for n in ("stop-loss", "claims-header", "pmpm", "member-months",
                                                 "medical-loss-ratio", "ibnr", "risk-adjustment",
                                                 "high-cost-claimants")] +
                          [(n, "personal") for n in ("stop-loss", "pmpm", "q4-renewal-analysis",
                                                     "sql-review-checklist", "eligibility-file-quirks")])
        self.assertEqual(names, expected)
        self.assertNotIn("dictionary", text.lower().replace("do not edit", ""))
        for skipped in ("rules", "tags", "concept", "metric", "2026-11-12-session-mlr-rebuild", "braincite"):
            self.assertNotIn("| %s |" % skipped, text)
        self.assertRegex(text, r"\| stop-loss \| personal \| personal/stop-loss.md \| .* \| stop-loss \|")

    # ------------------------------------------------------------ collect
    def test_two_approved_records_touching_one_page_give_one_packet(self):
        self.run_brain("collect")
        self.assertEqual(self.packets(), ["personal-ibnr.md", "personal-medical-loss-ratio.md",
                                          "personal-stop-loss.md"])
        pk = self.read("brain-work/packets/personal-stop-loss.md")
        self.assertIn("target: personal/stop-loss.md", pk)
        self.assertIn("2026-11-12-session-mlr-rebuild.md, personal/sources/2026-11-14-ingest-", pk)
        self.assertEqual(pk.count("(src: 2026-11-14-ingest-reinsurance-treaty-summary)"), 2)
        self.assertEqual(pk.count("(src: 2026-11-12-session-mlr-rebuild)"), 1)
        self.assertIn("tags: personal/tags.md, team/tags.md", pk)
        self.assertIn("rules: personal/rules.md", pk)
        self.assertIn("team_page_readonly: team/stop-loss.md", pk)
        self.assertNotIn("finance premium table", pk)  # unplaced never packeted
        self.assertNotIn("claims-header-dictionary", pk.split("## Valid wikilink names")[1])

    def test_missing_twin_created(self):
        self.assertFalse(os.path.exists(self.path("personal/ibnr.md")))
        out = self.run_brain("collect").stdout
        self.assertIn("twin created: personal/ibnr.md (twin of team/ibnr.md)", out)
        twin = self.read("personal/ibnr.md")
        self.assertIn("twin_of: ibnr", twin)
        self.assertIn("(../team/ibnr.md)", twin)
        self.assertNotRegex(twin, r"(?m)^- ")  # empty body: no facts yet
        self.assertIn("team_page_readonly: team/ibnr.md", self.read("brain-work/packets/personal-ibnr.md"))

    def test_bad_heading_fails_and_record_stays_approved(self):
        self.record("2026-11-18-session-bad", "## [[no-such-page]]\n- a fact\n\n## Random heading\n- another\n")
        p = self.run_brain("collect", ok=1)
        self.assertIn("no-such-page", p.stderr)
        self.assertIn("bad heading '## Random heading'", p.stderr)
        self.assertIn("nothing was written", p.stderr)
        self.assertIn("status: approved", self.read("personal/sources/2026-11-18-session-bad.md"))
        self.assertEqual(self.packets(), [])
        self.assertFalse(os.path.exists(self.path("personal/ibnr.md")))  # no side effects

    def test_dictionary_target_refused(self):
        self.record("2026-11-18-session-dict", "## [[claims-header-dictionary]]\n- paid_amt excludes cost share\n")
        p = self.run_brain("collect", ok=1)
        self.assertIn("REFUSED", p.stderr)
        self.assertIn("team/claims-header-dictionary.md", p.stderr)
        self.assertIn("[[claims-header]]", p.stderr)
        self.only_records("2026-11-18-session-dict")
        self.record("2026-11-18-session-dict", "## New page: claims-header-dictionary\n- x\n")
        p = self.run_brain("collect", "--new-page", "claims-header-dictionary", ok=1)
        self.assertIn("REFUSED", p.stderr)
        p = self.run_brain("promote", "claims-header-dictionary", "--lines", "10", ok=1)
        self.assertIn("REFUSED", p.stderr)
        p = self.run_brain("read", "--no-count", "claims-header-dictionary > Change history", "--side", "team", ok=1)
        self.assertIn("REFUSED", p.stderr)
        self.assertEqual(self.packets(), [])

    def test_section_level_packet_carries_only_that_section(self):
        self.only_records()
        self.record("2026-11-18-session-sec", "## [[stop-loss]] > Traps\n- Carrier lag is four months.\n")
        out = self.run_brain("collect").stdout
        self.assertIn("sections: Traps", out)
        pk = self.read("brain-work/packets/personal-stop-loss.md")
        self.assertIn("mode: sections", pk)
        self.assertIn("## Section: Traps", pk)
        m = re.search(r"section_lines: (\d+)-(\d+)", pk)
        self.assertTrue(m)
        lines = self.read("personal/stop-loss.md").split("\n")
        self.assertEqual(lines[int(m.group(1)) - 1], "## Traps")
        self.assertIn("Terminated members still count", pk)             # personal Traps text
        self.assertNotIn("Laser amounts I have seen", pk)               # personal Reference text
        self.assertIn("### Team section (read-only, team/stop-loss.md", pk)
        self.assertIn("reimbursements lag by two to four months", pk)   # team Traps text
        self.assertNotIn("Reimbursement formula", pk)                   # team Reference text
        self.assertIn("- Carrier lag is four months. (src: 2026-11-18-session-sec)", pk)

    def test_unknown_section_falls_back_to_page_level(self):
        self.only_records()
        self.record("2026-11-18-session-sec", "## [[stop-loss]] > Lasering detail\n- A fact.\n")
        out = self.run_brain("collect").stdout
        self.assertIn("is not a heading on the page", out)
        pk = self.read("brain-work/packets/personal-stop-loss.md")
        self.assertIn("mode: page", pk)
        self.assertIn("## Warnings", pk)
        self.assertIn("- A fact. (src: 2026-11-18-session-sec)", pk)

    def test_new_page_only_with_flag_and_near_match_flagged(self):
        out = self.run_brain("collect").stdout
        self.assertIn("skipped new page 'lasering'", out)
        self.assertFalse(os.path.exists(self.path("personal/lasering.md")))
        out = self.run_brain("collect", "--new-page", "lasering").stdout
        self.assertIn("new page created: personal/lasering.md", out)
        self.assertIn("personal-lasering.md", self.packets())
        self.only_records()
        self.record("2026-11-18-session-near", "## New page: Stop Losses\n- x\n\n## New page: losses-stop\n- y\n",
                    status="pending")
        out = self.run_brain("summary").stdout
        self.assertIn("NEAR: stop-loss (personal), stop-loss (team)", out)
        self.run_brain("approve", "--all")
        p = self.run_brain("collect", "--new-page", "Stop Losses", ok=1)
        self.assertIn("is near existing page(s) stop-loss", p.stderr)
        self.run_brain("collect", "--new-page", "Stop Losses", "--allow-near")
        self.assertTrue(os.path.exists(self.path("personal/Stop Losses.md")))

    # ---------------------------------------------------- summary/approve
    def test_summary_compact_and_approve_strike(self):
        self.only_records()
        self.record("2026-11-18-session-a", "## [[pmpm]]\n- Fact one.\n- Fact two.\n", status="pending")
        self.record("2026-11-18-ingest-b", "## [[pmpm]]\n- Doc fact one.\n- Doc fact two.\n\n## Unplaced\n- Loose.\n\n"
                    "## Warnings\n- Page 3 unreadable.\n", status="pending", origin="ingest")
        out = self.run_brain("summary").stdout
        self.assertIn("L13 Fact one.", out)              # session: bullets in full
        self.assertNotIn("Doc fact one", out)             # ingest: counts only
        self.assertIn("pages: pmpm 2", out)
        self.assertIn("unplaced: 1", out)
        self.assertIn("warn: Page 3 unreadable.", out)
        self.run_brain("approve", "--strike", "2026-11-18-session-a:13")
        self.assertIn("- [struck] Fact one.", self.read("personal/sources/2026-11-18-session-a.md"))
        self.assertIn("status: pending", self.read("personal/sources/2026-11-18-session-a.md"))
        self.run_brain("approve", "--strike", "2026-11-18-session-a:11", ok=1)  # not a bullet
        self.run_brain("approve", "--all")
        self.assertIn("status: approved", self.read("personal/sources/2026-11-18-ingest-b.md"))
        self.run_brain("collect")
        pk = self.read("brain-work/packets/personal-pmpm.md")
        self.assertNotIn("Fact one", pk)
        self.assertIn("Fact two", pk)

    # ---------------------------------------------------------- markfiled
    def test_markfiled_uses_collect_manifest_and_moves_inputs(self):
        p = self.run_brain("markfiled", ok=3)
        self.assertIn("run `brain.py collect` first", p.stderr)
        self.only_records()
        self.record("2026-11-18-stop-loss-rebuild", "## [[pmpm]]\n- A fact.\n")
        self.write("personal/sources/2026-11-18-stop-loss-rebuild.md",
                   self.read("personal/sources/2026-11-18-stop-loss-rebuild.md").replace(
                       "input: personal/raw/2026-11-18-stop-loss-rebuild.md",
                       "input: personal/raw/session-facts/2026-11-18-stop-loss-rebuild.md"))
        self.run_brain("collect")
        self.record("2026-11-18-late", "## [[pmpm]]\n- Approved after collect.\n")
        out = self.run_brain("markfiled").stdout
        self.assertIn("1 record(s) filed, 1 input file(s) moved", out)
        rec = self.read("personal/sources/2026-11-18-stop-loss-rebuild.md")
        self.assertIn("status: filed", rec)
        self.assertIn("input: personal/raw/processed/session-facts/2026-11-18-stop-loss-rebuild.md", rec)
        self.assertTrue(os.path.isfile(self.path("personal/raw/processed/session-facts/2026-11-18-stop-loss-rebuild.md")))
        self.assertFalse(os.path.exists(self.path("personal/raw/session-facts/2026-11-18-stop-loss-rebuild.md")))
        self.assertIn("status: approved", self.read("personal/sources/2026-11-18-late.md"))  # not collected
        self.assertEqual(self.packets(), [])
        self.assertIn("markfiled", self.read("brain-work/brain-log.md"))
        self.run_brain("log", "brain-filer", "--in-file", "personal/pmpm.md", "--out-chars", "120")
        self.assertRegex(self.read("brain-work/brain-log.md"), r"\| agent-call \| brain-filer \| \d+ \| 120 \|")

    def test_markfiled_failed_page_holds_its_records(self):
        self.run_brain("collect")  # sample records: A -> stop-loss, ibnr; B -> stop-loss, medical-loss-ratio
        self.record("2026-11-18-other", "## [[pmpm]]\n- Unrelated fact.\n")
        self.run_brain("collect")
        p = self.run_brain("markfiled", "--failed", "no-such-page", ok=3)
        self.assertIn("nothing was changed", p.stderr)
        out = self.run_brain("markfiled", "--failed", "ibnr").stdout
        self.assertIn("held (failed page ibnr): personal/sources/2026-11-12-session-mlr-rebuild.md", out)
        self.assertIn("status: approved", self.read("personal/sources/2026-11-12-session-mlr-rebuild.md"))
        self.assertIn("status: filed", self.read("personal/sources/2026-11-14-ingest-reinsurance-treaty-summary.md"))
        self.assertIn("status: filed", self.read("personal/sources/2026-11-18-other.md"))
        self.assertEqual(self.packets(), ["personal-ibnr.md"])
        self.assertIn("2026-11-12-session-mlr-rebuild.md", self.read("brain-work/collected.md"))
        out = self.run_brain("markfiled").stdout  # retry succeeded
        self.assertIn("filed: personal/sources/2026-11-12-session-mlr-rebuild.md", out)
        self.assertEqual(self.packets(), [])
        self.assertFalse(os.path.exists(self.path("brain-work/collected.md")))

    def test_work_folder_not_indexed(self):
        self.run_brain("collect")
        self.write("brain-work/notes.md", "# notes\n\n## Traps\n- x\n")
        self.write("personal/brain-work/stray.md", "# stray\n\n## Traps\n- x\n")
        self.run_brain("pagelist")
        text = self.read("brain-work/page-list.md")
        self.assertNotIn("brain-work/", text.split("| Name")[1])
        self.assertNotIn("brain-work", self.run_brain("sections").stdout)
        self.assertNotIn("stray", self.run_brain("sections").stdout)

    # ------------------------------------------------------------ promote
    def test_promote_removes_lines_and_strips_personal_tags(self):
        before = self.read("personal/stop-loss.md").split("\n")
        l1 = before.index([x for x in before if x.startswith("- Lasered members can be dropped")][0]) + 1
        l2 = before.index([x for x in before if x.startswith("- Reimbursement lag looks closer")][0]) + 1
        out = self.run_brain("promote", "stop-loss", "--lines", "%d,%d" % (l1, l2)).stdout
        self.assertIn("removed 2 line(s) from personal/stop-loss.md", out)
        self.assertIn("#hunch", out)
        self.assertIn("#verify", out)
        after = self.read("personal/stop-loss.md")
        self.assertNotIn("Lasered members can be dropped", after)
        self.assertNotIn("Reimbursement lag looks closer", after)
        self.assertIn("Terminated members still count", after)
        pk = self.read("brain-work/packets/team-stop-loss.md")
        self.assertIn("target: team/stop-loss.md", pk)
        self.assertIn("rules: team/rules.md", pk)
        self.assertIn("tags: team/tags.md\n", pk)
        self.assertNotIn("personal/tags.md", pk)
        self.assertIn("Lasered members can be dropped", pk)
        self.assertIn("#trap", pk)
        for tag in ("#verify", "#hunch"):
            self.assertNotIn(tag, pk)
        self.assertIn("### From twin section: Traps", pk)
        valid = pk.split("## Valid wikilink names")[1]
        self.assertNotIn("q4-renewal-analysis", valid)
        p = self.run_brain("promote", "stop-loss", "--lines", "%d" % l1, ok=1)  # packet still waiting
        self.assertIn("still waiting", p.stderr)
        self.run_brain("markfiled", "--promoted", "stop-loss")
        self.assertNotIn("team-stop-loss.md", self.packets())

    def test_promote_new_team_page_needs_template(self):
        p = self.run_brain("promote", "sql-review-checklist", "--text",
                           "- Integer division in some engines truncates PMPM; cast to decimal first. #trap", ok=1)
        self.assertIn("pass --template", p.stderr)
        self.assertIn("concept", p.stderr)
        self.run_brain("promote", "sql-review-checklist", "--text",
                       "- Integer division in some engines truncates PMPM; cast to decimal first. #trap",
                       "--template", "concept")
        pk = self.read("brain-work/packets/team-sql-review-checklist.md")
        self.assertIn("template: team/templates/concept.md", pk)
        self.assertIn("target_status: created-from-template", pk)
        self.assertIn("twin_of: sql-review-checklist", self.read("personal/sql-review-checklist.md"))

    # ---------------------------------------------------------- braincite
    def test_sections_index_excludes_dictionary_and_shows_page_lines(self):
        out = self.run_brain("sections", "--side", "team").stdout
        self.assertNotIn("dictionary", out.lower())
        self.assertIn("[[stop-loss]] team/stop-loss.md | 49 lines |", out)
        self.assertIn("twin: personal/stop-loss.md", out)
        self.assertRegex(out, r"\n  Overview \| \d+ \| \d+\n")
        out = self.run_brain("sections", "--side", "personal").stdout
        self.assertIn("twin of stop-loss", out)
        self.assertIn("  Purpose | 7 | 4\n", out)
        self.assertNotIn("team/", out.replace("twin of", ""))

    def cite_add(self, cite, data, ok=True):
        rows = os.path.join(self.tmp, "rows.json")
        with open(rows, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return self.run_brain("cite-add", "--cite", cite, "--rows", rows, "--title", "Test", ok=ok).stdout

    def test_cite_add_ids_validation_dedup_and_whole_page(self):
        cite = os.path.join(self.tmp, "proj", "braincite.md")
        out = self.cite_add(cite, [
            {"page": "pmpm", "section": "Traps", "side": "team", "why": "a"},
            {"page": "pmpm", "section": "Decisions", "side": "team", "why": "b"},
            {"page": "high-cost-claimants", "side": "team", "why": "c"},
            {"page": "pmpm", "section": "Traps", "side": "personal", "why": "d"},
            {"page": "pmpm", "section": "Nope", "side": "team", "why": "x"},
            {"page": "claims-header-dictionary", "section": "Change history", "side": "team", "why": "x"},
            {"page": "pmpm", "side": "nowhere", "why": "x"},
        ])
        self.assertIn("rejected: row 5 (pmpm > Nope, team): heading 'Nope' not found", out)
        self.assertIn("table team: added 3, already there 0, rejected 2", out)
        self.assertIn("total: 4 added, 0 already there, 3 rejected", out)
        t = cite_tables(slurp(cite))
        self.assertEqual(t["Team"], ["T1 [[pmpm]] | Traps", "T2 [[pmpm]] | Decisions",
                                     "T3 [[high-cost-claimants]] | (whole page)"])
        self.assertEqual(t["Personal"], ["P1 [[pmpm]] | Traps"])
        text = slurp(cite)
        self.assertIn("| # | Page | Section | Lines | Reads | Why read it |", text)
        self.assertRegex(text, r"\| T3 \| \[\[high-cost-claimants\]\] \| \(whole page\) \| \d+ \| 0 \| c \|")
        out = self.cite_add(cite, [{"page": "pmpm", "section": "Traps", "side": "team", "why": "dup"},
                                   {"page": "high-cost-claimants", "section": "Traps", "side": "team", "why": "x"}])
        self.assertIn("table team: added 0, already there 2, rejected 0", out)
        self.assertIn("(covered by whole page)", out)
        self.run_brain("read", "--cite", cite, "T1", "T1", "T2")  # T1 reads 2, T2 reads 1
        out = self.cite_add(cite, [{"page": "pmpm", "side": "team", "why": "whole"}])
        self.assertIn("replaced: T1 Traps, T2 Decisions by T4 pmpm > (whole page) (team)", out)
        t = cite_tables(slurp(cite))
        self.assertEqual(t["Team"], ["T4 [[pmpm]] | (whole page)", "T3 [[high-cost-claimants]] | (whole page)"])
        self.assertRegex(slurp(cite), r"\| T4 \| \[\[pmpm\]\] \| \(whole page\) \| \d+ \| 3 \| whole \|")
        self.cite_add(cite, [{"page": "ibnr", "section": "Traps", "side": "team", "why": "new"}])
        self.assertIn("T5 [[ibnr]] | Traps", cite_tables(slurp(cite))["Team"])  # T1, T2 never reused

    def test_read_chained_ids_and_direct_targets_in_order(self):
        sample = self.path("sample-project/braincite.md")
        p = self.run_brain("read", "--cite", sample, "T3", "stop-loss > Decisions", "p1", "pmpm",
                           "--side", "team")
        out = p.stdout
        heads = [ln for ln in out.splitlines() if ln.startswith("=== ")]
        self.assertEqual(heads[0], "=== T3 team stop-loss > Traps (8 lines) ===")
        self.assertEqual(heads[1], "=== T2 team stop-loss > Decisions (5 lines) ===")
        self.assertRegex(heads[2], r"^=== P1 personal q4-renewal-analysis \(\d+ lines\) ===$")
        self.assertRegex(heads[3], r"^=== T5 team pmpm \(\d+ lines\) ===$")  # unlisted: new entry
        self.assertTrue(out.startswith("=== T3 team stop-loss > Traps (8 lines) ===\n## Traps\n\n- Specific claims"))
        self.assertIn("=== T2 team stop-loss > Decisions (5 lines) ===\n## Decisions\n", out)
        self.assertNotIn("## Reference", out.split("=== T2")[0])
        self.assertNotIn("description:", out)
        n_lines = len(out.splitlines())
        self.assertEqual(n_lines, sum(int(re.search(r"\((\d+) lines\)", h).group(1)) + 1 for h in heads))
        text = slurp(sample)
        self.assertRegex(text, r"\| T3 \| \[\[stop-loss\]\] \| Traps \| 8 \| 1 \|")
        self.assertRegex(text, r"\| T2 \| \[\[stop-loss\]\] \| Decisions \| 5 \| 1 \|")
        self.assertRegex(text, r"\| P1 \| \[\[q4-renewal-analysis\]\] \| \(whole page\) \| \d+ \| 1 \|")
        self.assertRegex(text, r"\| T5 \| \[\[pmpm\]\] \| \(whole page\) \| \d+ \| 1 \| "
                               r"Read directly \(not listed by the analyst\)\. \|")
        # a section of a page with a whole-page entry gets its own entry
        self.run_brain("read", "--cite", sample, "pmpm > Traps", "--side", "team")
        self.assertIn("T6 [[pmpm]] | Traps", cite_tables(slurp(sample))["Team"])
        self.assertRegex(slurp(sample), r"\| T5 \| \[\[pmpm\]\] \| \(whole page\) \| \d+ \| 1 \|")

    def test_read_counts_survive_cite_add_and_report(self):
        sample = self.path("sample-project/braincite.md")
        self.run_brain("read", "--cite", sample, "T1", "t1", "P2")
        self.cite_add(sample, [{"page": "ibnr", "section": "Traps", "side": "team", "why": "x"}])
        text = slurp(sample)
        self.assertRegex(text, r"\| T1 \| \[\[stop-loss\]\] \| Overview \| \d+ \| 2 \|")
        self.assertRegex(text, r"\| P2 \| \[\[stop-loss\]\] \| Traps \| \d+ \| 1 \|")
        out = self.run_brain("candidates", "--cite", sample).stdout
        self.assertIn("T1 | stop-loss | Overview | team | 2 reads |", out)
        self.assertIn("T5 | ibnr | Traps | team | 0 reads |", out)
        out = self.run_brain("read", "--cite", sample, "--report").stdout
        self.assertIn("T1 | stop-loss > Overview | team | 6 lines | 2 reads", out)
        self.assertIn("read: 2 entries, 18 lines in total (lines x reads)", out)
        self.assertIn("never read: 5 of 7 entries", out)
        before = slurp(sample)
        out = self.run_brain("read", "--cite", sample, "--no-count", "T1", "stop-loss > Notes", "--side", "team").stdout
        self.assertIn("=== T1 team stop-loss > Overview", out)
        self.assertIn("=== - team stop-loss > Notes", out)
        self.assertEqual(slurp(sample), before)

    def test_read_bad_targets_dictionary_and_missing_cite(self):
        sample = self.path("sample-project/braincite.md")
        p = self.run_brain("read", "--cite", sample, "T3", "T99", "claims-header-dictionary", "stop-loss",
                           "pmpm > Nope", "P2", ok=1)
        self.assertIn("error: T99: no entry T99", p.stderr)
        self.assertIn("error: claims-header-dictionary: REFUSED", p.stderr)
        self.assertIn("error: stop-loss: 'stop-loss' is on both sides; pass --side team or --side personal", p.stderr)
        self.assertIn("error: pmpm > Nope:", p.stderr)
        self.assertEqual([ln[:6] for ln in p.stdout.splitlines() if ln.startswith("===")], ["=== T3", "=== P2"])
        p = self.run_brain("read", "--cite", sample, "claims-header-dictionary > Change history", "--side", "team",
                           ok=1)
        self.assertIn("REFUSED", p.stderr)
        self.assertEqual(p.stdout, "")
        self.assertNotIn("dictionary", slurp(sample))
        p = self.run_brain("read", "T1", ok=3)  # no --cite, no braincite.md in the current folder
        self.assertIn("pass --cite", p.stderr)
        out = self.run_brain("read", "--no-count", "pmpm > Traps", "--side", "team").stdout  # peek, no file
        self.assertTrue(out.startswith("=== - team pmpm > Traps"))

    def test_read_upgrades_old_format_in_place(self):
        old = os.path.join(self.tmp, "old", "braincite.md")
        os.makedirs(os.path.dirname(old))
        with open(old, "w", encoding="utf-8") as f:
            f.write("# BrainSight: old\n\n## Team\n\n| Page | Section | Lines | Why read it |\n|---|---|---|---|\n"
                    "| [[stop-loss]] | Traps | 6 | Why A. |\n| [[ibnr]] | (whole page) | 39 | Why B. |\n\n"
                    "## Personal\n\n| Page | Section | Lines | Why read it |\n|---|---|---|---|\n"
                    "| [[pmpm]] | Traps | 2 | Why C. |\n")
        out = self.run_brain("read", "--cite", old, "T1").stdout
        self.assertTrue(out.startswith("=== T1 team stop-loss > Traps"))
        text = slurp(old)
        self.assertIn("| # | Page | Section | Lines | Reads | Why read it |", text)
        self.assertRegex(text, r"\| T1 \| \[\[stop-loss\]\] \| Traps \| 8 \| 1 \| Why A\. \|")
        self.assertRegex(text, r"\| T2 \| \[\[ibnr\]\] \| \(whole page\) \| 39 \| 0 \| Why B\. \|")
        self.assertRegex(text, r"\| P1 \| \[\[pmpm\]\] \| Traps \| 2 \| 0 \| Why C\. \|")
        self.assertIn("<!-- braincite-next: T3 P2 -->", text)

    def test_read_twenty_parallel_processes_lose_no_count(self):
        sample = self.path("sample-project/braincite.md")
        procs = [subprocess.Popen([sys.executable, BRAIN, "--wiki", self.wiki, "read", "--cite", sample, "T3"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) for _ in range(20)]
        errs = [p.communicate()[1] for p in procs]
        self.assertEqual([p.returncode for p in procs], [0] * 20, errs)
        self.assertRegex(slurp(sample), r"\| T3 \| \[\[stop-loss\]\] \| Traps \| 8 \| 20 \|")
        self.assertFalse(os.path.exists(sample + ".lock"))
        self.assertEqual([f for f in os.listdir(os.path.dirname(sample)) if f.endswith(".tmp")], [])

    def test_candidates_reads_sample_braincite(self):
        sample = self.path("sample-project/braincite.md")
        out = self.run_brain("candidates", "--cite", sample).stdout
        self.assertIn("T1 | stop-loss | Overview | team | 0 reads | Read before", out)
        self.assertIn("P1 | q4-renewal-analysis | (whole page) | personal | 0 reads | Read before", out)
        self.assertIn("'## [[page]] > Section'", out)
        out = self.run_brain("candidates", "--cite", sample, "--side", "team").stdout
        self.assertNotIn("| personal |", out)
        self.run_brain("candidates", "--sight", sample, ok=2)  # old option name is gone
        self.run_brain("sight-add", "--rows", sample, ok=2)    # old command name is gone
        self.run_brain("candidates", "--cite", self.path("sample-project/none.md"), ok=3)
        self.assertEqual(list(cite_tables(slurp(sample)).keys()), ["Team", "Personal"])

    # ------------------------------------------------------- config, help
    def test_config_file_overrides(self):
        os.rename(self.path("personal"), self.path("mine"))
        p = self.run_brain("pagelist", ok=3)
        self.assertIn("personal_dir", p.stderr)
        cfg = {"personal_dir": "mine", "personal_rules": "mine/rules.md", "personal_tags": "mine/tags.md",
               "raw_dir": "mine/raw", "session_facts_dir": "mine/raw/session-facts",
               "processed_dir": "mine/raw/processed", "sources_dir": "mine/sources", "dictionary_patterns": []}
        with open(self.path("brain-config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        out = self.run_brain("pagelist").stdout
        self.assertIn("5 personal, 9 team; 0 dictionaries excluded", out)
        with open(self.path("brain-config.json"), "w", encoding="utf-8") as f:
            json.dump({"no_such_key": 1}, f)
        p = self.run_brain("pagelist", ok=2)
        self.assertIn("unknown key 'no_such_key'", p.stderr)

    def test_help_for_every_command(self):
        cmds = ["pagelist", "summary", "approve", "collect", "markfiled", "log", "promote", "sections",
                "read", "candidates", "cite-add", "root"]
        top = subprocess.run([sys.executable, BRAIN, "--help"], capture_output=True, text=True)
        self.assertEqual(top.returncode, 0)
        for c in cmds:
            self.assertIn(c, top.stdout)
            p = subprocess.run([sys.executable, BRAIN, c, "--help"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, c)
            self.assertIn("usage: brain.py %s" % c, p.stdout)

    # ------------------------------------------------------ fix round 2
    def test_sections_start_and_lines_read_exactly_one_section(self):
        out = self.run_brain("sections", "--side", "team").stdout
        block = out.split("[[stop-loss]] team/stop-loss.md")[1]
        m = re.search(r"\n  Traps \| (\d+) \| (\d+)\n", block)
        start, n = int(m.group(1)), int(m.group(2))
        lines = self.read("team/stop-loss.md").split("\n")
        got = lines[start - 1:start - 1 + n]
        self.assertEqual(got[0], "## Traps")
        self.assertTrue(got[-1].startswith("- Aggregate attachment is a percentage"))
        self.assertEqual(lines[start - 1 + n].strip(), "")
        self.assertEqual(lines[start + n], "## Reference")
        out = self.run_brain("sections", "--side", "team", "--out", "brain-work/new/sec.txt").stdout
        self.assertIn("wrote brain-work/new/sec.txt", out)
        self.assertIn("  Traps | %d | %d\n" % (start, n), self.read("brain-work/new/sec.txt"))
        self.run_brain("summary", "--status", "all", "--out", "brain-work/s/summary.txt")
        self.assertIn("total:", self.read("brain-work/s/summary.txt"))

    def test_team_write_guard_blocks_markfiled(self):
        self.run_brain("collect")
        team_page = self.read("team/ibnr.md")
        raw = {f: open(self.path(f), "rb").read() for f in ("team/ibnr.md", "team/claims-header-dictionary.md")}

        def restore(f):
            with open(self.path(f), "wb") as fh:
                fh.write(raw[f])

        self.write("team/ibnr.md", team_page + "- An intake agent wrote here.\n")
        p = self.run_brain("markfiled", ok=1)
        self.assertIn("team/ibnr.md", p.stderr)
        self.assertIn("nothing was filed", p.stderr)
        self.assertIn("status: approved", self.read("personal/sources/2026-11-12-session-mlr-rebuild.md"))
        restore("team/ibnr.md")
        self.write("team/claims-header-dictionary.md", self.read("team/claims-header-dictionary.md") + "x\n")
        p = self.run_brain("markfiled", ok=1)
        self.assertIn("team/claims-header-dictionary.md", p.stderr)
        restore("team/claims-header-dictionary.md")
        self.run_brain("markfiled")
        self.assertIn("status: filed", self.read("personal/sources/2026-11-12-session-mlr-rebuild.md"))
        # promotion: its own team page is exempt, any other team file is not
        lines = self.read("personal/pmpm.md").split("\n")
        ln = [i + 1 for i, x in enumerate(lines) if x.startswith("- Account managers like")][0]
        self.run_brain("promote", "pmpm", "--lines", str(ln))
        self.write("team/pmpm.md", self.read("team/pmpm.md") + "- filed by the filer\n")
        self.write("team/ibnr.md", team_page + "- stray\n")
        p = self.run_brain("markfiled", "--promoted", "pmpm", ok=1)
        self.assertIn("changed files other than team/pmpm.md: team/ibnr.md\n", p.stderr)
        restore("team/ibnr.md")
        self.run_brain("markfiled", "--promoted", "pmpm")

    def test_promote_template_twin_link_empty_headings_and_cites(self):
        page = "q4-renewal-analysis"
        lines = self.read("personal/%s.md" % page).split("\n")
        purpose = [i + 1 for i, x in enumerate(lines) if x.startswith("- ") and i < 12]
        self.assertEqual(len(purpose), 2)  # the whole Purpose section
        self.write("personal/%s.md" % page, "\n".join(
            x + (" (src: personal/sources/old.md)" if i + 1 == purpose[1] else "") for i, x in enumerate(lines)))
        show = self.run_brain("promote", page, "--show").stdout
        self.assertIn("L%d [no source] - Build renewal cost packs" % purpose[0], show)
        self.assertIn("[first person]", self.run_brain("promote", "stop-loss", "--show").stdout)
        out = self.run_brain("promote", page, "--lines", "%d,%d" % tuple(purpose), "--template", "concept").stdout
        self.assertIn("team page created from template: team/%s.md" % page, out)
        self.assertIn("empty headings dropped: Purpose", out)
        team = self.read("team/%s.md" % page)
        self.assertIn("description: TODO", team)
        self.assertIn("template: concept", team)
        self.assertIn("# %s\n\n## Overview\n\n## How it fits" % page, team)
        self.assertNotIn("Mistakes people make", team)  # placeholder text removed
        pers = self.read("personal/%s.md" % page)
        self.assertIn("twin_of: %s" % page, pers)
        self.assertIn("Team page: [%s](../team/%s.md)" % (page, page), pers)
        self.assertNotIn("## Purpose", pers)
        pk = self.read("brain-work/packets/team-%s.md" % page)
        self.assertRegex(pk, r"Build renewal cost packs .*\(src: promoted \d{4}-\d\d-\d\d\)")
        self.assertNotIn("personal/", pk.split("## Bullets")[1])
        self.assertIn("keep its (src: ...) unchanged", pk)

    def test_promote_warns_on_stripped_doubt_tag(self):
        lines = self.read("personal/stop-loss.md").split("\n")
        ln = [i + 1 for i, x in enumerate(lines) if "#verify" in x][0]
        self.assertIn("[#verify]", self.run_brain("promote", "stop-loss", "--show").stdout)
        out = self.run_brain("promote", "stop-loss", "--lines", str(ln)).stdout
        self.assertIn("warn: doubt tag #verify stripped from L%d" % ln, out)
        self.assertIn("(src: 2026-10-09-ingest-carrier-call-notes)",
                      self.read("brain-work/packets/team-stop-loss.md"))  # existing cite kept

    def test_log_out_text_and_missing_in_file(self):
        p = self.run_brain("log", "brain-filer", "--in-file", "no/such.md", "--in-chars", "5", "--out-text", "abcd")
        self.assertIn("warn: --in-file not found", p.stdout)
        self.assertIn("in=5 out=4", p.stdout)
        self.write("brain-work/packets/x.md", "12345")
        p = self.run_brain("log", "brain-filer", "--in-file", "brain-work/packets/x.md")  # wiki-root relative
        self.assertIn("in=5 out=0", p.stdout)

    def test_zz_source_test_wiki_unchanged(self):
        self.assertEqual(tree_hash(SOURCE_WIKI), SOURCE_HASH, "a test modified test-wiki/ itself")


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False).result
    if tree_hash(SOURCE_WIKI) != SOURCE_HASH:
        print("FAIL: test-wiki/ was modified by the tests")
        sys.exit(1)
    sys.exit(0 if result.wasSuccessful() else 1)
