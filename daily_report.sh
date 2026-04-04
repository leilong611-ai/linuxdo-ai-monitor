#!/bin/bash
# AI 情报雷达 V3 - 每日定时任务
cd "$(dirname "$0")"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始生成日报..."

# 运行监控脚本
python3 monitor.py

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 日报完成"
