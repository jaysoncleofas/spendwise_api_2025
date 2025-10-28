from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from models import TransactionType, RecurrenceFrequency

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class User(UserBase):
    id: int
    avatar_url: Optional[str] = None
    home_currency: str = "USD"
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    home_currency: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None

# Wallet Schemas
class WalletBase(BaseModel):
    name: str
    description: Optional[str] = None
    currency: str = "USD"
    icon: Optional[str] = None
    color: Optional[str] = None

class WalletCreate(WalletBase):
    balance: float = 0.0

class WalletUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    currency: Optional[str] = None

class Wallet(WalletBase):
    id: int
    user_id: int
    balance: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Category Schemas
class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    budget_limit: Optional[float] = None
    budget_type: Optional[str] = "monthly"  # "monthly" or "fixed"
    budget_start_date: Optional[str] = None  # Accept date string like "2025-10-26"
    budget_rollover: Optional[int] = 0
    rollover_balance: Optional[float] = 0.0

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    budget_limit: Optional[float] = None
    budget_type: Optional[str] = None
    budget_start_date: Optional[str] = None  # Accept string, will be converted in router
    budget_rollover: Optional[int] = None
    rollover_balance: Optional[float] = None

class Category(CategoryBase):
    id: int
    user_id: int
    fixed_budget_spent: Optional[float] = 0.0
    created_at: datetime
    updated_at: datetime
    
    @field_validator('budget_start_date', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        """Convert datetime to string for JSON serialization"""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.strftime('%Y-%m-%d')
        return v
    
    class Config:
        from_attributes = True

# Transaction Schemas
class TransactionBase(BaseModel):
    wallet_id: int
    category_id: Optional[int] = None
    transaction_type: TransactionType
    amount: float = Field(gt=0, description="Amount must be positive")
    description: Optional[str] = None
    notes: Optional[str] = None
    transaction_date: Optional[datetime] = None
    transfer_wallet_id: Optional[int] = None

class TransactionCreate(TransactionBase):
    pass

class TransactionUpdate(BaseModel):
    category_id: Optional[int] = None
    amount: Optional[float] = Field(None, gt=0)
    description: Optional[str] = None
    notes: Optional[str] = None
    transaction_date: Optional[datetime] = None

class Transaction(TransactionBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class TransactionWithDetails(Transaction):
    wallet_name: Optional[str] = None
    category_name: Optional[str] = None
    transfer_wallet_name: Optional[str] = None
    
    class Config:
        from_attributes = True

# Analytics Schemas
class CategoryExpenseSummary(BaseModel):
    category_id: int
    category_name: str
    total_amount: float
    transaction_count: int
    percentage: float

class DailySummary(BaseModel):
    date: str
    total_income: float
    total_expense: float
    net_amount: float
    transaction_count: int

class PeriodSummary(BaseModel):
    period: str
    start_date: datetime
    end_date: datetime
    total_income: float
    total_expense: float
    net_amount: float
    transaction_count: int
    top_categories: List[CategoryExpenseSummary]
    daily_breakdown: List[DailySummary]

class WalletSummary(BaseModel):
    wallet_id: int
    wallet_name: str
    balance: float
    total_income: float
    total_expense: float
    transaction_count: int

# Budget Schemas
class BudgetStatus(BaseModel):
    category_id: int
    category_name: str
    budget_limit: float
    budget_type: Optional[str] = "monthly"  # monthly or fixed
    spent: float
    remaining: float
    percentage: float
    alert_level: str  # safe, warning, critical, danger
    period_start: datetime
    period_end: datetime

class BudgetAlert(BaseModel):
    category_id: int
    category_name: str
    message: str
    severity: str  # warning, critical, danger
    percentage: float
    spent: float
    budget_limit: float

# Recurring Transaction Schemas
class RecurringTransactionBase(BaseModel):
    wallet_id: int
    category_id: Optional[int] = None
    transaction_type: TransactionType
    amount: float = Field(gt=0, description="Amount must be positive")
    description: Optional[str] = None
    notes: Optional[str] = None
    transfer_wallet_id: Optional[int] = None
    frequency: RecurrenceFrequency
    start_date: datetime
    end_date: Optional[datetime] = None
    is_active: bool = True

class RecurringTransactionCreate(RecurringTransactionBase):
    pass

class RecurringTransactionUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    description: Optional[str] = None
    notes: Optional[str] = None
    frequency: Optional[RecurrenceFrequency] = None
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None

class RecurringTransaction(RecurringTransactionBase):
    id: int
    user_id: int
    next_occurrence: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class RecurringTransactionWithDetails(RecurringTransaction):
    wallet_name: Optional[str] = None
    category_name: Optional[str] = None
    transfer_wallet_name: Optional[str] = None
    transaction_count: int = 0  # Number of transactions created from this recurring
    
    class Config:
        from_attributes = True

