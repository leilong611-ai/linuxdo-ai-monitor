#!/bin/bash
# AI 情报雷达 - Cloudflare Tunnel 快速隧道
# 启动后会输出一个 https://xxx.trycloudflare.com 地址

echo "🌐 启动 Cloudflare Tunnel..."
echo "   本地服务: http://localhost:5001"
echo "   按 Ctrl+C 停止"
echo ""
cloudflared tunnel --url http://localhost:5001
