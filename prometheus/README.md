# Prometheus

This directory contains Helm values for deploying Prometheus with host-based ingress on:

- `prometheus.sevflow.app`

## Install

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install prometheus prometheus-community/prometheus \
  --namespace monitoring \
  -f prometheus/values.yaml
```

## DNS

Create a GoDaddy `CNAME`:

- `prometheus` -> your ingress ELB hostname
