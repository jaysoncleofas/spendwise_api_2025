# SpendWise Backend API

FastAPI-based backend for SpendWise expense management application.

## Features

- 🔐 **User Authentication** - JWT-based authentication with secure password hashing
- 💰 **Wallet Management** - Multiple wallets with different currencies and balances
- 🏷️ **Category Management** - Organize transactions with custom categories
- 💳 **Transaction Tracking** - Income, Expense, and Transfer transactions
- 📊 **Advanced Analytics** - Comprehensive financial reports and insights
- 💵 **Budget System** - Monthly and fixed budgets with rollover support
- 🔁 **Recurring Transactions** - Automate bill payments and subscriptions
- 📷 **Receipt Management** - Upload receipts with OCR text extraction (text-only storage to save server space)
- 🏷️ **Tags System** - Flexible tagging for better transaction organization
- 💱 **Multi-Currency** - Support for different currencies with exchange rates
- 🔔 **Notifications** - Budget alerts and transaction reminders
- 📤 **Data Export** - Export transactions to CSV format
- 👤 **Profile Management** - User profiles with avatar upload support

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
CREATE DATABASE spendwise CHARACTER SET utf8o4 COLLATE utf8o4_unicode_ci;
```

### 4. Environment Variables
Create a `.env` file with the following variables:
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
- email (unique, indexed)
- username (unique, indexed)
- hashed_password
- full_name
- avatar_url
- home_currency
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
- budget_type (monthly/fixed)
- budget_start_date
- fixed_budget_spent
- budget_rollover
- rollover_balance
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
- recurring_transaction_id (for automated transactions)
- created_at
- updated_at

### RecurringTransaction
- id (primary key)
- user_id (foreign key)
- wallet_id (foreign key)
- category_id (foreign key)
- transaction_type
- amount
- description
- notes
- transfer_wallet_id
- frequency (daily/weekly/monthly/yearly)
- start_date
- end_date
- next_occurrence
- is_active
- created_at
- updated_at

### Receipt
- id (primary key)
- transaction_id (foreign key)
- user_id (foreign key)
- filename (original filename for reference)
- original_filename
- file_path (empty, files not stored)
- file_type
- file_size
- ocr_text (extracted text content stored)
- uploaded_at

### Tag
- id (primary key)
- user_id (foreign key)
- name
- color
- created_at

### TransactionTag
- id (primary key)
- transaction_id (foreign key)
- tag_id (foreign key)
- created_at

### Notification
- id (primary key)
- user_id (foreign key)
- type
- title
- message
- is_read
- related_id
- created_at

### ExchangeRate
- id (primary key)
- from_currency
- to_currency
- rate
- updated_at

### ExchangeRateHistory
- id (primary key)
- from_currency
- to_currency
- rate
- source
- recorded_at

## API Routes

### Authentication (`/api/auth`)
- POST `/register` - Register new user
- POST `/login` - Login (returns JWT token)
- GET `/me` - Get current user info

### Profile (`/api/profile`)
- GET `/` - Get user profile
- PUT `/` - Update user profile
- POST `/avatar` - Upload avatar image

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

### Budgets (`/api/budgets`)
- GET `/status` - Get budget status for all categories
- GET `/alerts` - Get budget alerts (warning, critical, danger)
- GET `/history/{category_id}` - Get budget history for a category
- PUT `/rollover/{category_id}` - Toggle budget rollover

### Recurring Transactions (`/api/recurring`)
- GET `/` - List all recurring transactions
- POST `/` - Create recurring transaction
- GET `/{id}` - Get specific recurring transaction
- PUT `/{id}` - Update recurring transaction
- DELETE `/{id}` - Delete recurring transaction
- PUT `/{id}/pause` - Pause recurring transaction
- PUT `/{id}/resume` - Resume recurring transaction
- POST `/process-due` - Process all due recurring transactions

### Receipts (`/api/receipts`)
- GET `/` - List all receipts with search and filters (includes transaction details)
- POST `/upload/{transaction_id}` - Upload receipt (extracts OCR text, stores text only)
- GET `/{id}` - Get specific receipt details
- GET `/{id}/download` - Get OCR text content as JSON (files not stored)
- DELETE `/{id}` - Delete receipt record
- GET `/transaction/{transaction_id}` - Get receipts for a specific transaction

### Tags (`/api/tags`)
- GET `/` - List all user tags
- POST `/` - Create new tag
- GET `/{id}` - Get specific tag
- PUT `/{id}` - Update tag
- DELETE `/{id}` - Delete tag
- GET `/analytics` - Get tag usage analytics
- GET `/top-tags` - Get most used tags

### Currency (`/api/currency`)
- GET `/convert` - Convert between currencies
- GET `/rates` - Get exchange rates
- GET `/rates/{from_currency}/{to_currency}` - Get specific rate
- POST `/rates` - Add/update exchange rate

### Notifications (`/api/notifications`)
- GET `/` - List all notifications
- GET `/unread-count` - Get unread notification count
- PUT `/{id}/read` - Mark notification as read
- PUT `/read-all` - Mark all notifications as read
- DELETE `/{id}` - Delete notification
- POST `/check-alerts` - Check for budget alerts

### Exports (`/api/exports`)
- GET `/transactions/csv` - Export transactions to CSV

## Authentication

This API uses JWT (JSON Web Tokens) for authentication.

### Getting a Token
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type:!

: application/x-www-form-urlencoded" \
  -d "username=your_username&password=your_password"
```

### Using the Token
Include the token in the Authorization header:
```bash
curl -X GET "http://localhost:8000/api/wallets" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Key Features Documentation

### Budget System
The budget system supports two types with different tracking logic:

#### Monthly Budgets
- Reset each month, with optional rollover of unused amounts
- Standard budget tracking: spending more = worse status
- Alerts generated when spending reaches:
  - 80-89% of budget (warning)
  - 90-99% of budget (critical)
  - 100%+ of budget (danger - exceeded)
  - Exactly 100% shows "Budget limit reached" message

#### Fixed Budgets
- One-time budget with a start date and no end date
- Positive progression tracking (like paying off a loan): more completion = better status
- Status levels:
  - 0-49%: Critical alert (low progress, need to catch up)
  - 50-79%: Warning alert (moderate progress, keep going)
  - 80-99%: Safe status (good progress)
  - 100%+: Completed status (green, goal achieved!)
- Completion alerts show positive messaging (e.g., "🎉 Budget completed!")

The system automatically differentiates between fixed and monthly budgets for appropriate status levels.

### Recurring Transactions
Automatically create transactions based on:
- **Frequency**: Daily, Weekly, Monthly, or Yearly
- **Start Date**: When to begin recurring
- **End Date**: Optional end date (null for indefinite)
- Auto-processing: Manually trigger or setup automated processing

### Receipt Management
- Upload receipts as images (JPEG, PNG, HEIC) or PDFs
- Automatic OCR text extraction (requires pytesseract)
- **Text-Only Storage**: Only OCR-extracted text is stored (files are not saved to disk)
- This saves server storage space while preserving searchable text content
- Search receipts by filename, transaction details, or OCR text
- Receipts can be linked to transactions
- Maximum file size: 10MB
- Returns OCR text as JSON when downloading

### Multi-Currency Support
- Each wallet can have its own currency
- Exchange rates are stored and can be updated manually
- Automatic currency conversion when viewing transactions

### Notification System
Notifications are generated for:
- Budget warnings, critical alerts, and overspending
- Low wallet balance alerts
- Bill payment reminders

## Development

### Database Migrations
Migrations are handled manually through SQL scripts in the `migrations/` directory.

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

## Dependencies

- **FastAPI** - Modern web framework
- **SQLAlchemy** - ORM for database operations
- **PyMySQL** - MySQL database driver
- **Python-JOSE** - JWT token handling
- **Passlib** - Password hashing with bcrypt
- **Python-Multipart** - File upload support
- **Pytesseract** - OCR text extraction
- **Pillow** - Image processing
- **Requests** - HTTP client for external APIs
- **Email-Validator** - Email validation

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

### OCR Not Working
- Install Tesseract OCR: `brew install tesseract` (Mac) or `apt-get install tesseract-ocr` (Linux)
- Ensure pytesseract and Pillow are installed

## API Documentation

Full interactive API documentation is available at `/docs` when the server is running.

## License

MIT License