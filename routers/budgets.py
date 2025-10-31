from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from database import get_db
from models import User, Category, Transaction, TransactionType
from schemas import BudgetStatus, BudgetAlert
from auth import get_current_user

router = APIRouter()

@router.get("/status", response_model=List[BudgetStatus])
async def get_budget_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get budget status for all categories with budget limits"""
    # Get current month date range
    today = datetime.now()
    start_of_month = datetime(today.year, today.month, 1)
    end_of_month = datetime(today.year, today.month + 1, 1) if today.month < 12 else datetime(today.year + 1, 1, 1)
    
    # Get categories with budget limits
    categories = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.budget_limit.isnot(None)
    ).all()
    
    # Get user's wallets
    from models import Wallet
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    budget_statuses = []
    
    for category in categories:
        budget_type = category.budget_type or "monthly"
        
        if budget_type == "fixed":
            # For fixed budgets, calculate total spent since budget start date
            start_date = category.budget_start_date or category.created_at
            spent = db.query(func.sum(Transaction.amount)).filter(
                Transaction.category_id == category.id,
                Transaction.wallet_id.in_(user_wallet_ids),
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= start_date
            ).scalar() or 0.0
            
            effective_budget = category.budget_limit
            period_start = start_date
            period_end = today  # Fixed budgets don't have an end date
        else:
            # For monthly budgets, calculate spent this month
            spent = db.query(func.sum(Transaction.amount)).filter(
                Transaction.category_id == category.id,
                Transaction.wallet_id.in_(user_wallet_ids),
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= start_of_month,
                Transaction.transaction_date < end_of_month
            ).scalar() or 0.0
            
            # Calculate effective budget (budget + rollover if enabled)
            effective_budget = category.budget_limit
            if category.budget_rollover and category.rollover_balance > 0:
                effective_budget += category.rollover_balance
            
            period_start = start_of_month
            period_end = end_of_month
        
        # Calculate percentage
        percentage = (spent / effective_budget * 100) if effective_budget > 0 else 0
        
        # Determine status
        # For fixed categories: positive progression (like paying off a loan)
        # - More completion = better status (inverted from monthly)
        # For monthly categories: standard budget tracking
        # - More spending = worse status
        if budget_type == "fixed":
            if percentage >= 100:
                alert_level = "completed"  # Fully paid/completed
            elif percentage >= 80:
                alert_level = "safe"  # Almost there, good progress
            elif percentage >= 50:
                alert_level = "warning"  # Halfway there, keep going
            else:
                alert_level = "critical"  # Low progress, need to catch up
        else:
            # Monthly budgets: standard budget tracking
            if percentage >= 100:
                alert_level = "danger"  # Over budget
            elif percentage >= 90:
                alert_level = "critical"  # Almost over budget
            elif percentage >= 80:
                alert_level = "warning"  # Getting close
            else:
                alert_level = "safe"  # Within budget
        
        budget_statuses.append(BudgetStatus(
            category_id=category.id,
            category_name=category.name,
            budget_limit=effective_budget,
            budget_type=budget_type,
            spent=spent,
            remaining=max(0, effective_budget - spent),
            percentage=percentage,
            alert_level=alert_level,
            period_start=period_start,
            period_end=period_end
        ))
    
    return budget_statuses

@router.get("/alerts", response_model=List[BudgetAlert])
async def get_budget_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get active budget alerts"""
    budget_statuses = await get_budget_status(current_user, db)
    
    alerts = []
    for status in budget_statuses:
        if status.budget_type == "fixed":
            # For fixed categories: alert on LOW progress (need to catch up)
            # Don't alert on high progress - that's good!
            if status.percentage >= 100:
                # Completed - positive alert
                message = f"🎉 {status.category_name} completed! Fully paid ${status.spent:.2f} of ${status.budget_limit:.2f}"
                severity = "completed"
            elif status.percentage < 50:
                # Low progress - critical alert
                message = f"⚠️ {status.category_name} needs attention: Only {status.percentage:.1f}% completed"
                severity = "critical"
            elif status.percentage < 80:
                # Moderate progress - warning to keep going
                message = f"📊 {status.category_name} at {status.percentage:.1f}% - Keep making progress!"
                severity = "warning"
            # Don't alert for 50-99% as that's good progress
            else:
                continue  # 80-99% is safe/good progress, no alert needed
        else:
            # For monthly categories: alert on HIGH usage (standard budget tracking)
            if status.percentage > 100:
                message = f"Budget exceeded for {status.category_name}! Spent ${status.spent:.2f} of ${status.budget_limit:.2f}"
                severity = "danger"
            elif status.percentage == 100:
                message = f"Budget limit reached for {status.category_name}. Spent ${status.spent:.2f} of ${status.budget_limit:.2f}"
                severity = "danger"
            elif status.percentage >= 90:
                message = f"Critical: {status.category_name} budget at {status.percentage:.1f}%"
                severity = "critical"
            elif status.percentage >= 80:
                message = f"Warning: {status.category_name} budget at {status.percentage:.1f}%"
                severity = "warning"
            else:
                continue  # Below 80% is safe, no alert
            
        alerts.append(BudgetAlert(
            category_id=status.category_id,
            category_name=status.category_name,
            message=message,
            severity=severity,
            percentage=status.percentage,
            spent=status.spent,
            budget_limit=status.budget_limit
        ))
    
    return alerts

@router.get("/history/{category_id}")
async def get_budget_history(
    category_id: int,
    months: int = 6,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get budget performance history for a category"""
    # Verify category belongs to user
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    if not category.budget_limit:
        raise HTTPException(status_code=400, detail="Category has no budget limit set")
    
    # Get user's wallets
    from models import Wallet
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    history = []
    today = datetime.now()
    
    for i in range(months):
        # Calculate month
        month_date = today - timedelta(days=30 * i)
        start_of_month = datetime(month_date.year, month_date.month, 1)
        
        if month_date.month < 12:
            end_of_month = datetime(month_date.year, month_date.month + 1, 1)
        else:
            end_of_month = datetime(month_date.year + 1, 1, 1)
        
        # Calculate spent
        spent = db.query(func.sum(Transaction.amount)).filter(
            Transaction.category_id == category_id,
            Transaction.wallet_id.in_(user_wallet_ids),
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.transaction_date >= start_of_month,
            Transaction.transaction_date < end_of_month
        ).scalar() or 0.0
        
        history.append({
            "month": start_of_month.strftime("%B %Y"),
            "budget_limit": category.budget_limit,
            "spent": spent,
            "remaining": category.budget_limit - spent,
            "percentage": (spent / category.budget_limit * 100) if category.budget_limit > 0 else 0
        })
    
    return {
        "category_id": category_id,
        "category_name": category.name,
        "current_budget_limit": category.budget_limit,
        "history": history
    }

@router.post("/process-rollover")
async def process_budget_rollover(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process budget rollover for all categories at month end"""
    # Get categories with rollover enabled
    categories = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.budget_limit.isnot(None),
        Category.budget_rollover == 1
    ).all()
    
    # Get user's wallets
    from models import Wallet
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    # Get last month's date range
    today = datetime.now()
    if today.month == 1:
        last_month = datetime(today.year - 1, 12, 1)
        start_of_last_month = last_month
        end_of_last_month = datetime(today.year, 1, 1)
    else:
        start_of_last_month = datetime(today.year, today.month - 1, 1)
        end_of_last_month = datetime(today.year, today.month, 1)
    
    processed = []
    
    for category in categories:
        # Calculate last month's spending
        spent = db.query(func.sum(Transaction.amount)).filter(
            Transaction.category_id == category.id,
            Transaction.wallet_id.in_(user_wallet_ids),
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.transaction_date >= start_of_last_month,
            Transaction.transaction_date < end_of_last_month
        ).scalar() or 0.0
        
        # Calculate remaining (with existing rollover)
        effective_budget = category.budget_limit + (category.rollover_balance or 0)
        remaining = max(0, effective_budget - spent)
        
        # Update rollover balance
        category.rollover_balance = remaining
        
        processed.append({
            "category_id": category.id,
            "category_name": category.name,
            "last_month_spent": spent,
            "last_month_budget": effective_budget,
            "rolled_over": remaining
        })
    
    db.commit()
    
    return {
        "message": f"Processed rollover for {len(processed)} categories",
        "processed": processed
    }

