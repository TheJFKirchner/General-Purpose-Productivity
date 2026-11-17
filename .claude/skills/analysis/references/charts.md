# Visuals

`charts(data)` returns a list. Each item is one card in the section.

| Field | Required | What |
| --- | --- | --- |
| `title` | yes | What the reader should see in it, plain words |
| `option` | one of | An ECharts option (dict). DataFrame columns can be passed directly as data |
| `table` | one of | A DataFrame, shown as a sortable table. At most 500 rows |
| `note` | no | One line under the visual: a definition or caveat the reader needs |
| `width` | no | `"half"`: two cards side by side. Default full width |
| `height` | no | Chart height, pixels. Default 360 |
| `format` | no | Tables only: `{"column": ",.0f"}` (Python number formats; `".1%"` for percents) |

## Pick the visual from the claim

| The claim is about | Use |
| --- | --- |
| One or two headline figures | No chart: `[]`, or one small table. The commentary states them |
| Size across a few categories | Bar, sorted largest first. Horizontal when labels are long |
| Change over time | Line (bar for a handful of periods) |
| Two sources or periods side by side | Grouped bar, or two lines |
| Where a gap sits | Bar of the gap itself, not two near-equal bars |
| A relationship between two measures | Scatter |
| A spread, and who is outside it | Histogram (bar of counts per range) or scatter |
| The specific records to act on | Table of the top rows, plus `EXPORT` for the full list |

## Rules

- The visual proves the section's claim. Shows something else: change it or cut it.
- Plot what the claim is about. Claim is a difference: plot the difference.
- At most 3 visuals per section. Usually 1 or 2.
- One y-axis. Never two scales on one chart.
- At most 6 series. Fewer categories beat more: top N plus "All other".
- Sort bars by value, unless the order means something (months, age bands).
- Axis names: about 25 characters at most, with the unit ("Paid amount, $"). Name every axis that is not obvious. Longer explanations: `title` or `note`.
- Plain words in titles, axis names, legend entries and table headings. Rename columns before charting (`df.rename(columns=...)`); never show `clm_amt_pd`.
- Codes and abbreviations: spell out, or explain in `note`.
- Tables: at most 6 columns (no sideways scroll). Only rows the reader will read: top 10 to 25; the rest in `EXPORT`.
- Colours come from `page.html` (blue first). Set none in a chart, except one highlight colour for the single bar or line the claim is about.

## Patterns

```python
# bar, largest first
d = data["by_reason"].sort_values("claims", ascending=False)
{"title": "Three reasons account for most differences",
 "option": {"xAxis": {"type": "category", "data": d["reason"]},
            "yAxis": {"type": "value", "name": "Claims"},
            "series": [{"type": "bar", "data": d["claims"]}]}}

# horizontal bar (long labels): swap the axes; reverse so the largest is on top
d = d.sort_values("claims")
"option": {"yAxis": {"type": "category", "data": d["reason"]},
           "xAxis": {"type": "value", "name": "Claims"},
           "series": [{"type": "bar", "data": d["claims"]}]}

# two lines over time
"option": {"xAxis": {"type": "category", "data": d["month"]},
           "yAxis": {"type": "value", "name": "Paid amount, $"},
           "series": [{"type": "line", "name": "Source A", "data": d["paid_a"]},
                      {"type": "line", "name": "Source B", "data": d["paid_b"]}]}

# scatter
"option": {"xAxis": {"type": "value", "name": "Billed, $"},
           "yAxis": {"type": "value", "name": "Paid, $"},
           "series": [{"type": "scatter", "symbolSize": 6, "data": d[["billed", "paid"]]}]}

# highlight one bar
"series": [{"type": "bar", "data": [
    {"value": v, "itemStyle": {"color": "#eb6834"}} if name == "March" else v
    for name, v in zip(d["month"], d["gap"])]}]

# table of the rows to act on
{"title": "Largest paid-amount differences",
 "table": data["differences"].head(20).rename(columns={"claim_id": "Claim", "gap": "Difference, $"}),
 "format": {"Difference, $": ",.2f"}}
```

- Already applied by `page.html`: colours, fonts, tooltips, legend (more than one series), margins, axis styling.
- Zoom on long time series: `"dataZoom": [{"type": "inside"}, {"type": "slider"}]`.
- Number formats on axes or tooltips: a string starting `js:` becomes a JavaScript function, e.g. `"axisLabel": {"formatter": "js:function (v) { return '$' + v.toLocaleString(); }"}`.

## Restyling

Only when the user asks. Edit `page.html` in the analysis folder, then `python run.py build`.

| To change | Edit in `page.html` |
| --- | --- |
| Font | `--font` in the `:root` block (page and charts) |
| Page colours | The other `:root` variables (`--navy` headings, `--accent` links, `--page` background ...) |
| Chart series colours | `--s1` to `--s6`, in the order used |
| Logo, header, footer, layout | The HTML and CSS below `:root` |

- Fonts and colours: read only the `:root` block (about the first 20 lines).
- Keep every `__TOKEN__`; the build stops if one is missing.
- Applies to this analysis only. Same look for every new analysis: the user changes the skill's `template/page.html`.
