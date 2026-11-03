from pathlib import Path
import json,csv,hashlib,shutil,re,datetime,zipfile
R=Path(r'E:\Codex\量化'); repo=R/'github-data-upload-20261030/repo'; T=repo/'research/complete_archive_20261103';T.mkdir(parents=True,exist_ok=True)
folders=['turning-research-canonical','turning-raw-reacquired','turning-rebuild','A-share-top-monitor-history','html-data-audit','turning-7day-preopen','dual80-research','turning-label-audit','turning-label-comparison','A-share-top-monitor-review','strategies','references','skills']
files=[];excluded=[];flags=[]
pat=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,}|sk-[A-Za-z0-9_-]{25,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|[\"\'](?:api_key|access_token|refresh_token|password)[\"\']\s*:\s*[\"\'][^\"\']{8,}[\"\'])',re.I)
def add(f,rel):
 content=f.read_bytes()
 if len(content)>90_000_000:raise ValueError('Oversize '+rel)
 if f.suffix.lower() in ['.json','.csv','.py','.cjs','.js','.html','.md','.ps1','.txt','.yml','.yaml'] and pat.search(content.decode('utf-8-sig',errors='replace')):flags.append(rel)
 dest=T/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest);files.append({'path':rel,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
for folder in folders:
 for f in sorted((R/folder).rglob('*')):
  if not f.is_file():continue
  rel=f.relative_to(R).as_posix();why=None
  if any(x in ['.git','__pycache__','node_modules'] for x in f.parts) or f.suffix in ['.pyc','.pyo']:why='Runtime cache or version-control internals, not source data'
  if any(x.startswith('browser-') for x in f.parts):why='Browser session/profile/cache; excluded to protect session state'
  if '/csindex_site/' in rel:why='Downloaded third-party website implementation, not source data'
  if why:excluded.append({'path':rel,'reason':why});continue
  add(f,rel)
for f in sorted(R.iterdir()):
 if f.is_file() and (f.suffix.lower()=='.md' or f.name=='ACTIVE_RESEARCH_CONTRACT.json' or f.name in ['prepare_github_upload.py','stage_github_upload.py','inventory_upload_20261103.py','archive_all_20261103.py']):add(f,'workspace_metadata/'+f.name)
original=Path(r'D:\edge下载\a_share_turning_complete_v30_online_poc_same_ui.html')
if original.exists():add(original,'original_user_material/'+original.name)
assert not flags,'Credential-like content found: '+repr(flags)
manifest={'archive_date':'2026-11-03 Asia/Shanghai','archive_scope':'Current local quant workspace data, methods, source code, receipts, research results, failed attempts, charts, historical review snapshots, supplemental learning/strategy materials, and original user HTML','files':files,'excluded':excluded,'duplicate_archives_not_reuploaded':['turning_raw_six_fields_reacquired_20261030.zip','turning-rebuild_20261030.zip','github-data-upload-20261030/all_research_data_20261030.zip'],'credential_scan_flags':flags,'research_only':True,'PIT_certified':False,'dual80_achieved':False,'production_modified':False,'included_folders':folders}
(T/'upload_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');(T/'.gitattributes').write_text('* -text\n',encoding='utf-8')
print(json.dumps({'files':len(files),'bytes':sum(x['bytes'] for x in files),'excluded':len(excluded),'flags':flags,'by_folder':{n:sum(f['path'].startswith(n+'/') for f in files) for n in folders}},ensure_ascii=False,indent=2))
