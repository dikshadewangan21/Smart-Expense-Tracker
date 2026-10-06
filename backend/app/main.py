import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.routers import (
    analytics, auth, bills, coach, dashboard, debts, goals,
    imports, networth, notifications, planning, privacy, receipts,
    recurring, shared, transactions
)

log = logging.getLogger("app")

app = FastAPI(title="Smart Expense Tracker API", version="0.1.0",
              description="Track less. Understand more. Save smarter.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(planning.router, prefix="/api")
app.include_router(recurring.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(bills.router, prefix="/api")
app.include_router(goals.router, prefix="/api")
app.include_router(debts.router, prefix="/api")
app.include_router(networth.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(receipts.router, prefix="/api")
app.include_router(coach.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(shared.router, prefix="/api")
app.include_router(privacy.router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
