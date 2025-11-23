#!/bin/bash
# Serve the Westside LA Events app via Tailscale

set -e

MODE="${1:-serve}"  # 'serve' for tailnet-only, 'funnel' for public internet

echo "=========================================="
echo "Westside LA Events - Tailscale Deployment"
echo "=========================================="
echo ""
echo "Mode: $MODE"
echo ""

# Security status
echo "🔒 Security Features:"
echo "  ✅ Rate limiting enabled (30-60 req/min per endpoint)"
echo "  ✅ Admin dashboard protected with login"
echo "  ✅ Security headers (XSS, CSP, etc.)"
echo "  ✅ Input sanitization on all user inputs"
echo "  ✅ HTTPS with automatic Tailscale certificates"
echo ""

# Security warning for funnel mode
if [ "$MODE" = "funnel" ]; then
    echo "⚠️  WARNING: FUNNEL MODE - PUBLIC INTERNET ACCESS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "This will expose your app to the ENTIRE INTERNET."
    echo ""
    echo "Security measures in place:"
    echo "  ✅ Rate limiting (prevents abuse)"
    echo "  ✅ Admin dashboard requires login"
    echo "  ✅ Input validation and sanitization"
    echo "  ✅ Security headers protection"
    echo ""
    echo "Recommendations for public deployment:"
    echo "  • Set ADMIN_PASSWORD_HASH environment variable"
    echo "  • Monitor logs for suspicious activity"
    echo "  • Consider Google Cloud Run for 24/7 uptime"
    echo ""
    echo "Admin Login (Development):"
    echo "  Username: admin"
    echo "  Password: admin123"
    echo "  ⚠️  CHANGE THESE IN PRODUCTION!"
    echo ""
    read -p "Continue with public deployment? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Aborted."
        exit 1
    fi
    echo ""
else
    echo "Mode: Tailnet-only (Private)"
    echo "Only devices on your Tailscale network can access this app."
    echo ""
fi

# Check if tailscale is running
if ! tailscale status &>/dev/null; then
    echo "Error: Tailscale is not running. Please start Tailscale first."
    exit 1
fi

# Get Tailscale hostname
HOSTNAME=$(tailscale status --json | grep -o '"HostName":"[^"]*"' | cut -d'"' -f4)
TAILNET=$(tailscale status --json | grep -o '"MagicDNSSuffix":"[^"]*"' | cut -d'"' -f4)

echo "Your app will be available at:"
echo "  https://${HOSTNAME}.${TAILNET}"
echo ""

# Start the app in the background
echo "Starting FastHTML app on port 8000..."
micromamba run -n la uvicorn src.web.app:app --host 127.0.0.1 --port 8000 &
APP_PID=$!

# Wait for app to start
sleep 3

# Start Tailscale serve or funnel
if [ "$MODE" = "funnel" ]; then
    echo "Starting Tailscale Funnel (public internet access)..."
    tailscale funnel --bg 8000
else
    echo "Starting Tailscale Serve (tailnet-only access)..."
    tailscale serve --bg 8000
fi

echo ""
echo "✓ App is now running!"
echo ""
echo "🌐 Access your app at:"
echo "   https://${HOSTNAME}.${TAILNET}"
echo ""
if [ "$MODE" = "funnel" ]; then
    echo "🔐 Admin Dashboard:"
    echo "   https://${HOSTNAME}.${TAILNET}/admin/analytics"
    echo "   Username: admin"
    echo "   Password: admin123 (change in production!)"
    echo ""
fi
echo "To stop:"
echo "  - Press Ctrl+C to stop this script"
if [ "$MODE" = "funnel" ]; then
    echo "  - Run: tailscale funnel reset"
else
    echo "  - Run: tailscale serve reset"
fi
echo "  - Run: kill $APP_PID"
echo ""

# Keep script running
wait $APP_PID
