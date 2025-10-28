from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from database import get_db
from models import User, Transaction, Wallet, Category, TransactionType
from schemas import TransactionCreate, TransactionUpdate, TransactionWithDetails
from auth import get_current_user

router = APIRouter()

def update_wallet_balance(
    db: Session,
    wallet: Wallet,
    transaction_type: TransactionType,
    amount: float,
    is_reversal: bool = False
):
    """Update wallet balance based on transaction type"""
    if is_reversal:
        # Reverse the transaction
        if transaction_type == TransactionType.INCOME:
            wallet.balance -= amount
        elif transaction_type == TransactionType.EXPENSE:
            wallet.balance += amount
    else:
        # Apply the transaction
        if transaction_type == TransactionType.INCOME:
            wallet.balance += amount
        elif transaction_type == TransactionType.EXPENSE:
            wallet.balance -= amount

@router.post("", response_model=TransactionWithDetails, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify wallet belongs to user
    wallet = db.query(Wallet).filter(
        Wallet.id == transaction.wallet_id,
        Wallet.user_id == current_user.id
    ).first()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    
    # Verify category belongs to user if provided
    if transaction.category_id:
        category = db.query(Category).filter(
            Category.id == transaction.category_id,
            Category.user_id == current_user.id
        ).first()
        if not category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    
    # Handle transfer transactions
    if transaction.transaction_type == TransactionType.TRANSFER:
        if not transaction.transfer_wallet_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transfer wallet is required for transfer transactions"
            )
        transfer_wallet = db.query(Wallet).filter(
            Wallet.id == transaction.transfer_wallet_id,
            Wallet.user_id == current_user.id
        ).first()
        if not transfer_wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer wallet not found")
        
        # Update balances for transfer
        wallet.balance -= transaction.amount
        transfer_wallet.balance += transaction.amount
    else:
        # Update wallet balance for income/expense
        update_wallet_balance(db, wallet, transaction.transaction_type, transaction.amount)
    
    # Create transaction
    db_transaction = Transaction(**transaction.dict())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    
    # Return transaction with details
    return get_transaction_with_details(db, db_transaction)

@router.get("", response_model=List[TransactionWithDetails])
def get_transactions(
    wallet_id: Optional[int] = None,
    category_id: Optional[int] = None,
    transaction_type: Optional[TransactionType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    tag_id: Optional[int] = None,  # Filter by tag
    sort_by: str = "date",  # date, amount, type
    sort_order: str = "desc",  # asc, desc
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get all wallets for the user
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    # If user has no wallets, return empty list
    if not user_wallet_ids:
        return []
    
    query = db.query(Transaction).filter(Transaction.wallet_id.in_(user_wallet_ids))
    
    if wallet_id:
        query = query.filter(Transaction.wallet_id == wallet_id)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    if search:
        # Search in description and notes
        search_filter = or_(
            Transaction.description.like(f"%{search}%"),
            Transaction.notes.like(f"%{search}%")
        )
        query = query.filter(search_filter)
    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Transaction.amount <= max_amount)
    if tag_id:
        # Filter by tag - join with transaction_tags
        from models import TransactionTag
        query = query.join(TransactionTag).filter(TransactionTag.tag_id == tag_id)
    
    # Apply sorting
    if sort_by == "amount":
        order_column = Transaction.amount
    elif sort_by == "type":
        order_column = Transaction.transaction_type
    else:  # default to date
        order_column = Transaction.transaction_date
    
    if sort_order == "asc":
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())
    
    transactions = query.offset(skip).limit(limit).all()
    
    return [get_transaction_with_details(db, t) for t in transactions]

@router.get("/{transaction_id}", response_model=TransactionWithDetails)
def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.wallet_id.in_(user_wallet_ids)
    ).first()
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    return get_transaction_with_details(db, transaction)

@router.put("/{transaction_id}", response_model=TransactionWithDetails)
def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.wallet_id.in_(user_wallet_ids)
    ).first()
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    # If amount is being updated, adjust wallet balance
    if transaction_update.amount and transaction_update.amount != transaction.amount:
        wallet = db.query(Wallet).filter(Wallet.id == transaction.wallet_id).first()
        # Reverse old transaction
        update_wallet_balance(db, wallet, transaction.transaction_type, transaction.amount, is_reversal=True)
        # Apply new transaction
        update_wallet_balance(db, wallet, transaction.transaction_type, transaction_update.amount)
    
    update_data = transaction_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(transaction, key, value)
    
    db.commit()
    db.refresh(transaction)
    return get_transaction_with_details(db, transaction)

@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.wallet_id.in_(user_wallet_ids)
    ).first()
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    # Reverse the transaction on wallet balance
    wallet = db.query(Wallet).filter(Wallet.id == transaction.wallet_id).first()
    update_wallet_balance(db, wallet, transaction.transaction_type, transaction.amount, is_reversal=True)
    
    # Handle transfer reversal
    if transaction.transaction_type == TransactionType.TRANSFER and transaction.transfer_wallet_id:
        transfer_wallet = db.query(Wallet).filter(Wallet.id == transaction.transfer_wallet_id).first()
        if transfer_wallet:
            transfer_wallet.balance -= transaction.amount
    
    db.delete(transaction)
    db.commit()
    return None

def get_transaction_with_details(db: Session, transaction: Transaction) -> TransactionWithDetails:
    """Helper function to get transaction with related details"""
    wallet = db.query(Wallet).filter(Wallet.id == transaction.wallet_id).first()
    category = None
    if transaction.category_id:
        category = db.query(Category).filter(Category.id == transaction.category_id).first()
    transfer_wallet = None
    if transaction.transfer_wallet_id:
        transfer_wallet = db.query(Wallet).filter(Wallet.id == transaction.transfer_wallet_id).first()
    
    return TransactionWithDetails(
        id=transaction.id,
        wallet_id=transaction.wallet_id,
        category_id=transaction.category_id,
        transaction_type=transaction.transaction_type,
        amount=transaction.amount,
        description=transaction.description,
        notes=transaction.notes,
        transaction_date=transaction.transaction_date,
        transfer_wallet_id=transaction.transfer_wallet_id,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
        wallet_name=wallet.name if wallet else None,
        category_name=category.name if category else None,
        transfer_wallet_name=transfer_wallet.name if transfer_wallet else None
    )


