from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from io import StringIO
import csv
from database import get_db
from models import User, Transaction, Wallet, Category, TransactionType
from auth import get_current_user

router = APIRouter()

@router.get("/transactions/csv")
async def export_transactions_csv(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    wallet_id: Optional[int] = None,
    category_id: Optional[int] = None,
    transaction_type: Optional[TransactionType] = None,
    tag_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export transactions to CSV format"""
    # Get user's wallets
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    # Build query
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
    if tag_id:
        from models import TransactionTag
        query = query.join(TransactionTag).filter(TransactionTag.tag_id == tag_id)
    
    transactions = query.order_by(Transaction.transaction_date.desc()).all()
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Date',
        'Type',
        'Amount',
        'Wallet',
        'Category',
        'Description',
        'Notes',
        'Transfer To',
        'Created At'
    ])
    
    # Write data
    for t in transactions:
        wallet = db.query(Wallet).filter(Wallet.id == t.wallet_id).first()
        category = db.query(Category).filter(Category.id == t.category_id).first() if t.category_id else None
        transfer_wallet = db.query(Wallet).filter(Wallet.id == t.transfer_wallet_id).first() if t.transfer_wallet_id else None
        
        writer.writerow([
            t.transaction_date.strftime('%Y-%m-%d %H:%M:%S'),
            t.transaction_type.value,
            f'{t.amount:.2f}',
            wallet.name if wallet else '',
            category.name if category else '',
            t.description or '',
            t.notes or '',
            transfer_wallet.name if transfer_wallet else '',
            t.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # Prepare response
    output.seek(0)
    filename = f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/budget-report/csv")
async def export_budget_report_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export budget report to CSV format"""
    from routers.budgets import get_budget_status
    
    budget_statuses = await get_budget_status(current_user, db)
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Category',
        'Budget Limit',
        'Spent',
        'Remaining',
        'Percentage',
        'Status',
        'Period Start',
        'Period End'
    ])
    
    # Write data
    for status in budget_statuses:
        writer.writerow([
            status.category_name,
            f'{status.budget_limit:.2f}',
            f'{status.spent:.2f}',
            f'{status.remaining:.2f}',
            f'{status.percentage:.1f}%',
            status.alert_level,
            status.period_start.strftime('%Y-%m-%d'),
            status.period_end.strftime('%Y-%m-%d')
        ])
    
    # Prepare response
    output.seek(0)
    filename = f"budget_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/summary-report/csv")
async def export_summary_report_csv(
    start_date: datetime,
    end_date: datetime,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export financial summary report to CSV format"""
    from routers.analytics import get_period_summary
    
    summary = get_period_summary(db, current_user, start_date, end_date, "Custom Period")
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write summary section
    writer.writerow(['FINANCIAL SUMMARY REPORT'])
    writer.writerow(['Period', summary.period])
    writer.writerow(['Start Date', start_date.strftime('%Y-%m-%d')])
    writer.writerow(['End Date', end_date.strftime('%Y-%m-%d')])
    writer.writerow([])
    
    writer.writerow(['OVERVIEW'])
    writer.writerow(['Total Income', f'${summary.total_income:.2f}'])
    writer.writerow(['Total Expense', f'${summary.total_expense:.2f}'])
    writer.writerow(['Net Amount', f'${summary.net_amount:.2f}'])
    writer.writerow(['Transaction Count', summary.transaction_count])
    writer.writerow([])
    
    # Write top categories
    writer.writerow(['TOP EXPENSE CATEGORIES'])
    writer.writerow(['Category', 'Amount', 'Transactions', 'Percentage'])
    for cat in summary.top_categories:
        writer.writerow([
            cat.category_name,
            f'${cat.total_amount:.2f}',
            cat.transaction_count,
            f'{cat.percentage:.1f}%'
        ])
    writer.writerow([])
    
    # Write daily breakdown
    writer.writerow(['DAILY BREAKDOWN'])
    writer.writerow(['Date', 'Income', 'Expense', 'Net', 'Transactions'])
    for day in summary.daily_breakdown:
        writer.writerow([
            day.date,
            f'${day.total_income:.2f}',
            f'${day.total_expense:.2f}',
            f'${day.net_amount:.2f}',
            day.transaction_count
        ])
    
    # Prepare response
    output.seek(0)
    filename = f"summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/wallets-report/csv")
async def export_wallets_report_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export wallets summary to CSV format"""
    from routers.analytics import get_wallets_summary
    
    wallets_summary = await get_wallets_summary(current_user, db)
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Wallet Name',
        'Current Balance',
        'Total Income',
        'Total Expense',
        'Net',
        'Transaction Count'
    ])
    
    # Write data
    for wallet in wallets_summary:
        net = wallet.total_income - wallet.total_expense
        writer.writerow([
            wallet.wallet_name,
            f'{wallet.balance:.2f}',
            f'{wallet.total_income:.2f}',
            f'{wallet.total_expense:.2f}',
            f'{net:.2f}',
            wallet.transaction_count
        ])
    
    # Prepare response
    output.seek(0)
    filename = f"wallets_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

