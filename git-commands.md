# Manual git push fallback

Track B backend work is happening on a local branch and is **not pushed yet**.
If the assistant session drops before pushing, run this yourself.

- Remote: `origin` -> `https://github.com/vinayBhoure/Ignite-Hackathon.git`
- Working branch: `feature/api/track-b-backend` (created off `main`)
- `gh` CLI is not installed on this machine, so PR creation below uses the web UI link.

## 1. Check what you have locally

```bash
git status
git branch --show-current
git log --oneline main..feature/api/track-b-backend
```

The last command should list one commit per logical change (schemas, API shell,
mocks, endpoints, etc.) - if it's empty, nothing has been committed yet and
there's nothing to push.

## 2. Push the branch

```bash
git push -u origin feature/api/track-b-backend
```

If the branch was already pushed before and you have new local commits:

```bash
git push
```

## 3. Open the PR

No `gh` CLI here, so use the web UI - after the push, GitHub prints a direct
"Compare & pull request" URL in the terminal output. If you miss it, go to:

```
https://github.com/vinayBhoure/Ignite-Hackathon/compare/main...feature/api/track-b-backend
```

Title suggestion: `feat(api): Track B backend - schemas, FastAPI shell, mocked endpoints`

## 4. If something looks wrong before pushing

- `git diff main..feature/api/track-b-backend` - see the full diff that would be pushed.
- `git status` - confirm nothing unintended is staged (never commit `.env`; it's gitignored).
- Do **not** run `git push --force` on this branch unless you specifically mean to overwrite
  a remote copy - ask first if unsure.

## 5. Later phases (for reference, not needed for the current push)

Once Phase 1 (backend) is merged, Phase 2 branches off it:

```bash
git checkout main
git pull
git checkout -b feature/ui/track-b-console
```
