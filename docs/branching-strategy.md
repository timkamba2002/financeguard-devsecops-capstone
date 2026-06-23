# Branching Strategy — Trunk-Based Development (Model B)

FinanceGuard uses **Trunk-Based Development** with a single long-lived branch (`main`) and
short-lived feature branches. Environment promotion is controlled by **GitHub Environment
approval gates**, not by merging between branches.

---

## The model at a glance

```
           feature/add-auth    fix/db-timeout
                  │                  │
                  └────── PR ────────┘
                           │
                         main  ◄── single source of truth
                           │
                    (push triggers CI/CD)
                           │
               ┌───────────┼────────────┐
               ▼           ▼            ▼
             dev        staging        prod
          (auto)      (✋ approve)   (✋ approve)
        Kubernetes   Kubernetes    Kubernetes
        namespace    namespace     namespace
```

**Key principle:** the same Docker image (tagged with the commit SHA) flows unchanged from
dev → staging → prod. Nothing is rebuilt between environments. Only the Helm values overlay
changes per environment.

---

## Long-lived branches

| Branch | Purpose |
|---|---|
| `main` | **Only** long-lived branch. Always deployable. Protected. |

All other branches are deleted after their PR is merged.

---

## Short-lived branch naming

| Prefix | Use | Example |
|---|---|---|
| `feature/` | New functionality | `feature/add-transaction-export` |
| `fix/` | Bug fixes | `fix/db-connection-timeout` |
| `chore/` | Dependency bumps, tooling, config | `chore/bump-fastapi-0.111` |
| `security/` | Security patches | `security/patch-cve-2024-1234` |

Rules:
- Branch from `main`
- Keep branches short-lived (hours to a few days — never weeks)
- One concern per branch; keep the diff small and reviewable
- Delete the branch after the PR is merged

---

## Day-to-day workflow

### 1. Create a branch from main

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

### 2. Make changes and push

```bash
# ... make changes ...
git add <files>
git commit -m "feat: describe what and why"
git push origin feature/your-feature-name
```

### 3. Open a Pull Request → main

```bash
gh pr create --base main --title "feat: your feature" --body "..."
```

The **PR Validation** pipeline runs automatically on the PR:

| Check | Tool | Gate |
|---|---|---|
| Secret scan | Gitleaks | ⚠️ demo: warn / prod: block |
| SAST | Semgrep (OWASP Top-10) | ⚠️ demo: warn / prod: block |
| IaC scan | Checkov + TFLint | ⚠️ demo: warn / prod: block |
| Unit tests | pytest + Black | ✅ always hard fail |
| Quality gate | SonarCloud | ⚠️ demo: warn / prod: block |

All checks must be green (or continue-on-error in demo mode) before a reviewer can approve.

### 4. Get a review and merge

- At least **1 approving review** is required (branch protection rule on `main`)
- Reviewer approves → merge → **branch is deleted automatically** (or run `git push origin --delete feature/your-feature-name`)
- The merge commit to `main` triggers the full CI/CD pipeline

### 5. The pipeline takes over

After merge to `main`:

```
Stage 0  PR Validation       ← skipped (only runs on PRs)
Stage 1  Build, Scan, Sign   ← auto
Stage 2  Deploy → dev        ← auto (no approval)
         Integration tests   ← auto (parallel with ZAP)
         ZAP baseline        ← auto (parallel with tests)
Stage 3  Deploy → staging    ← ✋ PAUSES for approval
         Integration tests   ← auto (parallel with ZAP)
         ZAP full scan       ← auto (parallel with tests)
Stage 4  Deploy → prod       ← ✋ PAUSES for approval
Stage 5  Evidence bundle     ← auto
```

To approve staging or production: go to the GitHub Actions run → click
**"Review deployments"** → select the environment → **Approve**.

GitHub records the approver's identity, timestamp, and commit SHA — this is your audit trail.

---

## What we removed and why

| Old branch | Was used for | Why removed |
|---|---|---|
| `development` | Deploying to dev environment | Dev deploys now trigger automatically on every push to `main` |
| `staging` | Deploying to staging environment | Staging promotion is now a GitHub Environment approval gate, not a branch merge |
| `production` | Deploying to production environment | Production promotion is the same — approval gate, not a branch |

**Before (GitFlow / Model A):**
- 3 long-lived branches + `main`
- Deploy by merging `development` → `staging` → `production`
- Branch merges were the promotion mechanism
- Each environment had its own branch to protect

**After (Trunk-Based / Model B):**
- 1 long-lived branch (`main`) + short-lived feature branches
- Deploy by approving in GitHub Environments UI
- Approval gates are the promotion mechanism
- `main` is always in a deployable state

The trunk-based model eliminates merge conflicts between long-lived branches, ensures every
change goes through PR review before touching `main`, and gives a clean audit trail of who
approved what promotion and when.

---

## Branch protection rules on `main`

Configured at **Settings → Branches → main**:

| Rule | Value |
|---|---|
| Require pull request before merging | ✅ |
| Required approving reviews | 1 |
| Dismiss stale reviews on new commits | ✅ |
| Require status checks to pass | ✅ |
| Require branches to be up to date | ✅ |
| Allow force pushes | ❌ |
| Allow deletions | ❌ |

No one — including admins — can push directly to `main` or bypass these rules.

---

## Cleaning up the old branches

> Run these commands once. They are safe — the old branch content is preserved in `main`
> (all branches were created from `main` and never diverged with unique work).

### Step 1 — verify there is no unique work on the old branches

```bash
# Show any commits on development that are NOT in main
git log main..origin/development --oneline

# Repeat for staging and production
git log main..origin/staging --oneline
git log main..origin/production --oneline
```

If any of these print commits, do NOT delete that branch yet — cherry-pick or merge those
commits to `main` first.

### Step 2 — back up the branch tips (optional safety net)

```bash
# Create local tags as a backup before deleting
git tag backup/development origin/development
git tag backup/staging      origin/staging
git tag backup/production   origin/production

# These tags stay in your local repo. To push them as a permanent record:
# git push origin backup/development backup/staging backup/production
```

### Step 3 — delete the remote branches

```bash
git push origin --delete development
git push origin --delete staging
git push origin --delete production
```

### Step 4 — delete the local tracking branches

```bash
git branch -d development
git branch -d staging
git branch -d production
git remote prune origin   # clean up stale remote-tracking refs
```

### Step 5 — verify

```bash
git branch -a
# Should show only:
#   * main
#   remotes/origin/main
```

---

## Related docs

- `docs/branch-protection.md` — branch protection rules and GitHub Environments setup
- `.github/workflows/ci-cd.yml` — the full pipeline definition
- `docs/adr-001-clerk-auth.md` — auth architecture decision record
