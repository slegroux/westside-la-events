# Tailscale Deployment Guide

## Overview

Deploy your Westside LA Events app from your local machine using Tailscale. This guide covers secure deployment for sharing with friends and limited groups.

## What is Tailscale?

Tailscale creates a secure mesh VPN network using WireGuard protocol. It allows you to:
- Expose local services without opening firewall ports
- Get automatic HTTPS certificates
- Control access through your identity provider
- Share services privately or publicly

## Quick Start

```bash
# For private access (Tailnet only - recommended)
./scripts/serve_tailscale.sh serve

# For public internet access
./scripts/serve_tailscale.sh funnel
```

## Deployment Modes

### Tailscale Serve (Private - Recommended for Friends)

**Best for**: Sharing with trusted friends/colleagues on your Tailscale network

**Security**: Very secure - only devices you've authorized on your Tailnet can access

**How it works**:
1. Friends install Tailscale and join your Tailnet
2. You run `./scripts/serve_tailscale.sh serve`
3. They access `https://your-machine.your-tailnet.ts.net`

**Advantages**:
- ✅ Zero trust security model
- ✅ End-to-end encryption
- ✅ No public exposure
- ✅ Free forever
- ✅ Automatic HTTPS

### Tailscale Funnel (Public)

**Best for**: Sharing with people NOT on your Tailnet

**Security**: Public internet access with built-in protections

**How it works**:
1. You run `./scripts/serve_tailscale.sh funnel`
2. Anyone can access `https://your-machine.your-tailnet.ts.net`
3. Tailscale provides rate limiting and DDoS protection

**Advantages**:
- ✅ Automatic HTTPS
- ✅ Built-in rate limiting
- ✅ No DNS/domain setup needed
- ✅ Free for personal use

**Limitations**:
- ⚠️ Your machine must stay on
- ⚠️ Limited to 100 concurrent connections (Tailscale limit)
- ⚠️ Your home IP is exposed to Tailscale

## Security Features

The app now includes comprehensive security:

### 1. Rate Limiting
- **Search endpoints**: 30 requests/minute
- **API endpoints**: 60 requests/minute
- **Admin endpoints**: 20 requests/minute
- **Scraper trigger**: 10 requests/hour

Prevents abuse and DoS attacks.

### 2. Admin Authentication
- Protected `/admin/analytics` dashboard
- Session-based authentication
- Password hashing (SHA-256)

**Default credentials (Development)**:
- Username: `admin`
- Password: `admin123`

**⚠️ MUST CHANGE IN PRODUCTION!**

### 3. Security Headers
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: enabled
- Content-Security-Policy: configured for maps/fonts
- Referrer-Policy: strict-origin-when-cross-origin

### 4. Input Validation
- All user inputs sanitized
- HTML escaping
- Length limits
- SQL injection prevention

### 5. HTTPS
- Automatic via Tailscale
- Valid certificates
- No configuration needed

## Production Setup

### Change Admin Password

```bash
# Generate password hash
python -c "import hashlib; password='YOUR_SECURE_PASSWORD'; print(hashlib.sha256(password.encode()).hexdigest())"

# Set environment variable
export ADMIN_PASSWORD_HASH="your_generated_hash"

# Run the app
./scripts/serve_tailscale.sh funnel
```

### Set Custom Admin Username (Optional)

```bash
export ADMIN_USERNAME="your_username"
export ADMIN_PASSWORD_HASH="your_password_hash"
./scripts/serve_tailscale.sh funnel
```

### Monitor Access

```bash
# View Tailscale status
tailscale status

# View Tailscale logs
journalctl -u tailscaled -f

# View app logs
# (App prints to stdout when running via script)
```

## Inviting Friends to Your Tailnet

### Option 1: Direct Invite (Recommended)

1. Go to https://login.tailscale.com/admin/settings/users
2. Click "Invite users"
3. Send invite link to friends
4. They install Tailscale and join your network
5. They can access your app at `https://your-machine.your-tailnet.ts.net`

### Option 2: Use Funnel (No Tailscale Required for Friends)

1. Run `./scripts/serve_tailscale.sh funnel`
2. Share the public URL: `https://your-machine.your-tailnet.ts.net`
3. Anyone can access without Tailscale

## Comparison: Tailscale vs Cloud Run

| Feature | Tailscale Serve | Tailscale Funnel | Google Cloud Run |
|---------|-----------------|------------------|------------------|
| **Setup Time** | 1 minute | 1 minute | 5 minutes |
| **Cost** | Free | Free | Free tier |
| **Security** | Excellent (private) | Good (public) | Excellent |
| **Uptime** | Machine must be on | Machine must be on | 24/7 |
| **Performance** | Local hardware | Local hardware | Google infrastructure |
| **Domain** | Tailscale domain | Tailscale domain | Custom domain |
| **Scalability** | Limited | 100 connections | Auto-scales |
| **Best For** | Private demos | Small groups | Production |

## Troubleshooting

### Port Already in Use

```bash
# Find process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
# Edit the script to change port 8000
```

### Tailscale Not Running

```bash
# Start Tailscale
sudo systemctl start tailscaled

# Login if needed
tailscale login
```

### Can't Access from Other Devices

**For Serve mode**:
- Ensure the other device is on your Tailnet
- Run `tailscale status` to verify

**For Funnel mode**:
- Check if Funnel is enabled: `tailscale funnel status`
- Verify Funnel is allowed in your Tailscale admin console

### App Won't Start

```bash
# Check micromamba environment
micromamba env list

# Verify dependencies
micromamba run -n la python -c "import fasthtml; print('OK')"

# Check for errors
micromamba run -n la uvicorn src.web.app:app --host 127.0.0.1 --port 8000
```

## Security Best Practices

### For Private Sharing (Serve)

1. ✅ Only invite trusted people to your Tailnet
2. ✅ Review connected devices regularly
3. ✅ Remove devices you no longer recognize
4. ✅ Monitor Tailscale access logs

### For Public Sharing (Funnel)

1. ✅ Change default admin password immediately
2. ✅ Set environment variables for credentials
3. ✅ Monitor logs for suspicious activity
4. ✅ Consider Google Cloud Run for always-on service
5. ✅ Be aware your machine's IP is visible to Tailscale
6. ✅ Test rate limiting with realistic traffic
7. ✅ Consider setting up monitoring/alerting

## Stopping the Service

```bash
# Method 1: Use Ctrl+C if running in foreground

# Method 2: Reset Tailscale serve/funnel
tailscale serve reset   # or: tailscale funnel reset

# Method 3: Kill the app process
pkill -f uvicorn

# Method 4: Kill specific PID (shown in script output)
kill <PID>
```

## Alternative: Docker + Tailscale

For easier management, you can run in Docker:

```dockerfile
# Dockerfile (example)
FROM python:3.10
# ... your app setup ...
CMD ["uvicorn", "src.web.app:app", "--host", "127.0.0.1", "--port", "8000"]
```

```bash
# Run with Docker
docker run -d --name westside-events -p 8000:8000 westside-events

# Expose via Tailscale
tailscale serve 8000
```

## When to Use Each Approach

### Use Tailscale Serve When:
- Sharing with 2-10 trusted people
- You want maximum privacy
- Friends can install Tailscale
- Testing/development scenarios
- Short-term demos

### Use Tailscale Funnel When:
- Sharing with people who can't install Tailscale
- Need a quick public URL
- Temporary public access (hours/days)
- Small audience (<100 people)
- You're okay with your machine being on

### Use Google Cloud Run When:
- Need 24/7 uptime
- Large audience (100+ people)
- Production deployment
- Want auto-scaling
- Need custom domain
- Want managed infrastructure

## Resources

- [Tailscale Documentation](https://tailscale.com/kb/)
- [Tailscale Serve Docs](https://tailscale.com/kb/1242/tailscale-serve/)
- [Tailscale Funnel Docs](https://tailscale.com/kb/1223/funnel/)
- [WireGuard Protocol](https://www.wireguard.com/)
- [Google Cloud Run Deployment](docs/DEPLOYMENT.md)

## FAQ

**Q: Is Tailscale safe?**
A: Yes, very safe. Uses WireGuard (audited crypto), zero-trust model, and end-to-end encryption.

**Q: Can Tailscale see my traffic?**
A: No, traffic is encrypted end-to-end. Tailscale only handles connection coordination.

**Q: What's the connection limit?**
A: Funnel: 100 concurrent connections. Serve: No hard limit (limited by your machine).

**Q: Do I need to pay?**
A: Personal use is free. Teams have paid plans with extra features.

**Q: Can I use a custom domain?**
A: Yes, with Tailscale HTTPS certificates or your own DNS/certificates.

**Q: What if my machine sleeps?**
A: The service stops. Consider Google Cloud Run for always-on deployment.

**Q: Is my IP address exposed?**
A: With Funnel, your machine's IP is visible to Tailscale. With Serve, only to your Tailnet devices.
