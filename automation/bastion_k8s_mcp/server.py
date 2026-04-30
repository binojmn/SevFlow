from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_PROTOCOL_VERSION = "2024-11-05"


class McpError(Exception):
    """Base server error with JSON-RPC metadata."""

    code = -32000

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigError(McpError):
    code = -32001


class ToolError(McpError):
    code = -32002


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def _read_json_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        header_line = line.decode("utf-8").strip()
        name, _, value = header_line.partition(":")
        headers[name.lower()] = value.strip()

    if "content-length" not in headers:
        raise McpError("Missing Content-Length header.")

    length = int(headers["content-length"])
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


def _write_json_message(payload: dict[str, Any]) -> None:
    body = _json_dumps(payload).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def _success_response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: Any, error: McpError) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": error.code, "message": error.message},
    }


def _tool_text_result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": False}


@dataclass
class BastionConfig:
    repo_root: Path
    host: str
    user: str = "ubuntu"
    port: int = 22
    ssh_bin: str = "ssh"
    ssh_key_path: str | None = None
    remote_kubectl_bin: str = "kubectl"
    remote_kubeconfig: str | None = None
    strict_host_key_checking: str = "accept-new"
    connect_timeout_seconds: int = 10

    @classmethod
    def load(cls, repo_root: Path) -> "BastionConfig":
        host = os.getenv("BASTION_HOST") or _infer_bastion_host(repo_root)
        if not host:
            raise ConfigError(
                "Missing bastion host. Set BASTION_HOST or make terraform/terraform.tfstate available with outputs.bastion_public_ip."
            )

        ssh_key_path = os.getenv("BASTION_SSH_KEY_PATH")
        default_key = repo_root / "terraform" / "bastion-key.pem"
        if not ssh_key_path and default_key.exists():
            ssh_key_path = str(default_key)

        remote_kubeconfig = os.getenv("REMOTE_KUBECONFIG")
        default_remote_kubeconfig = "~/kubeconfig"
        if not remote_kubeconfig:
            remote_kubeconfig = default_remote_kubeconfig

        return cls(
            repo_root=repo_root,
            host=host,
            user=os.getenv("BASTION_USER", "ubuntu"),
            port=int(os.getenv("BASTION_SSH_PORT", "22")),
            ssh_bin=os.getenv("SSH_BIN", "ssh"),
            ssh_key_path=ssh_key_path,
            remote_kubectl_bin=os.getenv("REMOTE_KUBECTL_BIN", "/usr/bin/kubectl"),
            remote_kubeconfig=remote_kubeconfig,
            strict_host_key_checking=os.getenv("STRICT_HOST_KEY_CHECKING", "accept-new"),
            connect_timeout_seconds=int(os.getenv("SSH_CONNECT_TIMEOUT_SECONDS", "10")),
        )

    def ssh_base_command(self) -> list[str]:
        command = [
            self.ssh_bin,
            "-o",
            "BatchMode=yes",
            "-o",
            f"StrictHostKeyChecking={self.strict_host_key_checking}",
            "-o",
            f"ConnectTimeout={self.connect_timeout_seconds}",
            "-p",
            str(self.port),
        ]
        if self.ssh_key_path:
            command.extend(["-i", self.ssh_key_path])
        command.append(f"{self.user}@{self.host}")
        return command


def _infer_bastion_host(repo_root: Path) -> str | None:
    state_path = repo_root / "terraform" / "terraform.tfstate"
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    outputs = data.get("outputs", {})
    bastion = outputs.get("bastion_public_ip", {})
    value = bastion.get("value")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def build_remote_command(config: BastionConfig, shell_command: str) -> list[str]:
    return [*config.ssh_base_command(), shell_command]


def resolve_remote_path(config: BastionConfig, remote_path: str) -> str:
    if remote_path == "~":
        return f"/home/{config.user}"
    if remote_path.startswith("~/"):
        return f"/home/{config.user}/{remote_path[2:]}"
    return remote_path


def build_kubectl_shell_command(config: BastionConfig, kubectl_args: list[str]) -> str:
    kubectl_bin = shlex.quote(config.remote_kubectl_bin)
    command = " ".join([kubectl_bin, *[shlex.quote(part) for part in kubectl_args]])
    if config.remote_kubeconfig:
        resolved_kubeconfig = resolve_remote_path(config, config.remote_kubeconfig)
        quoted_kubeconfig = shlex.quote(resolved_kubeconfig)
        return (
            f"if [ -r {quoted_kubeconfig} ]; then "
            f"KUBECONFIG={quoted_kubeconfig} {command}; "
            f"else {command}; fi"
        )
    return command


def run_remote_shell(config: BastionConfig, shell_command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        build_remote_command(config, shell_command),
        text=True,
        capture_output=True,
        check=False,
    )


def run_remote_kubectl_json(config: BastionConfig, kubectl_args: list[str]) -> dict[str, Any]:
    completed = run_remote_shell(config, build_kubectl_shell_command(config, kubectl_args))
    if completed.returncode != 0:
        raise ToolError(
            "Remote kubectl command failed:\n"
            f"command: {' '.join(kubectl_args)}\n"
            f"stderr: {completed.stderr.strip()}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ToolError(f"Remote kubectl did not return JSON: {exc}") from exc


def run_remote_kubectl_text(config: BastionConfig, kubectl_args: list[str]) -> str:
    completed = run_remote_shell(config, build_kubectl_shell_command(config, kubectl_args))
    if completed.returncode != 0:
        raise ToolError(
            "Remote kubectl command failed:\n"
            f"command: {' '.join(kubectl_args)}\n"
            f"stderr: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def summarize_nodes(nodes: dict[str, Any]) -> dict[str, Any]:
    total = 0
    ready = 0
    unhealthy: list[dict[str, str]] = []
    for item in nodes.get("items", []):
        total += 1
        name = item.get("metadata", {}).get("name", "unknown")
        conditions = item.get("status", {}).get("conditions", [])
        ready_condition = next((c for c in conditions if c.get("type") == "Ready"), None)
        if ready_condition and ready_condition.get("status") == "True":
            ready += 1
            continue
        unhealthy.append(
            {
                "name": name,
                "status": ready_condition.get("status", "Unknown") if ready_condition else "Unknown",
                "reason": ready_condition.get("reason", "NotReady") if ready_condition else "MissingReadyCondition",
            }
        )
    return {"total": total, "ready": ready, "unhealthy": unhealthy}


def pod_health_issues(pod: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    status = pod.get("status", {})
    phase = status.get("phase", "Unknown")
    if phase not in {"Running", "Succeeded"}:
        issues.append(f"phase={phase}")

    for container_status in status.get("containerStatuses", []) or []:
        name = container_status.get("name", "container")
        if not container_status.get("ready", False):
            state = container_status.get("state", {})
            if "waiting" in state:
                reason = state["waiting"].get("reason", "Waiting")
                issues.append(f"{name}:waiting:{reason}")
            elif "terminated" in state:
                reason = state["terminated"].get("reason", "Terminated")
                issues.append(f"{name}:terminated:{reason}")
            else:
                issues.append(f"{name}:not-ready")
        restart_count = int(container_status.get("restartCount", 0))
        if restart_count > 0:
            issues.append(f"{name}:restarts={restart_count}")

    return issues


def summarize_pods(pods: dict[str, Any]) -> dict[str, Any]:
    total = 0
    unhealthy: list[dict[str, Any]] = []
    for item in pods.get("items", []):
        total += 1
        issues = pod_health_issues(item)
        if not issues:
            continue
        metadata = item.get("metadata", {})
        unhealthy.append(
            {
                "namespace": metadata.get("namespace", "default"),
                "name": metadata.get("name", "unknown"),
                "issues": issues,
            }
        )
    return {"total": total, "unhealthy": unhealthy}


def summarize_deployments(deployments: dict[str, Any]) -> dict[str, Any]:
    total = 0
    degraded: list[dict[str, Any]] = []
    for item in deployments.get("items", []):
        total += 1
        metadata = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})
        desired = int(spec.get("replicas", 0))
        ready = int(status.get("readyReplicas", 0))
        available = int(status.get("availableReplicas", 0))
        unavailable = int(status.get("unavailableReplicas", 0))
        if ready >= desired and unavailable == 0:
            continue
        degraded.append(
            {
                "namespace": metadata.get("namespace", "default"),
                "name": metadata.get("name", "unknown"),
                "desired": desired,
                "ready": ready,
                "available": available,
                "unavailable": unavailable,
            }
        )
    return {"total": total, "degraded": degraded}


def summarize_services(services: dict[str, Any], endpoints: dict[str, Any]) -> dict[str, Any]:
    endpoint_map: dict[tuple[str, str], dict[str, Any]] = {}
    for item in endpoints.get("items", []):
        metadata = item.get("metadata", {})
        endpoint_map[(metadata.get("namespace", "default"), metadata.get("name", "unknown"))] = item

    total = 0
    missing_endpoints: list[dict[str, str]] = []
    for item in services.get("items", []):
        total += 1
        metadata = item.get("metadata", {})
        namespace = metadata.get("namespace", "default")
        name = metadata.get("name", "unknown")
        service_type = item.get("spec", {}).get("type", "ClusterIP")
        if service_type == "ExternalName":
            continue
        endpoint = endpoint_map.get((namespace, name), {})
        subsets = endpoint.get("subsets") or []
        has_addresses = any(subset.get("addresses") for subset in subsets)
        if not has_addresses:
            missing_endpoints.append({"namespace": namespace, "name": name})
    return {"total": total, "missingEndpoints": missing_endpoints}


def build_health_report(summary: dict[str, Any]) -> str:
    node_summary = summary["nodes"]
    pod_summary = summary["pods"]
    deployment_summary = summary["deployments"]
    service_summary = summary["services"]

    lines = [
        "Kubernetes health report",
        f"- Nodes ready: {node_summary['ready']}/{node_summary['total']}",
        f"- Unhealthy pods: {len(pod_summary['unhealthy'])}/{pod_summary['total']}",
        f"- Degraded deployments: {len(deployment_summary['degraded'])}/{deployment_summary['total']}",
        f"- Services without endpoints: {len(service_summary['missingEndpoints'])}/{service_summary['total']}",
    ]

    if node_summary["unhealthy"]:
        names = ", ".join(item["name"] for item in node_summary["unhealthy"][:5])
        lines.append(f"- Not ready nodes: {names}")
    if pod_summary["unhealthy"]:
        names = ", ".join(item["name"] for item in pod_summary["unhealthy"][:5])
        lines.append(f"- Problem pods: {names}")
    if deployment_summary["degraded"]:
        names = ", ".join(item["name"] for item in deployment_summary["degraded"][:5])
        lines.append(f"- Degraded deployments: {names}")
    if service_summary["missingEndpoints"]:
        names = ", ".join(item["name"] for item in service_summary["missingEndpoints"][:5])
        lines.append(f"- Services missing endpoints: {names}")

    lines.append("")
    lines.append(_json_dumps(summary))
    return "\n".join(lines)


def summarize_namespace_resources(resources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    replicasets = resources.get("replicasets", {}).get("items", [])
    return {
        "pods": len(resources.get("pods", {}).get("items", [])),
        "services": len(resources.get("services", {}).get("items", [])),
        "deployments": len(resources.get("deployments", {}).get("items", [])),
        "replicaSets": len(replicasets),
        "activeReplicaSets": sum(1 for item in replicasets if int(item.get("status", {}).get("replicas", 0) or 0) > 0),
        "ingresses": len(resources.get("ingresses", {}).get("items", [])),
        "configMaps": len(resources.get("configmaps", {}).get("items", [])),
        "secrets": len(resources.get("secrets", {}).get("items", [])),
        "serviceAccounts": len(resources.get("serviceaccounts", {}).get("items", [])),
        "persistentVolumeClaims": len(resources.get("persistentvolumeclaims", {}).get("items", [])),
        "horizontalPodAutoscalers": len(resources.get("hpas", {}).get("items", [])),
    }


def build_namespace_resource_report(namespace: str, resources: dict[str, dict[str, Any]]) -> str:
    summary = summarize_namespace_resources(resources)
    lines = [
        f"Namespace resource report: {namespace}",
        f"- Pods: {summary['pods']}",
        f"- Services: {summary['services']}",
        f"- Deployments: {summary['deployments']}",
        f"- ReplicaSets: {summary['replicaSets']} total ({summary['activeReplicaSets']} active)",
        f"- Ingresses: {summary['ingresses']}",
        f"- ConfigMaps: {summary['configMaps']}",
        f"- Secrets: {summary['secrets']}",
        f"- ServiceAccounts: {summary['serviceAccounts']}",
        f"- PVCs: {summary['persistentVolumeClaims']}",
        f"- HPAs: {summary['horizontalPodAutoscalers']}",
        "",
        _json_dumps(
            {
                "namespace": namespace,
                "summary": summary,
                "resources": resources,
            }
        ),
    ]
    return "\n".join(lines)


def summarize_replicaset_history(replicasets: dict[str, Any]) -> list[dict[str, Any]]:
    items = sorted(
        replicasets.get("items", []),
        key=lambda item: item.get("metadata", {}).get("creationTimestamp", ""),
    )
    history: list[dict[str, Any]] = []
    for item in items:
        metadata = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})
        container_specs = spec.get("template", {}).get("spec", {}).get("containers", []) or []
        history.append(
            {
                "name": metadata.get("name", "unknown"),
                "createdAt": metadata.get("creationTimestamp"),
                "revision": metadata.get("annotations", {}).get("deployment.kubernetes.io/revision"),
                "desired": int(spec.get("replicas", 0) or 0),
                "current": int(status.get("replicas", 0) or 0),
                "ready": int(status.get("readyReplicas", 0) or 0),
                "images": [container.get("image") for container in container_specs if container.get("image")],
            }
        )
    return history


def build_rollout_history_report(
    namespace: str,
    deployment_name: str,
    rollout_history: str,
    replicasets: dict[str, Any],
    deployment: dict[str, Any],
) -> str:
    metadata = deployment.get("metadata", {})
    spec = deployment.get("spec", {})
    container_specs = spec.get("template", {}).get("spec", {}).get("containers", []) or []
    history = summarize_replicaset_history(replicasets)
    active = next((item for item in reversed(history) if item["current"] > 0), None)
    payload = {
        "namespace": namespace,
        "deployment": deployment_name,
        "currentRevision": metadata.get("annotations", {}).get("deployment.kubernetes.io/revision"),
        "replicas": int(spec.get("replicas", 0) or 0),
        "strategy": spec.get("strategy", {}),
        "containers": [
            {
                "name": container.get("name"),
                "image": container.get("image"),
                "env": container.get("env", []),
                "ports": container.get("ports", []),
                "resources": container.get("resources", {}),
                "readinessProbe": container.get("readinessProbe"),
                "livenessProbe": container.get("livenessProbe"),
            }
            for container in container_specs
        ],
        "replicaSetHistory": history,
        "rolloutHistoryText": rollout_history,
    }
    lines = [
        f"Deployment rollout history: {deployment_name}",
        f"- Namespace: {namespace}",
        f"- Current revision: {payload['currentRevision']}",
        f"- Desired replicas: {payload['replicas']}",
        f"- Strategy: {spec.get('strategy', {}).get('type', 'Unknown')}",
    ]
    if active:
        active_images = ", ".join(active["images"]) if active["images"] else "unknown"
        lines.append(f"- Active ReplicaSet: {active['name']} ({active_images})")
    lines.extend(
        [
            "",
            rollout_history,
            "",
            _json_dumps(payload),
        ]
    )
    return "\n".join(lines)


def check_bastion_connectivity(config: BastionConfig) -> str:
    hostname_result = run_remote_shell(config, "hostname")
    if hostname_result.returncode != 0:
        raise ToolError(
            "Bastion connectivity check failed:\n"
            f"stderr: {hostname_result.stderr.strip()}"
        )

    whoami_result = run_remote_shell(config, "whoami")
    if whoami_result.returncode != 0:
        raise ToolError(
            "Bastion connectivity check failed when validating the remote user:\n"
            f"stderr: {whoami_result.stderr.strip()}"
        )

    kubectl_path = shlex.quote(config.remote_kubectl_bin)
    kubectl_check = run_remote_shell(config, f"test -x {kubectl_path} && printf %s {kubectl_path}")
    if kubectl_check.returncode != 0:
        raise ToolError(
            "Bastion connectivity check failed because kubectl is unavailable:\n"
            f"stderr: {kubectl_check.stderr.strip()}"
        )

    kubeconfig_result = None
    if config.remote_kubeconfig:
        kubeconfig_path = shlex.quote(config.remote_kubeconfig)
        kubeconfig_result = run_remote_shell(
            config,
            (
                f"if test -r {kubeconfig_path}; then "
                f"printf %s {kubeconfig_path}; "
                "elif test -r ~/.kube/config; then "
                "printf %s ~/.kube/config; "
                "fi"
            ),
        )
        if kubeconfig_result.returncode != 0 or not kubeconfig_result.stdout.strip():
            raise ToolError(
                "Bastion connectivity check failed because neither the configured kubeconfig nor ~/.kube/config is readable:\n"
                f"stderr: {kubeconfig_result.stderr.strip()}"
            )

    version_result = run_remote_shell(
        config,
        build_kubectl_shell_command(config, ["version", "--client", "--output=json"]),
    )
    if version_result.returncode != 0:
        raise ToolError(
            "Bastion connectivity check failed when running kubectl:\n"
            f"stderr: {version_result.stderr.strip()}"
        )

    lines = [
        f"hostname={hostname_result.stdout.strip()}",
        f"user={whoami_result.stdout.strip()}",
        f"kubectl={kubectl_check.stdout.strip()}",
    ]
    if kubeconfig_result is not None:
        lines.append(f"kubeconfig={kubeconfig_result.stdout.strip()}")
    lines.append(version_result.stdout.strip())
    return "\n".join(lines).strip()


def check_kubernetes_health(
    config: BastionConfig,
    namespace: str | None = None,
    all_namespaces: bool = False,
) -> str:
    namespace_args = ["-A"] if all_namespaces else ["-n", namespace or os.getenv("K8S_NAMESPACE", "sevflow")]
    nodes = run_remote_kubectl_json(config, ["get", "nodes", "-o", "json"])
    pods = run_remote_kubectl_json(config, ["get", "pods", *namespace_args, "-o", "json"])
    deployments = run_remote_kubectl_json(config, ["get", "deployments", *namespace_args, "-o", "json"])
    services = run_remote_kubectl_json(config, ["get", "services", *namespace_args, "-o", "json"])
    endpoints = run_remote_kubectl_json(config, ["get", "endpoints", *namespace_args, "-o", "json"])

    summary = {
        "scope": {"allNamespaces": all_namespaces, "namespace": None if all_namespaces else namespace_args[1]},
        "nodes": summarize_nodes(nodes),
        "pods": summarize_pods(pods),
        "deployments": summarize_deployments(deployments),
        "services": summarize_services(services, endpoints),
    }
    return build_health_report(summary)


def check_namespace_resources(config: BastionConfig, namespace: str | None = None) -> str:
    target_namespace = namespace or os.getenv("K8S_NAMESPACE", "sevflow")
    resources = {
        "pods": run_remote_kubectl_json(config, ["get", "pods", "-n", target_namespace, "-o", "json"]),
        "services": run_remote_kubectl_json(config, ["get", "services", "-n", target_namespace, "-o", "json"]),
        "deployments": run_remote_kubectl_json(config, ["get", "deployments", "-n", target_namespace, "-o", "json"]),
        "replicasets": run_remote_kubectl_json(config, ["get", "replicasets", "-n", target_namespace, "-o", "json"]),
        "ingresses": run_remote_kubectl_json(config, ["get", "ingress", "-n", target_namespace, "-o", "json"]),
        "configmaps": run_remote_kubectl_json(config, ["get", "configmaps", "-n", target_namespace, "-o", "json"]),
        "secrets": run_remote_kubectl_json(config, ["get", "secrets", "-n", target_namespace, "-o", "json"]),
        "serviceaccounts": run_remote_kubectl_json(config, ["get", "serviceaccounts", "-n", target_namespace, "-o", "json"]),
        "persistentvolumeclaims": run_remote_kubectl_json(config, ["get", "pvc", "-n", target_namespace, "-o", "json"]),
        "hpas": run_remote_kubectl_json(config, ["get", "hpa", "-n", target_namespace, "-o", "json"]),
    }
    return build_namespace_resource_report(target_namespace, resources)


def get_deployment_rollout_details(
    config: BastionConfig,
    deployment_name: str,
    namespace: str | None = None,
) -> str:
    target_namespace = namespace or os.getenv("K8S_NAMESPACE", "sevflow")
    rollout_history = run_remote_kubectl_text(
        config,
        ["rollout", "history", f"deployment/{deployment_name}", "-n", target_namespace],
    )
    deployment = run_remote_kubectl_json(
        config,
        ["get", "deployment", deployment_name, "-n", target_namespace, "-o", "json"],
    )
    selector = deployment.get("spec", {}).get("selector", {}).get("matchLabels", {})
    if not selector:
        raise ToolError(f"Deployment {deployment_name} does not have matchLabels to query ReplicaSets.")
    label_selector = ",".join(f"{key}={value}" for key, value in selector.items())
    replicasets = run_remote_kubectl_json(
        config,
        ["get", "replicasets", "-n", target_namespace, "-l", label_selector, "-o", "json"],
    )
    return build_rollout_history_report(target_namespace, deployment_name, rollout_history, replicasets, deployment)


class BastionK8sMcpServer:
    def __init__(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.config = BastionConfig.load(self.repo_root)
        self.protocol_version = DEFAULT_PROTOCOL_VERSION

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            client_version = params.get("protocolVersion")
            if isinstance(client_version, str) and client_version.strip():
                self.protocol_version = client_version
            return _success_response(
                request_id,
                {
                    "protocolVersion": self.protocol_version,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "bastion-k8s-health", "version": "0.1.0"},
                },
            )

        if method == "notifications/initialized":
            return None

        if method == "ping":
            return _success_response(request_id, {})

        if method == "tools/list":
            return _success_response(
                request_id,
                {
                    "tools": [
                        {
                            "name": "check_bastion_connectivity",
                            "description": "Verify SSH connectivity to the bastion host and confirm kubectl is installed there.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "additionalProperties": False,
                            },
                        },
                        {
                            "name": "check_kubernetes_health",
                            "description": "Connect through the bastion host and report Kubernetes node, pod, deployment, and service endpoint health.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "namespace": {"type": "string", "description": "Namespace to inspect. Defaults to sevflow."},
                                    "allNamespaces": {"type": "boolean", "description": "When true, checks all namespaces instead of a single namespace."},
                                },
                                "additionalProperties": False,
                            },
                        },
                        {
                            "name": "check_namespace_resources",
                            "description": "List common workload and supporting resources in a namespace, including pods, deployments, services, ingress, ReplicaSets, configmaps, secrets, service accounts, PVCs, and HPAs.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "namespace": {"type": "string", "description": "Namespace to inspect. Defaults to sevflow."},
                                },
                                "additionalProperties": False,
                            },
                        },
                        {
                            "name": "get_deployment_rollout_details",
                            "description": "Show rollout history and ReplicaSet/image revision details for a deployment in the target namespace.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "deploymentName": {"type": "string", "description": "Deployment name to inspect."},
                                    "namespace": {"type": "string", "description": "Namespace to inspect. Defaults to sevflow."},
                                },
                                "required": ["deploymentName"],
                                "additionalProperties": False,
                            },
                        },
                    ]
                },
            )

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            if name == "check_bastion_connectivity":
                return _success_response(request_id, _tool_text_result(check_bastion_connectivity(self.config)))
            if name == "check_kubernetes_health":
                namespace = arguments.get("namespace")
                all_namespaces = bool(arguments.get("allNamespaces", False))
                result = check_kubernetes_health(self.config, namespace=namespace, all_namespaces=all_namespaces)
                return _success_response(request_id, _tool_text_result(result))
            if name == "check_namespace_resources":
                namespace = arguments.get("namespace")
                result = check_namespace_resources(self.config, namespace=namespace)
                return _success_response(request_id, _tool_text_result(result))
            if name == "get_deployment_rollout_details":
                deployment_name = arguments.get("deploymentName")
                if not isinstance(deployment_name, str) or not deployment_name.strip():
                    return _error_response(request_id, ToolError("deploymentName is required."))
                namespace = arguments.get("namespace")
                result = get_deployment_rollout_details(self.config, deployment_name=deployment_name, namespace=namespace)
                return _success_response(request_id, _tool_text_result(result))
            return _error_response(request_id, ToolError(f"Unknown tool: {name}"))

        return _error_response(request_id, McpError(f"Unsupported method: {method}"))


def main() -> None:
    try:
        server = BastionK8sMcpServer()
    except McpError as error:
        _write_json_message(_error_response(None, error))
        return

    request: dict[str, Any] | None = None
    while True:
        try:
            request = _read_json_message()
            if request is None:
                break
            response = server.handle(request)
            if response is not None:
                _write_json_message(response)
        except McpError as error:
            request_id = request.get("id") if isinstance(request, dict) else None
            _write_json_message(_error_response(request_id, error))
        except Exception as error:  # pragma: no cover
            request_id = request.get("id") if isinstance(request, dict) else None
            _write_json_message(_error_response(request_id, McpError(str(error))))


if __name__ == "__main__":
    main()
