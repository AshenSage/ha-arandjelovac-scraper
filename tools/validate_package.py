"""Validate installability and release identity without network access."""
import ast
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
component=ROOT/'custom_components/arandjelovac_live'
manifest=json.loads((component/'manifest.json').read_text())
hacs=json.loads((ROOT/'hacs.json').read_text())
assert manifest['domain']=='arandjelovac_live'
assert manifest['config_flow'] is True
assert manifest['requirements']==[]
for key in ['domain','name','version','documentation','issue_tracker','codeowners']:assert manifest.get(key)
constants={}
for node in ast.parse((component/'const.py').read_text()).body:
    if isinstance(node,ast.Assign):constants[node.targets[0].id]=ast.literal_eval(node.value)
assert constants['VERSION']==manifest['version']
assert len([p for p in (ROOT/'custom_components').iterdir() if p.is_dir() and p.name!='__pycache__'])==1
assert (component/'frontend/arandjelovac-live-card.js').is_file()
assert (component/'brand/icon.png').is_file()
assert hacs['name']
strings=json.loads((component/'strings.json').read_text())
for path in (component/'translations').glob('*.json'):
    translated=json.loads(path.read_text())
    assert set(translated['entity']['sensor'])==set(strings['entity']['sensor'])
print('HACS structure, manifest, card, translations and version: OK')
