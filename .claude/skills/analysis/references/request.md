# Step 1: define the request (gate 1)

Nothing is created or analysed until the brief is complete and the user has said yes to it.

## How

1. **Look before asking.** Read the files or tables named. Note: columns, what one row is, date range, likely matching key. Quick counts and totals only; save nothing.
2. **Identify the request type** (below). It decides what must be settled.
3. **Ask once.** One round, at most five questions, specific not generic. Only what the data and request did not answer. Always cover any brief line you cannot fill.
4. **Open question:** draft the things to test (below). Pointed question: skip.
5. **Write the brief, show it.** Proceed only on a yes to the brief. Answers to your questions are not a yes.

- Auto: skip step 3 and the approval. Fill open lines yourself; list each under Assumptions (`auto.md`).
- Guided and the user is unavailable: stop.

## The brief

The analysis may be strict ("compare these two fields") or open ("why is this happening"). Success is never open: it is written down.

| Line | Must say |
| --- | --- |
| **Question** | One answerable sentence |
| **For whom** | Who reads it; what they already know about this data |
| **Background** | Why now; what prompted it |
| **How it will be used** | The decision or action that follows |
| **Where it fits** | The larger piece of work this feeds. In a project: the plan goal ids it serves (G1, G2), and what `findings.md` already says about them |
| **Success** | What the reader must be able to say or do after reading. One or two sentences |
| **Scope** | Strict or open-ended. What is out of scope |
| **Sources** | Each source: what one row is, the key, the period |
| **Definitions** | What counts as a match, a difference, material, unusual. One plain name per source |
| **Things to test** | Open: the agreed list (below). Pointed: "None; the request names what to compute" |
| **Assumptions** | Anything the user did not confirm |

## Things to test

| Request | Example | List |
| --- | --- | --- |
| Pointed: names the fields and the calculation | "How correlated are these two fields by month?" | None. Compute what was asked |
| Open: asks why, what or which, without naming where to look | "Why are claims high this month?" | Required. Nothing is tested until the user approves it |

Building the list:

1. In the one round of questions, ask what the user suspects and what is already ruled out. Suspicions go first; ruled-out items stay off.
2. Add candidates from the request type and the columns seen. Only ones that could plausibly explain the question.
3. Likeliest first. At most eight; more means the question is too wide.
4. One row each:

```markdown
| # | Test | Fields | Result |
| --- | --- | --- | --- |
| 1 | Is the increase in a few providers or spread across all? | provider, paid amount | |
| 2 | More claims, or a higher cost per claim? | claim count, paid amount | |
| 3 | Is it one line of business? | line of business, paid amount | |
```

- Result: filled in while exploring (`storyline.md`).
- The list is the limit on exploring. A field not on it is not checked.

## Request types

| Type | Example | Must be settled |
| --- | --- | --- |
| Compare two sources | "Where do these two files differ?" | Matching key; which fields count; tolerance; which source is treated as correct; period |
| Relationship | "Is X related to Y?" | Level (claim, member, month); how the two are joined; what size of relationship matters |
| Change and drivers | "Why did cost go up?" | The measure; the two periods; which breakdowns are allowed |
| Outliers | "Which providers look unusual?" | Unusual against what; minimum volume to count |
| Open question | "What is going on with denials?" | What prompted it; what answer would change a decision |

## Where it goes

- Brief: `README.md`, "Request".
- `config.py`: `QUESTION` is filled when the folder is created. Set `AUDIENCE` from "For whom", one line.

## Checklist

- [ ] Every brief line filled, or listed under Assumptions
- [ ] Success names something the reader can say or do, not "understand the data"
- [ ] Open question: things to test are in the brief, likeliest first
- [ ] User approved. README "Approved" line: who and the date. Auto: "auto mode, not yet confirmed"
