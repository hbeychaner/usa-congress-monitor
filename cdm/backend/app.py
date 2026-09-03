from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cdm.backend.api.router import api_router

app = FastAPI(
    title="Congress Tracker API",
    description="Backend APIs for state/member timelines and profiles.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
