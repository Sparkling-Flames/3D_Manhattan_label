from pathlib import Path
import json,hashlib
from recompute_floor import ROOT
def main():
 s=json.loads((ROOT/'results/summary.json').read_text());l=json.loads((ROOT/'results/local_structure_20.json').read_text());loc={r['record_id']:r for r in l['rows']};rr=json.loads((ROOT/'results/floor_recompute_20.json').read_text())['rows'];t=s['T30'];ids=json.loads((ROOT/'results/object_identity_20.json').read_text());identity={r['record_id']:r for r in ids['objects']}
 lines=['# uNb88四空间回执落实与底面复算','',
 '用户明确指定T30对应D，优先于自动比较。原历史“T30两者均不匹配 / 另一种空间”保留；补充C/D后新增人工复核为`reviewed / matches_selected / D`，并非把旧判断删掉。T29原人工指定A不变。',
 '',
 '局部结构优先的结果：20个展示对象中，18个当前点位表达在入口附近停止、未延伸到GT第6/7对远端；R03258/W031和R01412/W034确实表达狭长延伸空间，应保留为A/B族结构候选，不能为了“全部C/D”的预期强制改分。两个对象均追到真实人员manual源记录，`ground_truth=false`，没有声明父标注/预测派生。',
 '',
 '当前点位20份均可重建有效多边形，但这不等于20份获准参与正式统计：R01808仍hold、R02963仍excluded，本轮均不恢复。旧缓存只有19份footprint非空；R02963当前更新点位可重建有效底面，其A-IoU与冻结计算一致，只保留诊断行，不能把旧null变成全零IoU并按第一个argmax归A。18份未排除且`in_current_manual_pool`的记录中，全局最高底面IoU为D13、C3、B2、A0。',
 '',
 '## 分母与全局IoU对照','',
 '|对照集合|记录数|最高A|最高B|最高C|最高D|说明|','|---|---:|---:|---:|---:|---:|---|',
 '|编辑器展示的当前点位诊断|20|0|2|3|15|含1 hold与1 excluded，不能当正式人员分母|',
 '|旧缓存footprint非空|19|0|2|3|14|仍含hold；仅解释先前缓存快速检查|',
 '|当前未排除manual池/primary included|18|0|2|3|13|保留原资格，不额外批准质量|','',
 '20个对象来自19个worker编号；计入的18条来自18个worker编号。计数单位是记录/对象，本轮不开发人员或融合模型。全局最高IoU是几何误差基线，不是语义归属、真实意图或最高最终Q。',
 '',
 '## T30人工D的前后范围指标','',
 '|参考|底面IoU|漏出面积 / 参考面积|多出面积 / 参考面积|参考面积 h²|','|---|---:|---:|---:|---:|']
 for k in 'ABCD':
  m=t['comparisons'][k];lines.append(f"|{k}|{100*m['iou']:.4f}%|{100*m['missing_over_reference']:.4f}%|{100*m['excess_over_reference']:.4f}%|{m['reference_area']:.9f}|")
 lines+=['',f"T30从A的55.1462%到用户指定D的68.6802%，增加13.5340个百分点；相对旧A/B最佳B的61.2256%，增加7.4547个百分点。自动最高底面IoU也为D，但人工指定先于该结果；D与次高C差6.8274个百分点。作答面积为{t['annotation_area_h2']:.9f} h²。",'',
 'D下仍有11.4239%的参考面积未覆盖，以及相当于参考面积28.9688%的多出部分。原冻结Q=12.992947、自身D=11.795381°、F=1.930529°均保留，不能把底面IoU变高写成完整质量已经改善。','',
 '## 局部证据与3例核对','',
 'GT配对编号使用原14对顺序的一基编号：第5/8对是入口，第6/7对是远端。全景接缝跨越通过原ERP→XZ投影表达，不重排角点、不对齐拟合作答。局部区域同时保存`GT5–6–7–8`四边形与`A\\C`差异区域；后者面积1.512293383 h²。固定GT入口—远端轴只用于区分深半区，不是对作答做拟合。','',
 'GT5或GT8附近有点不是包含空间的充分证据。R03258的入口邻边向远端延伸约2.04/2.17 h，深半区覆盖约99.995%；R01412没有贴近GT8的独立角点（最近角点距离0.7611 h），但相邻长边确实走向远端且深半区覆盖100%，因此“漏一角点”不等于“缺这个空间”。R02963更新点位虽接近GT8（0.0252 h），邻边却在入口封口，深半区覆盖0；它是“入口有点不等于有延伸”的诊断反例，资格仍excluded。','',
 '![真实全景与同尺度BEV的3例](results/figures/local_structure_key_examples.png)','',
 '该图读取真实原始1536×768照片像素，并使用原GT/当前作答点位；未重新构造C/D顶界或3D。用户局部截图的像素已由主线程核对；本执行器该截图下载失败，尚未冒称独立查看其像素。当前图是独立生成的GT配对核对图。','',
 '|对象 / 人员|原资格|延伸区域覆盖|深半区覆盖|局部族候选|辅助空间候选 / 路由|','|---|---|---:|---:|---|---|']
 for a in rr:
  e=loc[a['record_id']];q=identity[a['record_id']]['main_quality_gate']['status'];family='A/B族：表达延伸' if e['local_family'].startswith('AB') else 'C/D族：入口停止' if e['local_family'].startswith('CD') else '局部不确定';route='局部差异证据' if e['geometric_candidate_route']=='two_local_difference_regions' else '族内底面IoU兜底，低置信';manual='；人工指定D' if a['record_id']=='R02962' else '';lines.append(f"|{a['record_id']} / {a['worker_id']}|{q}|{100*e['front_difference_coverage']:.3f}%|{100*e['far_half_coverage']:.3f}%|{family}|{e['geometric_candidate_space']}：{route}{manual}|")
 lines+=['',
 '本次局部量呈两类极端：18份延伸覆盖0–2.31%、深半区0；2份延伸覆盖99.15%/约100%、深半区约100%。原始邻边深度、角点近邻距离、远端边距离及所有覆盖量见机器表。辅助后方`B\\A`（亦对应`D\\C`）差异区域覆盖只用于补充分辨；残缺/歪斜的R03260、R03258、R01412、R03262在其局部族内使用底面IoU兜底，明确标低置信，其他未人工指定记录仍只是候选。R02963诊断行D/C差仅0.8739个百分点，不能据最高值恢复资格或强认意图。','',
 '5%/90%是把接近0/1的覆盖量与中间部分分开展示的宽证据带，并非最终合格线、已校准阈值或必须归类规则。角点数不必与GT一致；中间/部分/斜跨情况预留不确定，不以入口近点单独判正。','',
 '## 哪些低分存在参考范围影响，哪些残差仍在','',
 '可确认的是范围项对参考空间敏感；无法在C/D顶界缺失时认定旧低Q“主要”由参考不完整造成。参考差异的主要例子：','',
 '|对象|原冻结Q|旧A/B最佳IoU|新四空间最佳IoU|范围IoU增量|自身D / F|','|---|---:|---:|---:|---:|---:|']
 for rid in ['R01571','R02967','R03262','R02962']:
  a=next(v for v in rr if v['record_id']==rid);lines.append(f"|{rid}|{a['frozen_Q']:.4f}|{100*a['old_AB_best_IoU']:.4f}%|{100*a['new_ABCD_best_IoU']:.4f}%|{100*a['best_IoU_gain_over_AB']:.4f}百分点|{a['frozen_D_degrees']:.4f}° / {a['frozen_F_degrees']:.4f}°|")
 lines+=['',
 'R01571、R02967、R03262旧最佳范围IoU约76–80%，补充D后约88–91%，确有明确参考范围影响；仍需分别检查角点、墙线、顶界及规整性。R03262自身D=14.5522°仍在，换参考不能消掉该偏斜。R03258/R01412表达A/B族延伸，原A/B最佳不因新增C/D改善；不能把它们的低Q归结为遗漏C/D参考。R01808最佳底面IoU仍只有47.7086%、D=14.1551°且保持hold；R00219最佳61.1796%、R03260最佳63.6020%等仍有较大范围残差。多边形有效不等于标注良好；没有仅凭自动候选宣布全部匹配或统一严重程度。','',
 '## 计算定义、保留与缺口','',
 '- 同一camera-height-normalized XZ框架；面积单位h²，未取得米制高度，不写m²。原ERP为1024×512；每对取bottom点，`r=1/tan(v)`、`x=r sin(u)`、`z=-r cos(u)`。',
 '- `IoU=交集/并集`；漏出=参考减作答，多出=作答减参考；同时保留两者绝对面积、参考/作答/交集/并集分母及多出/作答比。未使用配准、缩放拟合、凸包、buffer修复或自动GT替换。',
 '- 全20份当前点位哈希与冻结组件一致，19份已有缓存与重建形状一致；20份A-IoU与冻结原计算一致。空/零面积/无效几何会保留原因而不参与argmax；本轮R02963是旧缓存缺失而当前重建有效，资格另外处理。',
 '- A/B继承既有认可，A没有本次confirm不等于撤销；C/D严格取本次明确确认版本（C 07:15:53.390Z，D 07:15:42.772Z），操作重放与草稿一致，均top_pending。原名仍含“待用户补画”，只保留源字段，实际状态以确认版本为准。',
 '- 原30回执原字节11986 bytes、SHA256 `8e26b9cd8fa4fc1f978fb0b71453e2142878eca667cd5c525dd913d8077ad35c`；新回执70795 bytes、SHA256 `754507bd4774baacdb2a8f4336b6a7af84387e4c39f2db39515180b4e9b4276e`。历史语义/顺序/身份字段完全相同，原件不改。',
 '- 自身D/F等冻结量不随参考改变；原I/S/Hstar/D/F/Q行保留。C/D无完整顶界，未重算新完整Q、3D IoU、顶边S或完整联合边界/高度参考误差，不借用A的顶界。',
 '- T29人工A与T21/T22研究警报原样保留，7错误GT排除及全部hold/资格不动。后续工作台用户偏好云端链接；本轮不改UI、不生成新ZIP、不追加旧功能测试。',
 '- 字节绑定、确认重放、对象源身份、几何有效性、分母与旧A-IoU一致性是本次必要核验；不是质量校准或最终公式验收。','',
 '详细结果：[四空间20行JSON](results/floor_recompute_20.json) · [四空间20行CSV](results/floor_recompute_20.csv) · [80组面积比较](results/floor_metrics_80_long.csv) · [局部证据20行](results/local_structure_20.csv) · [身份与资格20行](results/object_identity_20.json) · [参考清单](results/reference_ledger.json)。']
 # Use actual computed figures for residual examples; no hard-coded rounding drift.
 r00219=next(a for a in rr if a['record_id']=='R00219');r03260=next(a for a in rr if a['record_id']=='R03260')
 text='\n'.join(lines)+'\n';text=text.replace('61.1796%',f"{100*r00219['new_ABCD_best_IoU']:.4f}%").replace('63.6020%',f"{100*r03260['new_ABCD_best_IoU']:.4f}%")
 (ROOT/'RESULTS_ZH.md').write_text(text)
 print('Chinese result report generated from frozen tables; no new quality judgments')
if __name__=='__main__':main()
