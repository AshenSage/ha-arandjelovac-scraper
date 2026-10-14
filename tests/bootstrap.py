"""Load pure modules without executing the Home Assistant entrypoint."""
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'custom_components' / 'arandjelovac_live'
if 'live_test' not in sys.modules:
    module = types.ModuleType('live_test')
    module.__path__ = [str(PACKAGE)]
    sys.modules['live_test'] = module
