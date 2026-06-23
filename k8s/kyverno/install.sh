#!/usr/bin/env bash
# Install Kyverno and apply all policies.
# Run this once against the cluster after EKS is provisioned.
# Requires: helm, kubectl, AWS credentials pointing at financeguard-eks-dev

set -euo pipefail

echo "── Installing Kyverno ──────────────────────────────────────────────"
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update

helm upgrade --install kyverno kyverno/kyverno \
  --namespace kyverno --create-namespace \
  --version 3.2.6 \
  --set admissionController.replicas=2 \
  --wait

echo "── Waiting for Kyverno webhook to be ready ─────────────────────────"
kubectl rollout status deployment/kyverno-admission-controller -n kyverno --timeout=2m

echo "── Applying ClusterPolicies ────────────────────────────────────────"
kubectl apply -f k8s/kyverno/policies/

echo "── Verifying policies ──────────────────────────────────────────────"
kubectl get clusterpolicy

echo ""
echo "✅ Kyverno installed and policies applied."
echo ""
echo "Policy enforcement modes:"
echo "  Enforce (blocks):  require-non-root-containers"
echo "                     require-resource-limits"
echo "                     restrict-image-registries (staging + prod)"
echo "  Audit   (warns):   require-readonly-rootfs"
echo ""
echo "Switch require-readonly-rootfs to Enforce after adding emptyDir /tmp mounts."
