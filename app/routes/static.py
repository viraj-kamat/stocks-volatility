from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter()


def serve_static(app):
    """Mount static files and serve index.html for root path."""
    static_dir = Path(__file__).parent.parent / "static"

    # Serve static files
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def serve_root():
        index_path = static_dir / "index.html"
        return FileResponse(index_path)
