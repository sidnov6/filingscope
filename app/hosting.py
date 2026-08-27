from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.main import create_app


def create_hosted_app() -> FastAPI:
    """Serve API routes and the exported workstation from one Hugging Face port."""

    application = create_app()
    ui_dir = Path(os.environ.get("FILINGSCOPE_UI_DIR", "ui/out"))
    application.mount(
        "/",
        StaticFiles(directory=ui_dir, html=True, check_dir=False),
        name="workstation",
    )
    return application


app = create_hosted_app()
