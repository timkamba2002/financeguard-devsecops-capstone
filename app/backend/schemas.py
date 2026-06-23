from pydantic import BaseModel, Field


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

    class Config:
        from_attributes = True  # In Pydantic v2, this replaces orm_mode=True
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": "user_2Tsh3K...",
                "description": "AWS Invoice June 2026",
                "amount": -1240.50,
                "category": "Cloud Infrastructure",
                "type": "expense",
            }
        }
