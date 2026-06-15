# FinanceGuard Runbook: Incident & Operational Troubleshooting

This document defines standard operating procedures (SOPs) for addressing typical infrastructure and software runtime issues within the FinanceGuard cluster.

---

## 1. Auth Failures (Clerk JWT Validation Failures)

### Symptoms
- Frontend users see authentication alerts/errors.
- Backend API logs display multiple HTTP 401 Unauthorized codes: `Invalid token` or `Token signature has expired`.
- Database logs show no transactions being populated because requests are rejected.

### Troubleshooting Steps
1. **Check Environment Configuration**:
   - Verify `CLERK_JWKS_URL` is set in the backend deployment configuration.
   - Run `kubectl get configmap backend-config -o yaml` to check parameters.
2. **Verify Public Network Connectivity**:
   - The EKS backend pods must be able to resolve external DNS and query Clerk's public JWKS endpoint.
   - Execute a shell inside a backend pod:
     ```bash
     kubectl exec -it <backend-pod-name> -n financeguard-dev -- curl -I https://api.clerk.com/v1
     ```
   - If curl times out, check EKS **Egress Security Group** or **Nat Gateway routing table** configurations.
3. **Verify Token Expiry**:
   - Inspect the request bearer token header at `https://jwt.io`. Confirm that the `exp` (expiry time) claim is in the future.

---

## 2. Pod CrashLoopBackOff Errors

### Symptoms
- `kubectl get pods -n financeguard-dev` returns status `CrashLoopBackOff`.
- Grafana dashboard reports high container restart counts.

### Troubleshooting Steps
1. **Check Pod Logs**:
   ```bash
   kubectl logs <pod-name> -n financeguard-dev --previous
   ```
2. **Kyverno Security Blockage**:
   - If the pod fails to start with permissions issues, ensure the Dockerfile does not run as root.
   - Verify Kyverno pod security rules aren't blocking deployments:
     ```bash
     kubectl get clusterpolicyreport
     ```
3. **Database Unreachable**:
   - If the backend crashes during initialization because of db connection pool timeouts:
     - Verify database credentials in AWS Secrets Manager or local Kubernetes secrets.
     - Validate EKS Node-to-RDS Security Group rules (port 5432 ingress must allow the EKS subnet).

---

## 3. ArgoCD Sync Failures

### Symptoms
- ArgoCD dashboard reports state `OutOfSync` or `Degraded`.
- Changes merged to `development` or `staging` branches are not showing up in the cluster.

### Troubleshooting Steps
1. **Check Git Status on ArgoCD Dashboard**:
   - Ensure the repository target revision matches the correct branch (`development` for Dev environment overlays, `staging` for Staging, `main` for Production).
2. **View Sync Failures Logs**:
   - Navigate to the ArgoCD application details and click the event log to check parsing exceptions.
3. **Validate Helm Templates**:
   - Validate that Helm manifests render without errors:
     ```bash
     helm template ./helm/backend
     helm template ./helm/frontend
     ```
