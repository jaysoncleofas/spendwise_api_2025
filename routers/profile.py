from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import User as UserSchema, UserUpdate, PasswordChange
from auth import get_current_user, get_password_hash, verify_password
import os
import uuid
from pathlib import Path

router = APIRouter()

# Create uploads directory for avatars if it doesn't exist
UPLOAD_DIR = Path("uploads/avatars")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.get("/me", response_model=UserSchema)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return current_user

@router.put("/me", response_model=UserSchema)
async def update_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile information"""
    
    # Check if email is being changed and if it's already taken
    if user_update.email and user_update.email != current_user.email:
        existing_user = db.query(User).filter(User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        current_user.email = user_update.email
    
    # Check if username is being changed and if it's already taken
    if user_update.username and user_update.username != current_user.username:
        existing_user = db.query(User).filter(User.username == user_update.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        current_user.username = user_update.username
    
    # Update other fields
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    
    if user_update.home_currency:
        current_user.home_currency = user_update.home_currency
    
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/me/avatar", response_model=UserSchema)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload user avatar"""
    
    # Validate file type - accept all common image formats including HEIC
    allowed_types = {
        "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp",
        "image/heic", "image/heif"  # Apple HEIC format
    }
    if file.content_type not in allowed_types and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image (JPG, PNG, GIF, WEBP, HEIC supported)"
        )
    
    # Validate file size (max 5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 5MB"
        )
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename
    
    # Delete old avatar if exists
    if current_user.avatar_url:
        old_file_path = Path(current_user.avatar_url)
        if old_file_path.exists():
            try:
                old_file_path.unlink()
            except Exception as e:
    
    # Save new avatar
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Update user avatar URL
    current_user.avatar_url = str(file_path)
    db.commit()
    db.refresh(current_user)
    
    return current_user

@router.delete("/me/avatar", response_model=UserSchema)
async def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete user avatar"""
    
    if not current_user.avatar_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No avatar to delete"
        )
    
    # Delete avatar file
    avatar_path = Path(current_user.avatar_url)
    if avatar_path.exists():
        try:
            avatar_path.unlink()
        except Exception as e:
    
    # Update user
    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)
    
    return current_user

@router.post("/me/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}

