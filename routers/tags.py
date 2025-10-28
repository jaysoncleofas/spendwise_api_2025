from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from database import get_db
from models import User, Tag as TagModel, Transaction, TransactionTag, TransactionType
from auth import get_current_user
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter()

# Pydantic schemas
class TagBase(BaseModel):
    name: str
    color: str = "#6B7280"

class TagCreate(TagBase):
    pass

class TagUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None

class Tag(TagBase):
    id: int
    user_id: int
    
    class Config:
        from_attributes = True

class TagWithCount(Tag):
    usage_count: int

@router.post("", status_code=status.HTTP_201_CREATED, response_model=Tag)
def create_tag(
    tag: TagCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new tag"""
    
    # Check if tag already exists for user
    existing_tag = db.query(TagModel).filter(
        TagModel.user_id == current_user.id,
        TagModel.name == tag.name
    ).first()
    
    if existing_tag:
        raise HTTPException(status_code=400, detail="Tag with this name already exists")
    
    db_tag = TagModel(
        user_id=current_user.id,
        name=tag.name,
        color=tag.color
    )
    
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    
    return db_tag

@router.get("", response_model=List[TagWithCount])
def get_tags(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all tags for current user with usage count"""
    
    tags = db.query(TagModel).filter(TagModel.user_id == current_user.id).all()
    
    result = []
    for tag in tags:
        usage_count = db.query(TransactionTag).filter(TransactionTag.tag_id == tag.id).count()
        result.append({
            "id": tag.id,
            "user_id": tag.user_id,
            "name": tag.name,
            "color": tag.color,
            "usage_count": usage_count
        })
    
    return result

@router.get("/suggestions")
def get_tag_suggestions(
    query: str = "",
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get tag suggestions based on query (autocomplete)"""
    
    tags_query = db.query(TagModel).filter(TagModel.user_id == current_user.id)
    
    if query:
        tags_query = tags_query.filter(TagModel.name.like(f"%{query}%"))
    
    tags = tags_query.limit(limit).all()
    
    return [
        {
            "id": tag.id,
            "user_id": tag.user_id,
            "name": tag.name,
            "color": tag.color
        }
        for tag in tags
    ]

@router.get("/{tag_id}", response_model=Tag)
def get_tag(
    tag_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific tag"""
    
    tag = db.query(TagModel).filter(
        TagModel.id == tag_id,
        TagModel.user_id == current_user.id
    ).first()
    
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    return tag

@router.put("/{tag_id}", response_model=Tag)
def update_tag(
    tag_id: int,
    tag_update: TagUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a tag"""
    
    tag = db.query(TagModel).filter(
        TagModel.id == tag_id,
        TagModel.user_id == current_user.id
    ).first()
    
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    if tag_update.name is not None:
        # Check if new name conflicts with existing tag
        existing = db.query(TagModel).filter(
            TagModel.user_id == current_user.id,
            TagModel.name == tag_update.name,
            TagModel.id != tag_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Tag with this name already exists")
        
        tag.name = tag_update.name
    
    if tag_update.color is not None:
        tag.color = tag_update.color
    
    db.commit()
    db.refresh(tag)
    
    return tag

@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a tag"""
    
    tag = db.query(TagModel).filter(
        TagModel.id == tag_id,
        TagModel.user_id == current_user.id
    ).first()
    
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    db.delete(tag)
    db.commit()
    
    return None

@router.post("/transaction/{transaction_id}/tags", status_code=status.HTTP_201_CREATED)
def add_tags_to_transaction(
    transaction_id: int,
    tag_ids: List[int],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add multiple tags to a transaction"""
    
    # Verify transaction belongs to user
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Check if transaction belongs to user's wallet
    from models import Wallet
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    if transaction.wallet_id not in user_wallet_ids:
        raise HTTPException(status_code=403, detail="Not authorized to add tags to this transaction")
    
    # Remove existing tags
    db.query(TransactionTag).filter(TransactionTag.transaction_id == transaction_id).delete()
    
    # Add new tags
    added_tags = []
    for tag_id in tag_ids:
        # Verify tag belongs to user
        tag = db.query(TagModel).filter(
            TagModel.id == tag_id,
            TagModel.user_id == current_user.id
        ).first()
        
        if not tag:
            continue  # Skip invalid tags
        
        transaction_tag = TransactionTag(
            transaction_id=transaction_id,
            tag_id=tag_id
        )
        db.add(transaction_tag)
        added_tags.append({"id": tag.id, "name": tag.name, "color": tag.color})
    
    db.commit()
    
    return {"transaction_id": transaction_id, "tags": added_tags}

@router.get("/transaction/{transaction_id}/tags", response_model=List[Tag])
def get_transaction_tags(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all tags for a transaction"""
    
    # Verify transaction belongs to user
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    from models import Wallet
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    if transaction.wallet_id not in user_wallet_ids:
        raise HTTPException(status_code=403, detail="Not authorized to view this transaction's tags")
    
    # Get tags
    tag_ids = [tt.tag_id for tt in db.query(TransactionTag).filter(TransactionTag.transaction_id == transaction_id).all()]
    tags = db.query(TagModel).filter(TagModel.id.in_(tag_ids)).all() if tag_ids else []
    
    return tags

@router.get("/analytics/summary")
def get_tag_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive tag analytics"""
    
    # Get total tags
    total_tags = db.query(TagModel).filter(TagModel.user_id == current_user.id).count()
    
    # Get most used tags (top 10)
    most_used = db.query(
        TagModel.id,
        TagModel.name,
        TagModel.color,
        func.count(TransactionTag.transaction_id).label('usage_count')
    ).join(
        TransactionTag, TagModel.id == TransactionTag.tag_id
    ).filter(
        TagModel.user_id == current_user.id
    ).group_by(
        TagModel.id, TagModel.name, TagModel.color
    ).order_by(
        desc('usage_count')
    ).limit(10).all()
    
    # Get tags by transaction type
    tags_by_type = {}
    for trans_type in ['income', 'expense', 'transfer']:
        type_data = db.query(
            TagModel.id,
            TagModel.name,
            func.count(TransactionTag.transaction_id).label('count')
        ).join(
            TransactionTag, TagModel.id == TransactionTag.tag_id
        ).join(
            Transaction, TransactionTag.transaction_id == Transaction.id
        ).filter(
            TagModel.user_id == current_user.id,
            Transaction.transaction_type == trans_type
        ).group_by(
            TagModel.id, TagModel.name
        ).order_by(
            desc('count')
        ).limit(5).all()
        
        tags_by_type[trans_type] = [
            {"id": t.id, "name": t.name, "count": t.count}
            for t in type_data
        ]
    
    # Get total transaction count with tags
    tagged_transactions = db.query(TransactionTag).join(
        Transaction, TransactionTag.transaction_id == Transaction.id
    ).join(
        TagModel, TransactionTag.tag_id == TagModel.id
    ).filter(
        TagModel.user_id == current_user.id
    ).distinct(TransactionTag.transaction_id).count()
    
    # Get total amount by tag (top spending tags)
    tag_spending = db.query(
        TagModel.id,
        TagModel.name,
        TagModel.color,
        func.sum(Transaction.amount).label('total_amount')
    ).join(
        TransactionTag, TagModel.id == TransactionTag.tag_id
    ).join(
        Transaction, TransactionTag.transaction_id == Transaction.id
    ).filter(
        TagModel.user_id == current_user.id,
        Transaction.transaction_type == 'expense'
    ).group_by(
        TagModel.id, TagModel.name, TagModel.color
    ).order_by(
        desc('total_amount')
    ).limit(10).all()
    
    # Get recently used tags (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_tags = db.query(
        TagModel.id,
        TagModel.name,
        TagModel.color,
        func.count(TransactionTag.transaction_id).label('usage_count'),
        func.max(Transaction.transaction_date).label('last_used')
    ).join(
        TransactionTag, TagModel.id == TransactionTag.tag_id
    ).join(
        Transaction, TransactionTag.transaction_id == Transaction.id
    ).filter(
        TagModel.user_id == current_user.id,
        Transaction.transaction_date >= thirty_days_ago
    ).group_by(
        TagModel.id, TagModel.name, TagModel.color
    ).order_by(
        desc('usage_count')
    ).limit(10).all()
    
    return {
        "total_tags": total_tags,
        "tagged_transactions": tagged_transactions,
        "most_used_tags": [
            {"id": t.id, "name": t.name, "color": t.color, "usage_count": t.usage_count}
            for t in most_used
        ],
        "tags_by_type": tags_by_type,
        "top_spending_tags": [
            {"id": t.id, "name": t.name, "color": t.color, "total_amount": float(t.total_amount)}
            for t in tag_spending
        ],
        "recent_tags": [
            {
                "id": t.id,
                "name": t.name,
                "color": t.color,
                "usage_count": t.usage_count,
                "last_used": t.last_used.isoformat() if t.last_used else None
            }
            for t in recent_tags
        ]
    }
