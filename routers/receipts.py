from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pathlib import Path
from datetime import datetime, timedelta
from io import BytesIO
from database import get_db
from models import User, Receipt as ReceiptModel, Transaction
from auth import get_current_user

router = APIRouter()

# Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/gif", 
    "image/heic", "image/heif",  # Apple HEIC format
    "application/pdf"
}

# OCR Configuration
OCR_ENABLED = False  # Set to True if pytesseract is installed
try:
    import pytesseract
    from PIL import Image
    OCR_ENABLED = True
except ImportError:

def extract_text_from_image_bytes(image_bytes: bytes) -> Optional[str]:
    """Extract text from an image using OCR (process in memory, no file saved)"""
    if not OCR_ENABLED:
        return None
    
    try:
        image = Image.open(BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        return text.strip() if text else None
    except Exception as e:
        return None

def parse_ocr_text(ocr_text: str) -> dict:
    """Parse OCR text to extract amount, description, and notes"""
    import re
    
    result = {
        "amount": None,
        "description": None,
        "notes": ocr_text
    }
    
    if not ocr_text:
        return result
    
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    
    # Extract amount - look for currency symbols and numbers
    # Patterns: $123.45, 123.45, USD 123.45, etc.
    amount_patterns = [
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # $123.45, $1,234.56
        r'(\d+(?:,\d{3})*\.\d{2})\s*(?:USD|usd|\$)?',  # 123.45 USD
        r'(?:Total|TOTAL|Amount|AMOUNT|Pay|PAY)[\s:]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # Total: $123.45
    ]
    
    for pattern in amount_patterns:
        for line in lines:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    result["amount"] = float(amount_str)
                    break
                except ValueError:
                    continue
        if result["amount"]:
            break
    
    # Extract description - use first non-empty line or first line with reasonable length
    for line in lines:
        if len(line) >= 3 and len(line) <= 100 and not re.match(r'^\d+[\d\s\.\,\$]*$', line):
            result["description"] = line
            break
    
    return result

@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    file: UploadFile = File(...),
    transaction_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a receipt (optionally for a transaction)"""
    
    try:
        # If transaction_id provided, verify it belongs to user
        if transaction_id is not None:
            transaction = db.query(Transaction).filter(
                Transaction.id == transaction_id
            ).first()
            
            if not transaction:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            # Get user's wallet IDs
            from models import Wallet
            user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
            
            if transaction.wallet_id not in user_wallet_ids:
                raise HTTPException(status_code=403, detail="You don't have permission to add receipt to this transaction")
        
        # Validate file type
        if not file.content_type:
            raise HTTPException(
                status_code=400, 
                detail="File content type not detected. Please ensure the file is a valid image or PDF."
            )
        
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400, 
                detail=f"File type '{file.content_type}' not allowed. Allowed types: {', '.join(ALLOWED_TYPES)}"
            )
        
        # Read file content into memory
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_FILE_SIZE // 1024 // 1024}MB")
        
        # Extract text using OCR (process in memory, don't save file)
        ocr_text = None
        if file.content_type.startswith('image/'):
            ocr_text = extract_text_from_image_bytes(file_content)
        elif file.content_type == 'application/pdf':
            # PDF OCR not implemented yet, but text extraction could be added here
            # For now, we'll just store metadata
            ocr_text = None
    
        # Create receipt record (file NOT saved to disk - only OCR text stored)
        # Use original_filename for filename field since DB column is NOT NULL
        db_receipt = ReceiptModel(
            transaction_id=transaction_id,
            user_id=current_user.id,
            filename=file.filename,  # Use original filename (file not stored on disk)
            original_filename=file.filename,
            file_path="",  # Empty string instead of None (file not stored)
            file_type=file.content_type,
            file_size=file_size,
            ocr_text=ocr_text
        )
        
        db.add(db_receipt)
        db.commit()
        db.refresh(db_receipt)
        
        # Parse OCR text for structured data
        parsed_data = parse_ocr_text(ocr_text) if ocr_text else {}
        
        return {
            "id": db_receipt.id,
            "transaction_id": db_receipt.transaction_id,
            "original_filename": db_receipt.original_filename,
            "file_type": db_receipt.file_type,
            "file_size": db_receipt.file_size,
            "ocr_text": db_receipt.ocr_text,
            "parsed_data": parsed_data,
            "uploaded_at": db_receipt.uploaded_at,
            "note": "File content not stored - only OCR text extracted and saved"
        }
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during upload: {str(e)}"
        )

@router.get("/transaction/{transaction_id}")
async def get_transaction_receipts(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all receipts for a transaction"""
    
    # Verify transaction belongs to user
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    from models import Wallet
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    if transaction.wallet_id not in user_wallet_ids:
        raise HTTPException(status_code=403, detail="You don't have permission to view this transaction's receipts")
    
    receipts = db.query(ReceiptModel).filter(
        ReceiptModel.transaction_id == transaction_id
    ).all()
    
    return [
        {
            "id": r.id,
            "transaction_id": r.transaction_id,
            "original_filename": r.original_filename,
            "file_type": r.file_type,
            "file_size": r.file_size,
            "ocr_text": r.ocr_text,  # Include OCR text in response
            "uploaded_at": r.uploaded_at
        }
        for r in receipts
    ]

@router.get("/{receipt_id}/download")
async def download_receipt(
    receipt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get receipt OCR text (files are not stored to save server storage)"""
    
    receipt = db.query(ReceiptModel).filter(
        ReceiptModel.id == receipt_id,
        ReceiptModel.user_id == current_user.id
    ).first()
    
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    # Since files are not stored, return OCR text as JSON
    if not receipt.ocr_text:
        raise HTTPException(
            status_code=404, 
            detail="Receipt text content not available. Files are not stored on server to save storage space."
        )
    
    return {
        "id": receipt.id,
        "original_filename": receipt.original_filename,
        "file_type": receipt.file_type,
        "ocr_text": receipt.ocr_text,
        "uploaded_at": receipt.uploaded_at,
        "note": "File not stored - only text content available"
    }

@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_receipt(
    receipt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a receipt (only database record, no file to delete)"""
    
    receipt = db.query(ReceiptModel).filter(
        ReceiptModel.id == receipt_id,
        ReceiptModel.user_id == current_user.id
    ).first()
    
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    # No file to delete - files are not stored
    # Just delete database record
    db.delete(receipt)
    db.commit()
    
    return None

@router.put("/{receipt_id}/link-transaction")
async def link_receipt_to_transaction(
    receipt_id: int,
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Link an existing receipt to a transaction"""
    
    # Verify receipt belongs to user
    receipt = db.query(ReceiptModel).filter(
        ReceiptModel.id == receipt_id,
        ReceiptModel.user_id == current_user.id
    ).first()
    
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    # Verify transaction belongs to user
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    from models import Wallet
    user_wallet_ids = [w.id for w in db.query(Wallet.id).filter(Wallet.user_id == current_user.id).all()]
    
    if transaction.wallet_id not in user_wallet_ids:
        raise HTTPException(status_code=403, detail="You don't have permission to link receipt to this transaction")
    
    # Update receipt's transaction_id
    receipt.transaction_id = transaction_id
    db.commit()
    db.refresh(receipt)
    
    return {
        "id": receipt.id,
        "transaction_id": receipt.transaction_id,
        "message": "Receipt linked to transaction successfully"
    }

@router.get("/search")
async def search_receipts(
    query: Optional[str] = Query(None, description="Search by filename or transaction description"),
    file_type: Optional[str] = Query(None, description="Filter by file type (image or pdf)"),
    start_date: Optional[str] = Query(None, description="Filter by upload date (start)"),
    end_date: Optional[str] = Query(None, description="Filter by upload date (end)"),
    min_size: Optional[int] = Query(None, description="Minimum file size in bytes"),
    max_size: Optional[int] = Query(None, description="Maximum file size in bytes"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search and filter receipts across all transactions"""
    
    # Base query - only user's receipts
    receipts_query = db.query(ReceiptModel).filter(
        ReceiptModel.user_id == current_user.id
    )
    
    # Text search (filename, transaction description, or OCR text)
    if query:
        from models import Transaction as TransactionModel
        # Use left join to include receipts without transactions
        receipts_query = receipts_query.outerjoin(
            TransactionModel, ReceiptModel.transaction_id == TransactionModel.id
        ).filter(
            or_(
                ReceiptModel.original_filename.ilike(f"%{query}%"),
                TransactionModel.description.ilike(f"%{query}%"),
                ReceiptModel.ocr_text.ilike(f"%{query}%")
            )
        )
    
    # File type filter
    if file_type:
        if file_type.lower() == "image":
            receipts_query = receipts_query.filter(
                ReceiptModel.file_type.like("image/%")
            )
        elif file_type.lower() == "pdf":
            receipts_query = receipts_query.filter(
                ReceiptModel.file_type == "application/pdf"
            )
    
    # Date range filter
    if start_date:
        start = datetime.fromisoformat(start_date)
        receipts_query = receipts_query.filter(ReceiptModel.uploaded_at >= start)
    
    if end_date:
        end = datetime.fromisoformat(end_date)
        receipts_query = receipts_query.filter(ReceiptModel.uploaded_at <= end)
    
    # File size filter
    if min_size is not None:
        receipts_query = receipts_query.filter(ReceiptModel.file_size >= min_size)
    
    if max_size is not None:
        receipts_query = receipts_query.filter(ReceiptModel.file_size <= max_size)
    
    # Get total count
    total = receipts_query.count()
    
    # Apply pagination and ordering
    receipts = receipts_query.order_by(
        ReceiptModel.uploaded_at.desc()
    ).limit(limit).offset(offset).all()
    
    # Fetch transaction details for receipts that have transactions
    from models import Transaction as TransactionModel, Wallet, Category
    receipts_with_transactions = []
    
    for r in receipts:
        receipt_data = {
            "id": r.id,
            "transaction_id": r.transaction_id,
            "original_filename": r.original_filename,
            "file_type": r.file_type,
            "uploaded_at": r.uploaded_at,
            "transaction": None
        }
        
        # If receipt is linked to a transaction, include transaction details
        if r.transaction_id:
            transaction = db.query(TransactionModel).filter(
                TransactionModel.id == r.transaction_id
            ).first()
            
            if transaction:
                # Get wallet and category info
                wallet = db.query(Wallet).filter(Wallet.id == transaction.wallet_id).first()
                category = db.query(Category).filter(Category.id == transaction.category_id).first() if transaction.category_id else None
                
                receipt_data["transaction"] = {
                    "id": transaction.id,
                    "description": transaction.description,
                    "amount": transaction.amount,
                    "transaction_type": transaction.transaction_type,
                    "transaction_date": transaction.transaction_date.isoformat() if transaction.transaction_date else None,
                    "notes": transaction.notes,
                    "wallet": {
                        "id": wallet.id if wallet else None,
                        "name": wallet.name if wallet else None,
                        "currency": wallet.currency if wallet else None
                    },
                    "category": {
                        "id": category.id if category else None,
                        "name": category.name if category else None
                    } if category else None
                }
        
        receipts_with_transactions.append(receipt_data)
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "receipts": receipts_with_transactions
    }

