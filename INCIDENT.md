# Incident runbook: a secret was committed

Drill on 2026-11-23: a fake `FRAUD_REGISTRY_TOKEN` was committed to `configs/dev.env`,
then deleted in the next commit. `git log -p -S` still showed it in history.
Deleting a line does not remove a secret: git keeps every version of every file.

## Response, in this order

1. **Rotate the secret now.** Revoke the leaked token at the provider and issue a new one.
   Assume it is already compromised: automated scanners find pushed tokens within minutes.
   Put the new value only in the platform's secret store, never in a file in the repo.
2. **Clean the history.** If the commit was never pushed, drop it (`git reset`).
   If it was pushed, rewriting history needs a force push and coordination with the team,
   which is why rotation comes first: cleaning alone does not make the old token safe.
3. **Prevent a repeat.** Add a secret scanner (e.g. gitleaks) as a pre-commit hook and a CI job,
   and keep real values only in `.env` (git-ignored) or the secret store.

## Why this order
Rotation is the only step that makes the leaked value useless. History cleanup reduces
exposure but cannot recall copies that were already taken.
