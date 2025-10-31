#!/bin/bash

# SpendWise Backend Deployment Script for Laravel Forge
# Run this script on your server after uploading the code

set -e  # Exit on error

echo "🚀 Starting SpendWise Backend Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${GREEN}✓ Working directory: $SCRIPT_DIR${NC}"

# Check if Python 3.9 is installed
if ! command -v python3.9 &> /dev/null; then
    echo -e "${RED}✗ Python 3.9 is not installed!${NC}"
    echo -e "${YELLOW}Please install Python 3.9 first:${NC}"
    echo ""
    echo "sudo apt update"
    echo "sudo apt install -y software-properties-common"
    echo "sudo add-apt-repository -y ppa:deadsnakes/ppa"
    echo "sudo apt update"
    echo "sudo apt install -y python3.9 python3.9-venv python3.9-dev"
    echo ""
    echo -e "${YELLOW}Or see SETUP_GUIDE.md for full instructions${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Python 3.9 found: $(python3.9 --version)${NC}"
fi

# Step 1: Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    python3.9 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Step 2: Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Step 3: Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel --quiet

# Step 4: Install dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install -r requirements.txt --quiet
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Step 5: Create upload directories
echo -e "${YELLOW}Creating upload directories...${NC}"
mkdir -p uploads/avatars uploads/receipts
chmod -R 755 uploads/
echo -e "${GREEN}✓ Upload directories created${NC}"

# Step 6: Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${RED}⚠ WARNING: .env file not found!${NC}"
    echo -e "${YELLOW}Please create a .env file with the following variables:${NC}"
    echo ""
    echo "DATABASE_URL=mysql+pymysql://forge:BJgHQouHLcKSIqGubdln@127.0.0.1:3306/spendwise"
    echo "SECRET_KEY=your-super-secret-key-change-this"
    echo "ALGORITHM=HS256"
    echo "ACCESS_TOKEN_EXPIRE_MINUTES=1440"
    echo ""
    echo -e "${YELLOW}Run: nano .env${NC}"
    exit 1
else
    echo -e "${GREEN}✓ .env file found${NC}"
fi

# Step 7: Test database connection
echo -e "${YELLOW}Testing database connection...${NC}"
python3 -c "
from database import engine
try:
    conn = engine.connect()
    conn.close()
    print('✓ Database connection successful')
except Exception as e:
    print(f'✗ Database connection failed: {e}')
    exit(1)
" || {
    echo -e "${RED}✗ Database connection test failed${NC}"
    echo -e "${YELLOW}Please check your DATABASE_URL in .env file${NC}"
    exit 1
}

# Step 8: Run migrations if needed
if [ -f "migrations/add_fixed_budget_fields.py" ]; then
    echo -e "${YELLOW}Running database migrations...${NC}"
    python migrations/add_fixed_budget_fields.py || echo -e "${YELLOW}⚠ Migration may have already run${NC}"
fi

# Step 9: Create tables
echo -e "${YELLOW}Creating database tables...${NC}"
python3 -c "
from database import Base, engine
from models import *
Base.metadata.create_all(bind=engine)
print('✓ Database tables created/verified')
"

echo ""
echo -e "${GREEN}✅ Deployment preparation complete!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Make sure your .env file is configured correctly"
echo "2. Test the application: uvicorn main:app --host 0.0.0.0 --port 8000"
echo "3. Set up systemd service (see SETUP_GUIDE.md)"
echo "4. Configure Nginx in Laravel Forge"
echo ""
echo -e "${GREEN}For detailed instructions, see SETUP_GUIDE.md${NC}"

