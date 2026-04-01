"""オーケストレーター：全エージェントを統括する"""
import json
import os
import re
import sys
import time
import random
import argparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta
from pathlib import Path
from agents import writer, poster, analyst, buzz_analyzer, hook_optimizer, reply_poster
from agents import insights_analyzer, web_scraper, thread_poster, conversation_agent
from utils import threads_api
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
try:
    from line_notify import notify as line_notify
except ImportError:
    line_notify = None
try:
    from slack_notify import notify as slack_notify
except ImportError:
    slack_notify = None

# アフィリエイトURL辞書（楽天 + Amazon、post_countで交互切り替え）
# Amazonリンク形式: https://www.amazon.co.jp/dp/[ASIN]?tag=rikocosmelab-22
PRODUCT_AFFILIATE_URLS = {
    # ── 洗顔・クレンジング ──────────────────────────
    "キュレル泡洗顔": {
        "name": "キュレル 潤浸保湿 泡洗顔料",
        "amazon": "https://www.amazon.co.jp/dp/B0096HZBGG?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "バルクオム": {
        "name": "BULK HOMME THE FACE WASH",
        "amazon": "https://www.amazon.co.jp/dp/B00O2P9ALO?tag=rikocosmelab-22",
