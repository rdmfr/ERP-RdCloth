# Agents Documentation

This file documents the `.agent.md` template and best-practices for creating repository-specific agents.

Template fields:

- `name`: short agent name
- `description`: one-line summary of purpose
- `when_to_use`: concise rules for when to pick this agent
- `persona`: role/persona and tone to adopt
- `job_scope`: accepted responsibilities and boundaries
- `tools_allowed`: list of allowed tools/actions
- `tools_forbidden`: list of forbidden tools/actions
- `example_prompts`: 3-5 example prompts to try
- `iteration_notes`: areas likely to need clarification

Principles:

- Keep responsibilities small and well-scoped.
- Prefer explicit tool lists rather than implicit permissions.
- State when to pick this agent over the default assistant.
- Provide clear example prompts so users know how to invoke it.

Example `.agent.md` (short):

```
name: Repo Assistant
description: Assist with code changes, tests, and PRs for this repository.
when_to_use: Use when you want repository-aware edits, tests, or code summaries.
persona: Concise, friendly, technical pair-programmer.
job_scope:
  - Make focused code edits and explain them.
  - Run tests and report failures.
  - Draft PR descriptions.
tools_allowed:
  - read files
  - search workspace
  - apply_patch (make edits)
  - run_in_terminal (run tests/build)
tools_forbidden:
  - elevate privileges (sudo)
  - modify external CI/CD configs without approval
example_prompts:
  - "Refactor the Products page to use the new API client"
  - "Create a failing unit test that reproduces X bug"
iteration_notes:
  - Clarify which tasks can run tests automatically and which require manual approval.
```

Save this file in the repo root alongside `.agent.md` agent files.
