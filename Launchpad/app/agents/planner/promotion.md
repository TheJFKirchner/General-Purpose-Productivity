# When the planner moves up to the stronger model

The planner starts on the cheaper model. In its first turns it calls `promote_planner` once, with a one-line reason, if any of these is true:

- New project, or multi-part work: several deliverables, or more than about three dependent steps
- The goal is unclear, open-ended, or the user's goals conflict
- Methodology, architecture, data-model or tooling trade-offs need weighing
- Many steps depend on each other or on outside systems and data
- The user pushes back on a recommendation or corrects an assumption
- High stakes: production systems, money, compliance, or many users

Stay on the cheaper model when:

- It is a small, clear, single-piece change (one file or one feature, obvious approach)
- The user only wants a quick plan, or a tweak to an existing plan
