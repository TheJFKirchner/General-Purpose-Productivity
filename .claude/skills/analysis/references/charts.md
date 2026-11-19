# Charts beyond the shorthand, and restyling

## Pick the visual from the claim

| The claim is about | Use |
| --- | --- |
| One or two headline figures | No chart: `kpis` |
| Size across a few categories | `bar` sorted, or `hbar` when labels are long |
| Change over time | `line` (`bar` for six or fewer periods), `layout: "wide"` |
| Two sources or periods side by side | `bar` with two `y` columns, or two lines |
| Where a gap sits | A bar of the gap itself, not two near-equal bars |
| Parts of a whole across groups | `stack` |
| A relationship between two measures | `scatter` |
| The records to act on | `table` with `top`, plus `export` for the full list |

- One chart per section. The chart proves the section's claim; plot what the claim is about.
- One value axis. At most 6 series; top N beats a crowded chart.
- Plain words in captions, axis names and legends. No column names or codes.
- No colours set in charts, except `highlight` (or `"@orange"`) for the one bar the claim is about.
- A threshold the claim is judged against (target, materiality): draw it with `ref`, not in words only.

## A chart function

When the shorthand cannot draw it, `chart` takes a function of the analytic's tables that returns an ECharts option:

```python
def _waterfall(t):
    d = t["bridge"]
    return {
        "format": "$short",                         # value format, as in the shorthand
        "caption": "From April to May",             # optional caption; "height": 360 optional
        "xAxis": {"type": "category", "data": list(d["step"])},
        "yAxis": {"type": "value", "name": "Paid amount"},
        "series": [{"type": "bar", "stack": "w", "data": list(d["base"]),
                    "itemStyle": {"color": "transparent"}},
                   {"type": "bar", "stack": "w", "data": list(d["change"]),
                    "label": {"show": True, "position": "top"}}],
    }

SECTIONS = [{"analytic": "bridge", "title": "...", "chart": _waterfall}]
```

- DataFrame columns can be passed as data; `run.py` converts them.
- `"@blue"`, `"@orange"` ... anywhere in the option become the page's colours.
- Already applied by `page.html`: palette, font, axis styling, tooltip, legend for several series, margins, no animation, no hover state.

## Restyling

Only when asked. Edit that report's `page.html`, then `python run.py report`.

| To change | Edit |
| --- | --- |
| Colours, font | The `:root` block at the top (about 10 lines). Charts follow |
| Series order | `PALETTE` in the script near the end |
| Layout | The CSS below `:root` |

- Keep every `__TOKEN__`; the build stops if one is missing.
- No logo or company name. Same look for every new report: change the skill's `template/page.html`.
- No internet where the report is read: put `echarts.min.js` beside `run.py` and rebuild; it is embedded.
