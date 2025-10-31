from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"

class RecurrenceFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    home_currency = Column(String(10), default="USD")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")

class Wallet(Base):
    __tablename__ = "wallets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    balance = Column(Float, default=0.0)
    currency = Column(String(10), default="USD")
    icon = Column(String(50), nullable=True)
    color = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="wallets")
    transactions = relationship("Transaction", foreign_keys="Transaction.wallet_id", back_populates="wallet", cascade="all, delete-orphan")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    color = Column(String(20), nullable=True)
    budget_limit = Column(Float, nullable=True)
    budget_type = Column(String(20), default="monthly")  # "monthly" or "fixed"
    budget_start_date = Column(DateTime, nullable=True)  # Start date for fixed budgets
    fixed_budget_spent = Column(Float, default=0.0)  # Total spent for fixed budgets
    budget_rollover = Column(Integer, default=0)  # 0 = disabled, 1 = enabled (only for monthly)
    rollover_balance = Column(Float, default=0.0)  # Unused budget from previous month (only for monthly)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    transaction_date = Column(DateTime, default=func.now(), index=True)
    transfer_wallet_id = Column(Integer, ForeignKey("wallets.id", ondelete="SET NULL"), nullable=True)
    recurring_transaction_id = Column(Integer, ForeignKey("recurring_transactions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    wallet = relationship("Wallet", foreign_keys=[wallet_id], back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
    transfer_wallet = relationship("Wallet", foreign_keys=[transfer_wallet_id])
    recurring_transaction = relationship("RecurringTransaction", back_populates="transactions")
    tags = relationship("Tag", secondary="transaction_tags", back_populates="transactions")

class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    transfer_wallet_id = Column(Integer, ForeignKey("wallets.id", ondelete="SET NULL"), nullable=True)
    
    # Recurrence settings
    frequency = Column(SQLEnum(RecurrenceFrequency), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)  # NULL means indefinite
    next_occurrence = Column(DateTime, nullable=False, index=True)
    is_active = Column(Integer, default=1)  # 1 = active, 0 = paused
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    user = relationship("User")
    wallet = relationship("Wallet", foreign_keys=[wallet_id])
    category = relationship("Category")
    transfer_wallet = relationship("Wallet", foreign_keys=[transfer_wallet_id])
    transactions = relationship("Transaction", back_populates="recurring_transaction")

class Receipt(Base):
    __tablename__ = "receipts"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=True)  # Not storing files anymore
    original_filename = Column(String(255), nullable=False)  # Keep for reference
    file_path = Column(String(500), nullable=True)  # Not storing files anymore
    file_type = Column(String(50), nullable=False)  # image/jpeg, image/png, application/pdf
    file_size = Column(Integer, nullable=False)  # in bytes
    ocr_text = Column(Text, nullable=True)  # Extracted text from OCR - this is what we store
    uploaded_at = Column(DateTime, default=func.now())
    
    transaction = relationship("Transaction")
    user = relationship("User")

class Tag(Base):
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    color = Column(String(20), default="#6B7280")
    created_at = Column(DateTime, default=func.now())
    
    user = relationship("User")
    transactions = relationship("Transaction", secondary="transaction_tags", back_populates="tags")

class TransactionTag(Base):
    __tablename__ = "transaction_tags"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    
    id = Column(Integer, primary_key=True, index=True)
    from_currency = Column(String(10), nullable=False)
    to_currency = Column(String(10), nullable=False)
    rate = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class ExchangeRateHistory(Base):
    __tablename__ = "exchange_rate_history"
    
    id = Column(Integer, primary_key=True, index=True)
    from_currency = Column(String(10), nullable=False, index=True)
    to_currency = Column(String(10), nullable=False, index=True)
    rate = Column(Float, nullable=False)
    source = Column(String(50), default="manual")  # 'manual', 'api', 'migration'
    recorded_at = Column(DateTime, default=func.now(), index=True)

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # 'budget_alert', 'low_balance', 'bill_reminder'
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Integer, default=0, index=True)  # 0 = unread, 1 = read
    related_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    
    user = relationship("User")

