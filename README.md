# FinanceGuard - Enterprise DevSecOps Capstone Project

FinanceGuard is a secure, cloud-native synthetic transaction platform built to demonstrate a complete **Enterprise DevSecOps** operating model on AWS.

**Business Objective**: Show a production-grade platform for financial services with strong security, automation, observability, and compliance controls.

---

## 1. System Architecture Overview

- **Frontend**: Single-page app with Tailwind CSS and Clerk authentication
- **Backend**: Python FastAPI with Clerk JWT verification
- **Infrastructure**: Terraform + EKS Fargate + RDS PostgreSQL + ECR
- **CI/CD**: GitHub Actions (full pipeline with security scans)
- **CD**: Argo CD with Helm and GitOps
- **Security**: Trivy, Kyverno, Falco, Gitleaks, Cosign
- **Monitoring**: Prometheus, Grafana, OpenTelemetry (Golden Signals)

---

## 2. Directory Structure

```text
financeguard-devsecops-capstone/
├── terraform/                  # IaC (VPC, EKS Fargate, RDS, ECR, IAM)
├── app/
│   ├── backend/                # FastAPI + Clerk JWT
│   └── frontend/               # Tailwind + Clerk UI
├── helm/                       # Helm charts for frontend and backend
├── gitops/                     # Argo CD Applications (dev/staging/prod)
├── security/                   # Kyverno policies
├── monitoring/                 # Grafana dashboards
├── docs/                       # Architecture and evidence
├── .github/workflows/          # GitHub Actions CI/CD
├── README.md
├── AGENTS.md
└── .gitignore

## 3. Key Features Implemented

- **Multi-environment**: dev, staging, prod using Kubernetes namespaces + GitHub Environment approval gates
- **Immutable deployments**: Same image digest (tagged by commit SHA) flows unchanged from dev → staging → prod
- **Security**: Shift-left scans (Gitleaks, Semgrep, Checkov, Trivy, ZAP), runtime protection (Falco, Kyverno), secrets management (ESO + AWS Secrets Manager)
- **GitOps**: Argo CD for continuous synchronization
- **Monitoring**: Golden Signals and business transaction tracing (Prometheus + Grafana + Loki + Tempo)
- **Supply chain**: Cosign OIDC keyless image signing + SBOM (Syft/SPDX 2.3)

---

## 4. Branching Strategy — Trunk-Based Development (Model B)

```
  feature/add-auth    fix/db-timeout
         │                  │
         └────── PR ────────┘
                  │
                main  ◄── single long-lived branch
                  │
         (push triggers pipeline)
                  │
      ┌───────────┼────────────┐
      ▼           ▼            ▼
    dev        staging        prod
 (auto)      (✋ approve)   (✋ approve)
```

| Branch | Purpose |
|---|---|
| `main` | Only long-lived branch. Always deployable. |
| `feature/*` | New functionality — branch from `main`, PR back to `main`, delete after merge |
| `fix/*` | Bug fixes — same lifecycle as feature branches |

**There are no `development`, `staging`, or `production` branches.** Environment promotion is
controlled by GitHub Environment approval gates, not by merging between branches.

### How to contribute

```bash
# 1. Create a branch
git checkout main && git pull origin main
git checkout -b feature/your-feature

# 2. Make changes, commit, push
git add <files>
git commit -m "feat: describe your change"
git push origin feature/your-feature

# 3. Open a PR to main
gh pr create --base main --title "feat: your feature"

# 4. CI runs automatically — get a review — merge
# 5. Delete the branch after merge
git push origin --delete feature/your-feature
```

See [`docs/branching-strategy.md`](docs/branching-strategy.md) for the full guide.


5. Getting Started
Local Development
Bashcd app/backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload
Frontend: Open app/frontend/index.html

Terraform Backend: Configured with S3 + DynamoDB (uncomment in main.tf for production).
Argo CD: Deployed and configured with GitOps for all environments.