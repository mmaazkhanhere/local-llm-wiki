from fastapi import FastAPI

from llm_wiki_backend.api.router import api_router
from llm_wiki_backend.core.models import HealthResponse
from llm_wiki_backend.observability.events import EVENT_HUB
from llm_wiki_backend.observability.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
app = FastAPI(title="Local LLM Wiki Backend", version="0.1.0")
app.include_router(api_router)

@app.on_event("startup")
async def _startup() -> None:
    import asyncio

    EVENT_HUB.set_loop(asyncio.get_running_loop())
    logger.info("Backend startup complete")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    logger.debug("Health check")
    return HealthResponse.ok(version=app.version)
