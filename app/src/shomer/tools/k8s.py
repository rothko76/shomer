"""Read-only Kubernetes tools (ported from rothko76/ai-ops-agent@3958ec6, mutating tools removed).

Only list_*/read_* API calls are allowed in this module; tests/test_readonly.py enforces it, and
the chart's RBAC grants get/list/watch only.
"""

from functools import cache
from typing import Annotated, Any

import structlog
from kubernetes import client as k8s_client
from kubernetes import config
from kubernetes.client.exceptions import ApiException
from pydantic import Field
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from shomer.config import get_settings
from shomer.tools.registry import tool

log = structlog.get_logger(__name__)

RETRYABLE_STATUS = {0, 408, 429, 500, 502, 503, 504}
Namespace = Annotated[str, Field(description="Kubernetes namespace", min_length=1)]
Limit = Annotated[int, Field(ge=1, le=200)]


def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, ApiException) and exc.status in RETRYABLE_STATUS


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(multiplier=0.5, max=8),
    retry=retry_if_exception(_retryable),
    reraise=True,
)
def _call(func: Any, *args: Any, **kwargs: Any) -> Any:
    return func(*args, **kwargs)


@cache
def _load_config() -> None:
    try:
        config.load_incluster_config()  # type: ignore[no-untyped-call]
    except config.ConfigException:
        config.load_kube_config(context=get_settings().kube_context)  # type: ignore[no-untyped-call]


def core() -> Any:
    _load_config()
    return k8s_client.CoreV1Api()


def apps() -> Any:
    _load_config()
    return k8s_client.AppsV1Api()


def autoscaling() -> Any:
    _load_config()
    return k8s_client.AutoscalingV2Api()


def custom() -> Any:
    _load_config()
    return k8s_client.CustomObjectsApi()


def _err(action: str, err: ApiException) -> dict[str, Any]:
    return {"error": f"{action}: {err.status} {err.reason}"}


def _event_ts(event: Any) -> str:
    return str(event.last_timestamp or event.event_time or event.first_timestamp or "")


@tool
def list_namespaces() -> list[str] | dict[str, Any]:
    """List all namespaces in the cluster."""
    try:
        return [ns.metadata.name for ns in _call(core().list_namespace).items]
    except ApiException as err:
        return _err("list namespaces", err)


@tool
def get_pods(namespace: Namespace) -> list[dict[str, Any]] | dict[str, Any]:
    """List pods in a namespace with phase, restart count and node."""
    try:
        pods = _call(core().list_namespaced_pod, namespace=namespace).items
    except ApiException as err:
        return _err("list pods", err)
    return [
        {
            "name": p.metadata.name,
            "phase": p.status.phase,
            "restarts": sum(cs.restart_count or 0 for cs in p.status.container_statuses or []),
            "node": p.spec.node_name,
        }
        for p in pods
    ]


@tool
def get_failed_pods(namespace: Namespace) -> list[dict[str, Any]] | dict[str, Any]:
    """List unhealthy pods (Failed/Pending/Unknown, waiting containers, or restarts), worst first.

    Waiting reasons include CrashLoopBackOff, ImagePullBackOff, CreateContainerConfigError.
    """
    try:
        pods = _call(core().list_namespaced_pod, namespace=namespace).items
    except ApiException as err:
        return _err("list pods", err)
    failed: list[dict[str, Any]] = []
    for p in pods:
        statuses = p.status.container_statuses or []
        phase = p.status.phase or "Unknown"
        restarts = sum(cs.restart_count or 0 for cs in statuses)
        waiting = [
            {"container": cs.name, "reason": cs.state.waiting.reason, "message": cs.state.waiting.message}
            for cs in statuses
            if cs.state and cs.state.waiting and cs.state.waiting.reason
        ]
        if phase in {"Failed", "Unknown", "Pending"} or waiting or restarts > 0:
            failed.append(
                {
                    "name": p.metadata.name,
                    "phase": phase,
                    "node": p.spec.node_name,
                    "restarts": restarts,
                    "waiting": waiting,
                }
            )
    failed.sort(key=lambda item: item["restarts"], reverse=True)
    return failed


@tool
def get_events(
    namespace: Namespace,
    involved_object: Annotated[str | None, Field(description="Only events for this object name")] = None,
    warnings_only: bool = True,
    limit: Limit = 50,
) -> list[dict[str, Any]] | dict[str, Any]:
    """List recent events in a namespace, newest first. Optionally filter to one object."""
    selector = f"involvedObject.name={involved_object}" if involved_object else ""
    try:
        events = _call(core().list_namespaced_event, namespace=namespace, field_selector=selector).items
    except ApiException as err:
        return _err("list events", err)
    rows = [
        {
            "type": e.type,
            "reason": e.reason,
            "object": f"{e.involved_object.kind}/{e.involved_object.name}",
            "message": e.message,
            "count": e.count,
            "last_seen": _event_ts(e),
        }
        for e in events
        if not warnings_only or e.type == "Warning"
    ]
    rows.sort(key=lambda r: r["last_seen"], reverse=True)
    return rows[:limit]


@tool
def describe_pod(namespace: Namespace, pod_name: str) -> dict[str, Any]:
    """Pod details: phase, conditions, and per-container state, restarts and image."""
    try:
        p = _call(core().read_namespaced_pod, name=pod_name, namespace=namespace)
    except ApiException as err:
        return _err(f"read pod {pod_name}", err)
    return {
        "name": p.metadata.name,
        "namespace": p.metadata.namespace,
        "phase": p.status.phase,
        "node": p.spec.node_name,
        "start_time": str(p.status.start_time),
        "labels": p.metadata.labels or {},
        "owner": [f"{o.kind}/{o.name}" for o in p.metadata.owner_references or []],
        "conditions": [
            {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
            for c in p.status.conditions or []
        ],
        "containers": [
            {
                "name": c.name,
                "image": c.image,
                "ready": c.ready,
                "restarts": c.restart_count,
                "state": c.state.to_dict() if c.state else {},
                "last_state": c.last_state.to_dict() if c.last_state else {},
            }
            for c in p.status.container_statuses or []
        ],
        "resources": {c.name: c.resources.to_dict() if c.resources else {} for c in p.spec.containers or []},
    }


@tool
def get_pod_logs(
    namespace: Namespace,
    pod_name: str,
    container: str | None = None,
    previous: Annotated[bool, Field(description="Logs of the previous (crashed) container")] = False,
    tail: Annotated[int, Field(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    """Tail a pod's logs. Use previous=true for a container in CrashLoopBackOff."""
    try:
        logs = _call(
            core().read_namespaced_pod_log,
            name=pod_name,
            namespace=namespace,
            container=container,
            previous=previous,
            tail_lines=tail,
        )
    except ApiException as err:
        return _err(f"read logs of {pod_name}", err)
    return {"pod": pod_name, "container": container, "previous": previous, "logs": logs}


@tool
def get_deployments_status(namespace: Namespace) -> list[dict[str, Any]] | dict[str, Any]:
    """Desired vs ready/available/updated replicas for each deployment in a namespace."""
    try:
        deployments = _call(apps().list_namespaced_deployment, namespace=namespace).items
    except ApiException as err:
        return _err("list deployments", err)
    return [
        {
            "name": d.metadata.name,
            "desired": d.spec.replicas,
            "ready": d.status.ready_replicas or 0,
            "available": d.status.available_replicas or 0,
            "updated": d.status.updated_replicas or 0,
            "unavailable": d.status.unavailable_replicas or 0,
            "conditions": [
                {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
                for c in d.status.conditions or []
            ],
        }
        for d in deployments
    ]


def _images(pod_spec: Any) -> dict[str, list[dict[str, str]]]:
    return {
        "containers": [{"name": c.name, "image": c.image} for c in pod_spec.containers or []],
        "init_containers": [{"name": c.name, "image": c.image} for c in pod_spec.init_containers or []],
    }


@tool
def get_deployment_images(namespace: Namespace, name: str) -> dict[str, Any]:
    """Container images and imagePullSecrets configured on a deployment."""
    try:
        d = _call(apps().read_namespaced_deployment, name=name, namespace=namespace)
    except ApiException as err:
        return _err(f"read deployment {name}", err)
    spec = d.spec.template.spec
    return {
        "name": d.metadata.name,
        "images": _images(spec),
        "image_pull_secrets": [s.name for s in spec.image_pull_secrets or []],
    }


@tool
def get_rollout_history(namespace: Namespace, name: str, limit: Limit = 5) -> dict[str, Any]:
    """Deployment revisions (newest first) with their images. Useful for 'what changed?'."""
    try:
        d = _call(apps().read_namespaced_deployment, name=name, namespace=namespace)
        labels = d.spec.selector.match_labels or {}
        selector = ",".join(f"{k}={v}" for k, v in labels.items())
        replica_sets = _call(
            apps().list_namespaced_replica_set, namespace=namespace, label_selector=selector
        ).items
    except ApiException as err:
        return _err(f"read rollout history of {name}", err)
    history = []
    for rs in replica_sets:
        if not any(o.kind == "Deployment" and o.name == name for o in rs.metadata.owner_references or []):
            continue
        revision = (rs.metadata.annotations or {}).get("deployment.kubernetes.io/revision", "0")
        history.append(
            {
                "revision": int(revision) if revision.isdigit() else 0,
                "replicaset": rs.metadata.name,
                "created_at": str(rs.metadata.creation_timestamp),
                "replicas": rs.spec.replicas or 0,
                "ready": rs.status.ready_replicas or 0,
                "images": _images(rs.spec.template.spec),
            }
        )
    history.sort(key=lambda h: h["revision"], reverse=True)
    return {
        "name": name,
        "current_revision": (d.metadata.annotations or {}).get("deployment.kubernetes.io/revision"),
        "history": history[:limit],
    }


@tool
def get_nodes_status() -> list[dict[str, Any]] | dict[str, Any]:
    """Node readiness, pressure conditions, kubelet version and allocatable resources."""
    try:
        nodes = _call(core().list_node).items
    except ApiException as err:
        return _err("list nodes", err)
    rows = []
    for n in nodes:
        conditions = {c.type: c for c in n.status.conditions or []}
        ready = conditions.get("Ready")
        rows.append(
            {
                "name": n.metadata.name,
                "ready": ready.status if ready else "Unknown",
                "ready_reason": ready.reason if ready else None,
                "pressure": [t for t, c in conditions.items() if t != "Ready" and c.status == "True"],
                "unschedulable": bool(n.spec.unschedulable),
                "taints": [f"{t.key}={t.value}:{t.effect}" for t in n.spec.taints or []],
                "kubelet_version": n.status.node_info.kubelet_version,
                "allocatable": n.status.allocatable or {},
            }
        )
    return rows


@tool
def get_resource_usage(namespace: Namespace) -> list[dict[str, Any]] | dict[str, Any]:
    """Current CPU/memory usage per pod container (needs metrics-server)."""
    try:
        resp = _call(
            custom().list_namespaced_custom_object,
            group="metrics.k8s.io",
            version="v1beta1",
            namespace=namespace,
            plural="pods",
        )
    except ApiException as err:
        return {"error": f"pod metrics unavailable (is metrics-server installed?): {err.status} {err.reason}"}
    return [
        {
            "pod": item["metadata"]["name"],
            "containers": [
                {"name": c["name"], "cpu": c["usage"].get("cpu"), "memory": c["usage"].get("memory")}
                for c in item.get("containers", [])
            ],
        }
        for item in resp.get("items", [])
    ]


@tool
def get_hpa_status(namespace: Namespace) -> list[dict[str, Any]] | dict[str, Any]:
    """HorizontalPodAutoscalers: target, min/max/current/desired replicas and current metrics."""
    try:
        hpas = _call(autoscaling().list_namespaced_horizontal_pod_autoscaler, namespace=namespace).items
    except ApiException as err:
        return _err("list HPAs", err)
    return [
        {
            "name": h.metadata.name,
            "target": f"{h.spec.scale_target_ref.kind}/{h.spec.scale_target_ref.name}",
            "min": h.spec.min_replicas,
            "max": h.spec.max_replicas,
            "current": h.status.current_replicas,
            "desired": h.status.desired_replicas,
            "metrics": [m.to_dict() for m in h.status.current_metrics or []],
        }
        for h in hpas
    ]
