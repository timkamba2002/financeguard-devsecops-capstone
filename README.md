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

3. Key Features Implemented

Multi-environment: dev, staging, prod using namespaces and branches
Immutable deployments: Image digests + signing
Security: Shift-left scans, runtime protection, secrets management
GitOps: Argo CD for continuous synchronization
Monitoring: Golden Signals and business transaction tracing
Environment Variables: SSM Parameter Store + tfvars


4. Branching Strategy

main → Protected production source
development → Active development
staging → Pre-prod
production → Final release


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