#!/bin/bash

# Quick fix script for CORS and 502 errors
# Run this on your server: bash fix-cors-and-502.sh

set -e

echo "🔧 Fixing CORS and 502 Errors..."
echo "================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

APP_DIR="/home/forge/spendwise-api.on-forge.com"
SERVICE_NAME="spendwise-api"
cd "$APP_DIR" || { echo "Error: Cannot access $APP_DIR"; exit 1; }

# Step 1: Check .env file
echo -e "${BLUE}Step 1: Checking .env file...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env file not found!${NC}"
    echo -e "${YELLOW}Creating .env file template...${NC}"
    echo "Please edit .env with your actual values:"
    echo ""
    echo "DATABASE_URL=mysql+pymysql://forge:password@127.0.0.1:3306/spendwise"
    echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null || echo 'your-secret-key-here')"
    echo "ALGORITHM=HS256"
    echo "ACCESS_TOKEN_EXPIRE_MINUTES=1440"
    exit 1
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Step 2: Check virtual environment
echo -e "${BLUE}Step 2: Checking virtual environment...${NC}"
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found, creating...${NC}"
    python3.9 -m venv venv
fi
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment ready${NC}"

# Step 3: Check systemd service exists
echo -e "${BLUE}Step 3: Checking systemd service...${NC}"
if [ ! -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    echo -e "${YELLOW}⚠ Systemd service file not found${NC}"
    echo -e "${YELLOW}Create it manually or see 502_TROUBLESHOOTING.md${NC}"
    echo ""
    echo "For now, checking if backend can start manually..."
else
    echo -e "${GREEN}✓ Systemd service file exists${NC}"
    
    # Check backend status
    echo -e "${BLUE}Step 4: Checking backend service status...${NC}"
    if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}✓ Backend service is running${NC}"
    else
        echo -e "${RED}✗ Backend service is NOT running${NC}"
        echo -e "${YELLOW}Attempting to start backend service...${NC}"
        
        # Check logs first for errors
        echo "Recent error logs:"
        sudo journalctl -u "$SERVICE_NAME" -n 10 --no-pager | tail -5 || true
        
        sudo systemctl start "$SERVICE_NAME"
        sleep 3
        
        if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
            echo -e "${GREEN}✓ Backend service started successfully${NC}"
        else
            echo -e "${RED}✗ Failed to start backend service${NC}"
            echo ""
            echo -e "${YELLOW}Recent service logs:${NC}"
            sudo journalctl -u "$SERVICE_NAME" -n 30 --no-pager
            echo ""
            echo -e "${YELLOW}Common issues:${NC}"
            echo "  - Check .env file has correct DATABASE_URL"
            echo "  - Ensure MySQL is running: sudo systemctl status mysql"
            echo "  - Verify all dependencies installed: pip install -r requirements.txt"
            echo ""
            echo -e "${YELLOW}Try diagnosing: bash diagnose-502.sh${NC}"
            exit 1
        fi
    fi
fi

# Step 5: Test backend locally
echo -e "${BLUE}Step 5: Testing backend on localhost...${NC}"
MAX_RETRIES=5
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend responds on localhost:8000${NC}"
        HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
        echo "  Response: $HEALTH_RESPONSE"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo -e "${YELLOW}  Waiting for backend to start... (attempt $RETRY_COUNT/$MAX_RETRIES)${NC}"
            sleep 2
        else
            echo -e "${RED}✗ Backend not responding on localhost:8000${NC}"
            echo ""
            echo -e "${YELLOW}Troubleshooting steps:${NC}"
            echo "  1. Check if service is running: sudo systemctl status $SERVICE_NAME"
            echo "  2. View service logs: sudo journalctl -u $SERVICE_NAME -n 50"
            echo "  3. Check if port is in use: sudo lsof -i :8000"
            echo "  4. Try manual start: source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000"
            echo ""
            echo -e "${YELLOW}Run diagnostic: bash diagnose-502.sh${NC}"
            exit 1
        fi
    fi
done

# Step 6: Check Nginx
echo -e "${BLUE}Step 6: Checking Nginx configuration...${NC}"
if sudo nginx -t 2>&1 | grep -q "syntax is ok"; then
    echo -e "${GREEN}✓ Nginx configuration is valid${NC}"
else
    echo -e "${RED}✗ Nginx configuration has errors${NC}"
    sudo nginx -t
    echo ""
    echo -e "${YELLOW}Fix Nginx configuration errors before continuing${NC}"
    exit 1
fi

# Step 7: Restart services
echo -e "${BLUE}Step 7: Restarting services...${NC}"
echo -e "${YELLOW}Restarting backend service...${NC}"
sudo systemctl restart "$SERVICE_NAME"
sleep 2

echo -e "${YELLOW}Reloading Nginx...${NC}"
sudo systemctl reload nginx

# Step 8: Final verification
echo -e "${BLUE}Step 8: Final verification...${NC}"
sleep 2
if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is responding after restart${NC}"
else
    echo -e "${RED}✗ Backend not responding after restart${NC}"
    echo -e "${YELLOW}Check logs: sudo journalctl -u $SERVICE_NAME -n 50${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Services restarted successfully!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Test public endpoint: curl https://spendwise-api.on-forge.com/health"
echo "2. Visit API docs: https://spendwise-api.on-forge.com/docs"
echo "3. Monitor logs: sudo journalctl -u $SERVICE_NAME -f"
echo "4. Check Nginx logs: sudo tail -f /var/log/nginx/spendwise-api-error.log"
echo ""
echo -e "${YELLOW}If issues persist, run: bash diagnose-502.sh${NC}"
echo -e "${YELLOW}See 502_TROUBLESHOOTING.md for detailed guide${NC}"


