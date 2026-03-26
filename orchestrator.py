"""オーケストレーター：全エージェントを統括する"""
import json
import re
import sys
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from agents import researcher, writer, poster, analyst, buzz_analyzer, hook_optimizer, reply_poster
from agents import insights_analyzer, web_scraper




sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from line_notify import notify as line_notify




PRODUCT_AFFILIATE_URLS = {
        "RF美顔器":      "https://a.r10.to/h5yZS4",
        "美顔器":        "https://a.r10.to/h5yZS4",
        "日焼け止め":    "https://a.r10.to/h5b4am",
        "ダルバ":        "https://a.r10.to/h5b4am",
        "ORBIS":         "https://a.r10.to/h8N8vu",
        "オルビス":      "https://a.r10.to/h8N8vu",
        "アクアフォース": "https://a.r10.to/h8N8vu",
        "MISSHA":        "https://a.r10.to/hktN94",
        "ミシャ":        "https://a.r10.to/hktN94",
        "アンプル":      "https://a.r10.to/hktN94",
        "肌ラボ":        "https://a.r10.to/h8N8Bv",
        "ヒアルロン":    "https://a.r10.to/h8N8Bv",
        "アネッサ":      "https://a.r10.to/hkWt3Y",
        "ANESSA":        "https://a.r10.to/hkWt3Y",
}
AFFILIATE_URL = "https://a.r10.to/h5yZS4"  # フォールバック用




def get_affiliate_url(product_name: str) -> str:
    for keyword, url in PRODUCT_AFFILIATE_URLS.items():
        if keyword.lower() in product_name.lower():
            return url
    return AFFILIATE_URL
