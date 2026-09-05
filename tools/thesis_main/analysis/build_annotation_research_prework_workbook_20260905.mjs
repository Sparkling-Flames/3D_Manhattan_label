import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook, SpreadsheetFile, FileBlob} from 'file:///C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const root=path.resolve('analysis_results/annotation_research_prework_20260905_v2');
const preview=path.join(root,'workbook_qa');
const workbook=Workbook.create();
const json=async file=>JSON.parse(await fs.readFile(path.join(root,file),'utf8'));
async function csv(file){
  const imported=await Workbook.fromCSV(await fs.readFile(path.join(root,file),'utf8'),{sheetName:'输入'});
  const values=imported.worksheets.getItem('输入').getUsedRange().values;
  const headers=values[0].map(v=>String(v).replace(/^\uFEFF/,''));
  return values.slice(1).map(row=>Object.fromEntries(headers.map((h,i)=>{
    const value=row[i]??'';
    const numeric=!/id|source|version|path|status|condition|stage|name|class|reason|json|contract|note/i.test(h) && /^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$/.test(String(value));
    return [h,numeric?Number(value):value];
  })));
}
function sheet(name,note,headers,rows){
  const s=workbook.worksheets.add(name); s.showGridLines=false;
  const width=Math.max(5,headers.length);
  s.getRangeByIndexes(0,0,1,width).merge(); s.getRange('A1').values=[[name]];
  s.getRangeByIndexes(0,0,1,width).format={fill:'#17365D',font:{name:'Microsoft YaHei',size:16,bold:true,color:'#FFFFFF'},rowHeight:32};
  s.getRangeByIndexes(1,0,1,width).merge(); s.getRange('A2').values=[[note]];
  s.getRangeByIndexes(1,0,1,width).format={fill:'#E5EFF6',font:{name:'Microsoft YaHei',size:10,color:'#17365D'},wrapText:true,rowHeight:45,verticalAlignment:'center'};
  const range=s.getRangeByIndexes(3,0,rows.length+1,headers.length);
  range.values=[headers,...rows]; range.format={font:{name:'Microsoft YaHei',size:10},rowHeight:24,verticalAlignment:'center'};
  s.getRangeByIndexes(3,0,1,headers.length).format={fill:'#2E648A',font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:36};
  const widths=headers.map(h=>/图像|来源|说明|缺口|解释|特征|参考|文献|原因|下一步|项目/.test(h)?40:/身份|状态/.test(h)?28:18);
  for(let i=0;i<headers.length;i++){
    const column=s.getRangeByIndexes(3,i,rows.length+1,1);
    column.format.columnWidth=widths[i]; column.format.wrapText=true;
    if(/D_mask|效应|相关|比例/.test(headers[i])) column.format.numberFormat='0.000';
  }
  for(let row=0;row<rows.length;row++){
    const lines=Math.max(...rows[row].map((v,i)=>Math.ceil([...String(v??'')].reduce((n,c)=>n+(c.charCodeAt(0)>255?2:1),0)/(widths[i]*.9))));
    s.getRangeByIndexes(row+4,0,1,headers.length).format.rowHeight=Math.max(26,Math.min(120,lines*15+8));
  }
  s.freezePanes.freezeRows(4);
  return s;
}
const qa=await json('evidence/QA.json'), stats=await json('statistics/QA.json');
const evidence=await csv('evidence/record_evidence.csv');
const summary=sheet('阅读入口','探索性历史分析；保留全部可追溯历史人员。人工30与AI50复用上一轮，本轮不增加审图。',
 ['项目','数值/状态','解释','主要来源','下一步意义'],[
 ['历史响应',qa.record_count,'26人、214图、22栋建筑','evidence/record_evidence.csv','不是当前20人的子集'],
 ['完整活动时间',qa.time_status_counts.owner_valid_complete,'17条完整但有偏差另记','evidence/record_evidence.csv','人员时间可比较通道'],
 ['完整但带偏差',17,'纳入描述，偏差状态保留','evidence/record_evidence.csv','不可当作无偏实验'],
 ['部分会话覆盖',20,'不用于快慢分类','evidence/record_evidence.csv','不由lead time补齐'],
 ['仅lead time',353,'与活动时间分开','evidence/record_evidence.csv','仍保留几何通道'],
 ['活动时间缺失',79,'不计为0','evidence/record_evidence.csv','保留其他可分析通道'],
 ['同图交集',25,'Manual 135条 / Semi 106条','evidence/matched25_image_summary.csv','描述性比较'],
 ['初始与所选参考D_mask=0',24,'共同来源风险，不能证明Semi更正确','三轴建模与文献对照.md','核实参考独立性'],
 ['bootstrap',stats.bootstrap_diagnostic_row_count,'69个可估计部分 ×1000；失败保留','statistics/bootstrap_diagnostics.csv','不强行分组'],
 ['历史剩余回放',82800,'69单元 ×6个k ×200；k20剩3–6人','statistics/strict_medoid_replay_replicates.csv','不是新人员预测'],
 ['旧42回归','42/42一致','结构、人数和人员分区一致','statistics/QA.json','新条件另列'],
 ['房间实例','未核实','语义类别不等于实例','evidence/building_split_room_mapping.csv','需要可靠pano—room映射'],
 ['发展/旧资料',779,'379个runtime身份；105条有条件字段','evidence/additional_response_candidates.csv','本轮未确认新增独立响应'],
 ['完整报告','研究前置工作报告.md','研究建议与未核实缺口','本目录','供用户和导师共同决策']]);
const matched=await csv('evidence/matched25_image_summary.csv');
if(matched.some(r=>!r.base_task_id))throw new Error('matched image identity missing');
sheet('同图25','D_mask是图像平面代理误差；越小表示越接近该参考，不自动表示正确。两头分别报告，未挑较优头。',
 ['图像','Manual人数','Semi人数','Manual D_mask','Semi D_mask','初始→参考 D_mask','初始→最终 D_mask','HoHo离线 D_mask','Bi enclosed D_mask','Bi extended D_mask'],
 matched.map(r=>[r.base_task_id,r.manual_record_count,r.semi_record_count,r.manual_reference_d_mask_mean,r.semi_reference_d_mask_mean,r.initial_reference_d_mask,r.initial_final_d_mask_mean,r.hohonet_reference_d_mask,r.bilayout_enclosed_reference_d_mask,r.bilayout_extended_reference_d_mask]));
const profiles=(await csv('statistics/directional_worker_profiles.csv')).filter(r=>Number(r.threshold)===.8);
sheet('候选人员描述','同人可在多个阶段/参考/特征出现；行数不是人数。H/L表示对应特征的正负方向，U保留不确定，非正式资格。',
 ['阶段','条件','人员','特征','参考来源','任务支持','建筑支持','调整效应','候选方向','可用重采样'],
 profiles.map(r=>[r.stage,r.condition,'W'+r.worker_id,r.feature_name,String(r.reference_source_version).split('|')[0],r.task_support,r.building_support,r.task_adjusted_effect,r.directional_class,r.bootstrap_usable_count]));
const axes=await csv('statistics/quality_time_coexisting_axes.csv');
sheet('质量与时间','连续效应优先。快慢为相对表现，不解释成认真、敷衍或疲劳；参考来源和时间连通部分保留在完整CSV。',
 ['阶段','条件','人员','参考来源','质量效应','时间效应','质量方向','时间方向'],
 axes.map(r=>[r.stage,r.condition,'W'+r.worker_id,String(r.quality_reference_source_version).split('|')[0],r.quality_effect,r.time_effect,r.quality_directional_class,r.time_directional_class]));
const heldout=(await csv('statistics/continuous_vs_classified_summary.csv')).filter(r=>Number(r.threshold)===.8);
sheet('留出诊断','按任务/建筑留出。行数为人员×折描述，非独立人数。相关只作描述；单人无同部分同题比较者的单元不评价。',
 ['阶段','条件','特征','参考来源','留出方式','评价行数','连续相关','H次数','L次数','U次数','反例次数'],
 heldout.map(r=>[r.stage,r.condition,r.feature_name,String(r.reference_source_version).split('|')[0],r.evaluation_kind,r.evaluation_rows,r.continuous_train_heldout_correlation,r.classified_H_count,r.classified_L_count,r.classified_U_count,r.counterexample_count]));
const curves=await csv('statistics/strict_medoid_condition_summary.csv');
const curveSheet=sheet('人数诊断','只在已选k人中选择medoid，再评价剩余人员。200次嵌套前缀；保留原恢复全体曲线于第一轮目录。',
 ['阶段','条件','k','图像数','建筑数','图像等权 D_mask','建筑等权 D_mask','剩余最少','剩余最多'],
 curves.map(r=>[r.stage,r.condition,r.k,r.image_count,r.building_count,r.d_mask_image_equal,r.d_mask_building_equal,r.remaining_min,r.remaining_max]));
const chartRows=[['k','C1 Manual','P1 Manual','P1 OOS','P1 Semi'],...[15,16,17,18,19,20].map(k=>[k,...[['C1','manual'],['P1','manual'],['P1','oos'],['P1','semi']].map(([s,c])=>Number(curves.find(r=>r.stage===s&&r.condition===c&&Number(r.k)===k).d_mask_image_equal))])];
curveSheet.getRange('A32:E38').values=chartRows;
curveSheet.getRange('B33:E38').format.numberFormat='0.0000';
const chart=curveSheet.charts.add('line',curveSheet.getRange('A32:E38'));
chart.title='剩余人员D_mask（图像等权）';chart.hasLegend=true;chart.yAxis={numberFormatCode:'0.000'};chart.setPosition('A41','I57');
const structure=await csv('statistics/structure_sensitivity_summary.csv');
sheet('结构阈值','0.93 / 0.95 / 0.97固定同一图集和响应支持。多模态结构率不是正确率；严格阈值下碎片化可改变分类。',
 ['阶段','条件','阈值','图像数','建筑数','图像等权比例','建筑等权比例'],
 structure.map(r=>[r.stage,r.condition,r.cutoff,r.task_count,r.building_count,r.supported_multimodal_rate_task_equal,r.supported_multimodal_rate_building_equal]));
sheet('记录索引','完整身份、原始来源、初始化和时间来源详见evidence/record_evidence.csv；此页为全部2501条记录的轻量索引。',
 ['记录身份','阶段','条件','人员','图像','几何状态','时间状态','来源'],
 evidence.map(r=>[String(r.canonical_annotation_id),r.stage,r.condition,'W'+r.worker_id,r.base_task_id,r.geometry_status,r.active_time_owner_valid_status,r.raw_export_path]));
const coverage=await csv('evidence/worker_building_condition_coverage.csv');
sheet('建筑人员覆盖','以building作为覆盖/外推分组；尚无可靠房间实例映射。不同数据集任务的官方split不可混用。',
 ['阶段','条件','建筑','人员','记录数','图像数','严格几何数','完整活动时间数'],
 coverage.map(r=>[r.stage,r.condition,r.building_id,'W'+r.worker_id,r.record_count,r.image_count,r.strict_geometry_count,r.complete_active_time_count]));
sheet('三轴与文献','概念与可行性；排除旧实验三轴。完整书目、研究设计、原文链接和限制见三轴建模与文献对照.md。',
 ['对象','输入/比较','结果/用途','主要缺口或限制','定位'],[
 ['轴候选A','人数k × 独立场景难度','一个分歧或质量指标','难度不能循环定义','待导师确认'],
 ['轴候选B','数据条件 × 标注难度','增加标注的收益','图像数、人数、工时分开','待导师确认'],
 ['轴候选C','固定k人员组成 × 场景条件','一个质量或分歧指标','类型需独立证据和共同任务','待导师确认'],
 ['Gaube 2021','建议正确性与宣称来源','诊断准确性','建议实际由人制作','建议影响'],
 ['Kiani 2020','有/无辅助交叉设计','诊断准确性','总体改善不显著；图块由人选择','初始化/人员题目差异'],
 ['Sensakovic 2010','从零轮廓与编辑初始轮廓','观察者一致性','初始轮廓来自人；一致不等于正确','共享初始化'],
 ['Mikulová 2022','从零/预解析与工具支持','质量、时间','参考裁决源需核实','质量+时间'],
 ['Berzak 2016','审阅人/机器标注与盲评','锚定、一致性、质量','参考可能偏向模型','参考独立性'],
 ['Whitehill 2009 GLAD','人员能力、题目难度、真值','二元类别推断','不直接适用连续布局；补充文献','本轮不拟合']]);
const checks=sheet('校验','简单勾稽用公式；统计运算来自可复算Python，完整检查见FINAL_CHECKS.json与DELIVERY_QA.json。',
 ['项目','观察值','期望值','差值','解释'],[
 ['历史记录',evidence.length,2501,'','记录身份唯一'],['时间通道总数',0,2501,'','2032+17+20+353+79'],
 ['同图数量',matched.length,25,'','Manual与Semi交集'],['旧42回归',stats.old42_regression.checked_task_count,42,'','mismatch=0'],
 ['特征记录',stats.feature_row_count,12023,'','多通道长表不是人数']]);
checks.getRange('B6').formulas=[["=SUM('阅读入口'!B6:B10)"]];
for(let row=5;row<=9;row++)checks.getRange('D'+row).formulas=[['=B'+row+'-C'+row]];
await fs.mkdir(preview,{recursive:true});
const output=path.join(root,'研究前置证据与分类探索.xlsx');
await(await SpreadsheetFile.exportXlsx(workbook)).save(output);
for(const s of workbook.worksheets.items){
  const range=s.name==='人数诊断'?'A30:I58':`A1:${String.fromCharCode(64+Math.min(s.getUsedRange().values[0].length,11))}${Math.min(18,s.getUsedRange().values.length)}`;
  const rendered=await workbook.render({sheetName:s.name,range,scale:.85,format:'png'});
  await fs.writeFile(path.join(preview,s.name+'.png'),new Uint8Array(await rendered.arrayBuffer()));
}
const reopened=await SpreadsheetFile.importXlsx(await FileBlob.load(output));
const scan=await reopened.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',options:{useRegex:true,maxResults:100},summary:'error scan'});
const values=reopened.worksheets.getItem('校验').getRange('B5:D9').values;
if(values.some(row=>row[2]!==0)) throw new Error('workbook reconciliation failed: '+JSON.stringify(values));
await fs.writeFile(path.join(preview,'VALIDATION.json'),JSON.stringify({output,formula_error_scan:scan.ndjson,checks:values,
  sheets:reopened.worksheets.items.map(s=>({name:s.name,rows:s.getUsedRange().values.length})),native_chart_count:1},null,2));
console.log(JSON.stringify({output,checks:values,preview}));
