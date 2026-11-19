# Cold read (optional, only when accepted)

A fresh reader sees only the report and says what it concludes.

1. `python run.py text` prints the report as a reader meets it.
2. Give that text, and nothing else, to a fresh subagent with this prompt:

```
You are a busy reader who has never seen this data. Read the report below once. Answer briefly:
1. What question is it answering, and what is the answer?
2. What three things should you take away?
3. What would you do next because of it?
4. Any word, label or figure you could not work out? Say "none" if not.
5. Which section would you not miss?
```

3. Compare with the brief in `report.py`. Fix at the source: wrong conclusion, the headline or section order; unclear term, rename it in the analytic or the label; a section not missed, drop it unless it holds the only proof of something the answer states.
4. One read. Say what changed at hand-over.
