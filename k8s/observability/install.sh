#!/usr/bin/env bash
# FinanceGuard Observability Stack
#
# Deploys:
#   1. kube-prometheus-stack  (Prometheus + Grafana + Alertmanager + exporters)
#   2. Loki stack             (log aggregation + Promtail agent)
#   3. Tempo                  (distributed tracing)
#   4. OpenTelemetry Collector (receives OTLP, routes to all backends)
#
# All components land in the `monitoring` namespace.
# Run after EKS is provisioned and kubectl is configured.
#
# Prerequisites: helm >= 3.10, kubectl, AWS credentials

set -euo pipefail

NAMESPACE=monitoring
REGION=us-east-1
ACCOUNT=866934333672
CLUSTER=financeguard-eks-dev

echo "── Configuring kubectl ──────────────────────────────────────────────"
aws eks update-kubeconfig --region "$REGION" --name "$CLUSTER"

echo "── Adding Helm repos ────────────────────────────────────────────────"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana               https://grafana.github.io/helm-charts
helm repo add open-telemetry        https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

# ── 1. kube-prometheus-stack ─────────────────────────────────────────────────
echo ""
echo "── [1/4] kube-prometheus-stack (Prometheus + Grafana + Alertmanager) ──"
helm upgrade --install prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace "$NAMESPACE" --create-namespace \
  --version 58.2.1 \
  -f k8s/observability/prometheus-stack/values.yaml \
  --wait --timeout=10m

# ── 2. Loki (log aggregation) ────────────────────────────────────────────────
echo ""
echo "── [2/4] Loki + Promtail ───────────────────────────────────────────────"
helm upgrade --install loki grafana/loki-stack \
  --namespace "$NAMESPACE" \
  --version 2.10.2 \
  -f k8s/observability/loki/values.yaml \
  --wait --timeout=10m

# ── 3. Tempo (distributed tracing) ───────────────────────────────────────────
echo ""
echo "── [3/4] Tempo ─────────────────────────────────────────────────────────"
helm upgrade --install tempo grafana/tempo \
  --namespace "$NAMESPACE" \
  --version 1.7.2 \
  -f k8s/observability/tempo/values.yaml \
  --wait --timeout=10m

# ── 4. OpenTelemetry Collector ────────────────────────────────────────────────
echo ""
echo "── [4/4] OpenTelemetry Collector ───────────────────────────────────────"
helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
  --namespace "$NAMESPACE" \
  --version 0.82.0 \
  -f k8s/observability/otel-collector/values.yaml \
  --wait --timeout=10m

# ── Apply existing custom Prometheus rules ────────────────────────────────────
if [ -f monitoring/prometheus-rules.yaml ]; then
  echo ""
  echo "── Applying custom Prometheus rules ────────────────────────────────────"
  kubectl apply -f monitoring/prometheus-rules.yaml
fi

# ── Apply existing Grafana dashboards ─────────────────────────────────────────
if [ -f monitoring/grafana-dashboard.json ]; then
  echo ""
  echo "── Importing Grafana dashboard ─────────────────────────────────────────"
  kubectl create configmap financeguard-dashboard \
    --from-file=dashboard.json=monitoring/grafana-dashboard.json \
    --namespace "$NAMESPACE" \
    --dry-run=client -o yaml | \
    kubectl label --local -f - grafana_dashboard=1 -o yaml | \
    kubectl apply -f -
fi

echo ""
echo "── Deployment status ───────────────────────────────────────────────────"
kubectl get pods -n "$NAMESPACE"

# ── Access Grafana ─────────────────────────────────────────────────────────────
echo ""
echo "── Grafana access ──────────────────────────────────────────────────────"
echo "   kubectl port-forward svc/prometheus-stack-grafana 3000:80 -n monitoring"
echo "   URL:      http://localhost:3000"
echo "   Username: admin"
echo "   Password: kubectl get secret prometheus-stack-grafana -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d"

echo ""
echo "── Prometheus access ────────────────────────────────────────────────────"
echo "   kubectl port-forward svc/prometheus-stack-kube-prom-prometheus 9090:9090 -n monitoring"

echo ""
echo "── OTel Collector OTLP endpoint (for app instrumentation) ──────────────"
echo "   grpc: otel-collector.monitoring.svc.cluster.local:4317"
echo "   http: otel-collector.monitoring.svc.cluster.local:4318"

echo ""
echo "✅ Observability stack deployed."
