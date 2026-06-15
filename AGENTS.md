# Agent Guidelines for FinanceGuard Capstone

Welcome! This document governs any future AI agent's actions and contributions to the **FinanceGuard** Enterprise DevSecOps codebase.

## 1. Project Overview & Architecture
FinanceGuard is a secure enterprise-grade financial transaction tracking system.
- **Frontend**: Single-page application using Tailwind CSS and Clerk SDK for authentication. Hosted on Nginx inside Kubernetes (EKS).
- **Backend**: Python FastAPI service implementing Clerk JWT verification. Communicates with a PostgreSQL database (RDS).
- **IaC**: Terraform for AWS provisioning (VPC, EKS, RDS, ECR, IAM, etc.).
- **CI/CD**: GitHub Actions for build/test/scan/push, and ArgoCD for GitOps deployment to EKS.
- **Security**: Focus on Shift-Left Security (Trivy, Hadolint, Kyverno policies, OPA, TLS, network policies, IAM Roles for Service Accounts - IRSA).

## 2. Coding and Security Rules

### Backend Python (FastAPI)
- **Typing**: Use strict Python type hinting.
- **Dependencies**: Keep `requirements.txt` minimal and clean. Pin versions.
- **Authentication**: All endpoints under `/api/v1/transactions` MUST be protected by the `ClerkJWTBearer` security dependency. Never bypass validation.
- **Database**: Use SQLAlchemy for ORM. Always use migrations (Alembic) if database changes occur.
- **Testing**: Maintain >80% test coverage. Write unit and integration tests using `pytest` and `httpx.AsyncClient`.

### Frontend (HTML/JS/Tailwind)
- Use semantic HTML tags.
- Use Clerk's JS SDK for authentication flow. Maintain clean state checking.
- Do not store JWTs or sensitive user details in unencrypted localStorage.
- Styling must follow the existing Tailwind styling guidelines, prioritizing high-end glassmorphism/dark aesthetics.

### IaC (Terraform)
- Use remote state (S3 + DynamoDB locking) for staging and production environments.
- Always use variables and outputs properly. Do not hardcode values.
- Adhere to the AWS Well-Architected Framework: run EKS in private subnets, place RDS in isolated subnets, keep security groups tightly scoped.
- Ensure all resources have standard tags: `Project`, `Environment`, `ManagedBy`.

### Git & Branching
- Follow the branching strategy:
  - `main` - Protected. Production release tags.
  - `staging` - Pre-production.
  - `development` - Active development.
- Always create feature branches (e.g., `feature/xyz`) off `development` and merge via Pull Requests (PRs).
- Commits must follow [Conventional Commits](https://www.conventionalcommits.org/): `feat: ...`, `fix: ...`, `chore: ...`, `ci: ...`, `docs: ...`.

### Security and DevSecOps
- **Scanning**: Run `trivy` scans on local builds before pushing code.
- **IaC Static Analysis**: Use `tflint` and `checkov` to verify Terraform security compliance.
- **Kubernetes**: Ensure Kyverno policies (e.g., disallow root, require labels) are respected in Helm templates.

## 3. Deployment & Validation
- Helm charts live under `helm/`. Deploy changes by updating values in `gitops/` overlays and letting ArgoCD sync them.
- Always verify container security before deployment.
