"""An HTML file as a tree with exact source positions, data-free views of it, and safe edits.

Used by the editor server, the assistant's tools and the she.py command line.

1. Parse. Every element and text run knows its exact span in the original text, so an edit splices
   only those characters. Everything else in the file stays byte-for-byte as it was.
2. Redact. outline(), path(), find_text() and view_markup() describe the page WITHOUT its data:
   scripts, styles, charts, embedded files, data attributes and data-table cells are summarized, and
   numbers in text become {#1}, {#2} tokens. This is all the assistant (or Claude Code) ever sees.
3. Edit. set_text, set_style, set_attr, set_theme_var, set_page_rule, replace_markup. Each one is
   checked, is exactly one splice, and can be undone.

Ids: n12 = element, t45 = text run, v3 = theme variable (a CSS custom property). Element ids are
document order, so they stay put through every edit except replace_markup (which renumbers what
follows the edited element) and undo of one.
"""
from __future__ import annotations

import bisect
import html
import re
from html.parser import HTMLParser

VOID = frozenset("area base br col embed hr img input link meta param source track wbr keygen frame basefont bgsound".split())
FOREIGN = frozenset({"svg", "math"})
RAWTEXT = frozenset({"script", "style", "xmp", "noembed", "noframes", "noscript", "iframe"})
# Elements whose content is never shown, and what the outline calls them.
HIDDEN = {
    "script": "script", "style": "CSS", "svg": "graphic", "math": "formula", "canvas": "canvas drawing",
    "iframe": "embedded page", "object": "embedded object", "embed": "embedded object", "template": "template",
    "noscript": "no-script fallback", "video": "video", "audio": "audio", "picture": "picture",
    "map": "image map", "select": "drop-down", "datalist": "list", "textarea": "text box",
    "xmp": "raw text", "noembed": "raw text", "noframes": "raw text",
}
# Tags whose opening closes an open <p> (HTML parsing rules, simplified).
P_CLOSERS = frozenset(
    "address article aside blockquote center details dialog dir div dl fieldset figcaption figure footer form "
    "h1 h2 h3 h4 h5 h6 header hgroup hr main menu nav ol p pre section summary table ul li dd dt".split())
SCOPE = frozenset("applet caption html table td th marquee object template button".split())
HEADINGS = frozenset("h1 h2 h3 h4 h5 h6".split())
NEEDS_RULE = P_CLOSERS | HEADINGS | frozenset("li dt dd td th tr thead tbody tfoot option optgroup".split())

# Numbers in text: 12 · 1,234.5 · $4.2M · 45% · 2025-01-31 · 12:30 · 3/4
NUM = re.compile(r"[$€£¥]?\d+(?:[.,:/-]\d+)*%?(?:[kKMB](?![A-Za-z]))?")
TOKEN = re.compile(r"\{#(\d+)\}")
CUSTOM_STYLE_ID = "she-custom"
MASKED_ATTRS = ("title", "alt", "aria-label", "placeholder", "value")
LONG_TEXT = 600            # longer runs need old_text for a partial edit (never fully retyped)
MAX_MARKUP = 6000          # largest element replace_markup works on

MARKUP_TAGS = frozenset(
    "a abbr article aside b bdi bdo blockquote br cite code dd del details dfn div dl dt em figcaption figure "
    "footer h1 h2 h3 h4 h5 h6 header hr i ins kbd li main mark nav ol p pre q s samp section small span strong "
    "sub summary sup time u ul var".split())
MARKUP_ATTRS = frozenset("class id style title href target rel lang dir role datetime".split())
SET_ATTRS = frozenset("class title alt aria-label href target rel hidden lang dir role".split())


class EditError(ValueError):
    """An edit that was refused. The message says why, in words a model or a person can act on."""


# ---------------------------------------------------------------- small helpers

def mask(text: str) -> tuple[str, list[str]]:
    """'Revenue grew 12% to $4.2M' -> ('Revenue grew {#1} to {#2}', ['12%', '$4.2M'])."""
    tokens: list[str] = []

    def sub(m):
        tokens.append(m.group(0))
        return "{#%d}" % len(tokens)
    return NUM.sub(sub, text), tokens


def unmask(masked: str, tokens: list[str], allowed_digits: str | None) -> str:
    """Put the real numbers back. Typed digits are refused unless they appear in allowed_digits
    (the user's own message); allowed_digits=None allows any (the person or Claude Code typed them)."""
    if allowed_digits is not None:
        for d in re.findall(r"\d+", TOKEN.sub("", masked)):
            if d not in allowed_digits:
                raise EditError(f"typed number {d!r}: numbers stay as their {{#k}} tokens. Keep or drop tokens; "
                                "type a new number only if the user typed it in their message.")

    def sub(m):
        k = int(m.group(1))
        if not 1 <= k <= len(tokens):
            raise EditError(f"unknown number token {{#{k}}}: this text has {len(tokens)} token(s).")
        return tokens[k - 1]
    return TOKEN.sub(sub, masked)


def short(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def fmt_size(chars: int) -> str:
    if chars >= 1_000_000:
        return f"{chars / 1_000_000:.1f} MB"
    if chars >= 1_000:
        return f"{chars / 1_000:.0f} KB"
    return f"{chars} chars"


def check_css_value(value: str) -> str:
    v = value.strip()
    if not v:
        raise EditError("empty CSS value")
    if len(v) > 300:
        raise EditError("CSS value too long (max 300 characters)")
    if re.search(r"[;{}<>]|url\s*\(|expression\s*\(|javascript:|@import|\\", v, re.I):
        raise EditError(f"CSS value {short(v, 60)!r} is not allowed (no ; {{ }} < > url() expression() javascript: @import or backslashes)")
    return v


def check_css_prop(prop: str) -> str:
    p = prop.strip().lower()
    if not re.fullmatch(r"(--[a-z0-9_-]+|-?[a-z][a-z-]*)", p):
        raise EditError(f"bad CSS property {prop!r}")
    return p


def split_decls(style: str) -> list[list[str]]:
    """'color: red; background: url(a;b)' -> [['color', 'red'], ['background', 'url(a;b)']]"""
    out, depth, quote, cur = [], 0, None, ""
    for ch in style:
        if quote:
            quote = None if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            out.append(cur)
            cur = ""
            continue
        cur += ch
    out.append(cur)
    decls = []
    for d in out:
        if ":" in d:
            p, v = d.split(":", 1)
            if p.strip():
                decls.append([p.strip().lower(), v.strip()])
    return decls


def parse_decls(text: str) -> list[list[str]]:
    """Checked declarations for a page rule: 'color: #333; font-weight: 600'."""
    decls = split_decls(text)
    if not decls and text.strip():
        raise EditError("declarations must look like 'color: #333; font-weight: 600'")
    return [[check_css_prop(p), check_css_value(v)] for p, v in decls]


_ATTR = re.compile(r"""([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?""")
_SKIP = re.compile(r"[\s/]*")


def scan_attrs(raw: str, tag_len: int) -> list[tuple[str, str, int, int]]:
    """Attributes of a raw start tag with their spans: [(name, decoded value, start, end)]."""
    out, i, last = [], 1 + tag_len, len(raw) - 1
    while True:
        i = _SKIP.match(raw, i).end()
        if i >= last:
            return out
        m = _ATTR.match(raw, i)
        if not m or m.end() == i:
            i += 1
            continue
        val = next((g for g in m.groups()[1:] if g is not None), "")
        out.append((m.group(1).lower(), html.unescape(val), m.start(), m.end()))
        i = m.end()


# ---------------------------------------------------------------- parsing

class _Collector(HTMLParser):
    """Records where every token starts. A token's span runs to the next token's start."""

    def __init__(self, src: str):
        super().__init__(convert_charrefs=False)
        self.events: list[tuple[int, str, str | None]] = []
        self.attrs: list[list] = []
        self._lines = [0] + [m.end() for m in re.finditer("\n", src)]

    def _at(self) -> int:
        line, col = self.getpos()
        return self._lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        self.events.append((self._at(), "start", tag))
        self.attrs.append(attrs)

    def handle_startendtag(self, tag, attrs):
        self.events.append((self._at(), "startend", tag))
        self.attrs.append(attrs)

    def handle_endtag(self, tag):
        self.events.append((self._at(), "end", tag))

    def handle_data(self, data):
        self.events.append((self._at(), "text", None))

    def handle_entityref(self, name):
        self.events.append((self._at(), "text", None))

    def handle_charref(self, name):
        self.events.append((self._at(), "text", None))

    def handle_comment(self, data):
        self.events.append((self._at(), "other", None))

    handle_decl = handle_pi = unknown_decl = handle_comment


def collect(src: str) -> _Collector:
    c = _Collector(src)
    c.feed(src)
    c.close()
    return c


# Fast tokenizer for whole documents: (start, end, kind, tag) with kind 0 text, 1 start tag,
# 2 self-closing start tag, 3 end tag, 4 comment/doctype/other. Raw-text elements (script, style,
# textarea, title, ...) are one text token up to their end tag. HTMLParser (collect) is still used
# to check small snippets of new markup.
_TOKEN = re.compile(r"""<(?:
      (!--.*?(?:--!?>|\Z))                              # 1 comment
    | ([!?][^>]*>?)                                     # 2 doctype, <?xml ...>, bogus comment
    | /([A-Za-z][^\s/>]*)[^>]*>?                        # 3 end tag
    | ([A-Za-z][^\s/>]*)((?:[^>"']|"[^"]*"|'[^']*')*)>  # 4 start tag, 5 its attributes
    )""", re.S | re.X)
_RAW_END: dict = {}
RCDATA = frozenset({"textarea", "title"})


def tokenize(src: str):
    n, pos, search = len(src), 0, _TOKEN.search
    while pos < n:
        m = search(src, pos)
        if m is None:
            yield pos, n, 0, None
            return
        s, e = m.start(), m.end()
        if s > pos:
            yield pos, s, 0, None
        if m.group(4) is not None:
            tag = m.group(4).lower()
            yield s, e, 2 if m.group(5).endswith("/") else 1, tag
            if tag in RAWTEXT or tag in RCDATA:
                pat = _RAW_END.get(tag) or _RAW_END.setdefault(tag, re.compile(r"</%s[\s/>]" % re.escape(tag), re.I))
                close = pat.search(src, e)
                stop = close.start() if close else n
                if stop > e:
                    yield e, stop, 0, None
                e = stop
        elif m.group(3) is not None:
            yield s, e, 3, m.group(3).lower()
        else:
            yield s, e, 4, None
        pos = e


class Node:
    __slots__ = ("id", "tag", "start", "tag_end", "close_start", "end", "parent", "children", "foreign", "index")

    def __init__(self, id_, tag, start, tag_end, parent, foreign=False):
        self.id, self.tag, self.start, self.tag_end = id_, tag, start, tag_end
        self.close_start = None          # offset of its explicit end tag, if it has one
        self.end = tag_end               # end of the element (after its end tag / where it was closed)
        self.parent, self.children, self.foreign, self.index = parent, [], foreign, 0


class Run:
    __slots__ = ("id", "start", "end", "parent")

    def __init__(self, id_, start, end, parent):
        self.id, self.start, self.end, self.parent = id_, start, end, parent


class Doc:
    def __init__(self, src: str, name: str = "page.html"):
        self.src = src
        self.name = name
        self.original = src
        self.newline = "\r\n" if "\r\n" in src else "\n"
        self.version = 0          # every change
        self.struct_seq = 0       # changes that renumber ids (reparse)
        self.undo_stack: list[tuple] = []
        self._parse()

    # ------------------------------------------------------------ build
    def _parse(self):
        src, n = self.src, len(self.src)
        root = Node("n0", "#document", 0, 0, None)
        root.end = n
        self.root = root
        nodes: dict[str, Node] = {"n0": root}
        node_list: list[Node] = [root]
        runs: dict[str, Run] = {}
        items: list = [root]               # nodes and runs in document order
        stack, run = [root], None
        rules, void, foreign_tags = NEEDS_RULE, VOID, FOREIGN
        implied = self._implied_close
        for at, end, kind, tag in tokenize(src):
            if kind == 0:  # text
                parent = stack[-1]
                if run is not None and run.parent is parent and run.end == at:
                    run.end = end
                else:
                    run = Run("t%d" % (len(runs) + 1), at, end, parent)
                    parent.children.append(run)
                    runs[run.id] = run
                    items.append(run)
                continue
            run = None
            if kind == 1 or kind == 2:  # start tag, self-closing start tag
                top = stack[-1]
                if tag in rules and not top.foreign:
                    implied(stack, tag, at)
                    top = stack[-1]
                fgn = top.foreign or tag in foreign_tags
                el = Node("n%d" % len(node_list), tag, at, end, top, fgn)
                el.index = len(node_list)
                top.children.append(el)
                nodes[el.id] = el
                node_list.append(el)
                items.append(el)
                if not (tag in void or (kind == 2 and fgn)):
                    stack.append(el)
            elif kind == 3:  # end tag
                for i in range(len(stack) - 1, 0, -1):
                    if stack[i].tag == tag:
                        while len(stack) > i + 1:
                            stack.pop().end = at
                        el = stack.pop()
                        el.close_start, el.end = at, end
                        break
        while len(stack) > 1:
            stack.pop().end = n
        self.nodes, self.node_list, self.runs, self.items = nodes, node_list, runs, items
        self._node_starts = [nd.start for nd in node_list]
        self._caches: dict = {}

    @staticmethod
    def _implied_close(stack, tag, at):
        """Close what HTML closes implicitly when `tag` opens (simplified HTML rules)."""
        def find(targets, stop, through=()):
            for i in range(len(stack) - 1, 0, -1):
                t = stack[i].tag
                if t in targets:
                    return i
                if t in stop or (t in SCOPE and t not in through):
                    return None
            return None

        def close_to(i):
            while len(stack) > i:
                stack.pop().end = at

        if tag in P_CLOSERS:
            i = find(("p",), ())
            if i is not None:
                close_to(i)
        i = None
        if tag == "li":
            i = find(("li",), ("ul", "ol"))
        elif tag in ("dt", "dd"):
            i = find(("dt", "dd"), ("dl",))
        elif tag in ("td", "th"):
            top = stack[-1].tag
            if top in ("td", "th"):          # the common case: no search
                i = len(stack) - 1
            elif top != "tr":
                i = find(("td", "th"), ("tr", "table"))
        elif tag == "tr":
            i = find(("tr",), ("table", "thead", "tbody", "tfoot"), ("td", "th"))
        elif tag in ("thead", "tbody", "tfoot"):
            i = find(("thead", "tbody", "tfoot"), ("table",), ("td", "th"))
        elif tag in ("option", "optgroup"):
            i = find(("option", "optgroup") if tag == "optgroup" else ("option",), ("select", "datalist"))
        elif tag in HEADINGS and stack[-1].tag in HEADINGS:
            i = len(stack) - 1
        if i is not None:
            close_to(i)

    # ------------------------------------------------------------ lookups
    def node(self, node_id: str) -> Node:
        nd = self.nodes.get(node_id)
        if nd is None or nd is self.root:
            raise EditError(f"unknown element {node_id!r}; use an id from an outline you were shown")
        return nd

    def run(self, run_id: str) -> Run:
        r = self.runs.get(run_id)
        if r is None:
            raise EditError(f"unknown text {run_id!r}; use a t-id from an outline you were shown")
        return r

    def attrs(self, nd: Node) -> list[tuple[str, str, int, int]]:
        cache = self._caches.setdefault("attrs", {})
        if nd.id not in cache:
            cache[nd.id] = scan_attrs(self.src[nd.start:nd.tag_end], len(nd.tag)) if nd is not self.root else []
        return cache[nd.id]

    def attr(self, nd: Node, name: str) -> str | None:
        return next((v for n, v, _, _ in self.attrs(nd) if n == name), None)

    def run_text(self, r: Run) -> str:
        raw = self.src[r.start:r.end]
        return raw if r.parent.tag in RAWTEXT else html.unescape(raw)

    def descendants(self, nd: Node) -> int:
        """Number of elements inside nd."""
        hi = bisect.bisect_left(self._node_starts, nd.end, lo=nd.index + 1)
        return max(0, hi - nd.index - 1)

    def ancestors(self, nd: Node):
        p = nd.parent
        while p is not None and p is not self.root:
            yield p
            p = p.parent

    def hidden_context(self, nd: Node) -> Node | None:
        """The hidden element (script, svg, ...) nd is in or is, if any."""
        cur = nd
        while cur is not None and cur is not self.root:
            if cur.tag in HIDDEN or (cur.tag != "svg" and cur.foreign):
                return cur
            cur = cur.parent
        return None

    def elements(self, nd: Node):
        """All elements inside nd, in order."""
        hi = bisect.bisect_left(self._node_starts, nd.end, lo=nd.index + 1)
        return self.node_list[nd.index + 1:hi]

    # ------------------------------------------------------------ redacted views
    def tag_label(self, nd: Node) -> str:
        a = {n: v for n, v, _, _ in self.attrs(nd)}
        s = nd.tag
        if a.get("id"):
            s += "#" + short(a["id"], 40)
        classes = a.get("class", "").split()
        if classes:
            s += "." + ".".join(classes[:4]) + ("…" if len(classes) > 4 else "")
        return s

    def label(self, nd: Node) -> str:
        extras, data_attrs = [], 0
        for name, val, _, _ in self.attrs(nd):
            if name in ("id", "class"):
                continue
            if name.startswith("on"):
                extras.append(f"{name}=[script]")
            elif name.startswith("data-"):
                data_attrs += 1
            elif name in ("src", "href", "poster", "srcset", "action", "xlink:href"):
                if val.lower().startswith("data:"):
                    extras.append(f"{name}=[embedded {fmt_size(len(val))}]")
                elif re.match(r"\s*(javascript|vbscript):", val, re.I):
                    extras.append(f"{name}=[script]")
                else:
                    extras.append(f'{name}="{short(val, 60)}"')
            elif name in MASKED_ATTRS:
                extras.append(f'{name}="{short(mask(val)[0], 80)}"')
            elif name == "style":
                extras.append(f'style="{short(val, 160)}"')
            elif len(val) > 200:
                extras.append(f"{name}=[{fmt_size(len(val))} hidden]")
            else:
                extras.append(f'{name}="{short(val, 40)}"' if val else name)
        if data_attrs:
            extras.append(f"data-*×{data_attrs}=[hidden]")
        return f"{nd.id} <{self.tag_label(nd)}{' ' + ' '.join(extras) if extras else ''}>"

    def path(self, nd: Node) -> str:
        chain = [a for a in reversed(list(self.ancestors(nd))) if a.tag not in ("html",)] + [nd]
        return " > ".join(f"{a.id} {self.tag_label(a)}" for a in chain)

    def run_visible(self, r: Run) -> bool:
        return r.parent.tag not in RAWTEXT and bool(self.src[r.start:r.end].strip())

    def show_text(self, r: Run, limit: int = LONG_TEXT, reveal: str | None = None) -> str:
        if r.parent.tag == "td" and r.parent.id != reveal and self._in_data_table(r.parent):
            return "[cell value hidden]"
        m = re.sub(r"\s+", " ", mask(self.run_text(r))[0]).strip()
        if len(m) > limit:
            return f'"{m[:limit]}… [+{len(m) - limit} chars]"'
        return f'"{m}"'

    def is_data_table(self, table: Node) -> bool:
        cache = self._caches.setdefault("datatable", {})
        if table.id in cache:
            return cache[table.id]
        rows = cells = numeric = 0
        has_th = False
        for el in self.elements(table):
            if el.tag == "tr":
                rows += 1
            elif el.tag == "th":
                has_th = True
            elif el.tag == "td":
                cells += 1
                if any(isinstance(c, Run) and NUM.search(self.src, c.start, c.end) for c in el.children):
                    numeric += 1
        result = rows > 25 or (has_th and rows > 2) or (cells > 0 and numeric / cells >= 0.3)
        cache[table.id] = result
        return result

    def hidden_summary(self, nd: Node) -> str | None:
        t = nd.tag
        inner = (nd.close_start or nd.end) - nd.tag_end
        if t == "script":
            src = self.attr(nd, "src")
            if src and not src.startswith("data:"):
                return f"script file {short(src.rsplit('/', 1)[-1], 50)}"
            kind = (self.attr(nd, "type") or "").lower()
            return f"{'data block' if 'json' in kind else 'script'}, {fmt_size(inner)} hidden"
        if t == "style":
            if self.attr(nd, "id") == CUSTOM_STYLE_ID:
                return "page rules added in the editor (listed separately)"
            return f"CSS, {fmt_size(inner)}; theme variables are listed separately"
        if t == "svg":
            shapes = sum(1 for e in self.elements(nd) if e.tag in ("path", "rect", "circle", "line", "polyline", "polygon", "text", "ellipse"))
            return f"graphic, {shapes} shapes hidden"
        if t in ("select", "datalist"):
            return f"{HIDDEN[t]}, {sum(1 for e in self.elements(nd) if e.tag == 'option')} options hidden"
        if t in HIDDEN:
            return f"{HIDDEN[t]}, content hidden"
        if t == "table" and self.is_data_table(nd):
            rows = cols = 0
            heads, caption = [], None
            for el in self.elements(nd):
                if el.tag == "table":
                    break
                if el.tag == "tr":
                    rows += 1
                    if rows == 1 or cols == 0:
                        cols = max(cols, sum(1 for c in el.children if isinstance(c, Node) and c.tag in ("td", "th")))
                elif el.tag == "th" and len(heads) < 12:
                    r = next((c for c in el.children if isinstance(c, Run) and self.run_visible(c)), None)
                    if r:
                        heads.append(f"{r.id} {self.show_text(r, 40)}")
                elif el.tag == "caption":
                    r = next((c for c in el.children if isinstance(c, Run) and self.run_visible(c)), None)
                    caption = f"{r.id} {self.show_text(r, 80)}" if r else None
            parts = [f"data table: {cols} columns × {rows:,} rows"]
            if caption:
                parts.append(f"caption {caption}")
            if heads:
                parts.append("headers " + ", ".join(heads))
            parts.append("cell values hidden")
            return "; ".join(parts)
        return None

    def outline(self, node_id: str = "n0", depth: int = 2, max_lines: int = 120, mark: str | None = None,
                reveal: str | None = None) -> str:
        """A data-free outline of an element: ids, tags, classes, short attributes, texts with numbers
        as {#k} tokens. Hidden parts (scripts, charts, data tables, ...) are one summary line each.
        Data-table cells show no text, except the one cell `reveal` (the cell the person clicked)."""
        start = self.root if node_id in ("n0", "page", "") else self.node(node_id)
        lines: list[str] = []

        class Full(Exception):
            pass

        def add(s):
            if len(lines) >= max_lines:
                raise Full
            lines.append(s)

        def emit(nd: Node, d: int, ind: str):
            here = "  ◀ selected" if mark and nd.id == mark else ""
            summary = self.hidden_summary(nd)
            if summary:
                return add(f"{ind}{self.label(nd)} [{summary}]{here}")
            kids = [c for c in nd.children if isinstance(c, Node) or self.run_visible(c)]
            elems = [c for c in kids if isinstance(c, Node)]
            if len(kids) == 1 and not elems:
                return add(f"{ind}{self.label(nd)} {kids[0].id} {self.show_text(kids[0], reveal=reveal)}{here}")
            if not kids:
                return add(f"{ind}{self.label(nd)}{here}")
            if d >= depth and elems:
                return add(f"{ind}{self.label(nd)} … ({_count(self.descendants(nd), 'element')} inside){here}")
            add(f"{ind}{self.label(nd)}{here}")
            counts: dict[str, int] = {}
            for e in elems:
                counts[e.tag] = counts.get(e.tag, 0) + 1
            shown: dict[str, int] = {}
            for c in kids:
                if isinstance(c, Run):
                    add(f"{ind}  {c.id} {self.show_text(c, reveal=reveal)}")
                    continue
                if counts[c.tag] > 12:
                    shown[c.tag] = shown.get(c.tag, 0) + 1
                    if shown[c.tag] == 4:
                        add(f"{ind}  … {counts[c.tag] - 3} more <{c.tag}> like these (hidden; outline one by id to see it)")
                    if shown[c.tag] > 3:
                        continue
                emit(c, d + 1, ind + "  ")

        try:
            if start is self.root:
                for c in start.children:
                    if isinstance(c, Node):
                        emit(c, 1, "")
            else:
                emit(start, 0, "")
        except Full:
            lines.append(f"… outline cut at {max_lines} lines; outline a child by id for more")
        return "\n".join(lines) or "(empty)"

    def around(self, node_id: str, reveal: str | None = None) -> str:
        nd = self.node(node_id)
        parent = nd.parent if nd.parent is not self.root else None
        head = f"Path: {self.path(nd)}"
        if parent is None:
            return head + "\n" + self.outline(nd.id, depth=1, reveal=reveal)
        return head + "\nParent and siblings:\n" + self.outline(parent.id, depth=1, mark=nd.id, reveal=reveal)

    def find_text(self, query: str, limit: int = 12) -> str:
        q = re.sub(r"\s+", " ", query).strip().lower()
        if not q:
            raise EditError("empty search")
        hits = []
        for r in self.runs.values():
            if not self.run_visible(r) or self.hidden_context(r.parent):
                continue
            if r.parent.tag == "td" and self._in_data_table(r.parent):
                continue
            m = re.sub(r"\s+", " ", mask(self.run_text(r))[0]).strip()
            if q in m.lower():
                hits.append(f"{r.id} in {self.label(r.parent)}  ({self.path(r.parent)}): {self.show_text(r, 160)}")
                if len(hits) >= limit:
                    break
        return "\n".join(hits) if hits else f"No visible text contains {query!r} (data-table cells and hidden parts are not searched)."

    def _in_data_table(self, nd: Node) -> bool:
        t = next((a for a in self.ancestors(nd) if a.tag == "table"), None)
        return bool(t and self.is_data_table(t))

    def page_summary(self) -> str:
        scripts = styles = svgs = canvases = media = 0
        script_chars = embedded = 0
        tables = []
        for nd in self.node_list[1:]:
            t = nd.tag
            if t == "script":
                scripts += 1
                script_chars += (nd.close_start or nd.end) - nd.tag_end
            elif t == "style":
                styles += 1
            elif t == "svg":
                svgs += 1
            elif t == "canvas":
                canvases += 1
            elif t in ("img", "video", "picture", "iframe"):
                media += 1
            elif t == "table" and self.is_data_table(nd):
                tables.append(sum(1 for e in self.elements(nd) if e.tag == "tr"))
        for m in re.finditer(r"data:[a-z]+/[a-z0-9.+-]+;base64,", self.src[:20_000_000]):
            embedded += 1
        parts = [f"{self.name}, {fmt_size(len(self.src))}, {len(self.node_list) - 1:,} elements"]
        hidden = []
        if scripts:
            hidden.append(f"{scripts} scripts ({fmt_size(script_chars)})")
        if tables:
            hidden.append(f"{len(tables)} data tables ({sum(tables):,} rows)")
        if svgs or canvases:
            hidden.append(f"{svgs + canvases} charts/graphics")
        if embedded:
            hidden.append(f"{embedded} embedded files")
        if media:
            hidden.append(f"{media} images/media")
        if hidden:
            parts.append("hidden: " + ", ".join(hidden))
        return "; ".join(parts) + "."

    # ------------------------------------------------------------ theme variables and page rules
    def css_vars(self) -> list[dict]:
        """CSS custom properties declared in <style> blocks: [{id, name, value, context, start, end, run}]."""
        if "vars" in self._caches:
            return self._caches["vars"]
        out = []
        for nd in self.node_list:
            if nd.tag != "style" or nd.foreign:
                continue
            for r in nd.children:
                if isinstance(r, Run):
                    for name, value, s, e, ctx in _scan_vars(self.src[r.start:r.end]):
                        out.append({"id": f"v{len(out) + 1}", "name": name, "value": value, "context": ctx,
                                    "start": r.start + s, "end": r.start + e, "run": r})
        self._caches["vars"] = out
        return out

    def theme_text(self) -> str:
        vs = self.css_vars()
        if not vs:
            return "(none: this page sets its colors and fonts directly; use set_page_rule for page-wide looks)"
        rows = [f"{v['id']} {short(v['context'], 50)}  {v['name']}: {short(v['value'], 80)}" for v in vs[:80]]
        if len(vs) > 80:
            rows.append(f"… {len(vs) - 80} more")
        return "\n".join(rows)

    def custom_block(self) -> Node | None:
        return next((nd for nd in self.node_list if nd.tag == "style" and self.attr(nd, "id") == CUSTOM_STYLE_ID), None)

    def page_rules(self) -> list[tuple[str, str]]:
        nd = self.custom_block()
        if nd is None:
            return []
        text = self.src[nd.tag_end:nd.close_start or nd.end]
        return [(m.group(1).strip(), m.group(2).strip()) for m in re.finditer(r"^\s*([^{}\n/][^{}\n]*?)\s*\{\s*([^{}]*?)\s*\}\s*$", text, re.M)]

    def page_rules_text(self) -> str:
        rules = self.page_rules()
        return "\n".join(f"{s} {{ {d} }}" for s, d in rules) if rules else "(none yet)"

    # ------------------------------------------------------------ edits
    def _change(self, start: int, end: int, new: str, structural: bool, owner, label: str) -> str:
        old = self.src[start:end]
        if old == new:
            return "No change."
        self.src = self.src[:start] + new + self.src[end:]
        owner_id = None if structural or owner is None else owner.id
        self.undo_stack.append((start, start + len(new), old, label, owner_id))
        self.version += 1
        if structural:
            self._parse()
            self.struct_seq += 1
        else:
            self._shift(end, len(new) - len(old), owner)
        return "Done."

    def _shift(self, end: int, delta: int, owner):
        """Move every position at or after `end` by delta (an edit that kept the structure)."""
        def fix(obj):
            if obj.start >= end:
                obj.start += delta
            obj.end += delta if obj.end >= end else 0
            if isinstance(obj, Node):
                if obj.tag_end >= end:
                    obj.tag_end += delta
                if obj.close_start is not None and obj.close_start >= end:
                    obj.close_start += delta

        chain = [owner] + list(self.ancestors(owner if isinstance(owner, Node) else owner.parent))
        if isinstance(owner, Run):
            chain.insert(1, owner.parent)
        seen = set()
        for obj in chain + [self.root]:
            if id(obj) not in seen:
                seen.add(id(obj))
                fix(obj)
        starts = [it.start for it in self.items]
        i = bisect.bisect_left(starts, end)
        for obj in self.items[i:]:
            if id(obj) not in seen:
                fix(obj)
        self._node_starts = [nd.start for nd in self.node_list]
        self._caches = {}

    def undo(self) -> str | None:
        """Undo the last change. A change that kept the structure is undone in place (fast, ids
        unchanged); one that renumbered elements is undone by parsing again."""
        if not self.undo_stack:
            return None
        start, end, old, label, owner_id = self.undo_stack.pop()
        self.src = self.src[:start] + old + self.src[end:]
        self.version += 1
        owner = self.nodes.get(owner_id) or self.runs.get(owner_id) if owner_id else None
        if owner is not None and owner.start <= start and end <= owner.end:
            self._shift(end, len(old) - (end - start), owner)
        else:
            self._parse()
            self.struct_seq += 1
        return label

    def discard_all(self):
        self.src = self.original
        self.undo_stack.clear()
        self.version += 1
        self._parse()
        self.struct_seq += 1

    @property
    def dirty(self) -> bool:
        return self.src != self.original

    def _editable(self, nd: Node, what: str = "edited"):
        if nd is self.root or nd.tag in ("html", "head"):
            raise EditError(f"<{nd.tag}> can't be {what}; pick an element on the page")
        h = self.hidden_context(nd)
        if h is not None:
            raise EditError(f"{nd.id} is inside a hidden part ({HIDDEN.get(h.tag, h.tag)}); that is a Claude Code job")

    def _encode(self, text: str) -> str:
        enc = html.escape(text, quote=False)
        return re.sub(r"(?<!\r)\n", "\r\n", enc) if self.newline == "\r\n" else enc

    def set_text(self, run_id: str, new_text: str, old_text: str | None = None, *,
                 masked: bool = True, allowed_digits: str | None = None, expect: str | None = None) -> str:
        """Change one text run. masked=True (assistant / Claude Code): numbers are {#k} tokens,
        old_text replaces just that part. masked=False (the person typing): new_text is the full text."""
        r = self.run(run_id)
        self._editable(r.parent)
        raw = self.src[r.start:r.end]
        if r.parent.tag in RAWTEXT:
            raise EditError(f"{run_id} is code, not page text")
        if re.search(r"<[/!?A-Za-z]", raw):
            raise EditError(f"{run_id} has odd markup inside; use view_markup/replace_markup on {r.parent.id} instead")
        text = html.unescape(raw)
        if not masked:
            if expect is not None and _norm(expect) != _norm(text):
                raise EditError("this text changed since the page was loaded; reload and try again")
            new_full = new_text
        else:
            m, tokens = mask(text)
            if old_text is None:
                if len(m) > LONG_TEXT:
                    raise EditError(f"{run_id} is long; replace a part of it: give old_text (copied from the outline) and new_text")
                lead = text[:len(text) - len(text.lstrip())]
                trail = text[len(text.rstrip()):]
                new_full = lead + unmask(new_text.strip(), tokens, allowed_digits) + trail
            else:
                parts = old_text.split()
                if not parts:
                    raise EditError("old_text is empty")
                pat = re.compile(r"\s+".join(re.escape(p) for p in parts))
                hits = list(pat.finditer(m))
                if len(hits) != 1:
                    raise EditError(f"old_text found {len(hits)} times in {run_id}; copy a part that appears exactly once")
                h = hits[0]
                new_full = unmask(m[:h.start()] + new_text + m[h.end():], tokens, allowed_digits)
        if not new_full.strip() and masked:
            raise EditError("that would leave no text; to hide an element use set_style with display: none")
        if len(new_full) > 20000:
            raise EditError("text too long")
        enc = self._encode(new_full)
        return self._change(r.start, r.end, enc, structural=not new_full.strip(), owner=r,
                            label=f"text {run_id}")

    def _rewrite_attr(self, nd: Node, name: str, value: str | None, label: str) -> str:
        raw = self.src[nd.start:nd.tag_end]
        attrs = scan_attrs(raw, len(nd.tag))
        hit = next((a for a in attrs if a[0] == name), None)
        if value is None:
            if hit is None:
                return "No change."
            s = hit[2]
            while s > 0 and raw[s - 1] in " \t\r\n":
                s -= 1
            new_raw = raw[:s] + raw[hit[3]:]
        else:
            piece = f'{name}="{html.escape(value, quote=True)}"'
            if hit is not None:
                new_raw = raw[:hit[2]] + piece + raw[hit[3]:]
            else:
                at = attrs[-1][3] if attrs else 1 + len(nd.tag)
                new_raw = raw[:at] + " " + piece + raw[at:]
        return self._change(nd.start, nd.tag_end, new_raw, structural=False, owner=nd, label=label)

    def set_style(self, node_id: str, styles: dict) -> str:
        """Merge declarations into the element's style attribute. A value of None or "" removes one."""
        nd = self.node(node_id)
        self._editable(nd, "styled")
        if not styles:
            raise EditError("no styles given")
        decls = split_decls(self.attr(nd, "style") or "")
        for prop, val in styles.items():
            p = check_css_prop(prop)
            v = check_css_value(str(val)) if val not in (None, "") else None
            idx = next((i for i, d in enumerate(decls) if d[0] == p), None)
            if v is None:
                decls = [d for d in decls if d[0] != p]
            elif idx is None:
                decls.append([p, v])
            else:
                decls[idx][1] = v
        style = "; ".join(f"{p}: {v}" for p, v in decls)
        return self._rewrite_attr(nd, "style", style or None, f"style {node_id}")

    def set_attr(self, node_id: str, name: str, value: str | None, *, masked: bool = True,
                 allowed_digits: str | None = None) -> str:
        nd = self.node(node_id)
        self._editable(nd)
        name = name.strip().lower()
        if name == "style":
            raise EditError("use set_style for styles")
        if name not in SET_ATTRS:
            raise EditError(f"attribute {name!r} can't be set here; allowed: {', '.join(sorted(SET_ATTRS))}")
        if value is not None:
            if masked and name in MASKED_ATTRS:
                value = unmask(value, mask(self.attr(nd, name) or "")[1], allowed_digits)
            if name == "href" and re.match(r"\s*(javascript|vbscript|data):", value, re.I):
                raise EditError("links can't be javascript:, vbscript: or data: URLs")
            if len(value) > 2000:
                raise EditError("value too long")
        return self._rewrite_attr(nd, name, value, f"{name} on {node_id}")

    def set_theme_var(self, var_id: str, value: str) -> str:
        v = next((x for x in self.css_vars() if x["id"] == var_id), None)
        if v is None:
            raise EditError(f"unknown theme variable {var_id!r}")
        value = check_css_value(value)
        return self._change(v["start"], v["end"], value, structural=False, owner=v["run"],
                            label=f"theme {v['name']}")

    def set_page_rule(self, selector: str, declarations: str) -> str:
        """Add, replace or (with empty declarations) remove one CSS rule in the page-rules block,
        a <style id="she-custom"> placed last in the page so it wins over earlier rules."""
        sel = re.sub(r"\s+", " ", selector).strip()
        if not sel or len(sel) > 200 or re.search(r"[{}<>;@\\]", sel):
            raise EditError("bad selector (max 200 characters; no { } < > ; @ or backslashes)")
        decls = parse_decls(declarations)
        rules = [r for r in self.page_rules() if r[0] != sel]
        if decls:
            pos = next((i for i, r in enumerate(self.page_rules()) if r[0] == sel), len(rules))
            rules.insert(min(pos, len(rules)), (sel, "; ".join(f"{p}: {v}" for p, v in decls) + ";"))
        nl = self.newline
        body = nl + nl.join(f"{s} {{ {d} }}" for s, d in rules) + nl
        nd = self.custom_block()
        label = f"page rule {sel}"
        if nd is not None:
            if nd.close_start is None:
                raise EditError("the page-rules block has no end tag")
            run = next((c for c in nd.children if isinstance(c, Run)), None)
            if run is not None and run.start == nd.tag_end and run.end == nd.close_start:
                return self._change(run.start, run.end, body, structural=False, owner=run, label=label)
            return self._change(nd.tag_end, nd.close_start, body, structural=True, owner=nd, label=label)
        if not decls:
            return "No change."
        block = f'<style id="{CUSTOM_STYLE_ID}">{body}</style>{nl}'
        body_el = next((x for x in self.node_list if x.tag == "body"), None)
        at = body_el.close_start if body_el is not None and body_el.close_start is not None else len(self.src)
        return self._change(at, at, block, structural=True, owner=None, label=label)

    # ------------------------------------------------------------ markup of small, data-free elements
    def _markup_problem(self, nd: Node) -> str | None:
        if nd.close_start is None:
            return "it has no end tag"
        if nd.tag not in MARKUP_TAGS and nd.tag not in ("td", "th", "caption", "label", "button", "legend"):
            return f"<{nd.tag}> elements can't be rewritten; pick a text element inside it"
        if nd.close_start - nd.tag_end > MAX_MARKUP:
            return f"it is too big ({fmt_size(nd.close_start - nd.tag_end)}); pick a smaller element inside it"
        if "<!--" in self.src[nd.tag_end:nd.close_start]:
            return "it contains comments"
        for el in self.elements(nd):
            if el.tag in HIDDEN or el.tag in ("table", "form", "input", "img", "button", "link", "meta", "base"):
                return f"it contains a <{el.tag}> ({el.id})"
            for name, _, _, _ in self.attrs(el):
                if name.startswith(("data-", "on")):
                    return f"it contains data or script attributes ({el.id})"
        return None

    def _masked_markup(self, nd: Node) -> tuple[str, list[str]]:
        """Inner markup of nd with numbers as {#k} tokens (texts and title/alt/aria-label values)."""
        tokens: list[str] = []

        def tok(text):
            def sub(m):
                tokens.append(m.group(0))
                return "{#%d}" % len(tokens)
            return NUM.sub(sub, text)

        edits = []
        for r in self.runs.values():
            if nd.tag_end <= r.start and r.end <= nd.close_start:
                edits.append((r.start, r.end, html.escape(tok(self.run_text(r)), quote=False)))
        for el in self.elements(nd):
            for name, val, s, e in self.attrs(el):
                if name in MASKED_ATTRS:
                    edits.append((el.start + s, el.start + e, f'{name}="{html.escape(tok(val), quote=True)}"'))
        edits.sort()
        out, pos = [], nd.tag_end
        for s, e, text in edits:
            out.append(self.src[pos:s])
            out.append(text)
            pos = e
        out.append(self.src[pos:nd.close_start])
        return "".join(out), tokens

    def view_markup(self, node_id: str) -> str:
        nd = self.node(node_id)
        self._editable(nd)
        problem = self._markup_problem(nd)
        if problem:
            raise EditError(f"{node_id} can't be rewritten: {problem}")
        return self._masked_markup(nd)[0]

    def replace_markup(self, node_id: str, new_html: str, *, allowed_digits: str | None = None) -> str:
        nd = self.node(node_id)
        self._editable(nd)
        problem = self._markup_problem(nd)
        if problem:
            raise EditError(f"{node_id} can't be rewritten: {problem}")
        if len(new_html) > MAX_MARKUP + 2000:
            raise EditError("new markup too long")
        restored = unmask(new_html, self._masked_markup(nd)[1], allowed_digits)
        c = collect(restored)
        for (at, kind, tag), attrs in zip([e for e in c.events if e[1] in ("start", "startend")], c.attrs):
            if tag not in MARKUP_TAGS:
                raise EditError(f"<{tag}> is not allowed here; allowed: {', '.join(sorted(MARKUP_TAGS))}")
            for name, val in attrs:
                name = name.lower()
                if not (name in MARKUP_ATTRS or name.startswith("aria-")):
                    raise EditError(f"attribute {name!r} is not allowed here")
                if name == "style":
                    for p, v in split_decls(val or ""):
                        check_css_prop(p), check_css_value(v)
                if name == "href" and re.match(r"\s*(javascript|vbscript|data):", val or "", re.I):
                    raise EditError("links can't be javascript:, vbscript: or data: URLs")
        if any(e[1] == "other" for e in c.events):
            raise EditError("no comments or declarations in new markup")
        if self.newline == "\r\n":
            restored = re.sub(r"(?<!\r)\n", "\r\n", restored)
        result = self._change(nd.tag_end, nd.close_start, restored, structural=True, owner=nd, label=f"markup {node_id}")
        return result + f" Elements after {node_id} were renumbered; outline again before using their ids."

    # ------------------------------------------------------------ serving to the browser
    def served_html(self) -> str:
        """The page with data-she-id="nX" on every element (and data-she-mask on data-bearing ones),
        for the editor's frame only. The file itself never gets these."""
        cached = self._caches.get("served")
        if cached is not None:
            return cached
        src = self.src
        numeric = set()
        for r in self.runs.values():
            if r.parent.tag not in RAWTEXT and NUM.search(src, r.start, r.end):
                numeric.add(r.parent.id)
        pieces, pos = [], 0
        for nd in self.node_list[1:]:
            cut = nd.start + 1 + len(nd.tag)
            pieces.append(src[pos:cut])
            mask_it = nd.tag in ("td", "svg", "canvas", "img", "video", "picture", "iframe", "object", "embed") or (
                nd.id in numeric and nd.tag not in ("html", "head", "body") and self.descendants(nd) <= 6)
            pieces.append(f' data-she-id="{nd.id}"' + (' data-she-mask=""' if mask_it else ""))
            pos = cut
        pieces.append(src[pos:])
        out = "".join(pieces)
        self._caches["served"] = out
        return out

    def direct_runs(self, node_id: str) -> list[dict]:
        """Direct text runs of an element, for the person's own typing (real text; never sent to a model)."""
        nd = self.node(node_id)
        out = []
        for c in nd.children:
            if isinstance(c, Run):
                raw = self.src[c.start:c.end]
                editable = (nd.tag not in RAWTEXT and not self.hidden_context(nd)
                            and not re.search(r"<[/!?A-Za-z]", raw) and nd.tag not in ("html", "head"))
                out.append({"id": c.id, "text": self.run_text(c), "editable": editable})
        return out


def _count(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def _norm(s: str) -> str:
    return s.replace("\r\n", "\n")


def _scan_vars(css: str):
    """(name, value, value_start, value_end, context) for each --custom-property declaration."""
    clean = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), css, flags=re.S)
    # brace map: for each position, the stack of rule preludes
    events, stack, last = [], [], 0
    for i, ch in enumerate(clean):
        if ch == "{":
            stack.append(re.sub(r"\s+", " ", clean[last:i]).strip())
            last = i + 1
            events.append((i, tuple(stack)))
        elif ch == "}":
            if stack:
                stack.pop()
            last = i + 1
            events.append((i, tuple(stack)))
        elif ch == ";":
            last = i + 1
    starts = [e[0] for e in events]
    for m in re.finditer(r"(--[A-Za-z0-9_-]+)\s*:", clean):
        j = m.start() - 1
        while j >= 0 and clean[j].isspace():
            j -= 1
        if j < 0 or clean[j] not in "{;":
            continue
        k = bisect.bisect_right(starts, m.start()) - 1
        ctx = events[k][1] if k >= 0 else ()
        if not ctx:
            continue
        vs = m.end()
        while vs < len(clean) and clean[vs] in " \t\r\n":
            vs += 1
        depth, quote, ve = 0, None, vs
        while ve < len(clean):
            ch = clean[ve]
            if quote:
                quote = None if ch == quote else quote
            elif ch in "\"'":
                quote = ch
            elif ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch in ";}" and depth <= 0:
                break
            ve += 1
        end = ve
        while end > vs and clean[end - 1] in " \t\r\n":
            end -= 1
        if end > vs:
            yield m.group(1), css[vs:end], vs, end, " ".join(ctx)
