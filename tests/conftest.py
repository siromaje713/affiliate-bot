"""テスト設定: 外部依存をモックして単体テスト可能にする"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

for mod in [
    "anthropic", "pytrends", "playwright", "playwright.sync_api",
    "fal_client", "PIL", "PIL.Image", "bs4",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

if "dotenv" not in sys.modules:
    _dotenv = MagicMock()
    _dotenv.load_dotenv = lambda *a, **kw: None
    sys.modules["dotenv"] = _dotenv
