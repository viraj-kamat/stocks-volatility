"""Tail Docker container logs (whitelist only; nothing persisted)."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])

# Logical UI ids → label + compose service name (for flexible lookup)
ALLOWED_CONTAINERS = {
    "stocks-dashboard": {"label": "App", "service": "stocks-dashboard"},
    "stocks-mysql": {"label": "MySQL", "service": "mysql"},
    "stocks-redis": {"label": "Redis", "service": "redis"},
}

DEFAULT_CONTAINER = "stocks-dashboard"


@router.get("/containers")
def list_log_containers():
    return {
        "default": DEFAULT_CONTAINER,
        "containers": [
            {"id": cid, "label": meta["label"]}
            for cid, meta in ALLOWED_CONTAINERS.items()
        ],
    }


def _name_matches(logical_id: str, service: str, name: str) -> bool:
    """Match compose container_name, service, or broken recreate prefixes."""
    if name in (logical_id, service):
        return True
    if logical_id in name:
        return True
    if f"stocks-{service}" in name:
        return True
    for suffix in (f"_{logical_id}", f"-{logical_id}", f"_{service}_1", f"-{service}-1", f"_{service}", f"-{service}"):
        if name.endswith(suffix):
            return True
    return False


def _find_container(client, logical_id: str):
    """Resolve whitelist id to a running/stopped container by name or compose label."""
    import docker

    meta = ALLOWED_CONTAINERS[logical_id]
    service = meta["service"]

    try:
        return client.containers.get(logical_id)
    except docker.errors.NotFound:
        pass

    for container in client.containers.list(all=True):
        labels = container.labels or {}
        if labels.get("com.docker.compose.service") == service:
            return container

        name = (container.name or "").lstrip("/")
        if _name_matches(logical_id, service, name):
            return container

    return None


@router.get("/{container_id}")
def tail_container_logs(
    container_id: str,
    tail: int = Query(200, ge=1, le=2000),
):
    if container_id not in ALLOWED_CONTAINERS:
        raise HTTPException(status_code=400, detail="Container not allowed")

    try:
        import docker
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail="Docker SDK not installed in the app image",
        ) from e

    client = None
    try:
        client = docker.DockerClient(base_url="unix://var/run/docker.sock")
        container = _find_container(client, container_id)
        if container is None:
            raise HTTPException(
                status_code=404,
                detail=f"Container for {container_id} not found (is it running?)",
            )

        raw = container.logs(tail=tail, timestamps=True, stdout=True, stderr=True)
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        else:
            text = str(raw)
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        return {
            "container": container_id,
            "resolved_name": (container.name or "").lstrip("/"),
            "label": ALLOWED_CONTAINERS[container_id]["label"],
            "status": container.status,
            "lines": lines,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to read logs for %s", container_id)
        raise HTTPException(
            status_code=503,
            detail=f"Cannot read Docker logs (is /var/run/docker.sock mounted?): {e}",
        ) from e
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
