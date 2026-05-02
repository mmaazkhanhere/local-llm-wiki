from fastapi import FastAPI

from llm_wiki_backend.api.routes import router
from llm_wiki_backend.core.models import HealthResponse

app = FastAPI(title="Local LLM Wiki Backend", version="0.1.0")
app.include_router(router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse.ok(version=app.version)
