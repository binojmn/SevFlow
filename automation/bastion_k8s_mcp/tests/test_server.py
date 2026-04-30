from pathlib import Path
import unittest

from automation.bastion_k8s_mcp.server import (
    BastionConfig,
    build_health_report,
    build_kubectl_shell_command,
    build_namespace_resource_report,
    build_rollout_history_report,
    resolve_remote_path,
    summarize_deployments,
    summarize_namespace_resources,
    summarize_nodes,
    summarize_pods,
    summarize_replicaset_history,
    summarize_services,
)


class BastionK8sServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = BastionConfig(
            repo_root=Path(".").resolve(),
            host="1.2.3.4",
            user="ubuntu",
            ssh_key_path="/tmp/bastion.pem",
            remote_kubeconfig="~/kubeconfig",
            remote_kubectl_bin="/usr/bin/kubectl",
        )

    def test_build_kubectl_shell_command_includes_kubeconfig(self) -> None:
        command = build_kubectl_shell_command(self.config, ["get", "pods", "-n", "sevflow", "-o", "json"])
        self.assertIn("if [ -r /home/ubuntu/kubeconfig ]", command)
        self.assertIn("KUBECONFIG=/home/ubuntu/kubeconfig /usr/bin/kubectl get pods -n sevflow -o json", command)
        self.assertIn("else /usr/bin/kubectl get pods -n sevflow -o json; fi", command)

    def test_resolve_remote_path_expands_home(self) -> None:
        self.assertEqual(resolve_remote_path(self.config, "~/kubeconfig"), "/home/ubuntu/kubeconfig")
        self.assertEqual(resolve_remote_path(self.config, "~"), "/home/ubuntu")
        self.assertEqual(resolve_remote_path(self.config, "/etc/kubeconfig"), "/etc/kubeconfig")

    def test_summarize_nodes_marks_not_ready(self) -> None:
        summary = summarize_nodes(
            {
                "items": [
                    {"metadata": {"name": "node-1"}, "status": {"conditions": [{"type": "Ready", "status": "True"}]}},
                    {"metadata": {"name": "node-2"}, "status": {"conditions": [{"type": "Ready", "status": "False", "reason": "KubeletNotReady"}]}},
                ]
            }
        )
        self.assertEqual(summary["ready"], 1)
        self.assertEqual(summary["unhealthy"][0]["name"], "node-2")

    def test_summarize_pods_marks_waiting_and_restarts(self) -> None:
        summary = summarize_pods(
            {
                "items": [
                    {
                        "metadata": {"namespace": "sevflow", "name": "sevflow-app-abc"},
                        "status": {
                            "phase": "Running",
                            "containerStatuses": [
                                {
                                    "name": "app",
                                    "ready": False,
                                    "restartCount": 2,
                                    "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                                }
                            ],
                        },
                    }
                ]
            }
        )
        self.assertEqual(len(summary["unhealthy"]), 1)
        self.assertIn("app:waiting:CrashLoopBackOff", summary["unhealthy"][0]["issues"])
        self.assertIn("app:restarts=2", summary["unhealthy"][0]["issues"])

    def test_summarize_deployments_marks_degraded(self) -> None:
        summary = summarize_deployments(
            {
                "items": [
                    {
                        "metadata": {"namespace": "sevflow", "name": "sevflow-app"},
                        "spec": {"replicas": 3},
                        "status": {"readyReplicas": 2, "availableReplicas": 2, "unavailableReplicas": 1},
                    }
                ]
            }
        )
        self.assertEqual(len(summary["degraded"]), 1)
        self.assertEqual(summary["degraded"][0]["name"], "sevflow-app")

    def test_summarize_services_marks_missing_endpoints(self) -> None:
        summary = summarize_services(
            {
                "items": [
                    {"metadata": {"namespace": "sevflow", "name": "sevflow-app"}, "spec": {"type": "ClusterIP"}},
                    {"metadata": {"namespace": "sevflow", "name": "external"}, "spec": {"type": "ExternalName"}},
                ]
            },
            {"items": [{"metadata": {"namespace": "sevflow", "name": "sevflow-app"}, "subsets": []}]},
        )
        self.assertEqual(len(summary["missingEndpoints"]), 1)
        self.assertEqual(summary["missingEndpoints"][0]["name"], "sevflow-app")

    def test_build_health_report_contains_counts(self) -> None:
        report = build_health_report(
            {
                "nodes": {"ready": 2, "total": 3, "unhealthy": [{"name": "node-3"}]},
                "pods": {"total": 10, "unhealthy": [{"name": "bad-pod"}]},
                "deployments": {"total": 4, "degraded": [{"name": "sevflow-app"}]},
                "services": {"total": 3, "missingEndpoints": [{"name": "sevflow-app"}]},
            }
        )
        self.assertIn("Nodes ready: 2/3", report)
        self.assertIn("Problem pods: bad-pod", report)

    def test_summarize_namespace_resources_counts_objects(self) -> None:
        summary = summarize_namespace_resources(
            {
                "pods": {"items": [{}, {}]},
                "services": {"items": [{}]},
                "deployments": {"items": [{}]},
                "replicasets": {"items": [{"status": {"replicas": 1}}, {"status": {"replicas": 0}}]},
                "ingresses": {"items": [{}]},
                "configmaps": {"items": [{}, {}]},
                "secrets": {"items": [{}, {}, {}]},
                "serviceaccounts": {"items": [{}]},
                "persistentvolumeclaims": {"items": []},
                "hpas": {"items": []},
            }
        )
        self.assertEqual(summary["pods"], 2)
        self.assertEqual(summary["activeReplicaSets"], 1)
        self.assertEqual(summary["secrets"], 3)

    def test_summarize_replicaset_history_extracts_images(self) -> None:
        history = summarize_replicaset_history(
            {
                "items": [
                    {
                        "metadata": {
                            "name": "servflow-sevflow-app-abc",
                            "creationTimestamp": "2026-04-29T21:39:22Z",
                            "annotations": {"deployment.kubernetes.io/revision": "7"},
                        },
                        "spec": {
                            "replicas": 0,
                            "template": {"spec": {"containers": [{"image": "repo/app:tag1"}]}},
                        },
                        "status": {"replicas": 0, "readyReplicas": 0},
                    }
                ]
            }
        )
        self.assertEqual(history[0]["revision"], "7")
        self.assertEqual(history[0]["images"], ["repo/app:tag1"])

    def test_build_namespace_resource_report_contains_summary(self) -> None:
        report = build_namespace_resource_report(
            "sevflow",
            {
                "pods": {"items": [{}, {}]},
                "services": {"items": [{}]},
                "deployments": {"items": [{}]},
                "replicasets": {"items": []},
                "ingresses": {"items": [{}]},
                "configmaps": {"items": []},
                "secrets": {"items": [{}]},
                "serviceaccounts": {"items": [{}]},
                "persistentvolumeclaims": {"items": []},
                "hpas": {"items": []},
            },
        )
        self.assertIn("Namespace resource report: sevflow", report)
        self.assertIn('"pods":2', report)

    def test_build_rollout_history_report_contains_revision_and_active_rs(self) -> None:
        report = build_rollout_history_report(
            "sevflow",
            "servflow-sevflow-app",
            "REVISION  CHANGE-CAUSE\n7         <none>\n8         <none>",
            {
                "items": [
                    {
                        "metadata": {
                            "name": "servflow-sevflow-app-77f69974fd",
                            "creationTimestamp": "2026-04-29T21:44:44Z",
                            "annotations": {"deployment.kubernetes.io/revision": "8"},
                        },
                        "spec": {
                            "replicas": 2,
                            "template": {"spec": {"containers": [{"image": "repo/app:tag2"}]}},
                        },
                        "status": {"replicas": 2, "readyReplicas": 2},
                    }
                ]
            },
            {
                "metadata": {"annotations": {"deployment.kubernetes.io/revision": "8"}},
                "spec": {
                    "replicas": 2,
                    "strategy": {"type": "RollingUpdate"},
                    "template": {"spec": {"containers": [{"name": "app", "image": "repo/app:tag2"}]}},
                },
            },
        )
        self.assertIn("Current revision: 8", report)
        self.assertIn("Active ReplicaSet: servflow-sevflow-app-77f69974fd", report)


if __name__ == "__main__":
    unittest.main()
