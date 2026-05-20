# 🖥️ 服务器部署指南

> 适用于 **Ubuntu 20.04+ / Debian 11+ / CentOS 8+**
> 配套 Nginx 反向代理 + Systemd 守护进程 + Let's Encrypt HTTPS

---

## 环境要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 系统 | Ubuntu 20.04 / Debian 11 | Ubuntu 22.04 LTS |
| CPU | 1核 | 2核+ |
| 内存 | 1GB | 2GB+ |
| 带宽 | 5Mbps | 10Mbps+ |
| Python | 3.9+ | 3.10+ |
| 磁盘 | 5GB | 10GB+ |

---

## 第一步：上传项目到服务器

### 方法A：SCP（本地macOS/Linux）

```bash
# 把整个文件夹传到服务器
scp -r ~/Desktop/world_cup_predictor user@your-server-ip:/opt/

# 或压缩后传输（更快）
tar -czvf wc_predictor.tar.gz ~/Desktop/world_cup_predictor
scp wc_predictor.tar.gz user@your-server-ip:/tmp/
ssh user@your-server-ip "mkdir -p /opt/world_cup_predictor && tar -xzvf /tmp/wc_predictor.tar.gz -C /opt/"
```

### 方法B：Git（推荐）

```bash
# 在服务器上克隆
git clone https://github.com/your-repo/world_cup_predictor.git /opt/world_cup_predictor

# 或在本地先推送到GitHub再拉取
```

---

## 第二步：服务器环境准备

### 2.1 系统更新

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2 安装 Python 和 pip

```bash
# Ubuntu / Debian
sudo apt install -y python3 python3-pip python3-venv

# CentOS / RHEL
sudo dnf install -y python3 python3-pip python3-venv
```

### 2.3 安装 Node.js（可选，用于前端构建）

```bash
# 不需要，Streamlit是纯Python
```

### 2.4 防火墙开放端口

```bash
# 开放8501端口（Streamlit默认）
sudo ufw allow 8501/tcp comment 'World Cup Predictor'

# 如果用Nginx代理，同时开放80/443
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 启用防火墙
sudo ufw enable
sudo ufw status
```

---

## 第三步：安装项目依赖

### 3.1 创建虚拟环境（推荐）

```bash
cd /opt/world_cup_predictor

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 验证安装
python -c "import streamlit; print(f'Streamlit {streamlit.__version__} ✓')"
```

### 3.2 全局安装（不推荐）

```bash
sudo pip3 install -r requirements.txt
```

---

## 第四步：测试运行

```bash
cd /opt/world_cup_predictor
source venv/bin/activate

# 临时运行测试（Ctrl+C可停止）
streamlit run src/dashboard/leaderboard.py --server.port 8501 --server.headless true
```

浏览器访问 `http://服务器IP:8501` 确认正常运行后，按 `Ctrl+C` 停止。

---

## 第五步：配置 Systemd 守护进程

### 5.1 创建服务文件

```bash
sudo nano /etc/systemd/system/wc-predictor.service
```

写入以下内容：

```ini
[Unit]
Description=World Cup 2026 Champion Predictor
Documentation=https://github.com/your-repo/world_cup_predictor
After=network.target

[Service]
Type=simple

# 运行用户（建议创建专用用户）
User=www-data
Group=www-data

# 工作目录
WorkingDirectory=/opt/world_cup_predictor

# 激活虚拟环境
Environment="PATH=/opt/world_cup_predictor/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# 启动命令
ExecStart=/opt/world_cup_predictor/venv/bin/streamlit run src/dashboard/leaderboard.py \
    --server.port 8501 \
    --server.headless true \
    --server.address 127.0.0.1 \
    --server.enableCORS false \
    --server.enableXsrfProtection true

# 重启策略
Restart=always
RestartSec=5

# 日志
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wc-predictor

[Install]
WantedBy=multi-user.target
```

### 5.2 创建专用运行用户（安全加固）

```bash
# 创建专用用户（无登录shell，更安全）
sudo useradd -r -s /usr/sbin/nologin -d /nonexistent -M wc-predictor

# 修改项目权限
sudo chown -R wc-predictor:wc-predictor /opt/world_cup_predictor
```

### 5.3 启用并启动服务

```bash
# 重新加载systemd配置
sudo systemctl daemon-reload

# 启用开机自启
sudo systemctl enable wc-predictor

# 启动服务
sudo systemctl start wc-predictor

# 查看状态
sudo systemctl status wc-predictor
```

正常状态应显示：`Active: active (running)`

### 5.4 常用管理命令

```bash
# 查看日志（实时）
sudo journalctl -u wc-predictor -f

# 查看最近日志
sudo journalctl -u wc-predictor -n 50

# 重启服务
sudo systemctl restart wc-predictor

# 停止服务
sudo systemctl stop wc-predictor

# 取消开机自启
sudo systemctl disable wc-predictor
```

---

## 第六步：配置 Nginx 反向代理

### 6.1 安装 Nginx

```bash
sudo apt install -y nginx
```

### 6.2 创建 Nginx 站点配置

```bash
sudo nano /etc/nginx/sites-available/wc-predictor
```

写入以下内容：

```nginx
# HTTP -> HTTPS 重定向（推荐）
server {
    listen 80;
    server_name your-domain.com;   # 替换为你的域名或服务器IP

    # 强制跳转到HTTPS（配置完SSL后取消注释）
    # return 301 https://$server_name$request_uri;
}

# HTTPS 配置（配置SSL证书后启用）
server {
    listen 443 ssl http2;
    server_name your-domain.com;   # 替换为你的域名

    # SSL证书（Let's Encrypt 自动申请则自动配置）
    # ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    # ssl_protocols TLSv1.2 TLSv1.3;
    # ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

    # 日志
    access_log /var/log/nginx/wc-predictor_access.log;
    error_log /var/log/nginx/wc-predictor_error.log;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket支持（Streamlit实时通信）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 超时配置
        proxy_read_timeout 86400;
        proxy_connect_timeout 60s;

        # 缓存控制
        proxy_temp_file_write_size 64k;
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # 静态资源（如果有）
    location /static {
        alias /opt/world_cup_predictor/static;
        expires 30d;
    }
}
```

### 6.3 启用站点

```bash
# 启用配置
sudo ln -s /etc/nginx/sites-available/wc-predictor /etc/nginx/sites-enabled/

# 测试配置语法
sudo nginx -t

# 重载Nginx
sudo systemctl reload nginx
```

---

## 第七步：配置 HTTPS（Let's Encrypt 免费证书）

### 7.1 安装 Certbot

```bash
# Ubuntu 22.04+
sudo apt install -y certbot python3-certbot-nginx

# CentOS
# sudo dnf install -y certbot python3-certbot-nginx
```

### 7.2 申请证书

```bash
# 如果用域名（自动配置Nginx）
sudo certbot --nginx -d your-domain.com

# 如果用IP（仅生成证书，不自动配置）
sudo certbot certonly --standalone -d your-domain.com --agree-tos -m your-email@example.com

# IP访问方案（需手动编辑Nginx配置添加SSL部分）
```

### 7.3 自动续期

```bash
# 测试自动续期
sudo certbot renew --dry-run

# Let's Encrypt 证书90天有效期，自动续期已配置
```

### 7.4 证书过期后手动续期

```bash
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

---

## 第八步：安全加固

### 8.1 禁用root登录（SSH）

```bash
sudo nano /etc/ssh/sshd_config
# 设置：PermitRootLogin no
sudo systemctl restart sshd
```

### 8.2 配置 Fail2ban 防暴力破解

```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 8.3 设置 swap（内存不足时防OOM）

```bash
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 第九步：域名解析（如使用域名）

在域名服务商（阿里云/Cloudflare/etc.）添加DNS记录：

| 记录类型 | 主机记录 | 记录值 |
|---------|---------|--------|
| A | @ | 服务器IP |
| A | www | 服务器IP |

等待5-10分钟生效。

---

## 第十步：验证部署

```bash
# 检查服务状态
sudo systemctl status wc-predictor

# 检查端口
sudo lsof -i :8501

# 检查Nginx
sudo systemctl status nginx

# 检查防火墙
sudo ufw status
```

浏览器访问测试：

| 方式 | 地址 |
|------|------|
| 直接IP | `http://服务器IP:8501` |
| Nginx HTTP | `http://your-domain.com` |
| Nginx HTTPS | `https://your-domain.com` |

---

## 故障排查

### 页面无法访问

```bash
# 1. 检查服务是否运行
sudo systemctl status wc-predictor

# 2. 检查端口是否监听
sudo lsof -i :8501

# 3. 检查防火墙
sudo ufw status

# 4. 检查日志
sudo journalctl -u wc-predictor -n 30
```

### 502 Bad Gateway

```bash
# Nginx无法连接到Streamlit
# 检查Streamlit是否运行
sudo systemctl status wc-predictor
# 重启
sudo systemctl restart wc-predictor
```

### SSL证书申请失败

```bash
# 确认域名已解析
ping your-domain.com

# 确认80端口开放（Let's Encrypt需要）
sudo ufw allow 80/tcp

# 使用standalone模式
sudo certbot certonly --standalone -d your-domain.com
```

### 中文显示乱码

```bash
# 在systemd服务文件中添加环境变量
sudo nano /etc/systemd/system/wc-predictor.service
# 在[Service]下添加：
Environment="LANG=en_US.UTF-8"
Environment="LC_ALL=en_US.UTF-8"

sudo systemctl daemon-reload
sudo systemctl restart wc-predictor
```

### 内存不足（OOM）

```bash
# 查看内存使用
free -h

# 减少Streamlit并发进程数
# 在ExecStart中添加 --server.maxUploadSize 50
```

---

## 完整启动命令汇总

```bash
# === 一行命令完成部署（Ubuntu 22.04）===
sudo apt update && sudo apt install -y python3-pip nginx certbot python3-certbot-nginx ufw && \
sudo ufw allow 8501/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && \
cd /opt && sudo apt install -y python3-venv && \
python3 -m venv world_cup_predictor/venv && \
source world_cup_predictor/venv/bin/activate && \
pip install --upgrade pip && \
pip install -r world_cup_predictor/requirements.txt
```

---

## 快捷管理脚本

在服务器上创建，方便日常操作：

```bash
# 写入 /usr/local/bin/wc
sudo tee /usr/local/bin/wc << 'EOF'
#!/bin/bash
case "$1" in
  start)   sudo systemctl start wc-predictor ;;
  stop)    sudo systemctl stop wc-predictor ;;
  restart) sudo systemctl restart wc-predictor ;;
  status)  sudo systemctl status wc-predictor ;;
  log)     sudo journalctl -u wc-predictor -f ;;
  *)       echo "用法: wc {start|stop|restart|status|log}" ;;
esac
EOF
sudo chmod +x /usr/local/bin/wc

# 用法：
# wc start   — 启动
# wc stop    — 停止
# wc restart — 重启
# wc status  — 查看状态
# wc log     — 实时日志
```
