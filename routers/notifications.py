from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db
from models import User, Notification as NotificationModel, Category, Wallet
from auth import get_current_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class NotificationBase(BaseModel):
    type: str
    title: str
    message: str
    related_id: Optional[int] = None

class NotificationCreate(NotificationBase):
    pass

class Notification(NotificationBase):
    id: int
    user_id: int
    is_read: int
    created_at: datetime
    
    class Config:
        from_attributes = True

@router.get("", response_model=List[Notification])
def get_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notifications for current user"""
    
    query = db.query(NotificationModel).filter(NotificationModel.user_id == current_user.id)
    
    if unread_only:
        query = query.filter(NotificationModel.is_read == 0)
    
    notifications = query.order_by(desc(NotificationModel.created_at)).limit(limit).all()
    
    return notifications

@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get count of unread notifications"""
    
    count = db.query(NotificationModel).filter(
        NotificationModel.user_id == current_user.id,
        NotificationModel.is_read == 0
    ).count()
    
    return {"count": count}

@router.post("", status_code=status.HTTP_201_CREATED, response_model=Notification)
def create_notification(
    notification: NotificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a notification (internal use / testing)"""
    
    db_notification = NotificationModel(
        user_id=current_user.id,
        type=notification.type,
        title=notification.title,
        message=notification.message,
        related_id=notification.related_id
    )
    
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    
    return db_notification

@router.put("/{notification_id}/read")
def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark notification as read"""
    
    notification = db.query(NotificationModel).filter(
        NotificationModel.id == notification_id,
        NotificationModel.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = 1
    db.commit()
    
    return {"success": True}

@router.put("/read-all")
def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all notifications as read"""
    
    db.query(NotificationModel).filter(
        NotificationModel.user_id == current_user.id,
        NotificationModel.is_read == 0
    ).update({"is_read": 1})
    
    db.commit()
    
    return {"success": True}

@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a notification"""
    
    notification = db.query(NotificationModel).filter(
        NotificationModel.id == notification_id,
        NotificationModel.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    db.delete(notification)
    db.commit()
    
    return None

@router.post("/check-alerts")
def check_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check for budget and balance alerts and create notifications"""
    
    notifications_created = []
    
    # Check budget alerts
    from datetime import datetime
    from sqlalchemy import func, extract
    from models import Transaction, TransactionType
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    categories = db.query(Category).filter(Category.user_id == current_user.id).all()
    
    for category in categories:
        if not category.budget_limit or category.budget_limit <= 0:
            continue
        
        # Get wallets for user
        user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
        
        if not user_wallet_ids:
            continue
        
        # Calculate spending for this category this month
        monthly_spending = db.query(func.sum(Transaction.amount)).filter(
            Transaction.wallet_id.in_(user_wallet_ids),
            Transaction.category_id == category.id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            extract('month', Transaction.transaction_date) == current_month,
            extract('year', Transaction.transaction_date) == current_year
        ).scalar() or 0
        
        # Check if budget is exceeded or near limit
        budget_usage_percent = (monthly_spending / category.budget_limit) * 100
        
        if budget_usage_percent >= 100:
            # Budget exceeded
            notification = NotificationModel(
                user_id=current_user.id,
                type="budget_alert",
                title=f"⚠️ Budget Exceeded: {category.name}",
                message=f"You've spent ${monthly_spending:.2f} of your ${category.budget_limit:.2f} budget for {category.name} this month.",
                related_id=category.id
            )
            db.add(notification)
            notifications_created.append("budget_exceeded")
        elif budget_usage_percent >= 80:
            # Near budget limit
            notification = NotificationModel(
                user_id=current_user.id,
                type="budget_alert",
                title=f"⚡ Budget Alert: {category.name}",
                message=f"You've used {budget_usage_percent:.0f}% of your budget for {category.name}. Remaining: ${(category.budget_limit - monthly_spending):.2f}",
                related_id=category.id
            )
            db.add(notification)
            notifications_created.append("budget_warning")
    
    # Check low balance warnings
    wallets = db.query(Wallet).filter(Wallet.user_id == current_user.id).all()
    
    for wallet in wallets:
        if wallet.balance < 100:  # Alert if balance below $100
            notification = NotificationModel(
                user_id=current_user.id,
                type="low_balance",
                title=f"💰 Low Balance: {wallet.name}",
                message=f"Your {wallet.name} balance is ${wallet.balance:.2f}. Consider topping up!",
                related_id=wallet.id
            )
            db.add(notification)
            notifications_created.append("low_balance")
    
    db.commit()
    
    return {
        "success": True,
        "notifications_created": len(notifications_created),
        "types": notifications_created
    }

