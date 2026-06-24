# FinanceGuard DevSecOps Capstone — Complete Reference Notes

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Infrastructure — Terraform & AWS](#2-infrastructure--terraform--aws)
3. [Kubernetes Cluster Setup](#3-kubernetes-cluster-setup)
4. [Helm Charts — Packaging the App](#4-helm-charts--packaging-the-app)
5. [GitOps — Argo CD](#5-gitops--argo-cd)
6. [CI/CD Pipeline — GitHub Actions](#6-cicd-pipeline--github-actions)
7. [Security Scanning — Shift-Left](#7-security-scanning--shift-left)
8. [Supply Chain Security](#8-supply-chain-security)
9. [Runtime & Admission Security](#9-runtime--admission-security)
10. [Secret Management — External Secrets Operator](#10-secret-management--external-secrets-operator)
11. [Observability — Metrics, Logs, Traces](#11-observability--metrics-logs-traces)
12. [Multi-Environment Strategy](#12-multi-environment-strategy)
13. [Frontend Runtime URL Injection](#13-frontend-runtime-url-injection)
14. [Challenges & How They Were Fixed](#14-challenges--how-they-were-fixed)
15. [Useful Commands Cheatsheet](#15-useful-commands-cheatsheet)

---

## 1. Project Overview

**What it is:** FinanceGuard is a personal finance tracking API with a static HTML/JS frontend. The application is intentionally simple — the entire point of the project is the DevSecOps platform built around it.

**Stack:**
- Backend: Python FastAPI + SQLAlchemy + PostgreSQL (RDS)
- Frontend: Static HTML/JS served by Nginx
- Container registry: Amazon ECR
- Kubernetes: AWS EKS (Fargate)
- IaC: Terraform
- CI/CD: GitHub Actions
- GitOps: Argo CD
- Observability: Prometheus + Grafana + Loki + Tempo + OpenTelemetry

**Three environments:** `dev` (automatic), `staging` (human approval), `prod` (human approval)

**Core principle:** Git is the single source of truth. The pipeline writes image tags to git manifests. Argo CD reads from git and deploys. The pipeline never touches the cluster directly.

---

## 2. Infrastructure — Terraform & AWS

### What Terraform provisions

| Resource | Purpose |
|---|---|
| VPC + subnets | Isolated network for the cluster |
| EKS cluster (Fargate) | Serverless Kubernetes — no EC2 nodes to manage |
| ECR repositories | `financeguard-backend`, `financeguard-frontend`, `charts/` |
| RDS PostgreSQL | Managed database, one instance per environment |
| IAM roles | IRSA — pods get AWS permissions without static keys |
| AWS Load Balancer Controller | Creates ALBs from Kubernetes Ingress objects |

### EKS Fargate key points

- **No EC2 nodes** — every pod runs in its own micro-VM managed by AWS. You never SSH into nodes.
- **No DaemonSets** — tools that need DaemonSets (like node-exporter) are disabled. This is why `nodeExporter.enabled: false` is in the Prometheus Helm values.
- **No EBS volumes** — Fargate can't mount EBS. Use `emptyDir` for scratch space or EFS for persistence. This is why Loki/Tempo use `emptyDir` storage in this project.
- **ALB Ingress** — must use `alb.ingress.kubernetes.io/target-type: ip` (not `instance`) because Fargate pods don't register with node port.
- **Fargate profiles** — tell EKS which namespaces run on Fargate. Any namespace not in a profile falls back to EC2 nodes (which don't exist here — so those pods would be stuck Pending).

### IRSA (IAM Roles for Service Accounts)

Instead of putting AWS keys in environment variables, IRSA lets a Kubernetes ServiceAccount assume an IAM role via OIDC. The pod gets a temporary token that AWS accepts. This is how:
- The External Secrets Operator reads from AWS Secrets Manager
- The ALB controller creates load balancers
- The pipeline (GitHub Actions OIDC) signs images with Cosign

---

## 3. Kubernetes Cluster Setup

### Namespaces

| Namespace | Contents |
|---|---|
| `dev` | Development environment — backend, frontend |
| `staging` | Staging environment — backend, frontend |
| `prod` | Production environment — backend, frontend |
| `monitoring` | Prometheus, Grafana, Loki, Tempo, OTel Collector |
| `argocd` | Argo CD — all Application resources live here |
| `falco` | Falco runtime security agent |
| `kyverno` | Kyverno admission controller |
| `external-secrets` | External Secrets Operator |

### Key Kubernetes objects in this project

**Deployment** — runs the backend/frontend pods. Managed by Helm, adopted by Argo CD.

**Service (ClusterIP)** — internal DNS name for pod-to-pod communication. The backend Service is what the frontend hits internally.

**Ingress** — declares that this service should be reachable from outside the cluster. The AWS ALB controller reads the Ingress and creates a real AWS Application Load Balancer.

**HorizontalPodAutoscaler (HPA)** — automatically scales replicas based on CPU. Dev/staging: 2–5 replicas. Prod: 3–10 replicas.

**ConfigMap** — stores non-secret config (e.g. OTel Collector configuration YAML, Grafana dashboard JSON).

**Secret** — stores sensitive config. In this project, Secrets are never created manually — External Secrets Operator creates them automatically from AWS Secrets Manager.

**ServiceAccount** — identity for a pod. Annotated with an IAM role ARN for IRSA.

**ClusterRole / ClusterRoleBinding** — grants the OTel Collector permission to read pod/namespace metadata from the Kubernetes API (needed to enrich logs/traces with k8s attributes).

---

## 4. Helm Charts — Packaging the App

### What Helm does

Helm is a package manager for Kubernetes. Instead of writing raw YAML for every environment, you write templates with variables, then provide a `values.yaml` per environment. Helm renders the final YAML and applies it.

### Chart structure

```
helm/
  backend/
    Chart.yaml          # name, version, appVersion
    values.yaml         # defaults (image repo, resource limits, etc.)
    values-dev.yaml     # dev overrides
    values-staging.yaml # staging overrides
    values-prod.yaml    # prod overrides (3x replicas, 2x resources)
    templates/
      deployment.yaml
      service.yaml
      ingress.yaml
      hpa.yaml
      serviceaccount.yaml
  frontend/
    (same structure)
    templates/
      deployment.yaml   # passes BACKEND_API_URL env var to nginx container
```

### How values layering works

Helm merges values files in order. Later files override earlier ones:
```
values.yaml (base defaults)
  + values-dev.yaml (dev-specific overrides)
  = final rendered YAML for dev
```

In Argo CD, this is configured as:
```yaml
spec:
  source:
    helm:
      valueFiles:
        - values.yaml
        - values-dev.yaml
```

### Release name matters

The Helm release name becomes a prefix on all resources it creates:
- Release `financeguard-backend` → Deployment named `financeguard-backend-backend`
- Release `financeguard-backend-dev` → Deployment named `financeguard-backend-dev-backend`

These are two completely separate Helm releases. When we migrated from direct pipeline deploys to Argo CD, Argo CD was creating a new release with a `-dev` suffix. We fixed this by adding `helm.releaseName: financeguard-backend` to all Argo CD Application manifests so Argo CD adopts the existing release instead of creating a duplicate.

---

## 5. GitOps — Argo CD

### What GitOps means

The git repository is the desired state. You never run `kubectl apply` or `helm upgrade` manually in production. Instead:
1. The pipeline writes the new image tag to a YAML file in `gitops/`
2. The pipeline commits and pushes that change (tagged `[skip ci]` to avoid infinite loops)
3. Argo CD detects the git change and runs `helm upgrade` to update the cluster

**Benefits:** every deployment is a git commit — you have a full history of what was deployed, when, and by whom. Rolling back = `git revert`.

### App-of-Apps pattern

Instead of manually applying 6 Argo CD Application manifests every time you set up the cluster, one "parent" Application watches the `gitops/` directory and automatically creates/updates the child Applications when their YAML files change.

```
gitops/app-of-apps.yaml         ← parent: watches gitops/ directory
gitops/dev/backend.yaml         ← child Application: manages dev backend
gitops/dev/frontend.yaml
gitops/staging/backend.yaml
gitops/staging/frontend.yaml
gitops/prod/backend.yaml
gitops/prod/frontend.yaml
```

Bootstrap (one-time only):
```bash
kubectl apply -f gitops/app-of-apps.yaml
```

After that, everything is self-managing.

### Sync policies per environment

| Environment | `automated` | `selfHeal` | `prune` | Effect |
|---|---|---|---|---|
| dev | true | true | true | Auto-deploys on every git change; reverts manual kubectl changes |
| staging | true | true | true | Same as dev — auto-deploys when staging manifest is updated |
| prod | false | false | false | **Never** auto-deploys. Only the pipeline's explicit `argocd app sync` deploys to prod |

**Why prod has selfHeal: false:** If someone makes a manual `kubectl` change to fix a live incident, you don't want Argo CD immediately reverting it. Human judgement takes precedence in production.

### What each field in an Application manifest does

```yaml
spec:
  source:
    repoURL: https://github.com/.../financeguard-devsecops-capstone.git
    targetRevision: main        # which branch to watch
    path: helm/backend          # where the Helm chart is
    helm:
      releaseName: financeguard-backend   # MUST match existing pipeline release name
      valueFiles:
        - values.yaml
        - values-dev.yaml
      parameters:
        - name: image.tag
          value: "abc123..."    # updated by pipeline on every build
  destination:
    server: https://kubernetes.default.svc  # in-cluster
    namespace: dev
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true    # create the namespace if it doesn't exist
```

---

## 6. CI/CD Pipeline — GitHub Actions

### Pipeline flow

```
git push to main
    │
    ├── Stage 0: PR Validation (runs on pull_request only)
    │     Gitleaks · Semgrep · Checkov · pytest + Black · SonarCloud
    │
    ├── Stage 1: Build, Scan, Sign & Push
    │     Docker build (backend + frontend)
    │     Trivy CVE scan → upload SARIF to GitHub Security tab
    │     Syft SBOM generation → upload as artifact
    │     ECR push :sha + :latest
    │     Cosign keyless sign
    │     ECR lifecycle policy (expire untagged after 14 days)
    │     Helm chart package → push to ECR OCI
    │
    ├── Stage 1.5: GitOps — Promote to dev
    │     yq updates gitops/dev/backend.yaml and gitops/dev/frontend.yaml
    │     git commit + push [skip ci]
    │     Argo CD detects git change → auto-deploys dev
    │
    ├── Stage 2: Wait for dev rollout
    │     kubectl bootstrap (apply app-of-apps + dev apps)
    │     Cleanup orphaned helm releases (one-time migration)
    │     Poll every 15s until deployment shows new :sha (up to 10 min)
    │     kubectl rollout status
    │     Integration tests on dev ALB
    │     ZAP baseline (passive) DAST scan
    │
    │     ⏸ APPROVAL GATE — GitHub Environments "staging"
    │
    ├── Stage 3: Deploy → Staging
    │     git pull --rebase (avoid conflicts with dev promote commit)
    │     yq updates gitops/staging/ manifests
    │     git commit + push [skip ci]
    │     kubectl apply staging Argo CD apps
    │     Poll until staging shows new :sha
    │     kubectl rollout status
    │     Integration tests on staging ALB
    │     ZAP full (active) DAST scan
    │
    │     ⏸ APPROVAL GATE — GitHub Environments "production"
    │
    ├── Stage 4: Deploy → Production
    │     git pull --rebase
    │     yq updates gitops/prod/ manifests
    │     git commit + push [skip ci]
    │     kubectl apply prod Argo CD apps
    │     argocd app sync (explicit — prod never auto-syncs)
    │     Poll until prod shows new :sha
    │     kubectl rollout status
    │     Smoke test: curl /health → expect 200
    │
    └── Stage 5: Evidence Bundle + Release
          Download all artifacts from previous stages
          Assemble into evidence/ directory
          kubectl get applications -n argocd → saved to evidence
          Upload EVIDENCE-BUNDLE artifact (90-day retention)
          Retag :sha → :stable in ECR
          Create GitHub Release with notes
```

### Important pipeline concepts

**`[skip ci]`** — added to the git commit message when the pipeline pushes gitops manifest updates. Prevents GitHub from triggering a new pipeline run on that commit (which would create an infinite loop).

**`git pull --rebase` before pushing** — the staging promote job needs to pull first because the dev promote job may have pushed a commit ahead of it. Rebase replays your local commit on top of the remote, keeping history linear.

**`yq`** — a command-line YAML editor. Used to update the `image.tag` parameter in Argo CD Application manifests without parsing/regenerating the whole file. Example:
```bash
yq e "(.spec.source.helm.parameters[] | select(.name == \"image.tag\")).value = \"$SHA\"" -i gitops/dev/backend.yaml
```

**Polling loop** — after updating the git manifest, the pipeline doesn't blindly wait. It polls `kubectl get deployment` every 15 seconds, looking at `.spec.template.spec.containers[0].image` until it contains the new SHA. This confirms Argo CD has picked up and applied the change, not just that the deployment object exists.

**GitHub Environments** — configured in repo Settings → Environments. When a job has `environment: staging`, GitHub pauses the job and shows an "Approve/Reject" button to configured reviewers. GitHub records who approved and when — this is your audit trail.

**Artifact retention** — dev/staging artifacts kept 30 days. Prod/evidence artifacts kept 90 days (compliance requirement for capstone submission).

---

## 7. Security Scanning — Shift-Left

"Shift-left" means running security checks as early in the pipeline as possible — ideally on the PR before it even merges, not after it's in production.

### Gitleaks — Secret Scanning

**What it does:** Scans the entire git history (not just the latest commit) for accidentally committed secrets — API keys, passwords, tokens, private keys.

**When it runs:** PR validation (Stage 0)

**Why full history:** A secret committed 6 months ago and then deleted in a later commit is still visible in git history. Gitleaks checks every commit.

**Config:** No config needed for basic use. The `GITLEAKS_LICENSE` secret is only needed for the paid version (enterprise features). The free version works without it.

**Output:** If it finds something, the step fails with the file, line number, and rule that matched.

### Semgrep — SAST (Static Application Security Testing)

**What it does:** Analyzes Python source code for security vulnerabilities without running the code. Uses pattern matching rules.

**When it runs:** PR validation (Stage 0)

**Rule sets used:**
- `p/python` — Python-specific issues
- `p/owasp-top-ten` — OWASP Top 10 vulnerabilities (SQL injection, XSS, etc.)
- `p/secrets` — hardcoded credentials in source code
- `p/security-audit` — broader security patterns

**Output:** SARIF file uploaded to GitHub → appears in repo **Security** tab → **Code scanning** as individual alerts with file + line number.

### Checkov — IaC Scanning

**What it does:** Scans Terraform files for cloud misconfigurations before they're deployed. Checks hundreds of rules like "S3 bucket should have versioning enabled", "Security group should not allow 0.0.0.0/0 on port 22", "RDS should have deletion protection".

**When it runs:** PR validation (Stage 0)

**Why this matters:** Catching a misconfigured security group in Terraform before `terraform apply` is much cheaper than finding it after an incident.

### pytest + Black — Unit Tests & Code Style

**What it does:** Runs the backend unit test suite and checks code formatting.

**When it runs:** PR validation (Stage 0)

**DATABASE_URL:** The tests use `sqlite:///./test.db` — an in-memory SQLite database — so they don't need a real PostgreSQL instance to run in CI.

**Why Black:** Enforces consistent code formatting. `black --check` exits non-zero if any file would be reformatted. This prevents "style fix" commits from cluttering the PR history.

### SonarCloud — Code Quality Gate

**What it does:** Tracks code coverage, code smells, duplications, security hotspots, and maintainability ratings. Has a "Quality Gate" that fails if coverage drops below a threshold or new issues exceed limits.

**When it runs:** PR validation (Stage 0)

**Requires:** `SONAR_TOKEN` secret + `sonar-project.properties` file in the repo root.

### Trivy — Container Vulnerability Scanning

**What it does:** Scans the Docker image (after build, before push) for known CVEs in OS packages and language libraries.

**When it runs:** Stage 1, on the locally built image before it's pushed to ECR.

**Flags used:**
- `--severity CRITICAL,HIGH` — only report critical and high severity
- `--ignore-unfixed` — skip CVEs that have no fix available yet (nothing you can do about those)
- `--exit-code 1` — fail the job if findings are found (set to `continue-on-error: true` in this demo)

**SARIF upload:** Results also uploaded to GitHub Security tab alongside Semgrep findings.

---

## 8. Supply Chain Security

Supply chain security means proving that the artifact you're deploying is exactly what came out of your verified build process — not something tampered with in transit or storage.

### Syft — SBOM (Software Bill of Materials)

**What it does:** Generates a complete inventory of every package, library, and dependency inside the Docker image. Output format: SPDX 2.3 JSON.

**Why it matters:** If a new CVE is discovered in library X, you can instantly check your SBOM to see if any of your images contain library X — without rebuilding or scanning again.

**When it runs:** Stage 1, after build.

**Output:** `sbom-backend-<sha>.spdx.json` — uploaded as a pipeline artifact. Contains entries like:
```json
{
  "name": "fastapi",
  "version": "0.100.0",
  "type": "python",
  "locations": [{"path": "/usr/local/lib/python3.11/site-packages/fastapi"}]
}
```

### Cosign — Image Signing (Keyless OIDC)

**What it does:** Cryptographically signs the Docker image so you can prove it came from your specific GitHub Actions workflow.

**How keyless signing works:**
1. GitHub Actions gets a short-lived OIDC token from GitHub's identity provider
2. Cosign sends that token to Sigstore's Fulcio CA
3. Fulcio issues a short-lived signing certificate tied to the workflow identity
4. Cosign signs the image digest with that certificate
5. The signature + certificate are recorded in Sigstore's Rekor public transparency log
6. The certificate (and therefore the signature) expires — but the Rekor entry is permanent

**Why no long-lived keys:** Traditional signing requires managing a private key securely (rotation, storage, access control). Keyless signing uses the GitHub Actions job identity as proof — no key to lose or steal.

**Verify command:**
```bash
cosign verify \
  --certificate-identity-regexp "https://github.com/YOUR_REPO/.*" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  YOUR_IMAGE:SHA
```
A successful verify means: this image was signed by a GitHub Actions run in your repo.

**When it runs:** Stage 1 (sign), Stage 2/3/4 (verify before each deploy).

### ECR Image Lifecycle Policy

Automatically expires untagged images (intermediate build layers) after 14 days. Prevents ECR storage from growing unbounded. Tagged images (`:sha`, `:latest`, `:stable`) are not affected by this policy.

---

## 9. Runtime & Admission Security

### Kyverno — Admission Controller

**What it does:** Intercepts every Kubernetes API request to create/update a Pod. Evaluates the pod spec against policy rules. If the pod violates a policy, it's rejected before it ever runs.

**Think of it as:** A bouncer that checks every pod at the door.

**Policies in this project:**
- `require-non-root` — blocks any container with `securityContext.runAsUser: 0` or no user set
- `require-readonly-rootfs` — blocks containers without `readOnlyRootFilesystem: true`
- `require-resource-limits` — blocks containers with no CPU or memory limits (prevents runaway pods from starving the cluster)
- `restrict-image-registries` — only allows images from `866934333672.dkr.ecr.us-east-1.amazonaws.com` (your ECR). Blocks arbitrary public images.

**How to test it's working:**
```bash
kubectl run bad-pod \
  --image=nginx \
  --overrides='{"spec":{"containers":[{"name":"bad-pod","image":"nginx","securityContext":{"runAsUser":0}}]}}' \
  -n dev
# Expected: Error from server: admission webhook "validate.kyverno.svc" denied the request
```

**View all policies:**
```bash
kubectl get clusterpolicies
kubectl describe clusterpolicy require-non-root
```

### Falco — Runtime Threat Detection

**What it does:** Runs on each node and monitors every system call made by every container. Fires alerts when behaviour matches a threat pattern.

**How it works:** Falco uses eBPF (in modern versions) or a kernel module to hook into the Linux kernel's syscall interface. It sees every `open()`, `exec()`, `connect()`, `write()` call made by any container, regardless of what the container does to hide it.

**Default rules detect:**
- Shell spawned inside a container (`kubectl exec -- sh`)
- Process writing to `/etc/` or `/proc/`
- Outbound connection to unexpected port
- Privilege escalation attempts
- Sensitive file reads (`/etc/shadow`, `~/.ssh/`)

**View logs:**
```bash
kubectl logs -n falco -l app.kubernetes.io/name=falco --tail=50
```

**Trigger a detection to prove it works:**
```bash
kubectl exec -n dev deployment/financeguard-backend-backend -- sh -c "whoami"
kubectl logs -n falco -l app.kubernetes.io/name=falco --tail=5
# Look for: "Notice A shell was spawned in a container..."
```

### Kyverno vs Falco — the difference

| | Kyverno | Falco |
|---|---|---|
| When | Admission (before pod starts) | Runtime (while pod is running) |
| What | Declares what is allowed | Detects what is happening |
| Response | Block the request | Alert (log, webhook, Slack) |
| Analogy | Bouncer at the door | Security camera inside |

You need both: Kyverno prevents bad configs, Falco catches bad behaviour even from correctly-configured containers.

---

## 10. Secret Management — External Secrets Operator

### The problem

Database passwords, API keys, and other secrets should never be in git — not even encrypted. If the encryption key is ever compromised, all historical secrets in git history are exposed.

### How ESO works

1. Secrets are stored in **AWS Secrets Manager** (encrypted at rest, access controlled by IAM)
2. ESO runs in the cluster with an IAM role (via IRSA) that has read permission on specific secrets
3. You create an `ExternalSecret` object in Kubernetes that says "fetch secret X from AWS Secrets Manager and create a Kubernetes Secret named Y"
4. ESO syncs the value on a schedule (default: 1 hour) and whenever the ExternalSecret object changes

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: financeguard-db-secret
  namespace: dev
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: financeguard-db-secret   # creates this K8s Secret
  data:
    - secretKey: DATABASE_URL       # key in the K8s Secret
      remoteRef:
        key: financeguard/dev/database-url  # path in AWS Secrets Manager
```

**The Kubernetes Secret is generated at runtime** — it's never committed to git.

**Check sync status:**
```bash
kubectl get externalsecret -n dev
# STATUS column should show: SecretSynced
```

---

## 11. Observability — Metrics, Logs, Traces

### The three pillars

| Signal | Question it answers | Tool |
|---|---|---|
| Metrics | Is the system healthy? (numbers over time) | Prometheus → Grafana |
| Logs | What happened? (text events) | Loki → Grafana |
| Traces | Why did it take that long? (request flow) | Tempo → Grafana |

### OpenTelemetry (OTel)

OTel is a vendor-neutral standard for collecting telemetry. The application instruments itself once using the OTel SDK, and the OTel Collector routes signals to any backend.

**Architecture:**
```
FastAPI app
  │ (gRPC :4317 via localhost — sidecar)
  ▼
OTel sidecar container (in same pod)
  │ (gRPC :4317 via Kubernetes DNS)
  ▼
Central OTel Collector (monitoring namespace)
  │
  ├──► Tempo (traces)
  ├──► Loki (logs via Loki exporter)
  └──► Prometheus (metrics via remote write receiver)
```

**Why a sidecar + central collector:**
- The sidecar batches and retries locally — if the central collector is temporarily down, the sidecar buffers the data
- The central collector handles routing — if you want to add a new backend, change the collector config, not every application

### Application instrumentation

The FastAPI backend uses:
- `opentelemetry-instrumentation-fastapi` — auto-instruments every HTTP route with spans
- `opentelemetry-instrumentation-sqlalchemy` — auto-instruments every database query as child spans
- Custom metrics counter: `financeguard_transactions_created_total` — incremented each time a transaction is created
- Custom metrics counter: `financeguard_http_requests_total` — incremented on every request with `route` and `method` labels
- Structured logging: every log line includes `trace_id` and `span_id` so you can correlate a log line to a specific request trace

### Prometheus

**What it does:** Scrapes metrics from endpoints (pull model) and stores them as time series.

**kube-prometheus-stack** — the Helm chart that installs:
- Prometheus server
- Alertmanager
- Grafana
- kube-state-metrics (pod status, deployment status, etc.)
- Built-in dashboards for Kubernetes

**Remote write receiver** — enabled with `--web.enable-remote-write-receiver` flag so OTel Collector can push metrics to Prometheus (push model). Without this flag, Prometheus only pulls.

**Custom metrics visible at:**
```
Grafana → Explore → Prometheus → query: financeguard_transactions_created_total
```

### Loki

**What it does:** Stores logs indexed by stream labels (not full-text indexed like Elasticsearch). Much cheaper to run.

**Stream labels** — metadata attached to a log stream that you can filter on. In this project:
- `app` — e.g. `financeguard-backend`
- `namespace` — e.g. `dev`
- `level` — e.g. `INFO`, `ERROR`

**Why labels matter:** Loki only indexes labels, not log content. Queries MUST filter by label first: `{app="financeguard-backend"}`. Queries without a label selector are rejected.

**OTel → Loki path:** The OTel Collector's `transform/loki_labels` processor copies resource attributes (`service.name` → `app`, `k8s.namespace.name` → `namespace`) into Loki stream labels. Without this, all logs land in a single unlabeled stream.

**Query in Grafana:**
```
{app="financeguard-backend", namespace="dev", level="ERROR"}
```

### Tempo

**What it does:** Stores distributed traces. A trace is a tree of spans — each span represents one operation (HTTP handler, database query, external call) with start time, duration, and attributes.

**How to find traces:**
Grafana → Explore → Tempo → Search → Service Name: `financeguard-backend`

**Trace correlation:** Every log line from the instrumented app contains `trace_id`. In Grafana, clicking the trace ID in a log line jumps directly to the Tempo trace view for that specific request.

### Grafana Dashboards

Two custom dashboards:

**FinanceGuard Overview:**
- Pod status (up/down) per environment
- HTTP request rate
- Transaction totals (custom OTel counter)
- CPU and memory usage

**Logs Explorer:**
- Log stream filtered by `app`, `namespace`, `level` variables
- Log volume by level (bar chart)
- Errors-only panel
- Full log lines with trace ID

**Datasource UIDs:** Each Grafana datasource has a unique identifier (UID). Dashboard JSON panels reference datasources by UID. If the UID in the dashboard doesn't match the provisioned UID, all panels show "No data." Fixed by explicitly setting UIDs in the Grafana provisioning ConfigMap.

---

## 12. Multi-Environment Strategy

### Environment isolation

Each environment is a separate Kubernetes namespace with its own:
- Deployments (separate pods, separate image versions)
- Services and Ingresses (separate ALB hostnames)
- Secrets (separate database connection strings via ESO)
- Argo CD Application (separate sync policy)

### Deployment progression

Same image digest (`:sha`) flows through all three environments. Nothing is rebuilt per environment. Only the Helm values change between environments (replica counts, resource limits, backend URL).

```
build once → :sha image
               │
               ├── dev (image.tag = sha, values-dev.yaml)
               │     2 replicas, standard resources
               │
               ├── staging (image.tag = sha, values-staging.yaml)
               │     2 replicas, standard resources
               │
               └── prod (image.tag = sha, values-prod.yaml)
                     3 replicas, 2x resource limits, HPA 3-10
```

### Approval gates

GitHub Environments pauses a job until a configured reviewer clicks Approve. The approval is recorded in the GitHub Actions run log:
- Who approved
- When they approved
- Which run/commit they approved

This creates a compliance audit trail without any external tooling.

### Sequencing in the pipeline

The staging manifest is updated **inside the staging deploy job** — after the approval gate fires. Not before. This means:
- Argo CD doesn't know about the new staging image until a human approves
- Even with `selfHeal: true`, staging can't accidentally deploy the new version before approval

Same for prod.

---

## 13. Frontend Runtime URL Injection

### The problem

The frontend is a static HTML/JS file served by Nginx. Vite (the build tool) bakes environment variables into the JS bundle at **build time** — not at runtime.

If you set `VITE_API_BASE_URL` as a container environment variable, Nginx never reads it. The browser never sees it. The hardcoded URL from build time is what runs.

This means you can't use the same image across environments with different backend URLs — unless you solve the runtime injection problem.

### The solution — envsubst

1. In `index.html`, the API URL is written as a placeholder:
   ```js
   let API_URL = localStorage.getItem("FG_API_URL") || "${BACKEND_API_URL}";
   ```

2. At build time, `index.html` is copied as `index.html.template` inside the image.

3. In the Dockerfile `CMD`, before Nginx starts, `envsubst` substitutes the placeholder:
   ```dockerfile
   CMD ["/bin/sh", "-c", \
        "envsubst '${BACKEND_API_URL}' \
          < /usr/share/nginx/html/index.html.template \
          > /usr/share/nginx/html/index.html \
        && nginx -g 'daemon off;'"]
   ```

4. The `BACKEND_API_URL` environment variable comes from Helm:
   ```yaml
   # helm/frontend/templates/deployment.yaml
   env:
     - name: BACKEND_API_URL
       value: {{ .Values.env.BACKEND_API_URL }}
   ```

5. Each environment provides its own backend ALB URL in its values file:
   ```yaml
   # helm/frontend/values-dev.yaml
   env:
     BACKEND_API_URL: "http://k8s-dev-financeg-ff3bdf31f7-1789545035.us-east-1.elb.amazonaws.com"
   ```

**Result:** One image. Three environments. Three different backend URLs. Injected at container startup, not at build time.

---

## 14. Challenges & How They Were Fixed

### Challenge 1 — Double-deployer conflict

**What happened:** The GitHub Actions pipeline was running `helm upgrade --install` directly. Argo CD also had `selfHeal: true`. Both were trying to manage the same Helm release. Argo CD immediately reverted whatever the pipeline did, creating a constant drift loop.

**Fix:** Removed all `helm upgrade --install` from the pipeline. The pipeline now only writes image tags to git. Argo CD is the sole deployer.

**Lesson:** Pick one deployer and commit to it. If you use GitOps, the pipeline's job is to write to git, not to touch the cluster.

---

### Challenge 2 — Grafana "No data" on all panels

**What happened:** All dashboard panels showed "No data" even though metrics were flowing into Prometheus. The dashboard JSON was referencing a Prometheus datasource UID that didn't match the actual provisioned UID.

**Fix:** Explicitly set UIDs in the Grafana provisioning ConfigMap so the auto-generated UIDs always match what the dashboard JSON expects.

**Lesson:** Never let Grafana datasource UIDs be auto-generated if dashboards reference them. Set them explicitly.

---

### Challenge 3 — Loki logs visible via API but Grafana showed nothing

**What happened:** Confirmed 26 logs were in Loki via `curl` to the Loki API. Grafana showed nothing. Two root causes:
1. Dashboard queries used `{job=~"$app"}` but the actual Loki stream label was `app` (set by the OTel `transform/loki_labels` processor)
2. The default time window was `now-1h` and logs were older than 1 hour
3. Grafana's "All" template variable value `.*` didn't trigger a re-render on first load

**Fix:** Updated all queries to `{app=~"$app", namespace=~"$namespace"}`. Extended time window to `now-3h`. User discovered the "All" variable issue by switching the dropdown from "All" to "backend" and back.

**Lesson:** Verify stream label names with `curl loki/api/v1/labels` before writing dashboard queries.

---

### Challenge 4 — gitops-promote updating all three environments simultaneously

**What happened:** The original `gitops-promote` job updated dev, staging, and prod manifests at once. Argo CD immediately deployed to all three. The approval gates fired *after* production was already updated.

**Fix:** Split into per-environment promote steps. `gitops-promote-dev` runs immediately after build. Staging manifest is updated inside the staging deploy job (after the approval gate fires). Prod manifest is updated inside the prod deploy job (same).

**Lesson:** In GitOps, the approval gate must control WHEN the manifest is written to git. If the manifest is written before the gate, the gate is theatre.

---

### Challenge 5 — VITE_API_BASE_URL container env var had no effect

**What happened:** The frontend Helm chart set `VITE_API_BASE_URL` as a container environment variable. Nginx served the static HTML without ever reading it. The backend URL in the browser was always the hardcoded build-time default.

**Fix:** envsubst at container startup (see Section 13).

**Lesson:** Understand build-time vs runtime for your web framework. Vite = build-time only. Static HTML needs a different injection mechanism.

---

### Challenge 6 — OTel sidecar couldn't reach the central collector

**What happened:** The OTel sidecar was configured to send to `otel-collector:4317`. The actual Kubernetes Service name was `otel-collector-opentelemetry-collector` in the `monitoring` namespace. DNS resolution failed silently.

**Fix:** Updated the endpoint to `otel-collector-opentelemetry-collector.monitoring.svc.cluster.local:4317`.

**Lesson:** Kubernetes DNS for cross-namespace services: `<service-name>.<namespace>.svc.cluster.local`.

---

### Challenge 7 — k8sattributes processor had no RBAC

**What happened:** The OTel Collector's `k8sattributes` processor enriches spans and logs with Kubernetes metadata (pod name, namespace, node name). It does this by calling the Kubernetes API. The ServiceAccount had no ClusterRole, so all API calls were denied. Logs and spans were missing k8s labels.

**Fix:** Created a ClusterRole granting `get`/`list`/`watch` on pods and namespaces, bound to the OTel Collector ServiceAccount.

**Lesson:** Any Kubernetes component that calls the API server needs explicit RBAC. Default ServiceAccounts have no permissions.

---

### Challenge 8 — Duplicate Helm releases in dev namespace

**What happened:** The pipeline had created release `financeguard-backend` (→ deployment `financeguard-backend-backend`). Argo CD created a second release `financeguard-backend-dev` (using the Application name as the release name) (→ deployment `financeguard-backend-dev-backend`). Two deployments running in the same namespace serving the same traffic.

**Fix:** Added `helm.releaseName: financeguard-backend` to the Argo CD Application manifest so Argo CD adopts the existing release. The orphaned `-dev` releases were cleaned up with `helm uninstall`.

**Lesson:** Argo CD defaults to using the Application name as the Helm release name. Always explicitly set `releaseName` to match your existing releases.

---

### Challenge 9 — ECR ImageAlreadyExistsException failing the pipeline

**What happened:** The `retag images → :stable` step failed with exit code 254 when a previous run had already tagged that image digest as `:stable`. The error `ImageAlreadyExistsException` means the tag already points to the same digest — which is a success condition, not a failure.

**Fix:** The script now catches `ImageAlreadyExistsException` specifically and treats it as a success. Any other error still fails the job.

**Lesson:** Not all non-zero exit codes are real failures. Read error messages before treating them as blockers.

---

## 15. Useful Commands Cheatsheet

### Cluster status
```bash
kubectl get pods -n dev
kubectl get pods -n staging
kubectl get pods -n prod
kubectl get pods -n monitoring
kubectl get pods -n argocd
kubectl get applications -n argocd
```

### Get frontend URLs
```bash
kubectl get ingress -n dev
kubectl get ingress -n staging
kubectl get ingress -n prod
```

### Check Argo CD sync status
```bash
kubectl get applications -n argocd -o wide
kubectl describe application financeguard-backend-dev -n argocd
```

### Argo CD port-forward (access UI)
```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Open: https://localhost:8080
# Password: kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
```

### Grafana port-forward
```bash
kubectl port-forward svc/kube-prometheus-stack-grafana -n monitoring 3000:80
# Open: http://localhost:3000
# Password: kubectl get secret kube-prometheus-stack-grafana -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d
```

### Check OTel Collector metrics
```bash
kubectl port-forward svc/otel-collector-opentelemetry-collector -n monitoring 8888:8888
curl http://localhost:8888/metrics | grep otelcol_exporter
# Look for: otelcol_exporter_sent_spans, otelcol_exporter_sent_metric_points, otelcol_exporter_sent_log_records
```

### Check External Secrets sync
```bash
kubectl get externalsecret -n dev
kubectl describe externalsecret financeguard-db-secret -n dev
```

### Verify a Cosign-signed image
```bash
cosign verify \
  --certificate-identity-regexp "https://github.com/timkamba2002/financeguard-devsecops-capstone/.*" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  866934333672.dkr.ecr.us-east-1.amazonaws.com/financeguard-backend:latest
```

### Test Kyverno blocks root pods
```bash
kubectl run bad-pod \
  --image=nginx \
  --overrides='{"spec":{"containers":[{"name":"bad-pod","image":"nginx","securityContext":{"runAsUser":0}}]}}' \
  -n dev
```

### Check Falco alerts
```bash
kubectl logs -n falco -l app.kubernetes.io/name=falco --tail=50
```

### Force Argo CD sync (prod)
```bash
# Port-forward first (see above)
argocd login localhost:8080 --username admin --password <password> --insecure
argocd app sync financeguard-backend-prod --prune=false
argocd app sync financeguard-frontend-prod --prune=false
```

### View Loki labels (debug)
```bash
kubectl port-forward svc/loki -n monitoring 3100:3100
curl "http://localhost:3100/loki/api/v1/labels"
curl "http://localhost:3100/loki/api/v1/label/app/values"
```

### Helm — check releases
```bash
helm list -n dev
helm list -n staging
helm list -n prod
```

### Roll back a deployment (GitOps way)
```bash
# Find the commit that had the previous image tag
git log --oneline gitops/prod/backend.yaml
# Revert to it
git revert <bad-commit-sha>
git push origin main
# Argo CD will detect the revert and roll back automatically (staging/dev)
# For prod: trigger argocd app sync after the revert commits
```

---

*Last updated: June 2026 — FinanceGuard DevSecOps Capstone*
