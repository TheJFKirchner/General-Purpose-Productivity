"""List every wiki page with its description and section headings.

Usage:  python wiki_index.py "<wiki root>"
Writes: <wiki root>/brain-work/index.md  (and prints where it wrote it)

It only lists what is there. It makes no decisions and changes no page.
Standard library only.
"""
import fnmatch
import os
import sys

SIDES = ["team", "personal"]                      # page folders under the wiki root
SKIP_FILES = ["rules.md", "tags.md"]              # not pages
SKIP_FOLDERS = ["templates", "raw", "sources", "brain-work"]
DICTIONARY_PATTERNS = ["*-dictionary.md", "*.dictionary.md"]   # never listed


def describe(lines):
    """Return (description, twin_of) from the frontmatter, if any."""
    desc = twin = ""
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            key, _, value = line.partition(":")
            if key.strip() == "description":
                desc = value.strip()
            elif key.strip() == "twin_of":
                twin = value.strip()
    return desc, twin


def main():
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit('usage: python wiki_index.py "<wiki root>"')
    root = os.path.abspath(sys.argv[1])
    out = ["# Wiki index", "",
           "One block per page: path | lines | description. Under it, each section heading and its line number.",
           "Data dictionaries, rules, tags and templates are not pages and are not listed.", ""]
    count = 0
    for side in SIDES:
        out += ["## " + side, ""]
        for folder, subfolders, files in os.walk(os.path.join(root, side)):
            subfolders[:] = sorted(d for d in subfolders if d not in SKIP_FOLDERS)
            for name in sorted(files):
                if not name.endswith(".md") or name in SKIP_FILES:
                    continue
                if any(fnmatch.fnmatch(name, p) for p in DICTIONARY_PATTERNS):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as f:
                    lines = f.read().splitlines()
                desc, twin = describe(lines)
                rel = os.path.relpath(path, root).replace("\\", "/")
                head = "%s | %d lines | %s" % (rel, len(lines), desc or "(no description)")
                if twin:
                    head += " | personal additions to team page '%s'" % twin
                out.append(head)
                for number, line in enumerate(lines, 1):
                    if line.startswith("## "):
                        out.append("  %s (line %d)" % (line[3:].strip(), number))
                out.append("")
                count += 1
    target = os.path.join(root, "brain-work", "index.md")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print("index written: %s (%d pages)" % (target.replace("\\", "/"), count))


if __name__ == "__main__":
    main()
