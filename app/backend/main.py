import os
import jwt
import httpx
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

app = FastAPI(
    title="FinanceGuard API",
    description="Secure backend for Enterprise DevSecOps Capstone Project",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Pydantic Schemas
class TransactionBase(BaseModel):
    description: str = Field(..., example="AWS Invoice June 2026")
    amount: float = Field(..., example=1240.50)
    category: str = Field(..., example="Cloud Infrastructure")
    type: str = Field(..., example="expense")  # expense or income

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    id: int
    user_id: str

# In-memory database mock
MOCK_TRANSACTIONS = [
    {"id": 1, "user_id": "user_mock123", "description": "Consulting Fee", "amount": 5000.0, "category": "Revenue", "type": "income"},
    {"id": 2, "user_id": "user_mock123", "description": "GitHub Enterprise", "amount": -250.0, "category": "SaaS", "type": "expense"},
]
transaction_counter = 3

# Clerk configuration variables
CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL", "")
SKIP_AUTH_VERIFICATION = os.getenv("SKIP_AUTH_VERIFICATION", "true").lower() == "true"

# Fetch JWKS public keys from Clerk
jwks_keys = {}

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

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    
    if SKIP_AUTH_VERIFICATION:
        # Development bypass mode: Parse payload without validation
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return {"user_id": payload.get("sub", "user_mock123")}
        except Exception:
            return {"user_id": "user_mock123"}
            
    if not CLERK_JWKS_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Clerk JWKS URL is not configured."
        )
        
    try:
        # Parse headers to find the key ID (kid)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        # Locate matching key in JWKS
        jwk_key = next((key for key in jwks_keys if key.get("kid") == kid), None)
        if not jwk_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token key identifier."
            )
            
        # Construct public key and decode
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk_key)
        # Assuming Clerk uses standard JWT assertions
        payload = jwt.decode(token, public_key, algorithms=["RS256"])
        return {"user_id": payload.get("sub")}
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature has expired."
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )

# API Endpoints
@app.get("/health", tags=["Utilities"])
def health_check():
    return {"status": "healthy", "environment": os.getenv("ENVIRONMENT", "dev")}

@app.get("/api/v1/transactions", response_model=List[Transaction], tags=["Transactions"])
def list_transactions(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    return [t for t in MOCK_TRANSACTIONS if t["user_id"] == user_id or user_id == "user_mock123"]

@app.post("/api/v1/transactions", response_model=Transaction, status_code=status.HTTP_201_CREATED, tags=["Transactions"])
def create_transaction(transaction: TransactionCreate, current_user: dict = Depends(get_current_user)):
    global transaction_counter
    user_id = current_user["user_id"]
    
    new_tx = {
        "id": transaction_counter,
        "user_id": user_id,
        "description": transaction.description,
        "amount": transaction.amount,
        "category": transaction.category,
        "type": transaction.type
    }
    MOCK_TRANSACTIONS.append(new_tx)
    transaction_counter += 1
    return new_tx
