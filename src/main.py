from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app

from src.api.routes import api, ui
from src.observability.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


app = FastAPI(title="근거 기반 아이디어 발굴 그래프", version="0.2.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="src/ui/static"), name="static")
app.mount("/metrics", make_asgi_app())
app.include_router(api)
app.include_router(ui)
