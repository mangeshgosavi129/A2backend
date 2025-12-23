from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.database import engine, Base
from server.routes import router
from server.routes.prometheus import metrics_middleware
from sqlalchemy import inspect

# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(title="Task Management API")

origins = [
    "https://gsstask.vercel.app",
    "http://localhost:8001",
    "http://localhost:5050",
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],      # IMPORTANT – allows OPTIONS
    allow_headers=["*"],
)

# Register Prometheus middleware
app.middleware("http")(metrics_middleware)

# Include API Router
app.include_router(router)

# =========================================================
# AUTO-CREATE TABLES ON STARTUP
# =========================================================
@app.on_event("startup")
def init_database():
    print("🔄 Creating database tables if not exist...")
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    if not existing_tables:
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created")
    else:
        print("ℹ️ Tables already exist:", existing_tables)
