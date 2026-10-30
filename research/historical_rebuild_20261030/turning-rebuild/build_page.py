import json,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
 data=json.loads((ROOT/'outputs/dashboard_data.json').read_text(encoding='utf-8'))
 template=(ROOT/'dashboard_template.html').read_text(encoding='utf-8')
 (ROOT/'index.html').write_text(template.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('</','<\\/')),encoding='utf-8')
 source=(ROOT/'sources/a_share_turning_complete_v30_online_poc_same_ui.html').read_text(encoding='utf-8-sig')
 notice='<div style="background:#fff4d9;color:#654b13;padding:15px;font:14px/1.8 system-ui;text-align:center">原版界面存档：历史评分与净值沿用原文件，不是本次重新计算。<a href="index.html">返回可复算重建版</a></div>'
 source=re.sub(r'(<body[^>]*>)',lambda m:m.group(1)+notice,source,count=1)
 (ROOT/'original_v30_archive.html').write_text(source,encoding='utf-8')
 files=[ROOT/'index.html',ROOT/'original_v30_archive.html',ROOT/'model_core.cjs',ROOT/'raw_history.json']
 manifest=[{'file':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
 (ROOT/'outputs/build_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
 print('Built index.html and labelled original_v30_archive.html')
if __name__=='__main__':main()
