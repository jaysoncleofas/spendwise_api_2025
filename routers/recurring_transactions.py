from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database import get_db
from models import User, RecurringTransaction, Transaction, Wallet, Category, TransactionType, RecurrenceFrequency
from schemas import (
    RecurringTransactionCreate, 
    RecurringTransactionUpdate, 
    RecurringTransactionWithDetails
)
from auth import get_current_user

router = APIRouter()

def calculate_next_occurrence(current_date: datetime, frequency: RecurrenceFrequency) -> datetime:
    """Calculate the next occurrence date based on frequency"""
    if frequency == RecurrenceFrequency.DAILY:
        return current_date + timedelta(days=1)
    elif frequency == RecurrenceFrequency.WEEKLY:
        return current_date + timedelta(weeks=1)
    elif frequency == RecurrenceFrequency.MONTHLY:
        # Add one month
        month = current_date.month
        year = current_date.year
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1
        try:
            return current_date.replace(year=year, month=month)
        except ValueError:
            # Handle end of month edge cases (e.g., Jan 31 -> Feb 28)
            next_month = current_date.replace(year=year, month=month, day=1)
            return next_month + timedelta(days=-1)
    elif frequency == RecurrenceFrequency.YEARLY:
        try:
            return current_date.replace(year=current_date.year + 1)
        except ValueError:
            # Handle Feb 29 on non-leap years
            return current_date.replace(year=current_date.year + 1, day=28)
    return current_date

@router.post("", response_model=RecurringTransactionWithDetails, status_code=status.HTTP_201_CREATED)
async def create_recurring_transaction(
    recurring: RecurringTransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new recurring transaction"""
    # Verify wallet belongs to user
    wallet = db.query(Wallet).filter(
        Wallet.id == recurring.wallet_id,
        Wallet.user_id == current_user.id
    ).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # Verify category if provided
    if recurring.category_id:
        category = db.query(Category).filter(
            Category.id == recurring.category_id,
            Category.user_id == current_user.id
        ).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
    
    # Calculate next occurrence
    next_occurrence = recurring.start_date if recurring.start_date >= datetime.now() else calculate_next_occurrence(datetime.now(), recurring.frequency)
    
    # Create recurring transaction
    db_recurring = RecurringTransaction(
        user_id=current_user.id,
        wallet_id=recurring.wallet_id,
        category_id=recurring.category_id,
        transaction_type=recurring.transaction_type,
        amount=recurring.amount,
        description=recurring.description,
        notes=recurring.notes,
        transfer_wallet_id=recurring.transfer_wallet_id,
        frequency=recurring.frequency,
        start_date=recurring.start_date,
        end_date=recurring.end_date,
        next_occurrence=next_occurrence,
        is_active=1 if recurring.is_active else 0
    )
    
    db.add(db_recurring)
    db.commit()
    db.refresh(db_recurring)
    
    return get_recurring_transaction_with_details(db, db_recurring)

@router.get("", response_model=List[RecurringTransactionWithDetails])
async def get_recurring_transactions(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all recurring transactions for the current user"""
    query = db.query(RecurringTransaction).filter(RecurringTransaction.user_id == current_user.id)
    
    if not include_inactive:
        query = query.filter(RecurringTransaction.is_active == 1)
    
    recurring_transactions = query.all()
    return [get_recurring_transaction_with_details(db, rt) for rt in recurring_transactions]

@router.get("/{recurring_id}", response_model=RecurringTransactionWithDetails)
async def get_recurring_transaction(
    recurring_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific recurring transaction"""
    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recurring_id,
        RecurringTransaction.user_id == current_user.id
    ).first()
    
    if not recurring:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    
    return get_recurring_transaction_with_details(db, recurring)

@router.put("/{recurring_id}", response_model=RecurringTransactionWithDetails)
async def update_recurring_transaction(
    recurring_id: int,
    recurring_update: RecurringTransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a recurring transaction"""
    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recurring_id,
        RecurringTransaction.user_id == current_user.id
    ).first()
    
    if not recurring:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    
    update_data = recurring_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        if key == "is_active":
            setattr(recurring, key, 1 if value else 0)
        else:
            setattr(recurring, key, value)
    
    db.commit()
    db.refresh(recurring)
    return get_recurring_transaction_with_details(db, recurring)

@router.post("/{recurring_id}/pause")
async def pause_recurring_transaction(
    recurring_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Pause a recurring transaction"""
    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recurring_id,
        RecurringTransaction.user_id == current_user.id
    ).first()
    
    if not recurring:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    
    recurring.is_active = 0
    db.commit()
    return {"message": "Recurring transaction paused"}

@router.post("/{recurring_id}/resume")
async def resume_recurring_transaction(
    recurring_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resume a paused recurring transaction"""
    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recurring_id,
        RecurringTransaction.user_id == current_user.id
    ).first()
    
    if not recurring:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    
    recurring.is_active = 1
    db.commit()
    return {"message": "Recurring transaction resumed"}

@router.delete("/{recurring_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurring_transaction(
    recurring_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a recurring transaction"""
    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recurring_id,
        RecurringTransaction.user_id == current_user.id
    ).first()
    
    if not recurring:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    
    db.delete(recurring)
    db.commit()
    return None

@router.post("/process")
async def process_recurring_transactions(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process due recurring transactions (create actual transactions)"""
    now = datetime.now()
    
    # Get all active recurring transactions that are due
    due_recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.user_id == current_user.id,
        RecurringTransaction.is_active == 1,
        RecurringTransaction.next_occurrence <= now
    ).all()
    
    processed_count = 0
    
    for recurring in due_recurring:
        # Check if end date has passed
        if recurring.end_date and recurring.end_date < now:
            recurring.is_active = 0
            continue
        
        # Create the transaction
        wallet = db.query(Wallet).filter(Wallet.id == recurring.wallet_id).first()
        
        if not wallet:
            continue
        
        # Update wallet balance
        if recurring.transaction_type == TransactionType.INCOME:
            wallet.balance += recurring.amount
        elif recurring.transaction_type == TransactionType.EXPENSE:
            wallet.balance -= recurring.amount
        elif recurring.transaction_type == TransactionType.TRANSFER and recurring.transfer_wallet_id:
            transfer_wallet = db.query(Wallet).filter(Wallet.id == recurring.transfer_wallet_id).first()
            if transfer_wallet:
                wallet.balance -= recurring.amount
                transfer_wallet.balance += recurring.amount
        
        # Create transaction
        transaction = Transaction(
            wallet_id=recurring.wallet_id,
            category_id=recurring.category_id,
            transaction_type=recurring.transaction_type,
            amount=recurring.amount,
            description=recurring.description,
            notes=recurring.notes,
            transfer_wallet_id=recurring.transfer_wallet_id,
            recurring_transaction_id=recurring.id,
            transaction_date=now
        )
        
        db.add(transaction)
        
        # Update next occurrence
        recurring.next_occurrence = calculate_next_occurrence(recurring.next_occurrence, recurring.frequency)
        
        processed_count += 1
    
    db.commit()
    
    return {
        "message": f"Processed {processed_count} recurring transactions",
        "processed_count": processed_count
    }

def get_recurring_transaction_with_details(db: Session, recurring: RecurringTransaction) -> RecurringTransactionWithDetails:
    """Helper function to get recurring transaction with related details"""
    wallet = db.query(Wallet).filter(Wallet.id == recurring.wallet_id).first()
    category = None
    if recurring.category_id:
        category = db.query(Category).filter(Category.id == recurring.category_id).first()
    transfer_wallet = None
    if recurring.transfer_wallet_id:
        transfer_wallet = db.query(Wallet).filter(Wallet.id == recurring.transfer_wallet_id).first()
    
    # Count transactions created from this recurring
    transaction_count = db.query(Transaction).filter(Transaction.recurring_transaction_id == recurring.id).count()
    
    return RecurringTransactionWithDetails(
        id=recurring.id,
        user_id=recurring.user_id,
        wallet_id=recurring.wallet_id,
        category_id=recurring.category_id,
        transaction_type=recurring.transaction_type,
        amount=recurring.amount,
        description=recurring.description,
        notes=recurring.notes,
        transfer_wallet_id=recurring.transfer_wallet_id,
        frequency=recurring.frequency,
        start_date=recurring.start_date,
        end_date=recurring.end_date,
        next_occurrence=recurring.next_occurrence,
        is_active=bool(recurring.is_active),
        created_at=recurring.created_at,
        updated_at=recurring.updated_at,
        wallet_name=wallet.name if wallet else None,
        category_name=category.name if category else None,
        transfer_wallet_name=transfer_wallet.name if transfer_wallet else None,
        transaction_count=transaction_count
    )

