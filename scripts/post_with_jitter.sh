#!/bin/bash
# 最大30分のランダム遅延を加えてmake postを実行
DELAY=$((RANDOM % 1800))
echo "[jitter] $(date '+%Y-%m-%d %H:%M:%S') 待機 ${DELAY}秒..."
sleep $DELAY
echo "[jitter] $(date '+%Y-%m-%d %H:%M:%S') 投稿開始"
cd /Users/siromaje/Documents/affiliate-bot && make post
