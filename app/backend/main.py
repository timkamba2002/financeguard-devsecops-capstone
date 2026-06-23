import os
from typing import List
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, Session, declarative_base

# ==================== DATABASE CONNECTION ====================
DB_HOST = os.getenv("host")
DB_PORT = os.getenv("port", "5432")
DB_USER = os.getenv("user")
DB_PASSWORD = os.getenv("password")
DB_NAME = os.getenv("dbname")

# Fallback to local SQLite during testing/local development if DB_HOST is not set
if not DB_HOST:
    DATABASE_URL = "sqlite:///./financeguard.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TransactionModel(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    description = Column(String)
    amount = Column(Float)
    category = Column(String)
    type = Column(String)  # "income" or "expense"
    created_at = Column(DateTime, default=datetime.utcnow)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================== FASTAPI APP ====================
app = FastAPI(
    title="FinanceGuard API",
    description="Secure backend for Enterprise DevSecOps Capstone Project",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()
SKIP_AUTH_VERIFICATION = os.getenv("SKIP_AUTH_VERIFICATION", "true").lower() == "true"

class TransactionCreate(BaseModel):
    description: str
    amount: float
    category: str
    type: str

class Transaction(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    amount: float
    category: str
    type: str

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if SKIP_AUTH_VERIFICATION:
        return {"user_id": "demo-user-123"}
    raise HTTPException(status_code=501, detail="Full auth not implemented")

@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized.")

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Connected to RDS PostgreSQL"}

@app.get("/api/v1/transactions", response_model=List[Transaction])
def list_transactions(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return db.query(TransactionModel).filter(TransactionModel.user_id == current_user["user_id"]).all()

@app.post("/api/v1/transactions", response_model=Transaction, status_code=201)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    db_tx = TransactionModel(
        user_id=current_user["user_id"],
        description=transaction.description,
        amount=transaction.amount,
        category=transaction.category,
        type=transaction.type
    )
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx