import json,subprocess,sys
from pathlib import Path

def test_configs():
 for p in Path('config').glob('*.json'): json.loads(p.read_text())

def test_demo():
 r=subprocess.run([sys.executable,'run.py','demo','--output','outputs/test'],capture_output=True,text=True); assert r.returncode==0; assert Path('outputs/test/risk.json').exists()
