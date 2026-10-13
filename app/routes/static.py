from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path


def serve_static(app):
    """Mount static files and serve HTML pages."""
    static_dir = Path(__file__).parent.parent / "static"

    # Login page must be registered before the /static mount is fine either way;
    # keep HTML routes on the app, assets under /static.
    @app.get("/login")
    async def serve_login():
        return FileResponse(static_dir / "login.html")

    @app.get("/")
    async def serve_root():
        return FileResponse(static_dir / "index.html")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
