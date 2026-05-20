#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# 部署前检查脚本 — 验证依赖和环境
# ═══════════════════════════════════════════════════════════════════
echo "🔍 部署前环境检查..."
echo ""

ERRORS=0

# 1. Python版本
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
echo -n "✅ Python版本: ${PYTHON_VERSION} "
if [[ $(echo "$PYTHON_VERSION >= 3.9" | bc) -eq 1 ]]; then
    echo ">= 3.9 ✓"
else
    echo "< 3.9 ✗ — 需要 Python 3.9+"
    ERRORS=$((ERRORS+1))
fi

# 2. pip可用
if python3 -m pip --version &>/dev/null; then
    echo "✅ pip 可用"
else
    echo "❌ pip 不可用"
    ERRORS=$((ERRORS+1))
fi

# 3. 检查关键依赖
echo ""
echo "📦 检查依赖包..."
for pkg in streamlit pandas numpy matplotlib altair pillow requests; do
    if python3 -c "import ${pkg}" 2>/dev/null; then
        VER=$(python3 -c "import ${pkg}; print(${pkg}.__version__)")
        echo "  ✅ ${pkg}: ${VER}"
    else
        echo "  ❌ ${pkg}: 未安装"
        ERRORS=$((ERRORS+1))
    fi
done

# 4. 端口检查
echo ""
echo -n "📡 端口 8501 状态: "
if lsof -ti:8501 &>/dev/null; then
    echo "已被占用（PID: $(lsof -ti:8501))"
    echo "   → 使用其他端口：./start.sh 8502"
else
    echo "可用 ✓"
fi

# 5. 内存检查
MEM=$(free -m 2>/dev/null | awk '/Mem:/ {print $2}' || sysctl -n hw.memsize 2>/dev/null | awk '{print $1/1024/1024}')
if [[ -n "$MEM" ]]; then
    echo ""
    echo "💾 可用内存: ${MEM}MB"
fi

# 总结
echo ""
if [[ $ERRORS -eq 0 ]]; then
    echo "✅ 所有检查通过！可以运行：./start.sh"
else
    echo "❌ 有 ${ERRORS} 个问题需要修复"
    echo ""
    echo "安装缺失依赖："
    echo "  pip install -r requirements.txt"
fi
