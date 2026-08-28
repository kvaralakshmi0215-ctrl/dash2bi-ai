from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import init_db
from app.api.routes import router

app = FastAPI(
    title="Dash2BI AI",
    description="Converts AI-generated HTML dashboards + Excel datasets into Power BI Projects (PBIP).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return {"status": "ok", "service": "dash2bi-ai-backend"}


@app.get("/health")
def health():
    return {"status": "healthy"}
