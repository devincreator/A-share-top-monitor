from pathlib import Path
import json,re
p=Path(r'E:\Codex\量化\turning-label-comparison\charts')
s=(p/'rendered_check.html').read_text(encoding='utf-8-sig').split('<script>')[0]
r={'rendered_svg':s.count('<svg'),'rendered_polygons':s.count('<polygon'),'table_rows_including_header':s.count('<tr>'),'counts_text':re.search(r'id="counts"[^>]*>([^<]*)',s).group(1)}
assert r['rendered_svg']==2 and r['rendered_polygons']==243 and r['table_rows_including_header']==244,r
j=(p/'all_pivots.html').read_text(encoding='utf-8');(p/'check.js').write_text(j.split('<script>')[1].split('</script>')[0],encoding='utf-8')
(p/'browser_validation.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r,ensure_ascii=False))

