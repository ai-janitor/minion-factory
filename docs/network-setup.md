# Network Tier Setup — Cross-Machine Agent Comms

Connect agents across machines (e.g., Mac coordinator ↔ Debian GPU server).

## Architecture

```
Mac (coordinator)                    Debian GPU server
┌──────────────────┐                ┌──────────────────┐
│ minion network   │  ◄── HTTPS ──► │ minion poll      │
│ serve :8377      │                │ --agent X        │
│ ~/.minion/       │                │ ~/.minion/       │
│   network.db     │                │   (no server)    │
│   tls/cert.pem   │                │                  │
└──────────────────┘                └──────────────────┘
```

The **coordinator** runs on one machine. All others connect to it.

---

## 1. Coordinator Setup (Mac Side)

### Generate TLS Certificate

```bash
minion network gen-cert
# Creates: ~/.minion/tls/cert.pem + ~/.minion/tls/key.pem
```

### Set Environment Variables

```bash
# Generate a shared secret (run once, share with all machines)
export MINION_CLUSTER_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Save this token: $MINION_CLUSTER_TOKEN"
```

Add to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
export MINION_CLUSTER_TOKEN="<your-generated-token>"
```

### Start the Server

Foreground (testing):
```bash
minion network serve --port 8377
```

With pm2 (persistent):
```bash
pm2 start "minion network serve --port 8377" --name minion-network
pm2 save
```

With systemd (Linux coordinator):
```ini
# /etc/systemd/system/minion-network.service
[Unit]
Description=Minion Network Coordinator
After=network.target

[Service]
Type=simple
User=<your-user>
Environment=MINION_CLUSTER_TOKEN=<your-token>
ExecStart=/usr/local/bin/minion network serve --port 8377
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now minion-network
```

### Verify It's Running

```bash
curl -k -H "Authorization: Bearer $MINION_CLUSTER_TOKEN" https://localhost:8377/health
# {"status": "ok", "timestamp": "..."}
```

---

## 2. Remote Agent Setup (Debian GPU Server)

### Install Minion

```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install minion-factory
uv tool install git+https://github.com/ai-janitor/minion-factory.git
```

### Set Environment Variables

Add to `~/.bashrc`:

```bash
export MINION_NETWORK_URL="https://<mac-ip>:8377"
export MINION_CLUSTER_TOKEN="<same-token-as-coordinator>"
# For self-signed certs during dev:
export MINION_NETWORK_INSECURE=1
```

### Register and Poll

```bash
# Initialize a project workspace
cd ~/projects/<your-project>
minion init

# Register (writes to all 3 tiers: local, system global, API global)
minion register --name arc-gpu-coder --class coder

# Start polling (checks all tiers)
minion poll --agent arc-gpu-coder
```

---

## 3. Firewall / Network

### Port

The coordinator listens on **TCP 8377** (configurable via `--port`).

### LAN Setup

Open the port on the coordinator:

```bash
# macOS (if firewall enabled)
# System Preferences → Security → Firewall → Options → allow minion

# Linux (ufw)
sudo ufw allow 8377/tcp
```

Verify connectivity from remote:

```bash
curl -k -H "Authorization: Bearer $MINION_CLUSTER_TOKEN" https://<mac-ip>:8377/health
```

### WAN Considerations

For agents across the internet (not recommended for initial setup):
- Use a VPN (WireGuard/Tailscale) to keep traffic on a private network
- Or expose port 8377 via reverse proxy with proper TLS (not self-signed)
- Never expose plain HTTP over the internet

**For LAN-only use, self-signed TLS is sufficient.**

---

## 4. Token Generation

The cluster token authenticates all agents to the coordinator. Every machine uses the same token.

```bash
# Generate (run once)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Or with openssl
openssl rand -base64 32
```

Store it in:
- `~/.bashrc` / `~/.zshrc` on each machine as `MINION_CLUSTER_TOKEN`
- The systemd unit file (if using systemd)
- pm2 ecosystem config (if using pm2)

**Do not commit the token to git.**

---

## 5. Troubleshooting

### Can't Connect

```bash
# From remote machine, test raw connectivity:
curl -k https://<coordinator-ip>:8377/health

# If timeout: firewall blocking port 8377
# If connection refused: server not running
# If SSL error: cert issue (try with -k flag)
```

### Auth Fails (401)

```bash
# Verify token matches:
echo $MINION_CLUSTER_TOKEN  # on coordinator
echo $MINION_CLUSTER_TOKEN  # on remote — must be identical

# Test with explicit header:
curl -k -H "Authorization: Bearer <token>" https://<ip>:8377/health
```

### Messages Not Arriving

1. Is the recipient polling? `minion poll --agent <name>` must be running
2. Is the recipient registered on the network? `minion network who`
3. Check the offline outbox: `minion network outbox` — messages may be queued
4. Verify 3-tier routing: `minion comms send global --from X --to Y --message "test"`

### Offline Queue Behavior

When the network server is unreachable:
- `send_global()` queues the message to `~/.minion/outbox/<timestamp>.json`
- Next `minion poll` cycle drains the outbox (retries delivery)
- Messages stay queued until the server comes back
- Check queue: `minion network outbox`
- Files are plain JSON — you can inspect them directly in `~/.minion/outbox/`

---

## 6. End-to-End Example

### Mac (coordinator + agent)

```bash
# Terminal 1: Start network server
export MINION_CLUSTER_TOKEN="my-secret-token"
minion network serve --port 8377

# Terminal 2: Register and send
export MINION_CLUSTER_TOKEN="my-secret-token"
cd ~/projects/my-project
minion register --name mac-coder --class coder
minion comms send global --from mac-coder --to debian-coder --message "Build the GPU kernels"
```

### Debian GPU Server

```bash
# Set env
export MINION_NETWORK_URL="https://192.168.1.100:8377"
export MINION_CLUSTER_TOKEN="my-secret-token"
export MINION_NETWORK_INSECURE=1  # self-signed cert

# Register and poll
cd ~/projects/my-project
minion init
minion register --name debian-coder --class coder
minion poll --agent debian-coder
# → receives: "Build the GPU kernels" from mac-coder
```
