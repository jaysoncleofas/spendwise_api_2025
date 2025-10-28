from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db
from models import User, ExchangeRate as ExchangeRateModel, ExchangeRateHistory as ExchangeRateHistoryModel, Wallet
from auth import get_current_user
from pydantic import BaseModel
from datetime import datetime, timedelta
import requests

router = APIRouter()

# Free exchange rate API configuration
EXCHANGE_RATE_API_KEY = "your_api_key_here"  # Sign up at https://exchangerate-api.com for free
EXCHANGE_RATE_API_URL = "https://api.exchangerate-api.com/v4/latest/"

# Common currencies
CURRENCIES = [
    {"code": "USD", "name": "US Dollar", "symbol": "$"},
    {"code": "EUR", "name": "Euro", "symbol": "€"},
    {"code": "GBP", "name": "British Pound", "symbol": "£"},
    {"code": "JPY", "name": "Japanese Yen", "symbol": "¥"},
    {"code": "CAD", "name": "Canadian Dollar", "symbol": "C$"},
    {"code": "AUD", "name": "Australian Dollar", "symbol": "A$"},
    {"code": "CHF", "name": "Swiss Franc", "symbol": "CHF"},
    {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥"},
    {"code": "INR", "name": "Indian Rupee", "symbol": "₹"},
    {"code": "MXN", "name": "Mexican Peso", "symbol": "MX$"},
    {"code": "PHP", "name": "Philippine Peso", "symbol": "₱"},
    {"code": "SGD", "name": "Singapore Dollar", "symbol": "S$"},
    {"code": "HKD", "name": "Hong Kong Dollar", "symbol": "HK$"},
    {"code": "KRW", "name": "South Korean Won", "symbol": "₩"},
    {"code": "THB", "name": "Thai Baht", "symbol": "฿"},
    {"code": "VND", "name": "Vietnamese Dong", "symbol": "₫"},
]

class ExchangeRateBase(BaseModel):
    from_currency: str
    to_currency: str
    rate: float

class ExchangeRate(ExchangeRateBase):
    id: int
    
    class Config:
        from_attributes = True

class ConvertRequest(BaseModel):
    amount: float
    from_currency: str
    to_currency: str

class HomeCurrencyUpdate(BaseModel):
    home_currency: str

@router.get("/currencies")
def get_currencies():
    """Get list of supported currencies"""
    return CURRENCIES

@router.get("/home-currency")
def get_home_currency(
    current_user: User = Depends(get_current_user)
):
    """Get user's home currency"""
    return {"home_currency": current_user.home_currency or "USD"}

@router.put("/home-currency")
def update_home_currency(
    data: HomeCurrencyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's home currency"""
    
    user = db.query(User).filter(User.id == current_user.id).first()
    user.home_currency = data.home_currency
    db.commit()
    db.refresh(user)
    
    return {"home_currency": user.home_currency}

@router.get("/rates", response_model=List[ExchangeRate])
def get_exchange_rates(
    db: Session = Depends(get_db)
):
    """Get all exchange rates"""
    
    rates = db.query(ExchangeRateModel).all()
    return rates

@router.get("/rate/{from_currency}/{to_currency}")
def get_exchange_rate(
    from_currency: str,
    to_currency: str,
    db: Session = Depends(get_db)
):
    """Get exchange rate between two currencies"""
    
    if from_currency == to_currency:
        return {"from_currency": from_currency, "to_currency": to_currency, "rate": 1.0}
    
    rate = db.query(ExchangeRateModel).filter(
        ExchangeRateModel.from_currency == from_currency,
        ExchangeRateModel.to_currency == to_currency
    ).first()
    
    if not rate:
        # Try inverse rate
        inverse_rate = db.query(ExchangeRateModel).filter(
            ExchangeRateModel.from_currency == to_currency,
            ExchangeRateModel.to_currency == from_currency
        ).first()
        
        if inverse_rate:
            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": 1.0 / inverse_rate.rate
            }
        
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    
    return {
        "from_currency": rate.from_currency,
        "to_currency": rate.to_currency,
        "rate": rate.rate
    }

@router.post("/convert")
def convert_currency(
    data: ConvertRequest,
    db: Session = Depends(get_db)
):
    """Convert amount from one currency to another"""
    
    if data.from_currency == data.to_currency:
        return {
            "amount": data.amount,
            "from_currency": data.from_currency,
            "to_currency": data.to_currency,
            "converted_amount": data.amount,
            "rate": 1.0
        }
    
    rate_info = get_exchange_rate(data.from_currency, data.to_currency, db)
    converted_amount = data.amount * rate_info["rate"]
    
    return {
        "amount": data.amount,
        "from_currency": data.from_currency,
        "to_currency": data.to_currency,
        "converted_amount": round(converted_amount, 2),
        "rate": rate_info["rate"]
    }

@router.post("/rates", response_model=ExchangeRate)
def create_or_update_rate(
    rate_data: ExchangeRateBase,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    source: str = "manual"
):
    """Create or update an exchange rate (admin function)"""
    
    existing_rate = db.query(ExchangeRateModel).filter(
        ExchangeRateModel.from_currency == rate_data.from_currency,
        ExchangeRateModel.to_currency == rate_data.to_currency
    ).first()
    
    if existing_rate:
        existing_rate.rate = rate_data.rate
        db.commit()
        db.refresh(existing_rate)
    else:
        new_rate = ExchangeRateModel(
            from_currency=rate_data.from_currency,
            to_currency=rate_data.to_currency,
            rate=rate_data.rate
        )
        db.add(new_rate)
        db.commit()
        db.refresh(new_rate)
        existing_rate = new_rate
    
    # Save to history
    history_record = ExchangeRateHistoryModel(
        from_currency=rate_data.from_currency,
        to_currency=rate_data.to_currency,
        rate=rate_data.rate,
        source=source
    )
    db.add(history_record)
    db.commit()
    
    return existing_rate

@router.get("/summary")
def get_wallet_summary_in_home_currency(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get total balance across all wallets in home currency"""
    
    home_currency = current_user.home_currency or "USD"
    wallets = db.query(Wallet).filter(Wallet.user_id == current_user.id).all()
    
    total_in_home_currency = 0.0
    wallet_details = []
    
    for wallet in wallets:
        if wallet.currency == home_currency:
            converted_balance = wallet.balance
        else:
            try:
                rate_info = get_exchange_rate(wallet.currency, home_currency, db)
                converted_balance = wallet.balance * rate_info["rate"]
            except:
                converted_balance = wallet.balance  # Fallback if rate not found
        
        total_in_home_currency += converted_balance
        wallet_details.append({
            "id": wallet.id,
            "name": wallet.name,
            "balance": wallet.balance,
            "currency": wallet.currency,
            "converted_balance": round(converted_balance, 2)
        })
    
    return {
        "home_currency": home_currency,
        "total_balance": round(total_in_home_currency, 2),
        "wallets": wallet_details
    }

@router.post("/rates/fetch-latest")
def fetch_latest_rates(
    base_currency: str = "USD",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch latest exchange rates from external API and update database"""
    
    try:
        # Using free exchangerate-api.com (no API key required for basic usage)
        response = requests.get(f"{EXCHANGE_RATE_API_URL}{base_currency}", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "rates" not in data:
            raise HTTPException(status_code=500, detail="Invalid API response")
        
        rates = data["rates"]
        updated_count = 0
        
        # Update rates for common currencies
        for currency_info in CURRENCIES:
            to_currency = currency_info["code"]
            if to_currency in rates and to_currency != base_currency:
                rate = rates[to_currency]
                
                # Update or create rate
                existing_rate = db.query(ExchangeRateModel).filter(
                    ExchangeRateModel.from_currency == base_currency,
                    ExchangeRateModel.to_currency == to_currency
                ).first()
                
                if existing_rate:
                    existing_rate.rate = rate
                else:
                    new_rate = ExchangeRateModel(
                        from_currency=base_currency,
                        to_currency=to_currency,
                        rate=rate
                    )
                    db.add(new_rate)
                
                # Save to history
                history_record = ExchangeRateHistoryModel(
                    from_currency=base_currency,
                    to_currency=to_currency,
                    rate=rate,
                    source="api"
                )
                db.add(history_record)
                updated_count += 1
        
        db.commit()
        
        return {
            "success": True,
            "base_currency": base_currency,
            "updated_count": updated_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch rates: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating rates: {str(e)}")

@router.get("/rates/history/{from_currency}/{to_currency}")
def get_rate_history(
    from_currency: str,
    to_currency: str,
    days: int = Query(30, le=365, description="Number of days of history"),
    db: Session = Depends(get_db)
):
    """Get historical exchange rates for a currency pair"""
    
    start_date = datetime.now() - timedelta(days=days)
    
    history = db.query(ExchangeRateHistoryModel).filter(
        ExchangeRateHistoryModel.from_currency == from_currency,
        ExchangeRateHistoryModel.to_currency == to_currency,
        ExchangeRateHistoryModel.recorded_at >= start_date
    ).order_by(ExchangeRateHistoryModel.recorded_at.asc()).all()
    
    return {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "days": days,
        "history": [
            {
                "rate": h.rate,
                "source": h.source,
                "recorded_at": h.recorded_at.isoformat()
            }
            for h in history
        ]
    }

@router.get("/rates/trends")
def get_rate_trends(
    home_currency: Optional[str] = None,
    days: int = Query(30, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get exchange rate trends for user's currencies"""
    
    base_currency = home_currency or current_user.home_currency or "USD"
    
    # Get user's wallet currencies
    wallets = db.query(Wallet).filter(Wallet.user_id == current_user.id).all()
    user_currencies = list(set([w.currency for w in wallets if w.currency != base_currency]))
    
    start_date = datetime.now() - timedelta(days=days)
    trends = {}
    
    for currency in user_currencies:
        # Get latest rate
        latest = db.query(ExchangeRateHistoryModel).filter(
            ExchangeRateHistoryModel.from_currency == base_currency,
            ExchangeRateHistoryModel.to_currency == currency
        ).order_by(desc(ExchangeRateHistoryModel.recorded_at)).first()
        
        # Get oldest rate in period
        oldest = db.query(ExchangeRateHistoryModel).filter(
            ExchangeRateHistoryModel.from_currency == base_currency,
            ExchangeRateHistoryModel.to_currency == currency,
            ExchangeRateHistoryModel.recorded_at >= start_date
        ).order_by(ExchangeRateHistoryModel.recorded_at.asc()).first()
        
        if latest and oldest:
            change = ((latest.rate - oldest.rate) / oldest.rate) * 100
            trends[currency] = {
                "current_rate": latest.rate,
                "previous_rate": oldest.rate,
                "change_percent": round(change, 2),
                "trend": "up" if change > 0 else "down" if change < 0 else "stable"
            }
    
    return {
        "base_currency": base_currency,
        "period_days": days,
        "trends": trends
    }

