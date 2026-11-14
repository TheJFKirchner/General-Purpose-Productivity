"""Visual libraries for the Visualizer: which chart library a visual set is drawn with, and where its file is.

- Bundled (app/vendor): ECharts (default), Chart.js, D3. Installed: Plotly, Bokeh, found as their JavaScript file
  inside the installed Python package (the connected folder's .venv first, then Launchpad's own environment);
  never imported or run as Python
- choose_library: a name as the planner wrote it -> the library actually used (+ a "drawn in ECharts, styled like
  <library>" note when it falls back); libraries_note: the planner's one line about what is available here
- Served to the page by app/server.py (GET /vendor/lib/<key>.js)
"""
from __future__ import annotations

import re
import site
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path

from ...sessionfiles import inside, one_line

MAX_LIBRARY_NAME = 40
VENDOR = Path(__file__).resolve().parents[2] / "vendor"     # app/vendor
DEFAULT_LIBRARY = "echarts"
MAX_LIB_BYTES = 20_000_000             # an installed library file larger than this is not served
MIN_LIB_BYTES = 1_000
LIB_PART_SEPARATOR = "\n/*lp:next-script*/\n"   # between files of one library (the page makes one script tag each)


@dataclass(frozen=True)
class Library:
    key: str
    name: str                          # display name
    glob: str                          # the global the fragment uses
    files: tuple[str, ...]             # bundled: file names in app/vendor; installed: paths inside the package
    package: str | None = None         # installed: the Python package that carries the files (never imported)
    marker: str = ""                   # installed: text that must appear near the top of the first file

    @property
    def bundled(self) -> bool:
        return self.package is None


LIBRARIES: dict[str, Library] = {
    "echarts": Library("echarts", "ECharts", "echarts", ("echarts.min.js",)),
    "chartjs": Library("chartjs", "Chart.js", "Chart", ("chart.umd.min.js",)),
    "d3": Library("d3", "D3", "d3", ("d3.min.js",)),
    "plotly": Library("plotly", "Plotly", "Plotly", ("package_data/plotly.min.js",), package="plotly",
                      marker="plotly"),
    "bokeh": Library("bokeh", "Bokeh", "Bokeh", ("server/static/js/bokeh.min.js",
                                                 "server/static/js/bokeh-api.min.js"), package="bokeh",
                     marker="bokeh"),
}
_ALIASES = {"apacheecharts": "echarts", "echart": "echarts", "chartjs": "chartjs", "d3js": "d3",
            "plotlyjs": "plotly", "plotlyexpress": "plotly", "bokehjs": "bokeh"}
# how the agent's fragment calls each library (a fragment that calls another library than its set's is rejected)
LIB_USE = {
    "echarts": re.compile(r"\becharts\s*\.\s*init\s*\("),
    "chartjs": re.compile(r"\bnew\s+Chart\s*\("),
    "d3": re.compile(r"\bd3\s*\.\s*(?:select|selectAll|create)\s*\("),
    "plotly": re.compile(r"\bPlotly\s*\.\s*(?:newPlot|react|plot)\s*\("),
    "bokeh": re.compile(r"\bBokeh\s*\.\s*(?:Plotting|embed|Charts)\b"),
}


def library_key(name: str | None) -> str | None:
    """A library name as the planner wrote it ("Chart.js", "d3.js", "Apache ECharts") -> key, or None if unknown."""
    k = re.sub(r"[^a-z0-9]", "", str(name or "").lower())
    k = _ALIASES.get(k, k)
    return k if k in LIBRARIES else None


def _launchpad_site_dirs() -> list[Path]:
    """Launchpad's own environment: its site-packages folders (no import of anything)."""
    raw: list[str] = []
    paths = sysconfig.get_paths()
    raw += [paths.get("purelib") or "", paths.get("platlib") or ""]
    try:
        raw += list(site.getsitepackages())
    except AttributeError:                                   # some embedded / virtualenv builds
        pass
    try:
        raw.append(site.getusersitepackages())
    except AttributeError:
        pass
    raw += [p for p in sys.path if p and Path(p).name.lower() in ("site-packages", "dist-packages")]
    out: list[Path] = []
    for p in raw:
        if p and Path(p).is_dir() and Path(p) not in out:
            out.append(Path(p))
    return out


def _venv_site_dirs(project: Path) -> list[Path]:
    """The connected folder's .venv site-packages (Windows and POSIX layouts), kept inside the folder."""
    venv = Path(project) / ".venv"
    if not venv.is_dir():
        return []
    cands = [venv / "Lib" / "site-packages"] + sorted(venv.glob("lib/python3*/site-packages"))
    return [c for c in cands if c.is_dir() and inside(c, project)]


def _checked_file(pkg: Path, rel: str, limit: Path | None, marker: str) -> Path | None:
    """One library file inside an installed package, with the care app/files.py takes: resolved (symlinks, "..")
    and still inside the package folder (and inside the connected folder for a .venv), a plain file of a sane
    size, and JavaScript (not HTML) that names its library near the top. None when any check fails."""
    try:
        target = (pkg / rel).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not inside(target, pkg) or (limit is not None and not inside(target, limit)):
        return None
    if target.suffix.lower() != ".js" or not target.is_file():
        return None
    try:
        size = target.stat().st_size
        if not MIN_LIB_BYTES <= size <= MAX_LIB_BYTES:
            return None
        if marker:
            with target.open("rb") as f:
                head = f.read(4096)
            if head.lstrip().startswith(b"<") or marker.encode() not in head.lower():
                return None
    except OSError:
        return None
    return target


def library_files(key: str, project: Path | None = None) -> list[Path] | None:
    """The JavaScript file(s) to inline for a library, or None if it is not available for this folder.
    Bundled: app/vendor. Installed: the folder's .venv first, then Launchpad's own environment."""
    lib = LIBRARIES.get(key)
    if lib is None:
        return None
    if lib.bundled:
        files = [VENDOR / f for f in lib.files]
        return files if all(f.is_file() for f in files) else None
    try:
        roots: list[tuple[Path, Path | None]] = []
        if project is not None:
            proj = Path(project).resolve()
            roots += [(sp, proj) for sp in _venv_site_dirs(proj)]
        roots += [(sp, None) for sp in _launchpad_site_dirs()]
        for sp, limit in roots:
            pkg = sp / lib.package
            if not pkg.is_dir():
                continue
            files = [_checked_file(pkg, rel, limit, lib.marker if i == 0 else "") for i, rel in enumerate(lib.files)]
            if all(files):
                return files                                 # type: ignore[return-value]
    except OSError:                                          # unreadable folders: treat as not installed
        return None
    return None


def available_libraries(project: Path | None = None) -> list[str]:
    """Library keys available for a folder, in display order (bundled first)."""
    return [k for k in LIBRARIES if library_files(k, project)]


def libraries_note(project: Path | None = None) -> str:
    """One line for the planner's first message: what show_visuals can draw with here."""
    names = [LIBRARIES[k].name + (" (default)" if k == DEFAULT_LIBRARY else "") for k in available_libraries(project)]
    return "Visual libraries for this folder (show_visuals library): " + ", ".join(names) + "."


@dataclass(frozen=True)
class LibraryChoice:
    asked: str | None                  # as asked for: a key when known, else the name given; None = not asked
    drawn_with: str                    # the key actually used
    available: tuple[str, ...]         # keys available for the folder
    note: str | None                   # "drawn in ECharts, styled like <library>" when it fell back

    @property
    def styled_like(self) -> str | None:
        if self.note is None or self.asked is None:
            return None
        return LIBRARIES[self.asked].name if self.asked in LIBRARIES else self.asked


def choose_library(asked: str | None, project: Path | None = None) -> LibraryChoice:
    available = tuple(available_libraries(project))
    raw = one_line(re.sub(r"[<>\"'`]", "", str(asked or "")), MAX_LIBRARY_NAME)
    if not raw:
        return LibraryChoice(None, DEFAULT_LIBRARY, available, None)
    key = library_key(raw)
    if key and key in available:
        return LibraryChoice(key, key, available, None)
    shown = LIBRARIES[key].name if key else raw
    return LibraryChoice(key or raw, DEFAULT_LIBRARY, available,
                         f"drawn in {LIBRARIES[DEFAULT_LIBRARY].name}, styled like {shown}")
