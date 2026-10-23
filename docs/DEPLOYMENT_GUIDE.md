# Taskflow Pro — Production Deployment & Operations Guide

## 1. Hardware & System Requirements
- **Operating System**: Linux (Ubuntu 22.04 LTS / Debian 12) or Windows Server 2022.
- **Python**: Version 3.10 or higher.
- **Memory**: Minimum 512 MB RAM (1 GB recommended for concurrent workloads).
- **Disk**: 10 GB SSD storage.

## 2. Production Service Configuration (systemd)
Create `/etc/systemd/system/taskflow.service`:
```ini
[Unit]
Description=Taskflow Pro Production Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/taskflow
Environment="PATH=/var/www/taskflow/.venv/bin"
Environment="SECRET_KEY=production-secure-random-key"
Environment="DATABASE_URL=sqlite:////var/www/taskflow/database.db"
ExecStart=/var/www/taskflow/.venv/bin/gunicorn --workers 4 --bind 127.0.0.1:5000 run:app

[Install]
WantedBy=multi-user.target
```

## 3. Reverse Proxy Configuration (Nginx)
```nginx
server {
    listen 80;
    server_name taskflow.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name taskflow.example.com;

    ssl_certificate /etc/letsencrypt/live/taskflow.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/taskflow.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/taskflow/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }
}
```

## 4. SQLite Database Backup Strategy
Use SQLite online backup API or hourly cron snapshots:
```bash
sqlite3 /var/www/taskflow/database.db ".backup '/backups/taskflow-$(date +%Y%m%d_%H%M%S).db'"
```
