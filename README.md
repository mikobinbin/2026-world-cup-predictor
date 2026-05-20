# 🏆 2026 FIFA World Cup Champion Predictor
# 2026美加墨世界杯冠军预测系统

> 基于 Elo 评分 + 球员矩阵 + Monte Carlo 模拟 + 玄学因子的综合预测系统
> 52支球队 | 25支真实阵容数据 | 6大维度建模

---

## 功能特性

| Tab | 内容 |
|-----|------|
| 🏆 冠军概率榜 | TOP3 Hero卡片 + 概率进度条 + 完整排名 |
| 📊 因子拆解 | Elo/年龄/经验/状态/教练/玄学六大维度分析 |
| 👥 球员矩阵 | 关键球员实力评分与对比 |
| 🔮 玄学视角 | 彩票悖论 + 小组赛波动 + 淘汰赛命运 + 三重境界/道德经/易经 |
| 📋 球队画像 | 52支球队完整档案 |
| ⚔️ H2H对战预测 | 任意两队历史交锋与胜率预测 |

---

## 一键部署

### macOS / Linux 本地运行

```bash
cd world_cup_predictor

# 安装依赖（推荐使用虚拟环境）
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

pip install -r requirements.txt

# 启动（默认 8501 端口）
./start.sh

# 指定端口，例如 8080
./start.sh 8080
```

### Windows

```powershell
cd world_cup_predictor
pip install -r requirements.txt
streamlit run src/dashboard/leaderboard.py --server.port 8501
```

---

## 服务器部署（Nginx + Systemd）

### 1. 安装依赖

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
pip3 install -r requirements.txt

# 防火墙开放端口
sudo ufw allow 8501
```

### 2. 配置 Systemd 服务

```bash
sudo nano /etc/systemd/system/wc-predictor.service
```

写入以下内容：

```ini
[Unit]
Description=World Cup 2026 Champion Predictor
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/world_cup_predictor
ExecStart=/opt/world_cup_predictor/venv/bin/streamlit run src/dashboard/leaderboard.py --server.port 8501 --server.headless true --server.address 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3. 安装并启动

```bash
# 复制项目到服务器
sudo cp -r world_cup_predictor /opt/

# 安装依赖
cd /opt/world_cup_predictor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable wc-predictor
sudo systemctl start wc-predictor

# 检查状态
sudo systemctl status wc-predictor
```

### 4. Nginx 反向代理（可选，支持域名 + HTTPS）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

---

## 访问地址

| 环境 | 地址 |
|------|------|
| 本地 macOS/Linux | `http://localhost:8501` |
| 局域网（同一WiFi） | `http://<本机IP>:8501` |
| 服务器（直接IP） | `http://<服务器IP>:8501` |
| 服务器（Nginx代理） | `http://your-domain.com` |

查看本机局域网IP：
```bash
# macOS
ifconfig | grep "inet " | grep -v 127.0.0.1

# Linux
hostname -I
```

---

## 数据说明

- **阵容数据**：来自 Wikipedia 2026世界杯各队参赛名单（25/52支球队）
- **Elo评分**：FiveThirtyEight 历史积累 + 2026最新更新
- **其余27支**：基于同组别历史数据模拟
- **玄学因子**：彩票悖论 / 小组赛波动 / 淘汰赛命运 + 三重境界/道德经/易经哲学框架

---

## 目录结构

```
world_cup_predictor/
├── src/
│   ├── dashboard/
│   │   └── leaderboard.py     # 主应用（启动入口）
│   ├── models/
│   │   ├── player_scoring.py   # 球员评分
│   │   ├── team_scoring.py     # 球队评分
│   │   └── mystic_factor.py     # 玄学因子引擎
│   └── simulation/
│       └── monte_carlo.py       # Monte Carlo模拟
├── data/
│   ├── elo_cache_2026.json         # Elo评分数据
│   ├── wc2026_players_processed.json # 处理后球员数据
│   └── wc2026_squads_wikipedia.json  # Wikipedia阵容数据
├── .streamlit/
│   └── config.toml             # Streamlit主题配置
├── assets/
│   └── custom.css             # 自定义深色主题CSS
├── config.py                  # 全局配置
├── requirements.txt           # Python依赖
├── start.sh                   # 一键启动脚本
└── README.md                  # 本文件
```

---

## 更新预测数据

```bash
# 更新Elo评分
python scripts/elo_scraper.py

# 更新阵容数据
python scripts/wikipedia_squads.py
python scripts/ingest_wikipedia_squads.py
```

---

## 常见问题

**Q: 页面显示空白？**
> 可能是端口被占用，换一个端口：`./start.sh 8502`

**Q: 依赖安装失败？**
> 确保 Python 版本 >= 3.9：`python3 --version`

**Q: 手机无法访问？**
> 检查服务器防火墙：`sudo ufw allow 8501`

**Q: 中文显示乱码？**
> 确保服务器系统支持 UTF-8，Linux 可添加：`export LANG=en_US.UTF-8`
