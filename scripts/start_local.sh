#!/bin/bash
# Start local development server with broadcast mode for remote access via Tailscale

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  LA Events Aggregator - Local Server${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if micromamba is available
if ! command -v micromamba &> /dev/null; then
    echo -e "${RED}Error: micromamba not found${NC}"
    echo "Please install micromamba: https://mamba.readthedocs.io/en/latest/installation.html"
    exit 1
fi

# Check if 'la' environment exists
if ! micromamba env list | grep -q "la"; then
    echo -e "${RED}Error: 'la' environment not found${NC}"
    echo "Please create it with: micromamba create -n la python=3.10 -y"
    exit 1
fi

# Check if port 8000 is already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Port 8000 is already in use${NC}"
    echo -e "Attempting to kill existing process...\n"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# Check if database exists
if [ ! -f "data/events.db" ]; then
    echo -e "${YELLOW}Warning: Database not found at data/events.db${NC}"
    echo -e "Creating database...\n"
    micromamba run -n la python -c "from src.data.database import Database; Database('data/events.db')"
fi

# Count events in database
EVENT_COUNT=$(micromamba run -n la python -c "from src.data.database import Database; db = Database('data/events.db'); print(len(db.get_events()))" 2>/dev/null || echo "0")

echo -e "${GREEN}✓${NC} Environment: micromamba 'la'"
echo -e "${GREEN}✓${NC} Database: data/events.db (${EVENT_COUNT} events)"
echo -e "${GREEN}✓${NC} Server mode: Broadcast (0.0.0.0) - accessible via Tailscale\n"

# Get Tailscale IP if available
TAILSCALE_IP=""
if command -v tailscale &> /dev/null; then
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "")
fi

# Get local IP
LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "localhost")

echo -e "${BLUE}Starting server...${NC}\n"
echo -e "Access the application at:"
echo -e "  ${GREEN}Local:${NC}      http://127.0.0.1:8000"
echo -e "  ${GREEN}Network:${NC}    http://${LOCAL_IP}:8000"
if [ -n "$TAILSCALE_IP" ]; then
    echo -e "  ${GREEN}Tailscale:${NC}  http://${TAILSCALE_IP}:8000"
fi
echo -e "\n${YELLOW}Press Ctrl+C to stop the server${NC}\n"
echo -e "${BLUE}========================================${NC}\n"

# Start the server
micromamba run -n la uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
