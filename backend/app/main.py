import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.routers import analytics, auth, bills, dashboard, debts, goals, networth, planning, recurring, transactions

log = logging.getLogger("app")

app = FastAPI(title="Smart Expense Tracker API", version="0.1.0",
              description="Track less. Understand more. Save smarter.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
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


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
