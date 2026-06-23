# Branch Protection & GitHub Environments Setup

Trunk-based development (Model B) — single `main` branch, short-lived feature branches.

---

## Branch protection: `main`

Everything merges here. The branch protection rules make `main` the last line of defence before code reaches any environment.

### Settings (GitHub → Settings → Branches → Add rule → `main`)

| Setting | Value | Why |
|---|---|---|
| **Require a pull request before merging** | ✅ | No direct pushes — everything goes through PR Validation |
| **Required approvals** | 1 | At least one human review |
| **Dismiss stale reviews when new commits are pushed** | ✅ | Re-approval required after changes |
| **Require status checks to pass before merging** | ✅ | All PR Validation jobs must be green |
| **Require branches to be up to date before merging** | ✅ | Prevents "works locally but fails after merge" |
| **Require conversation resolution before merging** | ✅ | No unresolved review threads |
| **Do not allow bypassing the above settings** | ✅ | Admins can't bypass either |
| **Allow force pushes** | ❌ | Never rewrite `main` history |
| **Allow deletions** | ❌ | `main` cannot be deleted |

### Required status checks for `main`

Add these in the branch protection rule. GitHub only shows checks that have run at least once — trigger a PR first, then configure.

```
pr-secret-scan
pr-sast
pr-iac-scan
pr-test
```

> `pr-sonarcloud` is optional — add it once SONAR_TOKEN is confirmed working.
> The deploy jobs (`deploy-dev`, `deploy-staging`, `deploy-prod`) are NOT listed here —
> they run after merge, not as PR gates.

### Set up via GitHub CLI (run once after first PR runs)

```bash
gh api repos/timkamba2002/financeguard-devsecops-capstone/branches/main/protection \
  --method PUT \
  --field 'required_status_checks={"strict":true,"contexts":["pr-secret-scan","pr-sast","pr-iac-scan","pr-test"]}' \
  --field enforce_admins=true \
  --field 'required_pull_request_reviews={"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false \
  --field required_conversation_resolution=true
```

---

## Feature branch convention

| Prefix | Use |
|---|---|
| `feature/` | New functionality |
| `fix/` | Bug fixes |
| `chore/` | Dependency bumps, tooling, docs |
| `security/` | Security patches |

Branch from `main`, PR to `main`, delete after merge. Keep branches short-lived (days, not weeks). This avoids merge conflicts and keeps the diff reviewable.

---

## GitHub Environments (promotion gates)

These are the approval gates that control which commit SHA reaches each environment.

### Setup: `dev` (auto-deploy)

1. Go to **Settings → Environments → New environment → `dev`**
2. Leave **Required reviewers** empty (auto-deploy)
3. **Deployment branches**: restrict to `main` only
4. No wait timer

### Setup: `staging` (manual approval)

1. **Settings → Environments → New environment → `staging`**
2. **Required reviewers**: add yourself (or team lead)
3. **Deployment branches**: restrict to `main` only
4. Wait timer: 0 (optional — add a short delay if you want thinking time)

### Setup: `production` (manual approval)

1. **Settings → Environments → New environment → `production`**
2. **Required reviewers**: add yourself
3. **Deployment branches**: restrict to `main` only
4. **Environment secrets** (optional): per-environment AWS credentials if different from repo secrets

### How the approval gate works

When a commit is pushed to `main` the pipeline runs automatically through:
1. `build-sign-push` → completes automatically
2. `deploy-dev` → completes automatically (`dev` has no reviewers)
3. `deploy-staging` → **PAUSES** — you see a yellow "Waiting for review" banner in the Actions run. Click **Review deployments → staging → Approve**.
4. `deploy-prod` → **PAUSES** — same flow. Click **Review deployments → production → Approve**.

GitHub records who approved, when, and what commit SHA was deployed — this is your audit trail.

---

## Secrets required

| Secret | Where to add | Notes |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Repo → Settings → Secrets | Already added |
| `AWS_SECRET_ACCESS_KEY` | Repo → Settings → Secrets | Already added |
| `SONAR_TOKEN` | Repo → Settings → Secrets | Already added |
| `SLACK_WEBHOOK_URL` | Repo → Settings → Secrets | Already added |
| `GITLEAKS_LICENSE` | Repo → Settings → Secrets | Optional — free tier works without it |

No secrets needed for Cosign — it uses the GitHub Actions OIDC token automatically.

---

## Observability, Policy-as-Code, Runtime Security

These run on the cluster, not in CI. Apply them once after EKS is provisioned:

```bash
# Kyverno (policy-as-code: non-root, resource limits, ECR-only registry)
bash k8s/kyverno/install.sh

# External Secrets Operator + AWS Secrets Manager
kubectl apply -f k8s/external-secrets/

# Falco (runtime threat detection)
helm install falco falcosecurity/falco -n falco --create-namespace \
  -f k8s/falco/values.yaml

# Observability stack (Prometheus + Grafana + Loki + Tempo + OTel Collector)
bash k8s/observability/install.sh
```

See the respective directories for detailed setup instructions.
