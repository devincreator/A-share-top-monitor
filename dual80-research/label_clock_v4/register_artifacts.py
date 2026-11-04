from pathlib import Path
import hashlib,json
R=Path(r'E:\Codex\量化');P=R/'dual80-research/label_clock_v4'
old='两种定义平行保留，不按回测分数挑选真值。'
new=old+' 2026-11-02复核：混合盘中版不保证相邻反向拐点之间的实际最高/最低，5%有14处、9%有6处不一致；收盘版暂作研究基准，盘中版仅作实验对照。详见 label_clock_v4 标签审计。'
for f in [R/'turning-label-comparison/charts/all_pivots.html',R/'turning-label-comparison/build_charts.py']:
 text=f.read_text(encoding='utf-8-sig')
 if new not in text:
  assert old in text;text=text.replace(old,new);f.write_text(text,encoding='utf-8')
for f in [R/'turning-label-comparison/README.md',R/'turning-label-comparison/charts/README.md']:
 with f.open('a',encoding='utf-8') as out:out.write('\n2026-11-02后续复核：混合盘中版不保证相邻反向拐点之间的实际最高/最低，5%有14处、9%有6处不一致。收盘标签暂作可复算研究基准，盘中版保留实验对照；本页旧重评结果保留不变。详见 E:/Codex/量化/dual80-research/label_clock_v4/README.md 与 local_extreme_audit.json。\n')
files=[f for f in P.iterdir() if f.is_file() and f.name!='artifact_manifest.json'];manifest={f.name:{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in files};(P/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
with (R/'strategy_journal.md').open('a',encoding='utf-8') as out:out.write('\n2026-11-02 label_clock_v4：完成10片段与全量局部极值审计；撤回中途盘中主口径决定，最终收盘为暂定研究基准，混合盘中仅实验对照（5%14/169、9%6/70非相邻反向拐点间实际极值）。按D..D+6重训两标签×两特征组，追加预登记历史90分位发报对照，共32项任务无双80。固定价格模型收盘5%底部精确率33.9%、覆盖率51.3%，优于同队列原规则29.8%/35.9%；其余任务存在权衡，不替换生产。截断检查24816分数/876警报/512拟合，另22800阈值/553警报，标签特征及500组独立匹配通过。报告与图见dual80-research/label_clock_v4/README.md，全部本地。\n')
print('Saved report, label audit, 32 research outcomes, final contract and manifest',len(files))
