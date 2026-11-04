import json,csv,zipfile,datetime
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parent
def main():
 audit=json.loads((ROOT/'coverage_audit.json').read_text(encoding='utf-8'))
 labels={'all_a_close':'中证全指收盘价','hs300_close':'沪深300收盘价','zz1000_close':'中证1000收盘价','turnover':'中证全指成交额','turnover_rate':'中证全指换手率','financing_balance':'沪深两市融资余额合计'}
 descriptions={
 'all_a_close':{'provider_identifier':'000985.CSI','unit':'指数点','source':'iFinD index/index_data','definition':'当日收盘，不使用复权股价'},
 'hs300_close':{'provider_identifier':['000300.SH','399300.SZ'],'unit':'指数点','source':'iFinD index/index_data','definition':'沪深300收盘；优先SH发布代码，缺时采用同指数SZ代码，实际代码逐行留存'},
 'zz1000_close':{'provider_identifier':['000852.SH','399852.SZ'],'unit':'指数点','source':'iFinD index/index_data','definition':'中证1000历史收盘；双发布代码属于同一指数，发布前追溯序列不证明当时已知'},
 'turnover':{'provider_identifier':'000985.CSI','unit':'元（按回执显示量纲换算）','source':'iFinD index/index_data','definition':'指数成交金额。部分回执仅有亿/万亿缩写，非元级精度认证'},
 'turnover_rate':{'provider_identifier':'000985.CSI','unit':'百分数，例如1.2表示1.2%','source':'iFinD index/index_data','definition':'供应商指数换手率；与旧表分母/证券范围一致性尚未认证'},
 'financing_balance':{'provider_identifier':['S004273896','S004273905'],'unit':'元（从亿元换算）','source':'iFinD edb/get_edb_data; 回执标注沪深交易所','definition':'上交所融资余额加深交所融资余额，不含北交所，不是融资融券余额；是否等同旧融资字段尚未认证'}
 }
 for field,desc in descriptions.items():desc.update(label=labels[field],coverage=audit['fields'][field])
 (ROOT/'data_dictionary.json').write_text(json.dumps(descriptions,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 comparison=list(csv.DictReader((ROOT/'tables/legacy_comparison.csv').open(encoding='utf-8-sig')))
 serious=[]
 for field in labels:
  part=sorted([x for x in comparison if x['field']==field],key=lambda x:abs(Decimal(x['difference'])),reverse=True)[:10]
  serious.extend(part)
 with (ROOT/'tables/largest_legacy_differences.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(serious[0]));w.writeheader();w.writerows(serious)
 md=['# 六项原始数据重新取数验收','',f"目标范围：{audit['requested_start']} 至 {audit['requested_end']}。",'',
 '本目录的数据全部来自重新取得的iFinD原始回执。旧CSV和HTML只用于差异核对，不向新数据表提供数值。2022年以后的融资回执复用本会话先前独立取数结果，未复用旧模型输入。','',
 '| 数据 | 已取得日数 | 新旧重叠日数 | 最大绝对差（原单位） |','|---|---:|---:|---:|']
 for field,label in labels.items():
  d=audit['fields'][field];md.append(f"| {label} | {d['received_nonmissing_days']} | {d['overlap_days']} | {d['max_abs_difference']} |")
 md+=['',f"市场日期共{audit['market_days_received']}日；缺失字段{audit['missing_field_count']}个；非正异常字段{audit.get('invalid_field_count',0)}个；来源数值冲突{audit['conflicts']}个。",'',
 f"完整性结论：{'六项日度数值齐全' if audit['all_six_fields_complete'] else '仍存在缺口，查看coverage_audit.json及missing_fields.csv'}。",'',
 '## 文件', '',
 '- tables/raw_six_fields.csv：六项原始数据总表。价格与比率不从旧分数倒推。',
 '- tables/financing_sh_sz.csv：沪深融资分项，便于复核合计。',
 '- tables/field_lineage.csv：每个日期、每个字段对应的原始回执文件。',
 '- raw/：原始API响应；截断批次也保留，但不进入总表。',
 '- input_manifest.json：实际采用回执的SHA256。',
 '- tables/legacy_comparison.csv：完整旧表对账，旧值仅存在于此类核对文件。',
 '- tables/largest_legacy_differences.csv：每项差异最大的10条。',
 '- tables/alias_display_precision.csv：同一指数双发布代码的显示精度差异，采用SH值时仍保留另一返回值。',
 '- coverage_audit.json：缺日、缺字段、非正值和来源冲突核验。',
 '- data_dictionary.json：指标代码、单位和口径边界。','',
 '## 不能混淆的结论','',
 '数值齐全不等于与旧表同口径。新旧融资存在显著差异，换手率也有差异；不能直接把新系列当成旧模型的无缝续接。旧表存在零换手率与少数价格差异，已保留具体日期，不预判哪一方正确。', '',
 '沪深300及中证1000各有两个官方发布代码。已依据交易所和中证编制方案核实指数身份；双代码返回值差异小于较低显示精度一档时单列精度差异，优先采用SH代码。仅有SZ代码时使用该指数SZ发布值，不是用另一个指数补缺。实值差异更大时仍阻断完整性。证据见verified_index_aliases.json。', '',
 '中证1000在旧表中从2014-10-17才有值，而新供应商可提供更早追溯行情。发布前追溯值只可作明确标记的历史研究，不视为当时已发布的信息。', '',
 '成交金额在部分回执中缩写为亿或万亿，换算成元不增加精度。融资原单位亿元的小数精度也不等于元级精确。', '',
 '历史实际发布时间、官方日历以及供应商修订版本尚未完整认证。本轮没有发布网页、没有改变生产策略，也没有用数据缺口填零或插值。', '',
 '## 复算','',
 '运行python assemble.py重新从已取得回执构建数据表；再运行python finalize.py生成本报告。collect.cjs是取数入口，按季度/月份分批，发现截断则拆分，不将抽样结果算作完整数据。需要本机已配置iFinD skill。', '',
 '本轮检索过证券之星原融资页面作为来源线索；当前页面不能证明旧历史融资序列的统计范围。来源：https://quote.stockstar.com/Financing/FinancingTotal_2.html。该网页数值未进入新总表。']
 (ROOT/'README.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
 print(json.dumps({'complete':audit['all_six_fields_complete'],'days':audit['market_days_received'],'missing':audit['missing_field_count'],'invalid':audit.get('invalid_field_count',0)},ensure_ascii=False))
if __name__=='__main__':main()
