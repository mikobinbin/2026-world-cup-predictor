#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# World Cup 2026 Champion Predictor — 启动脚本
# ═══════════════════════════════════════════════════════════════════
# 用法: ./start.sh [端口]
# 默认端口: 8501

PORT=${1:-8501}

echo "🏆 启动世界杯冠军预测系统..."
echo "📍 访问地址: http://localhost:${PORT}"
echo "🌐 局域网: http://$(hostname -I | awk '{print $1}'):${PORT}"
echo ""

cd "$(dirname "$0")"

streamlit run src/dashboard/leaderboard.py \
  --server.port ${PORT} \
  --server.headless true \
  --browser.gatherUsageStats false \
  --server.address 0.0.0.0
