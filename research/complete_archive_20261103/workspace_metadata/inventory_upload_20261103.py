from pathlib import Path
import json
R=Path(r'E:\Codex\量化');out=[]
folders=['turning-research-canonical','turning-raw-reacquired','turning-rebuild','A-share-top-monitor-history','html-data-audit','turning-7day-preopen','dual80-research','turning-label-audit','turning-label-comparison','A-share-top-monitor-review']
for name in folders:
 ff=[p for p in (R/name).rglob('*') if p.is_file() and not any(x in p.parts for x in ['.git','__pycache__','node_modules']) and not any(x.startswith('browser-') for x in p.parts)]
 out.append({'folder':name,'files':len(ff),'MB':round(sum(x.stat().st_size for x in ff)/1e6,2),'large':[(str(p.relative_to(R)),p.stat().st_size) for p in ff if p.stat().st_size>40e6]})
print(json.dumps(out,ensure_ascii=False,indent=2))
