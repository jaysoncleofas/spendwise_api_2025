#!/bin/bash

# Diagnostic script for 502 Bad Gateway errors
# Run this script on your server to identify the issue

set -e

echo "🔍 Diagnosing 502 Bad Gateway Error..."
echo "======================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables
APP_DIR="/home/forge/spendwise-api.on-forge.com"
SERVICE_NAME="spendwise-api"
BACKEND_PORT=8000

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

echo -e "${BLUE}=== Step 1: Check Application Directory ===${NC}"
if [ -d "$APP_DIR" ]; then
    print_status 0 "Application directory exists: $APP_DIR"
    cd "$APP_DIR"
else
    print_status 1 "Application directory NOT found: $APP_DIR"
    echo "Please update APP_DIR in this script or create the directory."
    exit 1
fi

echo ""
echo -e "${BLUE}=== Step 2: Check .env File ===${NC}"
if [ -f ".env" ]; then
    print_status 0 ".env file exists"
    # Check for required variables
    if grep -q "DATABASE_URL" .env && grep -q "SECRET_KEY" .env; then
        print_status 0 ".env contains required variables (DATABASE_URL, SECRET_KEY)"
    else
        print_status 1 ".env missing required variables"
        print_warning "Make sure DATABASE_URL and SECRET_KEY are set"
    fi
else
    print_status 1 ".env file NOT found"
    print_warning "Create .env file with DATABASE_URL, SECRET_KEY, etc."
    exit 1
fi

echo ""
echo -e "${BLUE}=== Step 3: Check Virtual Environment ===${NC}"
if [ -d "venv" ]; then
    print_status 0 "Virtual environment exists"
    if [ -f "venv/bin/activate" ]; then
        print_status 0 "Virtual environment is valid"
        source venv/bin/activate
    else
        print_status 1 "Virtual environment is corrupted"
        print_warning "Recreate venv: python3.9 -m venv venv"
        exit 1
    fi
else
    print_status 1 "Virtual environment NOT found"
    print_warning "Create venv: python3.9 -m venv venv"
    exit 1
fi

echo ""
echo -e "${BLUE}=== Step 4: Check Python and Dependencies ===${NC}"
if command -v python3.9 &> /dev/null; then
    PYTHON_VERSION=$(python3.9 --version)
    print_status 0 "Python 3.9 found: $PYTHON_VERSION"
else
    print_status 1 "Python 3.9 NOT found"
    print_warning "Install Python 3.9 first"
    exit 1
fi

# Check if uvicorn/gunicorn is installed
if python3 -c "import uvicorn" 2>/dev/null; then
    print_status 0 "uvicorn is installed"
else
    print_status 1 "uvicorn is NOT installed"
    print_warning "Install dependencies: pip install -r requirements.txt"
fi

if python3 -c "import gunicorn" 2>/dev/null; then
    print_status 0 "gunicorn is installed"
else
    print_warning "gunicorn not found (may not be required if using uvicorn directly)"
fi

echo ""
echo -e "${BLUE}=== Step 5: Check Database Connection ===${NC}"
if python3 -c "
from database import engine
try:
    conn = engine.connect()
    conn.close()
    print('success')
except Exception as e:
    print(f'failed: {e}')
    exit(1)
" 2>&1 | grep -q "success"; then
    print_status 0 "Database connection successful"
else
    DB_ERROR=$(python3 -c "
from database import engine
try:
    conn = engine.connect()
    conn.close()
except Exception as e:
    print(e)
" 2>&1)
    print_status 1 "Database connection failed"
    print_warning "Error: $DB_ERROR"
    print_info "Check your DATABASE_URL in .env file"
    print_info "Verify MySQL is running: sudo systemctl status mysql"
fi

echo ""
echo -e "${BLUE}=== Step 6: Check Systemd Service ===${NC}"
if systemctl list-unit-files | grep -q "$SERVICE_NAME.service"; then
    print_status 0 "Systemd service file exists"
    
    # Check service status
    SERVICE_STATUS=$(systemctl is-active "$SERVICE_NAME" 2>/dev/null || echo "inactive")
    if [ "$SERVICE_STATUS" = "active" ]; then
        print_status 0 "Service is ACTIVE (running)"
    else
        print_status 1 "Service is NOT active (status: $SERVICE_STATUS)"
        print_warning "Start service: sudo systemctl start $SERVICE_NAME"
    fi
    
    # Check if service is enabled
    if systemctl is-enabled "$SERVICE_NAME" &>/dev/null; then
        print_status 0 "Service is enabled (auto-start on boot)"
    else
        print_warning "Service is not enabled (won't start on boot)"
        print_info "Enable it: sudo systemctl enable $SERVICE_NAME"
    fi
else
    print_status 1 "Systemd service file NOT found"
    print_warning "Create service file: sudo nano /etc/systemd/system/$SERVICE_NAME.service"
    print_info "See SETUP_GUIDE.md for service file template"
fi

echo ""
echo -e "${BLUE}=== Step 7: Check Service Logs ===${NC}"
if systemctl list-unit-files | grep -q "$SERVICE_NAME.service"; then
    echo "Recent service logs:"
    echo "---"
    sudo journalctl -u "$SERVICE_NAME" -n 20 --no-pager 2>/dev/null | tail -10 || print_warning "Could not read service logs"
    echo "---"
    print_info "View full logs: sudo journalctl -u $SERVICE_NAME -f"
fi

echo ""
echo -e "${BLUE}=== Step 8: Check if Backend is Listening on Port ===${NC}"
if netstat -tuln 2>/dev/null | grep -q ":$BACKEND_PORT " || ss -tuln 2>/dev/null | grep -q ":$BACKEND_PORT "; then
    LISTENING_PROCESS=$(sudo lsof -i :$BACKEND_PORT 2>/dev/null | grep LISTEN || echo "unknown")
    print_status 0 "Something is listening on port $BACKEND_PORT"
    print_info "Process: $LISTENING_PROCESS"
else
    print_status 1 "Nothing is listening on port $BACKEND_PORT"
    print_warning "Backend application is not running or not listening on port $BACKEND_PORT"
fi

echo ""
echo -e "${BLUE}=== Step 9: Test Local Backend Connection ===${NC}"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:$BACKEND_PORT/health 2>/dev/null | grep -q "200"; then
    print_status 0 "Backend responds to health check on localhost:$BACKEND_PORT"
    HEALTH_RESPONSE=$(curl -s http://localhost:$BACKEND_PORT/health)
    print_info "Response: $HEALTH_RESPONSE"
else
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$BACKEND_PORT/health 2>/dev/null || echo "000")
    print_status 1 "Backend does NOT respond on localhost:$BACKEND_PORT (HTTP $HTTP_CODE)"
    print_warning "This is likely the root cause of the 502 error"
fi

echo ""
echo -e "${BLUE}=== Step 10: Check Nginx Configuration ===${NC}"
if sudo nginx -t 2>&1 | grep -q "syntax is ok"; then
    print_status 0 "Nginx configuration is valid"
else
    print_status 1 "Nginx configuration has errors"
    echo "Nginx test output:"
    sudo nginx -t
fi

# Check if nginx is configured to proxy to the right port
if [ -f "/etc/nginx/sites-available/spendwise-api.on-forge.com" ] || [ -f "/etc/nginx/sites-enabled/spendwise-api.on-forge.com" ]; then
    NGINX_CONFIG=$(sudo cat /etc/nginx/sites-enabled/spendwise-api.on-forge.com 2>/dev/null || sudo cat /etc/nginx/sites-available/spendwise-api.on-forge.com 2>/dev/null)
    if echo "$NGINX_CONFIG" | grep -q "proxy_pass.*127.0.0.1:$BACKEND_PORT"; then
        print_status 0 "Nginx is configured to proxy to port $BACKEND_PORT"
    else
        print_warning "Nginx proxy_pass might not be configured correctly"
        print_info "Check that proxy_pass points to http://127.0.0.1:$BACKEND_PORT"
    fi
fi

echo ""
echo -e "${BLUE}=== Step 11: Check Nginx Error Logs ===${NC}"
NGINX_ERROR_LOG="/var/log/nginx/spendwise-api-error.log"
if [ -f "$NGINX_ERROR_LOG" ]; then
    echo "Recent Nginx errors:"
    echo "---"
    sudo tail -10 "$NGINX_ERROR_LOG" 2>/dev/null || print_warning "Could not read Nginx error log"
    echo "---"
else
    print_warning "Nginx error log not found at $NGINX_ERROR_LOG"
    print_info "Check Forge dashboard for Nginx logs"
fi

echo ""
echo -e "${BLUE}=== Summary and Recommendations ===${NC}"
echo ""

# Test if we can manually start the app
if [ ! -z "$(command -v uvicorn)" ]; then
    print_info "To test the app manually, run:"
    echo "  cd $APP_DIR"
    echo "  source venv/bin/activate"
    echo "  uvicorn main:app --host 0.0.0.0 --port $BACKEND_PORT"
    echo ""
fi

print_info "Common fixes for 502 errors:"
echo "  1. Start the service: sudo systemctl start $SERVICE_NAME"
echo "  2. Check service logs: sudo journalctl -u $SERVICE_NAME -f"
echo "  3. Restart services: sudo systemctl restart $SERVICE_NAME && sudo systemctl reload nginx"
echo "  4. Verify .env file has correct DATABASE_URL"
echo "  5. Ensure MySQL is running: sudo systemctl status mysql"
echo ""

print_info "Useful commands:"
echo "  • Service status: sudo systemctl status $SERVICE_NAME"
echo "  • Service logs: sudo journalctl -u $SERVICE_NAME -f"
echo "  • Restart service: sudo systemctl restart $SERVICE_NAME"
echo "  • Nginx logs: sudo tail -f /var/log/nginx/spendwise-api-error.log"
echo "  • Test API: curl http://localhost:$BACKEND_PORT/health"
echo ""

echo "======================================"
echo "Diagnostic complete!"

