"""Tail Docker container logs (whitelist only; nothing persisted)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])

# Only these containers may be tailed from the UI
ALLOWED_CONTAINERS = {
    "stocks-dashboard": "App",
    "stocks-mysql": "MySQL",
    "stocks-redis": "Redis",
}

DEFAULT_CONTAINER = "stocks-dashboard"


@router.get("/containers")
def list_log_containers():
    return {
        "default": DEFAULT_CONTAINER,
        "containers": [
            {"id": cid, "label": label}
            for cid, label in ALLOWED_CONTAINERS.items()
        ],
    }


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
        container = client.containers.get(container_id)
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
            "label": ALLOWED_CONTAINERS[container_id],
            "status": container.status,
            "lines": lines,
        }
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
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
