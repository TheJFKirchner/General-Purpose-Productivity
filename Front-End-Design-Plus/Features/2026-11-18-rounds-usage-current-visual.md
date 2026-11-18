# Rounds, usage bar and current visual

Status: built
Date: 2026-11-18

Three additions to the whiteboard, asked for after the first live session. Earlier rounds of cards are hidden by default so the board does not fill up. A bar shows the model, tokens used and an estimated cost. When the visual already exists in the deliverable, the whiteboard always starts from it and shows it as it looks today.

## Decisions

- **A round is one user message and the cards it produced.** Only the latest round shows by default. A "Show earlier cards (N)" control expands the rest, grouped by round, and the choice is remembered. Hidden cards have no frame running.
- **Saved cards and the current visual stay visible** whatever their round, so favourites and the reference are never hidden.
- **Usage covers the whole session**, including automatic fix turns, and survives a resume. The figures come from `agentlib` after every turn (tokens, cost, model); nothing is priced by hand. With the fake engine the numbers are estimates from text length and marked as no cost.
- **The existing visual is always passed in.** The skill rewrites it faithfully as a recipe body (same type, series, colours, labels), not an improved version, and tells the user before launching if it cannot. The agent treats it as the default starting point when a request names no ID, and never changes it; variants are new cards with it as parent.

## Interface changes

- Each card has `round` in `board.json`, `/api/session` and the `card` event. Round 0 is the card from `--existing`; each user message starts the next round. Saved recipe files are unchanged.
- `/api/session`, the `done` event and the `/api/card-error` reply also return `round`, `model` and `usage: {input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, total_tokens, cost_usd, turns}`.
- A board saved before rounds existed loads its cards as round 1.

## Known limits

- After a turn that fails partway, the tokens are counted but its cost is not, so the total cost reads slightly low.
- The cost wording for the real engine was not seen in a browser test; only the fake-engine wording was.
