---
name: brain-promote
description: Move chosen lines from a personal wiki page to the team page of the same name, creating the team page from a team template when it does not exist yet. The only brain skill that changes team pages. Run only when the user asks.
---

# brain-promote

Moves the lines the user picks from a personal page to the team page of the same name.

1. **Get the page.** The personal page the user named. None named: ask which.
2. **Show its content.** Read the personal page and show every line of content, numbered, under its heading. Point out any line written in the first person, any line the wiki's tags mark as a guess or unchecked, and any line with no source when the wiki's rules ask for one.
3. **The user picks.** Ask:
   - "Which lines move to the team page? They leave your page, so each must make sense to the team on its own. Reword any that need it."
   - No team page of that name yet: also list the files in `team/templates/` and ask which template to start it from.
   - Wait for the answer. Nothing picked: stop.
4. **Hand it to one `brain-promoter` sub-agent.** Give it the wiki root, the personal page path, the picked lines word for word (with any rewording), and the template name if a team page must be created. It adds the lines to the team page and removes them from the personal page.
5. **Tell the user** what moved: the promoter's lines as they are, `not moved` lines first.

Do not change either page yourself.
