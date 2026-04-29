# Argo CD And Argo Rollouts

This directory contains:

- Helm values for deploying Argo CD with host-based ingress on `argo.sevflow.app`
- Helm values for deploying Argo Rollouts with dashboard ingress on `argo-rollouts.sevflow.app`
- Argo CD `Application` manifests for SevFlow in rolling, canary, and blue/green modes

## Install Argo CD

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install argocd argo/argo-cd \
  --namespace argocd \
  -f argo/values.yaml
```

## Install Argo Rollouts

Apply the Argo CD application:

```bash
kubectl apply -f argo/argo-rollouts-application.yaml
```

Or install the chart directly:

```bash
kubectl create namespace argo-rollouts --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install argo-rollouts argo/argo-rollouts \
  --namespace argo-rollouts \
  -f argo/argo-rollouts-values.yaml
```

## Initial admin password

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
echo
```

## SevFlow Applications

Apply one of these, depending on the deployment style you want:

```bash
kubectl apply -f argo/sevflow-app-application.yaml
kubectl apply -f argo/sevflow-app-canary-application.yaml
kubectl apply -f argo/sevflow-app-bluegreen-application.yaml
```

Before applying them, update:

- `repoURL`
- `targetRevision`
- any placeholder hostnames if needed

The application manifests map to these Helm values:

- `sevflow-app-application.yaml`: `values-prod.yaml`
- `sevflow-app-canary-application.yaml`: `values-prod.yaml` + `values-canary.yaml`
- `sevflow-app-bluegreen-application.yaml`: `values-prod.yaml` + `values-bluegreen.yaml`

## DNS

Create a GoDaddy `CNAME`:

- `argo` -> your ingress ELB hostname
- `argo-rollouts` -> your ingress ELB hostname
