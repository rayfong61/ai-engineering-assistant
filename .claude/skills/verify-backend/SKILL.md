---
name: verify-backend
description: Use after making or reviewing changes to backend/app/**. Runs the real pytest suite inside the backend container and checks whether the change also needs manual browser verification, before reporting the change as done.
---

# Verify backend changes

This project's own history (see `docs/CHANGELOG.md`) has at least two real bugs that
shipped with a fully green `pytest` suite:

- Day 4: `EmailPreviewCard.jsx` showed "已寄出" for a send that had actually failed,
  because no backend test exercises how the frontend interprets a 200 response.
- Day 5: the Agent could claim it revised an email draft without ever calling the
  `draft_email` tool — a pure text hallucination with no failing test to catch it.

`pytest` passing means the backend logic it covers is correct. It does **not** mean
the feature works end-to-end. Treat these as two separate questions.

## Procedure

1. Run the real test suite, not a subset, so a regression elsewhere isn't missed:

   ```bash
   docker compose exec backend python -m pytest -v
   ```

   If the `backend` container isn't running, say so and stop — don't report "tests
   pass" without actually having run them. Don't run this while
   `scripts/eval_rag.py` might be executing inside the same container (Day 5 note 2,
   `docs/CHANGELOG.md`) — restarting/interrupting it loses that run's progress.

2. Report the real pass/fail count. If anything fails, that's the answer — stop
   here, don't move to step 3.

3. If all tests pass, decide whether this change also needs a manual check that
   `pytest` structurally cannot cover:

   - **Frontend interpretation of a backend response** (status fields, error
     shapes, anything a component branches on) — `pytest` never renders a
     component, so this needs an actual browser session.
   - **Agent tool-selection behavior** (does Claude actually call the tool it
     claims to, especially on a follow-up/revision turn) — a plausible-sounding
     assistant reply is not proof a tool was invoked; check the real
     `tool_calls`/`messages` for the turn.
   If the change falls into one of these categories, say so explicitly and either
   perform the manual check (use the `run` skill to drive the app in a browser) or
   tell the user it still needs manual verification — don't let a green `pytest`
   run stand in for it.

4. Only report the change as verified once both the applicable automated and
   manual checks have actually been done, not merely planned.
