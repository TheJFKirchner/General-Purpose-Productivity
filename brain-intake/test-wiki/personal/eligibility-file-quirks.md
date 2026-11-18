---
description: Quirks I have found in client eligibility files and how I handle them.
---

# eligibility-file-quirks

## Overview

- Client eligibility files arrive in several layouts; these are the quirks that changed my numbers.
- Team-level eligibility facts are on [[member-months]].

## Traps

- One client sends full-file replacements but names them like change files. #trap #verify
- Some files put the subscriber's id in the dependent id column for children. #trap
- Termination dates of the last day of the month are sometimes sent as the first day of the next month. #trap
- Weekend files can be partial; do not treat a smaller file as terminations without checking. #trap
- Retro adds can backdate coverage by three months; past member months then change. #trap

## Reference

- Standard layout: one row per member per coverage span, with effective and termination dates.
- Change-file layout: adds, changes and terms since the last file, with an action code.
- Full-file layout: every active member as of the file date.
- Action codes in change files: A add, C change, T term.

## Notes

- Keep a note of the file layout per client in the client folder.
- When counts move more than 2% month to month, compare the raw file counts first. #todo
- The enrollment platform team can resend a file if one was partial.
- Ask whether a client plans a layout change before each renewal. #question
- Most quirks show up in the first file after a plan year starts.
- Record each new quirk here the same day it is found.
- Promote a quirk to the team pages once it is seen for a second client.
- Older quirks from 2024 files are in my archive notes, not here.
- Duplicate spans for one member usually come from a layout change mid-year.
- Merged groups can send two files for one month during the transition.
