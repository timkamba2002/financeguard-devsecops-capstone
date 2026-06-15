# FinanceGuard - Enterprise DevSecOps Capstone Project

FinanceGuard is a secure, cloud-native enterprise application for tracking financial transactions. It is designed to demonstrate DevSecOps best practices, featuring automated CI/CD pipelines, Shift-Left security scans, Infrastructure as Code (IaC) provisioning, GitOps deployment, and continuous monitoring.

---

## 1. System Architecture Overview

```mermaid
graph TD
    Client[Web Browser / Frontend] -->|HTTPS / JWT| ALB[AWS ALB / Ingress Controller]
    ALB -->|Route traffic| EKS[AWS EKS Cluster]
    subgraph EKS [AWS EKS Cluster]
        FE_Pod[Frontend Pods - Nginx]
        BE_Pod[Backend Pods - FastAPI]
        FE_Pod -->|Internal API Calls| BE_Pod
    end
    BE_Pod -->|Read/Write| RDS[(Amazon RDS PostgreSQL)]
    Client -->|Authentication| Clerk[Clerk Auth Provider]
    BE_Pod -->|Verify JWT| Clerk
```

---

## 2. Directory Layout

The repository is structured as follows:

```text
financeguard-devsecops-capstone/
├── terraform/                  # IaC for AWS (VPC, EKS, RDS, ECR, IAM, etc.)
├── ansible/                    # Configuration management / bootstrapping playbooks
├── app/
│   ├── backend/                # Python FastAPI API + Clerk JWT Verification
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── tests/
│   └── frontend/               # Single-page client app (Tailwind + Clerk)
│       ├── index.html
│       └── Dockerfile (nginx)
├── helm/                       # Helm charts for frontend and backend deployment
├── gitops/                     # ArgoCD overlays (dev, staging, prod)
├── security/                   # Kyverno policies, custom rules, OPA policies
├── monitoring/                 # Grafana dashboards, Prometheus alert rules
├── runbooks/                   # Incident response and troubleshooting runbooks
├── docs/                       # Architectural Decision Records (ADRs), Diagrams, Evidence
├── .github/workflows/          # GitHub Actions pipelines (CI/CD, scanning)
├── README.md                   # Project overview and instructions
├── AGENTS.md                   # Instructions for future AI integrations
├── .gitignore                  # Git patterns to ignore
└── LICENSE                     # Project License
```

---

## 3. Tech Stack

- **Frontend**: HTML5, Tailwind CSS (via CDN), Clerk Auth JS SDK, Nginx (container runtime).
- **Backend**: Python 3.11, FastAPI, Pydantic, SQLAlchemy, PyJWT, pytest.
- **Infrastructure**: Terraform, AWS (VPC, EKS, RDS PostgreSQL, ECR, KMS, IAM).
- **CI/CD & GitOps**: GitHub Actions, Trivy, Hadolint, Checkov, Helm, ArgoCD.
- **Security**: Clerk JWT Auth, IAM Roles for Service Accounts (IRSA), Kyverno, Network Policies.
- **Monitoring**: Prometheus, Grafana.

---

## 4. Branching Strategy

To maintain high software quality and gate deployment environments, we enforce the following branching strategy:

- **`main`**: The source of truth for Production. Direct commits are blocked. Merges only occur from `staging` via approved PRs. Matches the `prod` ArgoCD deployment.
- **`staging`**: The source of truth for the Staging environment. Syncs with the `staging` ArgoCD overlay. Used for user acceptance testing (UAT).
- **`development`**: The main integration branch for active development. Syncs with the `dev` ArgoCD overlay.
- **`feature/*` or `bugfix/*`**: Ephemeral branches created by developers. Must be merged into `development` via PRs requiring linting, testing, and container scanning checks to pass.

---

## 5. Getting Started (Local Development)

### Running the Backend Locally
1. Navigate to `app/backend/`
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up environment variables (create a `.env` file):
   ```env
   CLERK_API_URL=https://api.clerk.com/v1
   CLERK_JWT_KEY_URL=https://your-clerk-frontend-api-domain/.well-known/jwks.json
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/financeguard
   ```
5. Run the FastAPI application:
   ```bash
   uvicorn main:app --reload
   ```

### Running the Frontend Locally
1. Navigate to `app/frontend/`
2. Open `index.html` in your browser, or serve it using a local HTTP server:
   ```bash
   python -m http.server 8000
   ```
3. Access the dashboard at `http://localhost:8000`.

---

## 6. DevSecOps Lifecycle & Automated Pipelines

1. **Shift-Left Static Analysis**: Code quality is checked automatically on every pull request.
   - Python linted with `flake8`/`black`.
   - Dockerfile scanned with `hadolint`.
   - Infrastructure Code scanned with `checkov` and `tflint`.
2. **Build and Container Vulnerability Scanning**:
   - Python backend and Nginx frontend images are built.
   - Images are scanned for vulnerabilities using **Trivy**.
   - If severe (HIGH/CRITICAL) vulnerabilities are found, the build fails.
3. **Deployment via GitOps**:
   - Upon merging to targeted branches, the manifests in `gitops/` are updated.
   - ArgoCD monitors the repository and applies the modifications to EKS.
