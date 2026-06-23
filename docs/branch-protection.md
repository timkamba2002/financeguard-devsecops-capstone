# Branch Protection Rules — FinanceGuard

Configure these rules in **GitHub → Settings → Branches** for each protected branch.

---

## `main` (Production)

This is your production branch. Every merge here triggers the `deploy-prod` job which
requires manual approval via GitHub Environments. The branch protection rules enforce
that _only code that has passed the full CI pipeline_ can merge.

### Settings to enable

| Setting | Value | Why |
|---|---|---|
| **Require a pull request before merging** | ✅ | No direct pushes to prod |
| **Required approvals** | 1 | At minimum one human review |
| **Dismiss stale pull request approvals when new commits are pushed** | ✅ | Re-review after force-push/amend |
| **Require review from Code Owners** | ✅ (if CODEOWNERS file exists) | Domain-specific review |
| **Require status checks to pass before merging** | ✅ | CI must be green |
| **Require branches to be up to date before merging** | ✅ | Prevents "works on my machine" merges |
| **Require conversation resolution before merging** | ✅ | No unresolved review threads |
| **Require signed commits** | ✅ | Cosign signs images; also sign commits |
| **Do not allow bypassing the above settings** | ✅ | Admins can't bypass either |
| **Allow force pushes** | ❌ | Never rewrite production history |
| **Allow deletions** | ❌ | Never delete the production branch |

### Required status checks for `main`

Add these as required checks (the exact job names from `ci-cd.yml`):

```
secret-scan
build
test
sonarcloud
security-scan
build-push
helm-package
```

> The `deploy-prod` job itself is NOT a required status check — it only runs after
> merge and requires manual approval. The checks above verify the code is safe BEFORE
> the PR can merge.

---

## `staging`

Staging represents code that passed dev integration tests and ZAP baseline. The same
discipline applies, slightly relaxed approval threshold.

### Settings to enable

| Setting | Value |
|---|---|
| **Require a pull request before merging** | ✅ |
| **Required approvals** | 1 |
| **Dismiss stale approvals when new commits are pushed** | ✅ |
| **Require status checks to pass before merging** | ✅ |
| **Require branches to be up to date** | ✅ |
| **Require conversation resolution** | ✅ |
| **Allow force pushes** | ❌ |
| **Allow deletions** | ❌ |

### Required status checks for `staging`

```
secret-scan
build
test
security-scan
build-push
helm-package
```

---

## `development`

Open for developer commits; looser rules so the team can iterate fast.

| Setting | Value |
|---|---|
| **Require a pull request before merging** | ✅ (at least for feature branches) |
| **Required approvals** | 0 (self-merge allowed for solo project) |
| **Require status checks to pass before merging** | ✅ |
| **Allow force pushes** | Only for repository admins |

### Required status checks for `development`

```
secret-scan
build
test
```

---

## Setting this up via GitHub CLI

```bash
# main — strict production rules
gh api repos/timkamba2002/financeguard-devsecops-capstone/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["secret-scan","build","test","sonarcloud","security-scan","build-push","helm-package"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false \
  --field required_conversation_resolution=true

# staging
gh api repos/timkamba2002/financeguard-devsecops-capstone/branches/staging/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["secret-scan","build","test","security-scan","build-push","helm-package"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false

# development
gh api repos/timkamba2002/financeguard-devsecops-capstone/branches/development/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["secret-scan","build","test"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews=null \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

> Run these once after the initial CI run creates the status check names. GitHub only
> lists checks that have run at least once in the branch protection dropdown.

---

## GitHub Environments (production approval gate)

Set up the `production` environment for the manual approval gate:

1. Go to **Settings → Environments → New environment → `production`**
2. Enable **Required reviewers**: add yourself (or the team lead)
3. Set **Wait timer**: 0 minutes (immediate after approval)
4. Under **Deployment branches**: restrict to `main` only
5. Add environment secrets if you want per-environment AWS credentials

The `deploy-prod` job in `ci-cd.yml` already references `environment: production` —
it will pause until you click **Approve** in the Actions UI.

Set up `staging` and `dev` environments similarly (no required reviewers needed unless
desired).
