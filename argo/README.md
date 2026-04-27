# Argo CD

This directory contains Helm values for deploying Argo CD with host-based ingress on:

- `argo.sevflow.app`

## Install

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install argocd argo/argo-cd \
  --namespace argocd \
  -f argo/values.yaml
```

## Initial admin password

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
echo
```

## DNS

Create a GoDaddy `CNAME`:

- `argo` -> your ingress ELB hostname
