# Grafana

This directory contains Helm values for deploying Grafana with host-based ingress on:

- `grafana.sevflow.app`

## Install

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install grafana grafana/grafana \
  --namespace monitoring \
  -f grafana/values.yaml
```

## DNS

Create a GoDaddy `CNAME`:

- `grafana` -> your ingress ELB hostname

## Dashboard

Import the dashboard JSON at:

- `grafana/dashboards/sevflow-observability-dashboard.json`

It expects the Prometheus datasource to be named `Prometheus`, which matches the existing kube-prometheus-stack values in this repo.
