import os
import jwt
import httpx
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# For local testing without DB
# from sqlalchemy import create_engine
# from sqlalchemy.orm import Session, sessionmaker
# from database import Base, get_db
# from models import TransactionModel
# from schemas import Transaction, TransactionCreate

app = FastAPI(
    title="FinanceGuard API",
    description="Secure backend for Enterprise DevSecOps Capstone Project",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Clerk config
CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL", "")
SKIP_AUTH_VERIFICATION = os.getenv("SKIP_AUTH_VERIFICATION", "true").lower() == "true"

jwks_keys = []

async def fetch_jwks():
    global jwks_keys
    if not CLERK_JWKS_URL:
        return
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(CLERK_JWKS_URL)
            if response.status_code == 200:
                jwks_keys = response.json().get("keys", [])
    except Exception as e:
        print(f"Error fetching JWKS keys: {e}")

@app.on_event("startup")
async def startup_event():
    await fetch_jwks()
    print("Backend started successfully (Database connection skipped for local testing)")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    if SKIP_AUTH_VERIFICATION:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return {"user_id": payload.get("sub", "user_mock123")}
        except:
            return {"user_id": "user_mock123"}
    raise HTTPException(status_code=501, detail="Full JWT verification not implemented in this update")

# Health Check
@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Backend is running (DB skipped for local testing)"}

# TODO: Re-enable these when DB is ready
# @app.get("/api/v1/transactions", response_model=List[Transaction])
# def list_transactions(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
#     user_id = current_user["user_id"]
#     return db.query(TransactionModel).filter(TransactionModel.user_id == user_id).all()

# @app.post("/api/v1/transactions", response_model=Transaction, status_code=201)
# def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
#     db_tx = TransactionModel(
#         user_id=current_user["user_id"],
#         description=transaction.description,
#         amount=transaction.amount,
#         category=transaction.category,
#         type=transaction.type
#     )
#     db.add(db_tx)
#     db.commit()
#     db.refresh(db_tx)
#     return db_tx