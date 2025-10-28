# SpendWise Backend API

FastAPI-based backend for SpendWise expense management application.

## Setup

### 1. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Database
Create a MySQL database:
```sql
CREATE DATABASE spendwise CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 4. Environment Variables
Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

Edit `.env`:
```env
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/spendwise
SECRET_KEY=your-super-secret-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 5. Run the Application
```bash
uvicorn main:app --reload
```

The API will be available at:
- API: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc

## Database Models

### User
- id (primary key)
- email (unique)
- username (unique)
- hashed_password
- full_name
- created_at
- updated_at

### Wallet
- id (primary key)
- user_id (foreign key)
- name
- description
- balance
- currency
- icon
- color
- created_at
- updated_at

### Category
- id (primary key)
- user_id (foreign key)
- name
- description
- icon
- color
- budget_limit
- created_at
- updated_at

### Transaction
- id (primary key)
- wallet_id (foreign key)
- category_id (foreign key)
- transaction_type (income/expense/transfer)
- amount
- description
- notes
- transaction_date
- transfer_wallet_id (for transfers)
- created_at
- updated_at

## API Routes

### Authentication (`/api/auth`)
- POST `/register` - Register new user
- POST `/login` - Login (returns JWT token)
- GET `/me` - Get current user info

### Wallets (`/api/wallets`)
- GET `/` - List all user wallets
- POST `/` - Create new wallet
- GET `/{id}` - Get specific wallet
- PUT `/{id}` - Update wallet
- DELETE `/{id}` - Delete wallet
- POST `/{id}/add-money` - Add money to wallet

### Categories (`/api/categories`)
- GET `/` - List all user categories
- POST `/` - Create new category
- GET `/{id}` - Get specific category
- PUT `/{id}` - Update category
- DELETE `/{id}` - Delete category

### Transactions (`/api/transactions`)
- GET `/` - List transactions (with filters)
  - Query params: wallet_id, category_id, transaction_type, start_date, end_date
- POST `/` - Create new transaction
- GET `/{id}` - Get specific transaction
- PUT `/{id}` - Update transaction
- DELETE `/{id}` - Delete transaction

### Analytics (`/api/analytics`)
- GET `/summary/today` - Today's financial summary
- GET `/summary/week` - This week's summary
- GET `/summary/month` - This month's summary
- GET `/summary/custom` - Custom period summary
- GET `/wallets/summary` - All wallets summary
- GET `/categories/top-expenses` - Top expense categories

## Authentication

This API uses JWT (JSON Web Tokens) for authentication.

### Getting a Token
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your_username&password=your_password"
```

### Using the Token
Include the token in the Authorization header:
```bash
curl -X GET "http://localhost:8000/api/wallets" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Development

### Database Migrations (Optional - for future)
```bash
# Initialize alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

### Running Tests
```bash
pytest
```

### Code Style
```bash
# Format code
black .

# Check linting
flake8 .
```

## Production Deployment

### Using Gunicorn
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

### Using Docker
```dockerfile
FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production
```env
DATABASE_URL=mysql+pymysql://user:pass@db-host:3306/spendwise
SECRET_KEY=very-secure-secret-key-for-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

## Security Considerations

1. **Change the SECRET_KEY** in production
2. Use **HTTPS** in production
3. Set up proper **CORS** policies
4. Use **environment variables** for sensitive data
5. Implement **rate limiting**
6. Add **request validation**
7. Set up **logging and monitoring**

## Performance Optimization

1. Add database indexes on frequently queried fields
2. Implement caching (Redis)
3. Use connection pooling
4. Optimize database queries
5. Add pagination for large datasets

## Troubleshooting

### Database Connection Error
- Check MySQL is running
- Verify credentials in `.env`
- Ensure database exists

### Import Errors
- Activate virtual environment
- Reinstall requirements: `pip install -r requirements.txt`

### Token Errors
- Check SECRET_KEY is set correctly
- Verify token is not expired
- Ensure token is sent in Authorization header

## API Documentation

Full interactive API documentation is available at `/docs` when the server is running.


