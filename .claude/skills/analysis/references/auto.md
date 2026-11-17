# Auto mode

Same steps, files and report. You answer the gate questions yourself, record each answer as an assumption, and ask the user once, at the end.

## What changes

| Step | Guided | Auto |
| --- | --- | --- |
| Gate 1, the brief | One round of questions; user approves | Ask nothing. Fill every line from the request and the data. Each line the user did not state is an assumption. Gate passes when you can fill the brief: create the folder, then write it in the README |
| Things to test | User approves the list | Write it yourself, likeliest first. Off-list finding: add at most two rows, marked "added" |
| Gate 2, the answer | User agrees it is the answer | Check it against the brief's Success line yourself. Not met after the list is finished: stop and report, do not build |
| Report, commentary, cold read | As written | As written. Gate 3 is never skipped |
| Hand-over | Report path, answer, what is unverified | The note below |

## Assumptions

- Log each in the README, "Assumptions", when made: what you assumed, what you would have asked.
- An assumption: a choice the user could reasonably have made differently (the period, the measure, what counts as a match, which source is correct, who reads it, what is in scope).
- Brief lines with no basis in the request (Background, How it will be used, Where it fits): write "not stated". Do not invent them; do not list them as assumptions.
- Pick the most ordinary reading. Two readings give different answers: say in one line what the other would have shown.
- README "Approved" lines: "auto mode, not yet confirmed".

## The note

An email to a manager. Plain sentences, only the headings shown, about 300 words at most. Put it in the README, "Hand-over notes", and show it in the conversation.

```
Subject: <the question>: answer and assumptions to confirm

<Name or "Hi">,

You asked: <the request, in their words>.

Answer: <two sentences, with the key figure>.

What I did:
- <three to five lines: the sources used, what was tested, what was ruled out>

Assumptions I made. Do these sound right?
1. <assumption>. If not: <what would change>.
2. ...

Not checked: <anything unverified, or "nothing">.

Report: <full path to the HTML>

If any assumption is wrong, tell me which number and I will rerun it.
```

- Order assumptions by how much the answer depends on them. Ten at most.
- None that cannot change the answer or the report. The README may hold more than the note.

## After the user replies

| Reply | Do |
| --- | --- |
| All fine | "Approved" lines: who and the date |
| An assumption is wrong | Fix the brief; rerun from the first step it affects (`rerun.md`); send a short updated note |
| The question was different | New analysis folder, guided mode |
