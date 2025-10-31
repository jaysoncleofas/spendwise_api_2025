from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract
from datetime import datetime, timedelta
from database import get_db
from models import User, Transaction, Wallet, Category, TransactionType
from schemas import PeriodSummary, CategoryExpenseSummary, DailySummary, WalletSummary
from auth import get_current_user
from calendar import monthrange

router = APIRouter()

@router.get("/summary/today", response_model=PeriodSummary)
def get_today_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    today = datetime.now().date()
    start_date = datetime.combine(today, datetime.min.time())
    end_date = datetime.combine(today, datetime.max.time())
    
    return get_period_summary(db, current_user, start_date, end_date, "Today")

@router.get("/summary/week", response_model=PeriodSummary)
def get_week_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    today = datetime.now().date()
    start_date = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
    end_date = datetime.combine(today, datetime.max.time())
    
    return get_period_summary(db, current_user, start_date, end_date, "This Week")

@router.get("/summary/month", response_model=PeriodSummary)
def get_month_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    today = datetime.now().date()
    start_date = datetime.combine(today.replace(day=1), datetime.min.time())
    end_date = datetime.combine(today, datetime.max.time())
    
    return get_period_summary(db, current_user, start_date, end_date, "This Month")

@router.get("/summary/custom", response_model=PeriodSummary)
def get_custom_summary(
    start_date: datetime,
    end_date: datetime,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_period_summary(db, current_user, start_date, end_date, "Custom Period")

@router.get("/wallets/summary", response_model=List[WalletSummary])
def get_wallets_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    wallets = db.query(Wallet).filter(Wallet.user_id == current_user.id).all()
    
    summaries = []
    for wallet in wallets:
        # Calculate income
        total_income = db.query(func.sum(Transaction.amount)).filter(
            Transaction.wallet_id == wallet.id,
            Transaction.transaction_type == TransactionType.INCOME
        ).scalar() or 0.0
        
        # Calculate expenses
        total_expense = db.query(func.sum(Transaction.amount)).filter(
            Transaction.wallet_id == wallet.id,
            Transaction.transaction_type == TransactionType.EXPENSE
        ).scalar() or 0.0
        
        # Count transactions
        transaction_count = db.query(func.count(Transaction.id)).filter(
            Transaction.wallet_id == wallet.id
        ).scalar() or 0
        
        summaries.append(WalletSummary(
            wallet_id=wallet.id,
            wallet_name=wallet.name,
            balance=wallet.balance,
            total_income=total_income,
            total_expense=total_expense,
            transaction_count=transaction_count
        ))
    
    return summaries

@router.get("/categories/top-expenses", response_model=List[CategoryExpenseSummary])
def get_top_expense_categories(
    limit: int = 10,
    start_date: datetime = None,
    end_date: datetime = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get user's wallet IDs
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    # Build query
    query = db.query(
        Category.id,
        Category.name,
        func.sum(Transaction.amount).label('total_amount'),
        func.count(Transaction.id).label('transaction_count')
    ).join(
        Transaction, Transaction.category_id == Category.id
    ).filter(
        Transaction.wallet_id.in_(user_wallet_ids),
        Transaction.transaction_type == TransactionType.EXPENSE
    )
    
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    
    results = query.group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).limit(limit).all()
    
    # Calculate total for percentage
    total_expenses = sum(r.total_amount for r in results)
    
    return [
        CategoryExpenseSummary(
            category_id=r.id,
            category_name=r.name,
            total_amount=r.total_amount,
            transaction_count=r.transaction_count,
            percentage=(r.total_amount / total_expenses * 100) if total_expenses > 0 else 0
        )
        for r in results
    ]

@router.get("/comparison/month-over-month")
def get_month_over_month_comparison(
    months: int = 6,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get month-over-month comparison for the last N months"""
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    today = datetime.now().date()
    comparison_data = []
    
    for i in range(months - 1, -1, -1):
        # Calculate the month
        month_date = today.replace(day=1) - timedelta(days=i * 30)
        month_date = month_date.replace(day=1)
        
        # Get last day of month
        last_day = monthrange(month_date.year, month_date.month)[1]
        start_date = datetime.combine(month_date, datetime.min.time())
        end_date = datetime.combine(month_date.replace(day=last_day), datetime.max.time())
        
        # Calculate income
        income = db.query(func.sum(Transaction.amount)).filter(
            Transaction.wallet_id.in_(user_wallet_ids),
            Transaction.transaction_type == TransactionType.INCOME,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).scalar() or 0.0
        
        # Calculate expenses
        expense = db.query(func.sum(Transaction.amount)).filter(
            Transaction.wallet_id.in_(user_wallet_ids),
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).scalar() or 0.0
        
        comparison_data.append({
            "month": month_date.strftime("%B %Y"),
            "month_short": month_date.strftime("%b %y"),
            "income": income,
            "expense": expense,
            "net": income - expense
        })
    
    return {
        "period": "month-over-month",
        "data": comparison_data
    }

@router.get("/comparison/year-over-year")
def get_year_over_year_comparison(
    years: int = 3,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get year-over-year comparison"""
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    current_year = datetime.now().year
    comparison_data = []
    
    for i in range(years - 1, -1, -1):
        year = current_year - i
        start_date = datetime(year, 1, 1, 0, 0, 0)
        end_date = datetime(year, 12, 31, 23, 59, 59)
        
        # Calculate income
        income = db.query(func.sum(Transaction.amount)).filter(
            Transaction.wallet_id.in_(user_wallet_ids),
            Transaction.transaction_type == TransactionType.INCOME,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).scalar() or 0.0
        
        # Calculate expenses
        expense = db.query(func.sum(Transaction.amount)).filter(
            Transaction.wallet_id.in_(user_wallet_ids),
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).scalar() or 0.0
        
        comparison_data.append({
            "year": year,
            "income": income,
            "expense": expense,
            "net": income - expense
        })
    
    return {
        "period": "year-over-year",
        "data": comparison_data
    }

@router.get("/heatmap/spending-patterns")
def get_spending_heatmap(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get spending patterns for heatmap visualization (by day of week and hour)"""
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    # Initialize heatmap data (7 days x 24 hours)
    heatmap_data = [[0 for _ in range(24)] for _ in range(7)]
    
    # If no wallets, return empty heatmap
    if not user_wallet_ids:
        return {
            "period": f"last_{days}_days",
            "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
            "hours": list(range(24)),
            "data": heatmap_data
        }
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    try:
        # Get transactions grouped by day of week and hour
        # MySQL uses DAYOFWEEK (1=Sunday, 7=Saturday) and HOUR functions
        day_of_week_col = func.dayofweek(Transaction.transaction_date).label('day_of_week')
        hour_col = func.hour(Transaction.transaction_date).label('hour')
        
        transactions = db.query(
            day_of_week_col,
            hour_col,
            func.sum(Transaction.amount).label('total_amount'),
            func.count(Transaction.id).label('transaction_count')
        ).filter(
            Transaction.wallet_id.in_(user_wallet_ids),
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).group_by(
            day_of_week_col, hour_col
        ).all()
        
        for trans in transactions:
            # MySQL DAYOFWEEK returns 1-7 (1=Sunday), convert to 0-6 (0=Sunday)
            day = (int(trans.day_of_week) - 1) if trans.day_of_week else 0
            hour = int(trans.hour)
            if 0 <= day < 7 and 0 <= hour < 24:  # Safety check
                heatmap_data[day][hour] = float(trans.total_amount)
    except Exception as e:
        # Return empty heatmap instead of failing
    
    return {
        "period": f"last_{days}_days",
        "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        "hours": list(range(24)),
        "data": heatmap_data
    }

def get_period_summary(
    db: Session,
    current_user: User,
    start_date: datetime,
    end_date: datetime,
    period_name: str
) -> PeriodSummary:
    """Helper function to get summary for a specific period"""
    # Get user's wallet IDs
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    # Calculate total income
    total_income = db.query(func.sum(Transaction.amount)).filter(
        Transaction.wallet_id.in_(user_wallet_ids),
        Transaction.transaction_type == TransactionType.INCOME,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date
    ).scalar() or 0.0
    
    # Calculate total expenses
    total_expense = db.query(func.sum(Transaction.amount)).filter(
        Transaction.wallet_id.in_(user_wallet_ids),
        Transaction.transaction_type == TransactionType.EXPENSE,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date
    ).scalar() or 0.0
    
    # Count transactions
    transaction_count = db.query(func.count(Transaction.id)).filter(
        Transaction.wallet_id.in_(user_wallet_ids),
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date
    ).scalar() or 0
    
    # Get top categories
    category_results = db.query(
        Category.id,
        Category.name,
        func.sum(Transaction.amount).label('total_amount'),
        func.count(Transaction.id).label('transaction_count')
    ).join(
        Transaction, Transaction.category_id == Category.id
    ).filter(
        Transaction.wallet_id.in_(user_wallet_ids),
        Transaction.transaction_type == TransactionType.EXPENSE,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).limit(10).all()
    
    top_categories = [
        CategoryExpenseSummary(
            category_id=r.id,
            category_name=r.name,
            total_amount=r.total_amount,
            transaction_count=r.transaction_count,
            percentage=(r.total_amount / total_expense * 100) if total_expense > 0 else 0
        )
        for r in category_results
    ]
    
    # Get daily breakdown
    daily_breakdown = []
    current_date = start_date.date()
    end_date_date = end_date.date()
    
    while current_date <= end_date_date:
        day_start = datetime.combine(current_date, datetime.min.time())
        day_end = datetime.combine(current_date, datetime.max.time())
        
        day_income = db.query(func.sum(Transaction.amount)).filter(
            Transaction.wallet_id.in_(user_wallet_ids),
            Transaction.transaction_type == TransactionType.INCOME,
            Transaction.transaction_date >= day_start,
            Transaction.transaction_date <= day_end
        ).scalar() or 0.0
        
        day_expense = db.query(func.sum(Transaction.amount)).filter(
            Transaction.wallet_id.in_(user_wallet_ids),
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.transaction_date >= day_start,
            Transaction.transaction_date <= day_end
        ).scalar() or 0.0
        
        day_count = db.query(func.count(Transaction.id)).filter(
            Transaction.wallet_id.in_(user_wallet_ids),
            Transaction.transaction_date >= day_start,
            Transaction.transaction_date <= day_end
        ).scalar() or 0
        
        daily_breakdown.append(DailySummary(
            date=current_date.strftime("%Y-%m-%d"),
            total_income=day_income,
            total_expense=day_expense,
            net_amount=day_income - day_expense,
            transaction_count=day_count
        ))
        
        current_date += timedelta(days=1)
    
    return PeriodSummary(
        period=period_name,
        start_date=start_date,
        end_date=end_date,
        total_income=total_income,
        total_expense=total_expense,
        net_amount=total_income - total_expense,
        transaction_count=transaction_count,
        top_categories=top_categories,
        daily_breakdown=daily_breakdown
    )


