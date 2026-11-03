from pathlib import Path
import zipfile,hashlib,json,re,datetime
root=Path(r'E:\Codex\量化');dest=root/'github-data-upload-20261030';dest.mkdir(exist_ok=True)
folders=['turning-research-canonical','turning-raw-reacquired','turning-rebuild','A-share-top-monitor-history','html-data-audit']
files=[];excluded=[];flags=[]
pat=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,}|sk-[A-Za-z0-9_-]{25,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|[\"\'](?:api_key|access_token|refresh_token|password|mcp密钥)[\"\']\s*:\s*[\"\'][^\"\']{8,}[\"\'])',re.I)
for folder in folders:
 for f in sorted((root/folder).rglob('*')):
  if not f.is_file():continue
  rel=f.relative_to(root).as_posix()
  if '__pycache__' in f.parts or f.suffix in ['.pyc','.pyo'] or '/csindex_site/' in rel:
   excluded.append({'path':rel,'reason':'Python cache or downloaded website implementation, not research data'});continue
  content=f.read_bytes()
  if f.suffix.lower() in ['.json','.csv','.py','.cjs','.js','.html','.md','.ps1','.txt']:
   text=content.decode('utf-8-sig',errors='replace')
   if pat.search(text):flags.append(rel)
  files.append({'path':rel,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
manifest={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'included_directories':folders,'files':files,'excluded':excluded,'credential_pattern_scan_flags':flags,'research_only':True,'PIT_certified':False,'production_updated':False}
(dest/'upload_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
assert not flags,flags
zpath=dest/'all_research_data_20261030.zip'
with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for item in files:z.write(root/item['path'],item['path'])
 z.write(dest/'upload_manifest.json','upload_manifest.json')
with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
print(json.dumps({'files':len(files),'uncompressed_bytes':sum(f['bytes'] for f in files),'zip_bytes':zpath.stat().st_size,'zip_sha256':hashlib.sha256(zpath.read_bytes()).hexdigest(),'excluded':len(excluded),'credential_flags':flags},ensure_ascii=False))
