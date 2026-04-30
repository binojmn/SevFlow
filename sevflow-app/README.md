# SevFlow App

Simple SevFlow microservice with:

- Python Flask app
- Dockerfile
- Helm chart
- Optional `ingress-nginx` Helm dependency

## Run locally

```bash
docker build -t sevflow-app:latest .
docker run -p 8080:8080 sevflow-app:latest
```

## Endpoints

- `/`
- `/health`
- `/api/severity`

## Helm chart

The Helm chart is under `helm/sevflow-app`.

Recommended storage model:

- Source Helm chart stays in this repo under `sevflow-app/helm/sevflow-app`
- CI packages the chart on every run
- Docker image is pushed to Amazon ECR
- Packaged Helm chart is pushed to Amazon ECR as an OCI chart on `push`
- You can later either:
  - keep deploying the chart source directly with Argo CD, or
  - deploy the packaged chart from Amazon ECR OCI

Example install:

```bash
helm dependency update helm/sevflow-app
helm upgrade --install sevflow-app helm/sevflow-app \
  --namespace sevflow \
  --create-namespace
```

The chart also supports configuring the Kubernetes deployment strategy. By default it uses a rolling update:

```yaml
deploymentStrategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0
    maxSurge: 1
```

If you need to recreate Pods instead of rolling them, set:

```yaml
deploymentStrategy:
  type: Recreate
```

For progressive delivery, the chart can also switch from a plain `Deployment` to an Argo Rollouts `Rollout`. Set:

```yaml
progressiveDelivery:
  enabled: true
  strategy: canary
```

or:

```yaml
progressiveDelivery:
  enabled: true
  strategy: blueGreen
```

When `canary` is enabled, the chart renders stable and canary Services and points the main Ingress at the stable Service so Argo Rollouts can manage traffic with nginx. When `blueGreen` is enabled, the chart renders active and preview Services, and you can optionally enable a preview Ingress for validation before promotion.

For canary mode, keep `ingress.enabled=true` because the chart uses nginx ingress traffic routing. You will also need the Argo Rollouts controller and CRDs installed in the cluster before applying the chart in progressive delivery mode.

To enable the bundled `ingress-nginx` dependency:

```bash
helm dependency update helm/sevflow-app
helm upgrade --install sevflow-app helm/sevflow-app \
  --namespace sevflow \
  --create-namespace \
  --set ingress-nginx.enabled=true
```

## CI

GitHub Actions workflow:

- `.github/workflows/sevflow-app-ci.yml`

The CI pipeline:

- installs Python dependencies
- runs unit tests
- builds the Docker image
- packages the Helm chart
- runs `helm dependency update`
- runs `helm lint`
- renders manifests with `helm template`
- pushes the Docker image to Amazon ECR on `push`
- pushes the packaged Helm chart to Amazon ECR OCI on `push`
- writes the immutable image tag (`github.sha`) back to `values-prod.yaml` on `push`

## GitHub Actions secrets

The workflow expects this GitHub secret:

- `AWS_GITHUB_ACTIONS_ROLE_ARN`: IAM role ARN that GitHub Actions can assume using OIDC

Default workflow settings:

- AWS region: `us-east-1`
- ECR repository: `sevflow-app`
- Helm OCI repository: `sevflow-app-chart`

If the ECR repositories do not exist yet, create them first:

```bash
aws ecr create-repository --repository-name sevflow-app --region us-east-1
aws ecr create-repository --repository-name sevflow-app-chart --region us-east-1
```

## Update image location for deployment

Set the chart image repository to your ECR image URL when deploying, for example:

```bash
helm upgrade --install sevflow-app helm/sevflow-app \
  --namespace sevflow \
  --create-namespace \
  --set image.repository=<account-id>.dkr.ecr.us-east-1.amazonaws.com/sevflow-app \
  --set image.tag=<image-tag>
```

If you want to pull the packaged chart from ECR OCI:

```bash
aws ecr get-login-password --region us-east-1 | \
helm registry login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

helm install sevflow-app \
  oci://<account-id>.dkr.ecr.us-east-1.amazonaws.com/sevflow-app-chart/sevflow-app \
  --version 0.1.0 \
  --namespace sevflow \
  --create-namespace \
  --set image.repository=<account-id>.dkr.ecr.us-east-1.amazonaws.com/sevflow-app \
  --set image.tag=<image-tag>
```

## Production values

Production-oriented Helm values are in:

- `helm/sevflow-app/values-prod.yaml`

The image tag in `values-prod.yaml` is intended to be updated by CI to an immutable commit SHA so Argo CD can detect a real manifest change and roll the deployment automatically.

Update these placeholders before deployment:

- `image.repository`
- `ingress.host` if you want host-based routing

Example:

```bash
helm upgrade --install sevflow-app helm/sevflow-app \
  --namespace sevflow \
  --create-namespace \
  -f helm/sevflow-app/values-prod.yaml \
  --set image.repository=<account-id>.dkr.ecr.us-east-1.amazonaws.com/sevflow-app \
  --set image.tag=<image-tag>
```

The current production values are configured for host-based routing using `app.sevflow.app`.

## Argo CD

Starter Argo CD application manifests:

- `../argo/sevflow-app-application.yaml`
- `../argo/sevflow-app-canary-application.yaml`
- `../argo/sevflow-app-bluegreen-application.yaml`

Before applying it, update:

- `repoURL`
- `targetRevision` if needed
- `image.repository`
- any hostname placeholders

The application manifest is already annotated for Argo CD Image Updater, so once Image Updater is installed and allowed to read ECR plus write back to Git, it can automatically move `image.tag` forward for you.

Apply with:

```bash
kubectl apply -f argo/sevflow-app-application.yaml
```
