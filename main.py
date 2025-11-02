from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routers import auth, wallets, categories, transactions, analytics, budgets, recurring_transactions, exports, receipts, tags, currency, notifications, profile
from pathlib import Path

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SpendWise API",
    description="Finance Management Application API",
    version="1.0.0",
    redirect_slashes=False  # Prevent redirect issues with CORS
)

# CORS configuration
# IMPORTANT: Order matters - CORS middleware must be added before routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "https://spendwise.on-forge.com",  # Production frontend
        "https://www.spendwise.on-forge.com",  # With www if needed
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],  # Explicit methods
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(profile.router, prefix="/api/profile", tags=["Profile"])
app.include_router(wallets.router, prefix="/api/wallets", tags=["Wallets"])
app.include_router(categories.router, prefix="/api/categories", tags=["Categories"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(budgets.router, prefix="/api/budgets", tags=["Budgets"])
app.include_router(recurring_transactions.router, prefix="/api/recurring", tags=["Recurring Transactions"])
app.include_router(exports.router, prefix="/api/exports", tags=["Exports"])
app.include_router(receipts.router, prefix="/api/receipts", tags=["Receipts"])
app.include_router(tags.router, prefix="/api/tags", tags=["Tags"])
app.include_router(currency.router, prefix="/api/currency", tags=["Currency"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])

# Mount static files for avatars
avatars_dir = Path("uploads/avatars")
avatars_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads/avatars", StaticFiles(directory=str(avatars_dir)), name="avatars")

@app.get("/")
async def root():
    return {"message": "Welcome to SpendWise API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


