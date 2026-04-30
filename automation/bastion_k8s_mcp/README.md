# Bastion Kubernetes MCP Server

This MCP server connects to your bastion host over SSH, runs read-only `kubectl` health checks on the remote side, and returns a concise report through the Model Context Protocol over stdio.

## What it exposes

- `check_bastion_connectivity`
  - verifies SSH access
  - confirms `kubectl` exists on the bastion
- `check_kubernetes_health`
  - checks node readiness
  - checks pod health
  - checks deployment readiness
  - checks Services that have no backing endpoints
- `check_namespace_resources`
  - lists common namespace resources such as pods, deployments, services, ingress, ReplicaSets, configmaps, secrets, service accounts, PVCs, and HPAs
- `get_deployment_rollout_details`
  - shows deployment rollout history
  - summarizes ReplicaSet revisions and container image history
  - includes the current deployment pod template details

## Runtime requirements

- Python 3.11+
- local `ssh` client available on `PATH`
- bastion host reachable from the machine running the MCP server
- `kubectl` installed on the bastion host
- bastion host able to access the target Kubernetes cluster

## Configuration

Environment variables:

- `BASTION_HOST`
  - optional if `terraform/terraform.tfstate` exists and contains `outputs.bastion_public_ip.value`
- `BASTION_USER`
  - default: `ubuntu`
- `BASTION_SSH_PORT`
  - default: `22`
- `BASTION_SSH_KEY_PATH`
  - optional
  - defaults to `terraform/bastion-key.pem` if present
- `SSH_BIN`
  - default: `ssh`
- `STRICT_HOST_KEY_CHECKING`
  - default: `accept-new`
- `SSH_CONNECT_TIMEOUT_SECONDS`
  - default: `10`
- `REMOTE_KUBECTL_BIN`
  - default: `/usr/bin/kubectl`
- `REMOTE_KUBECONFIG`
  - default: `~/kubeconfig`
- `K8S_NAMESPACE`
  - default: `sevflow`

## Run locally

```bash
python automation/bastion_k8s_mcp/server.py
```

## Codex MCP config example

Add a server entry that launches the script over stdio. Example shape:

```toml
[mcp_servers.bastion_k8s_health]
command = "C:\\Users\\binoj\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe"
args = ["C:\\Binoj\\ci-cd-demoapp\\SevFlow\\automation\\bastion_k8s_mcp\\server.py"]

[mcp_servers.bastion_k8s_health.env]
BASTION_HOST = "1.2.3.4"
BASTION_USER = "ubuntu"
BASTION_SSH_KEY_PATH = "C:\\Binoj\\ci-cd-demoapp\\SevFlow\\terraform\\bastion-key.pem"
REMOTE_KUBECONFIG = "~/kubeconfig"
REMOTE_KUBECTL_BIN = "/usr/bin/kubectl"
K8S_NAMESPACE = "sevflow"
```

## Notes

- The server intentionally runs read-only checks only.
- It uses direct remote `kubectl` commands over SSH and summarizes JSON responses locally.
- The connectivity check validates the remote user, `kubectl` path, kubeconfig readability, and `kubectl version --client`.
- The default remote command path assumes `kubectl` is installed at `/usr/bin/kubectl` on the bastion.
- If your bastion uses another kubeconfig path or a different kubectl location, set `REMOTE_KUBECONFIG` or `REMOTE_KUBECTL_BIN`.
