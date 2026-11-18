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


def sight_tables(text):
    """{side title: ['[[page]] | Section', ...] or ['None.']} in file order."""
    out, side = {}, None
    for ln in text.splitlines():
        if ln.startswith("## "):
            side = ln[3:].strip()
            out[side] = []
        elif side and ln.startswith("| [["):
            cells = [c.strip() for c in ln.strip("|").split("|")]
            out[side].append("%s | %s" % (cells[0], cells[1]))
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
        for skipped in ("rules", "tags", "concept", "metric", "2026-11-12-session-mlr-rebuild", "brainsight"):
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
        p = self.run_brain("section", "claims-header-dictionary", "Change history", ok=1)
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

    # --------------------------------------------------------- brainsight
    def test_section_returns_only_that_section(self):
        out = self.run_brain("section", "stop-loss", "traps", "--side", "team").stdout
        self.assertTrue(out.startswith("team/stop-loss.md | Traps\n## Traps"))
        self.assertIn("lasered member has a higher attachment point", out)
        self.assertNotIn("## Reference", out)
        self.assertNotIn("## Decisions", out)
        self.assertNotIn("Reimbursement formula", out)
        p = self.run_brain("section", "stop-loss", "Traps", ok=1)  # on both sides
        self.assertIn("--side", p.stderr)
        p = self.run_brain("section", "pmpm", "No such heading", "--side", "team", ok=3)
        self.assertIn("headings: Overview, Decisions", p.stderr)

    def test_sections_index_excludes_dictionary_and_shows_page_lines(self):
        out = self.run_brain("sections", "--side", "team").stdout
        self.assertNotIn("dictionary", out.lower())
        self.assertIn("[[stop-loss]] team/stop-loss.md | 49 lines |", out)
        self.assertIn("twin: personal/stop-loss.md", out)
        self.assertRegex(out, r"\n  Overview \| \d+ \| \d+\n")
        self.assertNotRegex(out, r"\| (plan|work)\n")
        out = self.run_brain("sections", "--side", "personal").stdout
        self.assertIn("twin of stop-loss", out)
        self.assertIn("  Purpose | 7 | 4\n", out)
        self.assertNotIn("team/", out.replace("twin of", ""))

    def test_section_without_heading_prints_whole_page(self):
        out = self.run_brain("section", "q4-renewal-analysis").stdout
        self.assertTrue(out.startswith("personal/q4-renewal-analysis.md | (whole page)\n# q4-renewal-analysis"))
        self.assertNotIn("description:", out)
        self.assertIn("## Purpose", out)
        self.assertIn("After delivery, move durable lessons", out)

    def test_sight_add_validates_dedups_and_whole_page(self):
        sight = os.path.join(self.tmp, "proj", "brainsight.md")
        rows = os.path.join(self.tmp, "rows.json")

        def add(data):
            with open(rows, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return self.run_brain("sight-add", "--sight", sight, "--rows", rows, "--title", "Test").stdout

        out = add([
            {"page": "pmpm", "section": "Traps", "side": "team", "why": "a"},
            {"page": "pmpm", "section": "Decisions", "side": "team", "why": "b"},
            {"page": "high-cost-claimants", "side": "team", "why": "c"},
            {"page": "pmpm", "section": "Traps", "side": "personal", "why": "d"},
            {"page": "pmpm", "section": "Nope", "side": "team", "why": "x"},
            {"page": "claims-header-dictionary", "section": "Change history", "side": "team", "why": "x"},
            {"page": "pmpm", "side": "nowhere", "why": "x"},
        ])
        self.assertIn("rejected: row 5 (pmpm > Nope, team): heading not found", out)
        self.assertIn("table team: added 3, already there 0, rejected 2", out)
        self.assertIn("table personal: added 1, already there 0, rejected 0", out)
        self.assertIn("total: 4 added, 0 already there, 3 rejected", out)
        t = sight_tables(slurp(sight))
        self.assertEqual(list(t.keys()), ["Team", "Personal"])
        self.assertEqual(t["Team"], ["[[pmpm]] | Traps", "[[pmpm]] | Decisions",
                                     "[[high-cost-claimants]] | (whole page)"])
        self.assertEqual(t["Personal"], ["[[pmpm]] | Traps"])
        self.assertIn("| Page | Section | Lines | Why read it |", slurp(sight))
        self.assertIn("| [[high-cost-claimants]] | (whole page) | 38 | c |", slurp(sight))
        self.assertNotIn("Topic", slurp(sight))
        out = add([{"page": "pmpm", "section": "Traps", "side": "team", "why": "dup"},
                   {"page": "high-cost-claimants", "section": "Traps", "side": "team", "why": "covered"}])
        self.assertIn("table team: added 0, already there 2, rejected 0", out)
        self.assertIn("(covered by whole page)", out)
        out = add([{"page": "pmpm", "section": "", "side": "team", "why": "whole"}])
        self.assertIn("replaced: pmpm > Traps, Decisions (team) by (whole page)", out)
        t = sight_tables(slurp(sight))
        self.assertEqual(t["Team"], ["[[pmpm]] | (whole page)", "[[high-cost-claimants]] | (whole page)"])
        self.assertEqual(t["Personal"], ["[[pmpm]] | Traps"])  # other side untouched
        tsv = os.path.join(self.tmp, "rows.tsv")
        with open(tsv, "w", encoding="utf-8") as f:
            f.write("page\tsection\tside\twhy\nstop-loss\tOverview\tpersonal\tFrame it.\n")
        self.run_brain("sight-add", "--sight", sight, "--rows", tsv)
        self.assertEqual(sight_tables(slurp(sight))["Personal"], ["[[pmpm]] | Traps", "[[stop-loss]] | Overview"])

    def test_candidates_reads_sample_brainsight(self):
        sample = self.path("sample-project/brainsight.md")
        out = self.run_brain("candidates", "--sight", sample).stdout
        self.assertIn("stop-loss | Overview | team | Read before", out)
        self.assertIn("stop-loss | Traps | personal | Read before", out)
        self.assertIn("q4-renewal-analysis | (whole page) | personal | Read before", out)
        self.assertIn("'## [[page]] > Section'", out)
        out = self.run_brain("candidates", "--sight", sample, "--side", "team").stdout
        self.assertNotIn("| personal |", out)
        self.run_brain("candidates", "--sight", sample, "--use", "plan", ok=2)  # removed option
        self.run_brain("candidates", "--sight", self.path("sample-project/none.md"), ok=3)
        t = sight_tables(slurp(sample))
        self.assertEqual(list(t.keys()), ["Team", "Personal"])
        self.assertIn("[[q4-renewal-analysis]] | (whole page)", t["Personal"])

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
                "section", "candidates", "sight-add", "root"]
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
        self.write("team/ibnr.md", team_page + "- An intake agent wrote here.\n")
        p = self.run_brain("markfiled", ok=1)
        self.assertIn("team/ibnr.md", p.stderr)
        self.assertIn("nothing was filed", p.stderr)
        self.assertIn("status: approved", self.read("personal/sources/2026-11-12-session-mlr-rebuild.md"))
        self.write("team/ibnr.md", team_page)
        self.write("team/claims-header-dictionary.md", self.read("team/claims-header-dictionary.md") + "x\n")
        p = self.run_brain("markfiled", ok=1)
        self.assertIn("team/claims-header-dictionary.md", p.stderr)
        self.write("team/claims-header-dictionary.md", self.read("team/claims-header-dictionary.md")[:-2])
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
        self.write("team/ibnr.md", team_page)
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
