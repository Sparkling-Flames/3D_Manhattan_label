'use strict';
(()=>{
const C=WorkbenchCore,$=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const requestedRelease=new URLSearchParams(location.hash.slice(1)).get('release')||'v2';
const dataset=window.RESEARCH_DATASETS.find(d=>d.release===requestedRelease);
const SNAPSHOT=dataset?.snapshot;
const modules={
 overview:['研究发现总览','主要发现与对应证据；全研究结论、专题和完整明细都保留入口，可自行展开。',[]],
 case_story:['跨专题典型案例','十个保存案例，含原图、每人的完整标注和团队几何；每个案例列出总体支持范围和记录条数。',[]],
 evidence:['方法与证据','任务范围、质量测量和结构共识的概念，以及对应的保存案例。页面只读取已保存结果，不重新评分或融合。',[['任务与门洞',null],['质量度量',null],['融合机制',null],['研究支持',null]]],
 conditions:['难度与范围','固定参考结构、不同采集条件下的表现和逐图范围支持，三部分分开查看。',[]],
 images:['图片与空间','逐图查看目标空间、原图标注和参考；更多条件在筛选里设置。',[]],
 profiles:['人员画像 · 本轮','Q 水平、偏低的部分（P10）、作答用时和不同难度下的表现。Manual 与 Semi 分开，审核只在有记录的范围内统计。',[]],
 personnel_main:['人员标法与团队','人员分类、构成、难度、人数和共识机制，共六步；固定图与可筛选明细分开。',[]],
 method_supplements:['已验收方法补充','三组已验收的补充方法：D10 人员形成、同队三法融合、质量指标与实际缺陷对照；只读取固定结果和已保存几何。',[["人员形成与构成",null],["同队三法融合",null],["质量指标验证",null]]],
 taxonomy:['人员分类 · 阶段历史','保留旧阶段的工作标签和原来的统计范围；新研究见“人员标法与团队”。',[]],
 mechanisms:['条件与局部机制 · 10/21','按同图、同参考、精确成员和保存节点逐层追溯。难度、质量、融合和同房结果各自保留支持与资格。',[]],
 workers:['画像明细与历史','原尺度 Q 与任务调整 Q 并列。Scope 分开显示拒绝倾向、历史裁定结局和当前可判断的记录；这些不是全量正确率。',[
  ['连续画像与分组','workers__person_profiles_and_evidence'],['原尺度Q与P10','workers__absolute_Q_training_profiles'],['楼外画像','workers__fold_person_profiles'],['难度与场景','difficulty__worker_strata'],['Scope裁定覆盖','workers__scope_worker_opportunities'],['历史Scope结局','workers__scope_outcome_counts'],['可靠性与排除','workers__record_evidence'],['门洞专项','workers__doorway_specialist_profiles']]],
 quality:['个体质量','展示原图、BEV／3D 几何，以及评分、计算状态和质量用途。',[
  ['作答几何与分项','quality__shared_records'],['诊断与用途原因','difficulty__record_ledger']]],
 patterns:['类别原答与融合','选择研究类别或本图标法，叠加原答并查看对应的保存团队。GT 问题与门洞单独解释。',[]],
 benefits:['人员组合效益','高低 Q 配比、快慢配比、固定核心增人和实际投票案例。这里不新增正式人员类型。',[['配比与收益',null],['原答／投票／融合案例',null]]],
 fusion:['融合过程','人员组合、同图、真实路径、成员和已保存几何，可逐层查看。',[
  ['人员组合策略','workers__strategy_vs_random'],['纯类同k逐图对照','workers__pure_group_direct_by_image'],['固定构成换人','statistics__replacement_group_summary'],['换指标与重新选人','workers__metric_reselection_contrasts'],['真实人数过程','fusion__trajectory_scores'],['同k换组稳定性V','fusion__same_k_stability'],['完整率与失败','fusion__completion'],['构成汇总','statistics__team_composition_summary'],['团队成员与几何','workers__team_results']]],
 same_room:['同房跨视角规律','在已有关系和可比范围内比较同成员的跨视角表现。没有同房记录时按未知处理，不当作异房。',[
  ['原答图对','same_room__endpoint_pairs'],['同成员同顺序过程','same_room__process_paired_prefixes'],['配对过程汇总','same_room__consumer_pair_summary'],['关系组与覆盖','statistics__room_group_registry'],['候选与过程接入','same_room__same_room_endpoint_integration']]],
 multiview:['同房多视角叠加','沿相同人员或相同保存团队比较不同视角；原答与团队评分分开显示。',[]],
 same_room_review:['同房独立补算 · 10/21','个人 Q 校准、结构迁移增量和源图人数选择。支持范围、偏低的部分（P10）、缺失和反例分别保留；页面不重新融合。',[]],
 time:['时间与Semi','来源时间、同目标时间、兼容净改善和确认纠错分别解释。',[
  ['Semi初始化与最终','workers__semi_initialization_scores'],['来源活动时间','quality__shared_records'],['同目标审计时间','quality__shared_records'],['确认错误与未知','workers__semi_correction_evidence'],['初始化来源','workers__initialization_evidence'],['时间缺失','statistics__time_missing_records']]],
 data:['数据探索','按对象粒度查看作答、图片、人员、团队和过程节点；筛选与来源都可追溯。',[
  ['作答明细','quality__shared_records'],['图片清单','statistics__image_inventory'],['人员清单','statistics__worker_inventory'],['团队结果','fusion__TEAM_RESULTS'],['过程节点','fusion__trajectory_scores']]],
 coverage:['数据覆盖','作答、图片、人员和目标分开计数。能算出几何，不代表满足主质量要求。',[
  ['计算状态与用途','difficulty__record_ledger'],['逐图人数','statistics__image_inventory'],['逐人清单与排除','statistics__worker_inventory'],['重叠原因','difficulty__reason_ledger'],['原因计数','difficulty__reason_counts'],['补人计划（只读）',null]]],
 sources:['数据与方法与历史','数据、分析、评分、画像和融合版本分别登记。上游状态只在构建时核对。',[]]
};
const labels={object_id:'作答ID',image_id:'图片ID',image_code:'图片',image:'图片',worker_id:'人员',condition:'采集条件',building_id:'建筑',reference_id:'评分参考',rescore_target_id:'评分目标',current_target_id:'当前目标',target_id:'目标',B8L2:'B8L2',D10:'D10',IoU3D100:'均高棱柱IoU ×100',iou_2d:'底面IoU（0–1）',S_bottom_deg:'S_bottom_deg（°）',dir:'dir（方向残差°）',Hmean:'Hmean（冻结引擎高度误差）',Hcenter:'Hcenter（冻结引擎局部高度误差）',quality_usable:'主质量可用',calculation_status:'计算状态',diagnostic_B8L2:'B8L2诊断',diagnostic_D10:'D10诊断',quality_exclusion_reasons:'质量用途限制',Q_effect:'相对Q效应',Q_group:'既有Q二分',QT_group:'既有Q×T四格',T_group:'既有T分组',T_source_effect:'来源T效应',T_target_effect:'同目标T效应',Q_contexts:'Q支持任务数',Q_buildings:'Q支持建筑数',member_workers:'成员',path_id:'路径',path_kind:'路径类型',subset:'成员子集',pool_id:'人员池',k:'人数k',policy:'策略',selection_metric:'选人指标',metric:'画像指标',source_active_seconds:'累计来源活动时间（秒）',source_active_time_seconds:'来源活动时间（秒）',target_matched_time_seconds:'同目标时间（秒）',main_comparison_allowed:'主比较允许',score_status:'测量状态',R_union_normalized:'R 原答两两差异',floor_jaccard_difference:'V 同k换组差异',complete_evaluable:'完整可评价',request_id:'请求ID',reference_version:'参考版本',reasons:'测量原因',geometry_reason:'几何原因',submissions:'规范提交数',historical_gold:'有历史gold记录数',historical_eligible:'排除hold后的历史可诊断记录数',current_clear_compatible:'历史gold与当前场景相容的记录数',current_task_unknown:'当前任务裁定未知数',historical_outcome:'历史裁定结局',historical_gold_current_clear_compatible:'历史gold与当前明确普通场景相容'};
const displayValues={new:'新增人员',individual:'本人源视角',other_source_people:'源视角其他人员',calibrated_history:'校准历史基线',copy_source:'复制本人源视角',history_plus_source:'历史＋源视角',worker_history:'原历史基线'};
const fmt=v=>C.empty(v)?'—':C.numeric(v)?v.toLocaleString('zh-CN',{maximumFractionDigits:3}):typeof v==='boolean'?(v?'是':'否'):typeof v==='object'?JSON.stringify(v):(displayValues[v]||String(v));
const label=k=>labels[k]||k;
Object.assign(labels,{origin:'人员来源',mode:'预测模式',method:'预测方法',building:'建筑',building_equal_mae:'建筑等权MAE',buildings:'建筑数',directions:'有向图对数',prediction_rows:'预测记录数',actual:'实际值',predicted:'预测值',absolute_error:'绝对误差',error_unit:'误差单位',warm_start:'有历史支持',relation_eligible:'关系可比准入',n_paired:'共同有效人数',supported:'模型折可支持',gain_vs_calibrated_history:'较校准历史基线改善（正为好）'});
const placeholder=(title,reason)=>`<div class="placeholder"><strong>${esc(title)}</strong>${esc(reason)}</div>`;
const metricHints={
 B8L2:['综合几何工作分，0—100，越高越接近当前固定参考。','同时看底面／边界、自身方向和高度；同分可能有不同局部结构。只在相同参考、资格和条件下比较。例：同节点数也可能位置不同。来源：质量测量专题。'],
 D10:['方向容忍尺度改为10°的对照分；越高越接近该尺度。','与 B8L2 使用同一原答、参考和资格，只把方向尺度 8° 改为 10°；分数差不是几何改善。来源：质量测量专题。'],
 iou_2d:['底面 IoU，0—1；越高表示候选与参考底面更重合。','只看俯视底面交并比，不直接测顶界或全部必要转折。例：平面接近仍可能高度不同。来源：固定评分实现。'],
 S_bottom_deg:['底边球面角距，单位度；越低越接近参考边界。','冻结实现为双向平均距离，不表示墙角身份对应正确率。来源：质量分项合同。'],
 dir:['自身方向残差，单位度；越低越规整。','测输出自身的方向规整性，不是每条墙相对 GT 的方向误差。来源：质量分项合同。'],
 Hmean:['整体均高相对绝对差；0.1表示相差参考均高的10%。','先按底面周长加权求候选和参考均高，再取绝对差/参考均高；无量纲，正负另看height_mean_ratio−1。它是评分输入，不是缩放后的高度损失，也不是几何自遮挡H。'],
 Hcenter:['扣掉整体均高差后的局部高度轮廓相对残差；越小越接近参考。','按最近底面位置匹配，做双向均方根并除以参考均高；center指去掉均高，不是房间中心。无量纲，既不是米，也不证明同一语义墙面已对应。'],
 floor_jaccard_difference:['同人数换组后的底面差异；越低表示较稳定。','V 描述更换成员的敏感性，不保证融合更接近参考；跨方法的归一范围不同。来源：融合人数专题。'],
 source_active_time_seconds:['来源活动时间，单位人秒；只统计有来源的记录。','与报告时间、同目标时间和交付历时分开；缺失不补零。来源：时间字段合同。'],
 target_matched_time_seconds:['同目标匹配时间，单位人秒。','只对可匹配目标的真实记录统计，不可用来源活动时间或 lead time 偷换。来源：时间字段合同。'],
 occlusion_h:['几何自遮挡 H：在实心墙假设下被墙自身遮住的代理。','不同于家具、窗帘遮挡，也不同于质量公式中的高度损失 H。需结合目标范围和结构看。来源：难度解释合同。'],
 height_loss_h:['高度损失 H：评分中的候选与参考高度差。','越低越接近参考；不同于难度条件中的几何自遮挡 H。来源：质量评分合同。'],
 direction_d:['方向残差 D：布局输出自身的规整性。','单位度，越低越规整；不是共同背景 D，也不是相对 GT 的墙向误差。来源：质量分项。'],
 background_d:['共同背景 D：两支团队共用的真实成员集合。','这里 D 是成员集合，不是方向残差；相同 D 才能解释固定背景下的换人比较。来源：团队构成合同。'],
 source_k:['源历史人数 k：预测时已见过的源视角人员数。','这是源视角历史支持量，不是目标图融合团队人数。来源：同房预测合同。'],
 team_k:['融合团队人数 k：当前已纳入共识的真实成员数。','同 k 换组比较保持人数相同，但成员可能不同；不是源历史人数。来源：融合人数合同。']
};
Object.assign(metricHints,{
 medoid:['代表原答：同一团队中最接近其他原答的一份完整标注。','按团队内平均 1−底面IoU 最小选择，不用 GT 或目标质量分挑最好人；保留所选人的完整顶底界。'],
 ARI:['ARI：两套人员分区的一致程度。','不受类别名字置换影响；1 表示分区相同，0 附近是随机参照，不是人员正确率。ALL 和楼外折应分开。'],
 eta2:['η²：固定团队质量波动中的配比格间描述比例。','不是预测准确率。若团队分数没有波动则未定义，必须标为不适用，不能填 0。'],
 common_evaluable_domain:['共同可评域：比较的两种方法都可评分的团队。','均分、偏低的部分（P10）和几何差在同一组团队上比较；无连接、少点等失败另按全部预定尝试报告。'],
 layout_depth:['布局深度误差：由声明的顶底边界渲染逐列深度，再与参考比较。','它能响应局部高度，不是相机实测深度；统一相机高下的归一单位与米制字段分开。'],
 oos_disagreement:['原答底面分歧：同图两份底面的对称差面积除以二者并集，再对人员对平均。','0表示重合，1表示不重合；比较人员之间的近似表达，不比较GT，也不衡量顶面是否忠实。子类在每图汇总后按图等权。'],
 oos_scope_choice:['不可标选择：参与者对当次任务的响应。','327/804是新Manual任务选择的记录比例；28图中6图为多数人选择不可标。它不是OOS识别准确率，可见因素与参与者目标范围分别保留。']
});
// 短释义/展开说明沿用 CONTEXT.md；单位和实际分母仍在正文、表格中显示。
Object.assign(metricHints,{
 mae:['MAE：预测与实际差的绝对值，再取平均；越小越准。','预测Q时单位是分，预测比例时按表中比例/百分点单位读取。比较方法须保持目标、样本和图/楼权重相同；平均预测改善不能用来筛查严重低 Q。'],
 rmse:['RMSE：误差平方后取平均，再开方；对大误差更敏感。','单位与预测目标相同。它与MAE关注的大误差权重不同，不能把两种指标直接混为同一排名。'],
 bias:['有符号偏差：平均预测值减实际值。','正值表示平均高估，负值表示平均低估；正负误差可以抵消，接近零不保证每次预测都准。'],
 pearson_r:['Pearson r：两组数值一起线性变化的程度。','范围−1至1；相关不是数值相等，也不代表预测误差小。它与看排序的Spearman相关应分别读取。'],
 spearman_r:['Spearman ρ：两组数值排序一起变化的程度。','范围−1至1；对排名一致性的描述不代表绝对 Q 预测准确，必须核对共同支持与聚合层级。'],
 R2:['R²：相对声明基准的平方误差改善程度，可以为负。','常见形式为1−残差平方和/总平方和。面板内相对变化的解释能力，不代表陌生图片绝对 Q 的预测能力。'],
 SD:['SD：结果围绕均值的分散程度；Q的SD单位是分。','自然曲线这里描述同图、同人数的顺序间质量波动，不是均值的置信区间，也不同于几何波动V；样本少于2个时不可估。'],
 P10:['P10：当前样本的第10百分位，Q中通常表示较差端。','约10%的观测不高于此值；它不是最低分或10%错误率。分位数随支持集合变化，分位带不是置信区间。'],
 P50:['P50：当前样本的中位数。','约一半观测不高于此值；它描述结果分布的中间位置，不是均值或估计精度。'],
 P90:['P90：当前样本的第90百分位。','约90%的观测不高于此值；对Q是较高端，对误差则是较大误差端。分位带不是置信区间。'],
 resampling_unit:['重抽区间：按声明的建筑、图片或路径单位重复抽样得到。','重抽次数不是新增独立数据。旧R03的2000次bootstrap仅重抽原24条且范围到k20；新补充的独立新24、合48、重点96和精确有限边际须分别读取，不能把重抽次数当新增路径。探索选型后的区间仍属内部分析。'],
 natural_paths:['路径是一次人员进入顺序；同k取前k名人员形成团队。','当前主展示普通点为合48，重点池另有96；旧24保留历史身份，均为抽样而非全排列。路径共享成员，同一成员集合复用端点。满员回到同一支团队、SD/V归零，不代表Q正确；角色优先的8条配对顺序另列。'],
 saved_endpoint:['端点：一支确定团队在既定规则下的保存融合输出。','同一端点可被多个路径或事件引用，因此端点引用次数不是独立团队数。页面读取已保存结果，不按筛选重新融合。'],
 comparison_event:['事件：一次换人、换类或前缀端点的对照。','事件有各自A/B/C或前后端点，可能共享图片、团队和人员；事件数不是独立图片数或独立团队数。'],
 paired_quality:['同一路径两端可评Q：只比较同一条路径前后都能评分的结果。','两端各自可评路径的边际均分可能来自不同路径集合。配对Q与边际Q分列；恢复、新增失败和两端失败另按全部尝试报告。'],
 all_attempts:['全部尝试：包含真实失败和缺Q的预定团队/路径记录。','失败率按对应全部尝试计算；原实验暂缓未运行不计成功或失败。Q缺失不填0，也不把只在成功子集上的均分当作全部尝试表现。'],
 percentage_points:['百分点：两个百分比直接相减。','失败率10%→15%是增加5个百分点，相对原值增加50%；两种读法不能混写。Q的0—100分变化仍用分表示。'],
 pair_nodes:['一个布局节点对应一组顶底点；4个节点是8个点。','节点表示候选布局转折，近共线分段需按对应定义解释。少于4节点的保存诊断点不能闭合为完整可评布局；没有坐标时不补造。']
});
for(const [key,source] of Object.entries({r2:'R2',pearson:'pearson_r',spearman:'spearman_r',sd:'SD',p10:'P10',q10:'P10',p50:'P50',p90:'P90',building_equal_mae:'mae',own_source_mae:'mae',source_peers_mae:'mae',outside_history_mae:'mae',descriptive_bootstrap_lower:'resampling_unit',descriptive_bootstrap_upper:'resampling_unit',attempts:'all_attempts',attempted_paths:'all_attempts',paired_Q_paths:'paired_quality',paired_Q:'paired_quality',path_id:'natural_paths',team_key:'saved_endpoint',event_id:'comparison_event',nodes:'pair_nodes'}))metricHints[key]=metricHints[source];
metricHints.absolute_error=['单次绝对误差：本次预测与实际相差多少，不保留正负号。','同单位的多次绝对误差再按声明权重平均才是MAE；这一个值不是总体预测精度。'];
metricHints.method_dstruct_k2=['二类是困难结构表达的粗层，不是两人团队。','K为类别数，n为每队人数，m为替换人数，N为当图可用池。二/三类保留各自保存名单和实验，楼外同号类不跨折套用角色。'];
const metricHintLabels={mae:'MAE平均绝对误差',rmse:'RMSE均方根误差',pearson_r:'Pearson线性相关',spearman_r:'Spearman排序相关',bias:'有符号偏差',resampling_unit:'重抽单位与区间',natural_paths:'自然路径',saved_endpoint:'保存端点',comparison_event:'对照事件',paired_quality:'同一路径两端可评Q',all_attempts:'全部尝试',percentage_points:'百分点',pair_nodes:'节点与顶底点对',oos_disagreement:'原答底面分歧',oos_scope_choice:'不可标选择'};
const hintButton=key=>metricHints[key]?`<button class="hint-trigger" type="button" data-hint="${esc(key)}" aria-label="解释 ${esc(metricHintLabels[key]||labels[key]||key)}" aria-describedby="metricHint">?</button>`:'';
let hintPopover=null,activeHint=null,hintPinned=false;
function hideHint(){if(activeHint)activeHint.setAttribute('aria-expanded','false');activeHint=null;hintPinned=false;if(hintPopover)hintPopover.hidden=true;}
function showHint(trigger,detailed){const content=metricHints[trigger.dataset.hint];if(!content||!hintPopover)return; if(activeHint&&activeHint!==trigger)activeHint.setAttribute('aria-expanded','false');activeHint=trigger;hintPinned=detailed;trigger.setAttribute('aria-expanded',String(detailed));hintPopover.textContent=detailed?content.join(' '):content[0];hintPopover.hidden=false;const rect=trigger.getBoundingClientRect(),width=hintPopover.offsetWidth,height=hintPopover.offsetHeight;hintPopover.style.left=Math.max(8,Math.min(rect.left,innerWidth-width-8))+'px';hintPopover.style.top=(rect.bottom+height+8<innerHeight?rect.bottom+6:Math.max(8,rect.top-height-6))+'px';}
const panel=(title,html)=>`<section class="panel"><h2>${esc(title)}</h2>${html}</section>`;
const fieldList=row=>`<dl class="fields">${Object.entries(row).filter(([k])=>!['path','parts','source','score_source','source_path','source_file','source_state','geometry_origin','manifest','provenance','readme_path','research_basis_path'].includes(k)).map(([k,v])=>`<dt>${esc(label(k))}${hintButton(k)}</dt><dd>${esc(fmt(v))}</dd>`).join('')}</dl>`;
const select=(id,items,current,caption)=>`<label>${esc(caption)}<select id="${id}">${items.map(([v,t])=>`<option value="${esc(v)}" ${String(v)===String(current)?'selected':''}>${esc(t)}</option>`).join('')}</select></label>`;
const unique=(rows,key)=>[...new Set(rows.flatMap(r=>C.tokens(C.value(r,key))))];
const state={module:'overview',tab:0,table:'',filters:{},where:[],page:0,pageSize:25,sort:null,focusImage:'',focusObject:'',focusWorker:'',pool:'',path:'',k:null,metric:'B8L2',rows:[],all:[],meta:null,selected:new Set(),notes:{},loadToken:0,tableCache:new Map(),pending:new Map(),geometryCache:new Map()};
let index,assets,overview,imageMap=new Map(),scoreMap=new Map(),lastNoteKey='';
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,4500);}
function download(name,body,type){const url=URL.createObjectURL(new Blob([body],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);}
async function read(path){if(!state.pending.has(path)){const p=window.readResearchJSON(path).finally(()=>state.pending.delete(path));state.pending.set(path,p);}return state.pending.get(path);}
async function table(id){
 if(state.tableCache.has(id))return state.tableCache.get(id);
 const meta=index.tables.find(t=>t.id===id);if(!meta)throw Error('尚未接入数据表：'+id);
 const task=(async()=>{const rows=[];for(const part of meta.parts){const d=await read(dataset.tablesBase+part.path);if(d.columns.join('\u001f')!==meta.columns.join('\u001f'))throw Error('字段漂移：'+id);for(const r of d.rows){if(r.length!==d.columns.length)throw Error('行宽漂移：'+id);rows.push(Object.fromEntries(d.columns.map((k,i)=>[k,r[i]])));}}if(rows.length!==meta.row_count)throw Error('行数不一致：'+id);return rows;})();
 state.tableCache.set(id,task);while(state.tableCache.size>4)state.tableCache.delete(state.tableCache.keys().next().value);
 try{return await task;}catch(e){state.tableCache.delete(id);throw e;}
}
async function imageDetail(id){const im=imageMap.get(id);if(!im)throw Error('该图片没有接入几何索引：'+id);return geometry(dataset.resourcesBase+im.detail);}
async function geometry(path){if(!state.geometryCache.has(path)){state.geometryCache.set(path,read(path));while(state.geometryCache.size>5)state.geometryCache.delete(state.geometryCache.keys().next().value);}return state.geometryCache.get(path);}
function route(patch={}){
 const p=new URLSearchParams(location.hash.slice(1));for(const [k,v] of Object.entries(patch)){if(v===null||v==='')p.delete(k);else p.set(k,typeof v==='object'?JSON.stringify(v):String(v));}
 if(!p.has('module'))p.set('module','overview');const next=p.toString();if(next===location.hash.slice(1))render();else{$('content').dataset.ready='';location.hash=next;}
}
function readRoute(){const p=new URLSearchParams(location.hash.slice(1)),aliases={all:'data',inventory:'coverage',difficulty:'images',history:'sources'};
 const previous=[state.module,state.tab,state.table].join('|');
 state.module=aliases[p.get('module')]||p.get('module')||'overview';if(!modules[state.module])state.module='overview';
 state.tab=Number(p.get('tab')||0);state.table=p.get('table')||'';state.filters={};for(const [k,v] of p)if(k.startsWith('f_'))state.filters[k.slice(2)]=v;
 state.where=JSON.parse(p.get('where')||'[]');state.focusImage=p.get('image')||state.focusImage;state.focusObject=p.get('object')||'';state.focusWorker=p.get('worker')||'';state.metric=p.get('metric')||'B8L2';state.page=0;state.selected.clear();
 const allowed=state.module==='same_room'?['B8L2','D10','IoU3D100','source_time_seconds','source_active_time_seconds','target_matched_time_seconds']:['B8L2','D10'];
 state.metricNotice=allowed.includes(state.metric)?'':`当前模块没有 ${state.metric} 画像／终点评价，改用B8L2；原比较可在同房模块查看。`;
 if(state.metricNotice)state.metric='B8L2';
 if(previous!==[state.module,state.tab,state.table].join('|')){state.chartField='';state.currentRecord=null;}
}
function activeContext(){const f=state.filters,active=Object.entries(f).filter(([,v])=>v);$('activeFilters').innerHTML=active.map(([k,v])=>`<span class="chip">${esc(filterLabels[k]||k)}：${esc(v)} <button data-remove="${esc(k)}" aria-label="移除${esc(filterLabels[k]||k)}">×</button></span>`).join('')||'<span class="muted">全部记录 · 无附加交叉筛选</span>';
 if(state.where.length)$('activeFilters').insertAdjacentHTML('beforeend',state.where.map((w,i)=>`<span class="chip">${esc(label(w.field))} ${esc(w.op)} ${esc(w.val??'')} <button data-where-remove="${i}">×</button></span>`).join(''));
 const bar=$('activeFilters').closest('.contextbar');if(bar)bar.hidden=!(active.length||state.where.length);
}
const filterLabels={condition:'采集条件',image:'图片ID／代码',worker:'人员ID',difficulty:'难度',doorway:'门洞交界',oos:'OOS',gt:'参考／图级状态',scope:'空间范围',building:'建筑',target:'目标／参考ID',relation:'已有关系组／请求',analysis:'用途',search:'全文搜索'};
function openFilters(){const f=state.filters;
 const opts={condition:[['','全部'],['manual','Manual'],['semi','Semi'],['oos','OOS采集条件']],difficulty:[['','全部'],...[...new Set(assets.images.map(i=>i.difficulty.label))].sort().map(v=>[v,v])],doorway:[['','全部'],['true','是'],['false','明确否'],['null','未记录']],oos:[['','全部'],['true','是'],['false','明确否'],['null','未记录']],gt:[['','全部'],['gt_problem','GT／参考问题'],['gt_uncertain','GT不确定'],['image_hold','分析暂缓'],['current_pending','问题待定']],scope:[['','全部'],['multiple','多空间／参考'],['candidate','有人工候选'],['incomplete','完整顶界待补']],analysis:[['','全部记录'],['quality','主质量可用'],['diagnostic','有诊断值、非主质量']]};
 $('filterFields').innerHTML=Object.entries(filterLabels).map(([key,title])=>opts[key]?select('f-'+key,opts[key],f[key]||'',title):`<label>${title}<input id="f-${key}" name="${key}" value="${esc(f[key]||'')}" placeholder="完整ID或留空"></label>`).join('');
 $('filters').showModal();
}
function metricCards(items){return `<div class="metrics">${items.map(([caption,v,note])=>`<div class="metric"><span>${esc(caption)}</span><strong>${esc(fmt(v))}</strong>${note?`<small>${esc(note)}</small>`:''}</div>`).join('')}</div>`;}
function support(rows){return metricCards([['当前表记录',rows.length,'不自动视作独立样本'],['关联图片',unique(rows,'image').length||null,'按源表可识别ID去重'],['关联人员',unique(rows,'worker').length||null,'缺成员字段时不推断']]);}
function passesWhere(r){return state.where.every(w=>{const v=r[w.field];if(w.op==='any')return true;if(w.op==='missing')return C.empty(v);if(w.op==='present')return !C.empty(v);if(w.op==='range')return C.numeric(v)&&v>=Number(w.val)&&v<=Number(w.max);return w.op==='contains'?String(v??'').includes(w.val):String(v??'')===w.val;});}
function facetDefaults(rows){
 const f={};if(state.module==='fusion'&&state.meta?.id!=='fusion__trajectory_scores'&&rows.some(r=>r.selection_metric==='B8L2'))f.selection_metric='B8L2';
 return Object.fromEntries(Object.entries(f).filter(([k])=>!state.where.some(w=>w.field===k)));
}
function facetControls(rows){const keys=state.module==='fusion'&&state.meta?.id!=='fusion__trajectory_scores'?['selection_metric','label_basis','policy','replacement_kind','k','layer','both_main_quality']:state.module==='workers'?['Q_group','QT_group','fold']:state.module==='same_room'?['origin','mode','method','k','layer','relation_eligible','supported','warm_start','request_id','both_quality']:[];
 const defaults=facetDefaults(rows);return keys.filter(k=>rows.some(r=>!C.empty(r[k]))).map(k=>{
  const vals=[...new Set(rows.map(r=>r[k]).filter(v=>!C.empty(v)))];if(vals.length>80)return '';
  const chosen=state.where.find(w=>w.field===k&&w.facet)?.val??defaults[k]??'';
  const caption=k==='selection_metric'?'分类／选人指标（与终点评价分开）':label(k);
  return `<label>${esc(caption)}<select data-facet="${esc(k)}"><option value="">全部</option>${vals.map(v=>`<option value="${esc(String(v))}" ${String(v)===String(chosen)?'selected':''}>${esc(fmt(v))}</option>`).join('')}</select></label>`;
 }).join('');}
function applyRows(rows){let result;
 if(state.module==='workers'&&rows.some(r=>Object.hasOwn(r,'Q_effect')||Object.hasOwn(r,'relative_q'))){
  const records=C.filterRows([...scoreMap.values()],state.filters,imageMap).rows,workers=new Set(records.map(r=>r.worker_id));
  result={rows:rows.filter(r=>workers.has(r.worker_id)),unsupported:[]};
  $('notice').innerHTML=dataset.release==='v2'?'<div class="info">图片／条件筛选限定可查看的人员名单，不重算画像。此处画像采用原快照的描述性候选；最新人员分类与楼外验证见“人员标法与团队”。</div>':'<div class="info">图片／条件筛选仅限定可查看的人员名单。Q/T效应仍为所选源画像的冻结训练结果，不因筛选重新拟合；楼外、专项结果请使用对应页签。</div>';
 }else result=C.filterRows(rows,state.filters,imageMap);const defaults=facetDefaults(rows);let out=result.rows.filter(r=>passesWhere(r)&&Object.entries(defaults).every(([k,v])=>r[k]===v));
 if(rows.some(r=>r.metric)&&['workers','same_room'].includes(state.module))out=out.filter(r=>!r.metric||r.metric===state.metric);
 state.rows=out;return result.unsupported;
}
function defaultColumns(rows){const cols=Object.keys(rows[0]||{});if(state.meta?.id.startsWith('same_room_prediction__')){const preferred=['metric','origin','mode','k','method','building','building_equal_mae','buildings','worker_id','actual','predicted','absolute_error','error_unit','warm_start','relation_eligible','n_paired','absolute_mean_gap','mean_absolute_person_delta','worker_spearman','gain_vs_calibrated_history','image_a','image_b'];return [...preferred.filter(k=>cols.includes(k)),...cols.filter(k=>!preferred.includes(k))].slice(0,14);}const prior=['image_code','image','image_id','object_id','worker_id','pool_id','path_id','k','request_id','rescore_target_id','reference_id','condition','selection_metric','policy','Q_effect','Q_group','T_source_effect','QT_group','Q_contexts','Q_buildings','B8L2','D10','IoU3D100','quality_usable','calculation_status','score_status','member_workers'];return [...prior.filter(k=>cols.includes(k)),...cols.filter(k=>!prior.includes(k))].slice(0,14);}
function drawTable(){const host=$('tableArea');if(!host)return;const rows=[...state.rows];if(state.sort){const {key,asc}=state.sort;rows.sort((a,b)=>{const x=a[key],y=b[key];if(C.empty(x))return 1;if(C.empty(y))return -1;return (C.numeric(x)&&C.numeric(y)?x-y:String(x).localeCompare(String(y)))*(asc?1:-1);});}
 state.viewRows=rows;const columns=defaultColumns(rows),pages=Math.max(1,Math.ceil(rows.length/state.pageSize));state.page=Math.min(state.page,pages-1);
 const start=state.page*state.pageSize;
 host.innerHTML=`<div class="checkbar"><span class="muted">单击行：详情／几何；复选框：批量比较，互不改变当前详情。</span><button data-act="compare">比较选中 ${state.selected.size} 项</button></div><div class="tablewrap"><table id="dataTable"><thead><tr><th>比较</th>${columns.map(k=>`<th scope="col"><button data-sort="${esc(k)}">${esc(label(k))}${state.sort?.key===k?(state.sort.asc?' ↑':' ↓'):''}</button>${hintButton(k)}</th>`).join('')}</tr></thead><tbody>${rows.slice(start,start+state.pageSize).map((r,i)=>`<tr data-row="${start+i}" tabindex="0"><td><input type="checkbox" data-check="${start+i}" aria-label="加入比较 ${esc(r.object_id||r.worker_id||r.request_id||start+i)}" ${state.selected.has(rowKey(r))?'checked':''}></td>${columns.map(k=>`<td class="${C.numeric(r[k])?'num':''}" title="${esc(fmt(r[k]))}">${esc(fmt(r[k]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div><div class="pagination"><span id="rowCount">${rows.length.toLocaleString('zh-CN')} 条 · 完整筛选结果</span><label>每页 <select id="pageSize">${[25,50,100].map(n=>`<option ${n===state.pageSize?'selected':''}>${n}</option>`).join('')}</select></label><button data-page="-1" ${state.page===0?'disabled':''}>上一页</button><span>${state.page+1} / ${pages}</span><button data-page="1" ${state.page>=pages-1?'disabled':''}>下一页</button></div>${!rows.length?placeholder('当前条件无记录','不补示例行；可修改筛选或选择其它表。'):''}`;
}
function rowKey(r){return [state.meta?.id,r.object_id||r.worker_id||r.request_id||r.pool_id||'',r.path_id||'',r.k??'',r.metric||'',r.fold||'',JSON.stringify(r)].join(':');}
function tablePanel(){return `<section class="panel"><div class="subheading"><h2>完整筛选明细</h2><div class="actions"><button data-act="export">导出完整明细</button><button data-act="source">当前表来源</button></div></div><div class="toolbar"><label>字段<select id="whereField">${state.meta.columns.map(k=>`<option value="${esc(k)}">${esc(label(k))}</option>`).join('')}</select></label><label>关系<select id="whereOp"><option value="eq">等于</option><option value="contains">包含</option><option value="range">数值区间</option><option value="missing">缺失</option><option value="present">非缺失</option></select></label><label>值<input id="whereVal"></label><label>区间上界<input id="whereMax"></label><button data-act="addWhere">应用表内筛选</button></div><div id="tableArea"></div></section>`;}
function exportRows(rows,kind){if(!rows?.length){toast('当前没有可导出的记录');return;}const meta={__snapshot:SNAPSHOT,__table:state.meta?.id||state.module,__scope:kind,__evaluation_metric:state.metric,__filters:JSON.stringify(state.filters),__where:JSON.stringify(state.where),__default_facets:JSON.stringify(facetDefaults(state.all))};
 const out=rows.map(r=>({...meta,...r})),columns=[...new Set(out.flatMap(r=>Object.keys(r)))];download(`research-${state.module}-${kind}-${dataset.release}.csv`,C.csv(out,columns),'text/csv;charset=utf-8');}

const supportSets=new Map();let chartCounter=0;
function svgChart(rows,yKey,type='histogram',xKey=null,title=null){
 const id=String(++chartCounter),usable=C.metricRows(rows,yKey).filter(r=>!xKey||C.numeric(r[xKey]));supportSets.set(id,usable);
 if(!usable.length)return placeholder(title||label(yKey),'当前筛选与该指标没有真实非空交集；缺失不补零。');
 const y=usable.map(r=>r[yKey]),s=C.stats(y),W=620,H=250,P={l:55,r:20,t:20,b:45},pw=W-P.l-P.r,ph=H-P.t-P.b;
 let shapes='',xMin=0,xMax=1,yMin=0,yMax=1;
 if(type==='histogram'){
  xMin=Math.min(...y);xMax=Math.max(...y);if(xMax===xMin){xMin-=.5;xMax+=.5;}
  const bins=Array.from({length:20},()=>[]);usable.forEach(r=>bins[Math.min(19,Math.floor((r[yKey]-xMin)/(xMax-xMin)*20))].push(r));yMax=Math.max(...bins.map(b=>b.length),1);
  shapes=bins.map((b,i)=>{const h=b.length/yMax*ph;return `<rect x="${P.l+i/20*pw}" y="${P.t+ph-h}" width="${pw/20-2}" height="${h}" fill="#1d4ed8"><title>${b.length}条 · ${fmt(xMin+i/20*(xMax-xMin))} 至 ${fmt(xMin+(i+1)/20*(xMax-xMin))}</title></rect>`;}).join('');
 }else{
  const x=usable.map(r=>r[xKey]);xMin=Math.min(...x);xMax=Math.max(...x);yMin=Math.min(0,...y);yMax=Math.max(...y);if(xMax===xMin)xMax=xMin+1;if(yMax===yMin)yMax=yMin+1;
  const step=Math.max(1,Math.ceil(usable.length/800));shapes=usable.filter((_,i)=>i%step===0).map(r=>`<circle cx="${P.l+(r[xKey]-xMin)/(xMax-xMin)*pw}" cy="${P.t+(1-(r[yKey]-yMin)/(yMax-yMin))*ph}" r="3" fill="#1d4ed8" opacity=".65"><title>${esc(label(xKey))} ${fmt(r[xKey])} · ${esc(label(yKey))} ${fmt(r[yKey])}</title></circle>`).join('');
 }
 if(yKey.startsWith('D10'))shapes=shapes.replaceAll('#1d4ed8','#b45309');
 const axes=Array.from({length:5},(_,i)=>{const xx=P.l+i/4*pw,yy=P.t+ph-i/4*ph;return `<line x1="${P.l}" x2="${W-P.r}" y1="${yy}" y2="${yy}" stroke="#e2e8f0"/><text x="${P.l-7}" y="${yy+4}" text-anchor="end">${esc(fmt(yMin+(yMax-yMin)*i/4))}</text><text x="${xx}" y="${H-25}" text-anchor="middle">${esc(fmt(xMin+(xMax-xMin)*i/4))}</text>`;}).join('');
 return `<section class="panel chart"><div class="subheading"><h2>${esc(title||label(yKey))}${hintButton(yKey)}</h2><button data-support="${id}">导出图表支持明细</button></div><p class="scope-label">真实支持 n=${usable.length} · 中位数 ${fmt(s.median)} · P10 ${fmt(s.p10)} · IQR ${fmt(s.p25)}–${fmt(s.p75)}</p><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title||label(yKey))}">${axes}${shapes}<text x="${W/2}" y="${H-3}" text-anchor="middle">${esc(type==='histogram'?label(yKey):label(xKey))}</text><text x="8" y="12">${esc(type==='histogram'?'记录数':label(yKey))}</text></svg>${type!=='histogram'&&usable.length>800?'<small>散点按源表顺序等间隔显示至多800点；统计与导出使用完整的支持范围。</small>':''}</section>`;
}
function lineChart(rows,yKey,title){
 const sorted=[...rows].sort((a,b)=>a.k-b.k).map(r=>/^(B8L2|D10)$/.test(yKey)&&!C.metricRows([r],yKey).length?{...r,[yKey]:null}:r),actual=sorted.filter(r=>C.numeric(r[yKey]));if(!actual.length)return placeholder(title,'当前路径没有该项主比较可用的保存测量；诊断值或原留出不补入。');
 const lo=Math.min(...sorted.map(r=>r.k)),hi=Math.max(lo+1,...sorted.map(r=>r.k)),max=Math.max(...actual.map(r=>r[yKey]),.01),min=Math.min(0,...actual.map(r=>r[yKey]));
 const x=k=>50+(k-lo)/(hi-lo)*510,y=v=>160-(v-min)/(max-min)*125;let segment=[],paths='';const flush=()=>{if(segment.length>1)paths+=`<polyline points="${segment.join(' ')}" fill="none" stroke="#1d4ed8" stroke-width="2"/>`;segment=[];};
 for(const r of sorted){if(!C.numeric(r[yKey])){flush();continue;}segment.push(`${x(r.k)},${y(r[yKey])}`);}flush();
 if(yKey==='D10')paths=paths.replaceAll('#1d4ed8','#b45309').replaceAll('stroke-width="2"','stroke-width="2" stroke-dasharray="6 4"');
 const dots=sorted.map(r=>`<text x="${x(r.k)}" y="182" text-anchor="middle">${r.k}</text>${C.numeric(r[yKey])?`<circle data-k="${r.k}" tabindex="0" role="button" aria-label="查看k=${r.k}节点" cx="${x(r.k)}" cy="${y(r[yKey])}" r="5" fill="${yKey==='D10'?'#b45309':'#1d4ed8'}" stroke="${r.k===state.k?'#111':'none'}" stroke-width="2"><title>k=${r.k} · ${fmt(r[yKey])}</title></circle>`:`<text x="${x(r.k)}" y="156" text-anchor="middle">缺失</text>`}`).join('');
 return `<section class="panel chart"><h3>${esc(title)}</h3><svg viewBox="0 0 590 210" role="img" aria-label="${esc(title)}"><line x1="50" y1="160" x2="560" y2="160" stroke="#94a3b8"/><text x="45" y="35" text-anchor="end">${fmt(max)}</text><text x="45" y="160" text-anchor="end">${fmt(min)}</text>${paths}${dots}<text x="300" y="205" text-anchor="middle">人数k · 点击节点联动已保存成员与几何</text></svg></section>`;
}
function chosenMetric(rows){const cols=Object.keys(rows[0]||{});return (C.fields[state.metric]||[]).find(k=>cols.includes(k)&&rows.some(r=>C.numeric(r[k])))||cols.find(k=>k.startsWith(state.metric)&&rows.some(r=>C.numeric(r[k])));}
function genericChart(rows){const presets={'fusion__same_k_stability':'floor_jaccard_difference','same_room__endpoint_pairs':'mean_absolute_person_delta','workers__absolute_Q_training_profiles':'mean','workers__semi_initialization_scores':'worker_attributable_gain_'+state.metric};const preset=presets[state.meta?.id];const k=state.chartField&&rows.some(r=>C.numeric(r[state.chartField]))?state.chartField:preset||chosenMetric(rows);
 return k?svgChart(rows,k,'histogram'):placeholder('专题图表待配置','明细已接通；该表尚未绑定默认数值图，不用其它字段代替质量结果。');}
function sameRoomPredictionPanel(id){
 if(!id.startsWith('same_room_prediction__'))return '';
 const base='../../same_room/same_room_v2_prediction_20261019/';
 const note=`<div class="info">v2同房条件预测：OOS已排除，门洞单列；此首轮预测面板未纳入人员分类，同房构成与大块结果在后续表保留原标签。源视角Q已有评价参考，尚无确认异房匹配对照。MAE越低越好；耗时误差在log(1+秒数)上计算，不能读作秒数。配对描述及审计表保留未准入关系；主分析需普通场景、关系可比、共同有效人员≥4。 · </div>`;
 if(id!=='same_room_prediction__prediction_summary')return note;
 const coverage=index.documents.find(d=>d.content.schema==='same_room_v2_prediction_20261019_r1').content.coverage.find(r=>r.metric==='B8L2');
 return note+`<section class="panel"><h2>首轮固定的研究范围</h2><p>以下覆盖与原报告图是固定结果，不随下方明细筛选或指标切换重算。质量描述、本人源视角预测和其他人数实验各有自己的支持范围。</p>${metricCards([['质量直接同房关系',coverage.pairs,'不是独立房间数'],['图片 / 建筑',`${coverage.images} / ${coverage.buildings}`,'质量描述范围'],['共同有效人员中位数',coverage.median_common,'每对关系']])}<div class="split equal"><figure><img style="width:100%;height:auto" src="${base}prediction_by_building.png" alt="本人源视角预测的逐建筑增益，旧新增人员分列"><figcaption>本人源视角预测：人员来源分开，正增益表示误差下降。</figcaption></figure><figure><img style="width:100%;height:auto" src="${base}source_people_learning.png" alt="固定评价面板中源视角其他人员从4增加到16人的预测误差"><figcaption>人数实验固定30对关系、39图、10栋、35名新增人员；k是源视角其他人员数，不是融合团队人数。</figcaption></figure></div></section>`;
}
function findingSummary(module){
 const item=dataset.release==='v2'&&overview.sections.find(s=>s.id===module);if(!item)return '';
 return `<section class="panel"><h2>${esc(item.title)}</h2><p><strong>${esc(item.finding)}</strong></p><p>${esc(item.example)}</p><p class="scope-label">支持：${esc(item.support)}</p><p class="scope-label">边界：${esc(item.counterexample)}</p><p class="scope-label">固定专题支持，不随明细筛选重算。<a href="${esc(item.source)}" target="_blank" rel="noopener">完整研究与来源</a></p></section>`;
}
async function render(){
 const token=++state.loadToken,mod=modules[state.module];supportSets.clear();chartCounter=0;
  const exportButton=document.querySelector('.pagehead [data-act="export"]');exportButton.disabled=false;exportButton.textContent='导出筛选明细';
 $('title').textContent=mod[0];$('description').textContent=mod[1];$('crumb').textContent=`数据 ${dataset.release} / ${dataset.analysisLabel} / ${mod[0]}`;activeContext();
 document.querySelectorAll('#navigation a').forEach(a=>{const active=a.dataset.module===state.module;a.classList.toggle('active',active);if(active&&a.closest('details'))a.closest('details').open=true;});
 const tabs=mod[2];state.tab=Math.min(Math.max(0,state.tab),Math.max(0,tabs.length-1));
 $('tabs').innerHTML=tabs.map(([title],i)=>`<button type="button" role="tab" aria-selected="${i===state.tab}" aria-controls="content" data-tab="${i}" class="${i===state.tab?'active':''}">${esc(title)}</button>`).join('');
 $('content').dataset.ready='';$('content').innerHTML='<div class="placeholder" role="status">正在按需读取本地数据…</div>';
 $('notice').innerHTML='';state.rows=[];state.meta=null;
 try{
  if(['profiles','benefits'].includes(state.module)){await PersonnelResults.render($('content'),{mode:state.module,tab:state.tab,assets,loadImage:imageDetail,read,isCurrent:()=>token===state.loadToken,resourcesBase:dataset.resourcesBase,snapshot:SNAPSHOT,release:dataset.release});if(token===state.loadToken&&state.module==='profiles'&&state.tab===0)$('content').insertAdjacentHTML('afterbegin',findingSummary('profiles'));return;}
  if(state.module==='personnel_main'){await PersonnelMain.render($('content'),{release:dataset.release,index,tab:state.tab,table,hintButton,assets,imageDetail,filters:state.filters,isCurrent:()=>token===state.loadToken});return;}
  if(state.module==='method_supplements'){await MethodSupplements.render($('content'),{release:dataset.release,tab:state.tab,assets,read,resourcesBase:dataset.resourcesBase,snapshot:SNAPSHOT,hintButton,imageDetail,isCurrent:()=>token===state.loadToken});return;}
  if(state.module==='case_story'){await CaseStory.render($('content'),{release:dataset.release,assets,deepLink:new URLSearchParams(location.hash.slice(1)),imageDetail,read,resourcesBase:dataset.resourcesBase,snapshot:SNAPSHOT,hintButton,isCurrent:()=>token===state.loadToken,navigate:patch=>route(patch)});return;}
  if(state.module==='evidence'){await ResearchEvidence.render($('content'),{tab:state.tab,assets,loadImage:imageDetail,read,isCurrent:()=>token===state.loadToken,filters:state.filters,navigate:patch=>route(patch),resourcesBase:dataset.resourcesBase,snapshot:SNAPSHOT,release:dataset.release});return;}
  if(['patterns','multiview'].includes(state.module)){if(dataset.release!=='v2'){ $('content').textContent='该交互使用v2保存结果，请切换到v2。';return; }await ResearchComparison.render($('content'),{mode:state.module,assets,loadImage:imageDetail,read,isCurrent:()=>token===state.loadToken,filters:state.filters,snapshot:SNAPSHOT,release:dataset.release,deepLink:new URLSearchParams(location.hash.slice(1)),onNavigate:patch=>route(patch),onContext:context=>{if(context.blind){$('activeFilters').textContent='盲审模式 · 人员身份、类别与分数隐藏；实际上下文随反馈导出。';const bar=$('activeFilters').closest('.contextbar');if(bar)bar.hidden=false;}else activeContext();}});return;}
  if(state.module==='overview'){renderOverview();return;}
  if(state.module==='sources'){renderSources();return;}
  if(state.module==='images'){await renderImages(token);return;}
  if(state.module==='conditions'&&dataset.release==='v1'){$('content').innerHTML=placeholder('当前条件表属于 v2','请切换到 v2；v1 历史结果仍从数据浏览进入。');return;}
  if(dataset.release==='v2'&&!tabs.length){$('content').innerHTML=placeholder('v2专题尚未运行','该专题当前仅有v1历史结果，可切换数据版本查看。不将历史融合或分簇结果计入v2。');return;}
  if(state.module==='coverage'&&state.tab===5&&dataset.release==='v1'){renderPlan();return;}
  const id=state.table||tabs[state.tab]?.[1]||'quality__shared_records';const rows=await table(id);if(token!==state.loadToken)return;
  state.meta=index.tables.find(t=>t.id===id);state.all=rows;state.sort=null;
  const unsupported=applyRows(rows);
  if(unsupported.length){$('notice').innerHTML=`<div class="warning">当前表缺少 ${esc(unsupported.join('、'))} 所需关联字段，未展示未筛选的汇总。请选择可关联明细或明确修改条件。</div>`;}
  const options=state.module==='data'?index.tables.map(t=>[t.id,t.id+(t.status==='superseded'?' · 被替代接口':'')]):tabs.filter(t=>t[1]).map(t=>[t[1],t[0]+' · '+t[1]]);
  const numericCols=state.meta.columns.filter(k=>rows.some(r=>C.numeric(r[k])));
  if(state.module==='time'&&!state.chartField&&(state.tab===1||state.tab===2))state.chartField=state.tab===1?'source_active_time_seconds':'target_matched_time_seconds';
  const metricOptions=[['B8L2','B8L2 主线'],['D10','D10 敏感性']];if(state.module==='same_room'&&rows.some(r=>r.metric))metricOptions.push(['IoU3D100','均高棱柱IoU×100'],['source_time_seconds','历史来源活动时间'],['source_active_time_seconds','v2来源报告耗时（预测误差为log1p）'],['target_matched_time_seconds','同目标时间（预测误差为log1p）']);
  const toolbar=`<section class="panel"><div class="toolbar">${select('tableSelect',options,id,'当前表／对象粒度')}${select('metricSelect',metricOptions,state.metric,state.module==='workers'?'画像指标':'终点评价指标')}${facetControls(rows)}${select('chartField',[['','使用专题默认字段'],...numericCols.map(k=>[k,label(k)])],state.chartField||'','图表字段')}<span class="muted">数值、单位及用途按当前表的研究口径解释；缺失不填0。</span></div></section>`;
  const title=support(state.rows);
  if(state.module==='quality'){
   $('content').innerHTML=`<div class="info">已验收的 25 题人工质量判断、完整双人标注与高度/底点控制：<a href="#module=method_supplements&tab=2">进入质量方法补充</a>。</div>`+toolbar+`<div id="focusPanel"></div>`+tablePanel()+`<details><summary>当前范围分布与指标对照</summary>${genericChart(state.rows)}${svgChart(state.rows,'D10','scatter','B8L2','同输入、同参考B8L2／D10对照')}</details>`;
   const row=state.rows.find(r=>r.object_id===state.focusObject)||state.rows.find(r=>C.truth(r.quality_usable))||state.rows[0];if(row)await qualityFocus(row,$('focusPanel'),token);
  }else if(state.module==='workers'){
   $('content').innerHTML=toolbar+title+`<div class="split"><div>${tablePanel()}${genericChart(state.rows)}</div><section class="panel" id="focusPanel"></section></div>`;
   const row=state.rows.find(r=>r.worker_id===state.focusWorker)||state.rows[0];if(row)profile(row);
  }else if(state.module==='same_room'){
   $('content').innerHTML=(state.tab===0?findingSummary('same_room'):'')+sameRoomPredictionPanel(id)+toolbar+title+`<div id="focusPanel"></div>`+tablePanel();const row=state.rows[0];if(row)await pairFocus(row,token);
  }else if(state.module==='same_room_review'){
   $('content').innerHTML=`<section class="panel"><h2>结构表达可重复，位置迁移与严重错误筛查仍有限</h2><p>44图、7楼、55人中，本人源视角对9°未匹配参考角点比例的预测MAE比同源他人少1.099个百分点，5/7楼改善；底点偏移和面积log误差却7/7楼更差。未匹配也可能来自定位偏离，不直接等同漏画。</p><p>同预算个人Q校准MAE从12.364降至11.145，6/7楼改善；目标Q&lt;50的事后子集MAE为25.719，对照23.443，反而更差。改善平均预测不能用来筛查严重错误；该子集也不是选人时已知的信息。</p><p class="hint-glossary">预测误差 MAE ${hintButton('mae')} · 有符号偏差 ${hintButton('bias')} · 相关与预测精度 ${hintButton('spearman_r')} · 百分点 ${hintButton('percentage_points')} · 重抽区间 ${hintButton('resampling_unit')}。</p><div class="actions"><a href="../../same_room/same_room_independent_followup_20261021/structure/summary.csv">结构迁移逐指标汇总</a></div></section>`+toolbar+title+tablePanel();
  }else if(state.module==='fusion'&&id==='fusion__trajectory_scores'){
   $('content').innerHTML=`<div class="info">固定 138 队的墙线、代表原答和 Lee MV50 同队比较：<a href="#module=method_supplements&tab=1">进入融合方法补充</a>。</div>`+toolbar+`<div id="processFocus"></div>`+tablePanel();await processFocus(token);
  }else if(state.module==='fusion'){
   $('content').innerHTML=`<div class="info">固定 138 队的三法保存几何、均值和偏低的部分（P10）以及全部失败：<a href="#module=method_supplements&tab=1">进入融合方法补充</a>。</div>`+toolbar+`<div class="info">选人指标、终点评价和成员是否改变分开。以下只展示现有请求与保存结果，不生成新团队。</div><div id="teamFocus"></div>`+title+genericChart(state.rows)+tablePanel();
   if(state.rows[0])await teamFocus(state.rows[0],token);
  }else if(state.module==='time'&&state.tab===0){
   $('content').innerHTML=toolbar+title+`<div id="focusPanel"></div>`+genericChart(state.rows)+tablePanel();if(state.rows[0])await semiFocus(state.rows[0],token);
  }else if(state.module==='data'){
   $('content').innerHTML=toolbar+`<p class="scope-label">当前表 ${state.rows.length.toLocaleString('zh-CN')} 条 · 关联图片 ${unique(state.rows,'image').length} · 关联人员 ${unique(state.rows,'worker').length}；记录数不作为独立样本数。</p><div class="split equal">${genericChart(state.rows)}${id==='quality__shared_records'?svgChart(state.rows,'D10','scatter','B8L2','B8L2／D10 · 同输入对照'):placeholder('对象关联','单击明细行可追到图像、人员、几何和来源。')}</div>`+tablePanel();
  }else{
   let note='';if(state.module==='fusion')note='<div class="info">当前为同图同k的既有组合／换人／重选成员证据。成员选择指标与终点评价分开；打开记录可追到真实路径和来源。单条路径位于“真实人数过程”。</div>';
   if(state.module==='coverage')note='<div class="info">计算状态、主质量用途与诊断状态分别读取；多重原因可重叠，原因行数不能直接相加作为作答总数。</div>';
   if(state.module==='taxonomy')note='<div class="info">M0/M1是Manual结构表达工作分类；SP_LOW是Semi条件性尺度组，A2是独立几何关系分区。楼外表先在图内合并参考面板，再按图、楼等权；A2严格匹配加入共同点数层，n_pairs为匹配前对数，n_pairs_contributing为实际贡献对数。换入M1的历史Q较高，当前没有标法独立净收益结论。 · <a href="#module=patterns" data-module="patterns">查看此前保存原答/融合</a></div><details class="panel"><summary>历史分类原答与团队正反例图</summary><p>图例对应的逐对象成员在“图例与逐对象成员”页签；C13/C14为保存团队，页面筛选不会重新融合。历史图沿用图内配色：原图黄色线、BEV黑色虚线为参考；粉色、蓝色等表示图内对应人员或队伍。坐标单位为相机高度h，不是米。</p><div class="actions"><a href="../../workers/personnel_taxonomy_20261021/figures/C01_manual_classes.png">C01 Manual短转折</a><a href="../../workers/personnel_taxonomy_20261021/figures/C02_manual_classes.png">C02 GT遗漏与标法分开</a><a href="../../workers/personnel_taxonomy_20261021/figures/C08_A2_positive.png">C08 A2正例</a><a href="../../workers/personnel_taxonomy_20261021/figures/C09_A2_counterexample.png">C09 A2反例</a><a href="../../workers/personnel_taxonomy_20261021/figures/C10_Semi_height.png">C10 Semi尺度</a><a href="../../workers/personnel_taxonomy_20261021/figures/C11_Semi_height_counterexample.png">C11 Semi反例</a><a href="../../workers/personnel_taxonomy_20261021/figures/C13_jtc26_third_vote.png">C13 同类关键第三票</a><a href="../../workers/personnel_taxonomy_20261021/figures/C14_Uw22_threshold.png">C14 必要结构失选与恢复</a></div></details>';
   if(state.module==='mechanisms')note='<div class="info">16张接续表按源模块保留原粒度。共同77图的快慢差异、近分异形、同配比不同成员/对应、G046/G057局部同房观测可经图或对象关联回原研究台；无关联字段的汇总在全局筛选下明确停显。G046 A/B同角已确认；G057局部预测未胜恒定0.5基线。<a href="../review_progress_20261021/index.html">六站原图与机制图</a> · <a href="#module=images" data-module="images">逐图原答/参考</a></div>';
   if(state.module==='time'){
    note='<div class="info">来源活动时间和同目标审计时间各自按真实非空支持统计。未改动不自动判失败，编辑后未知不判成功。</div>';
   }
   $('content').innerHTML=toolbar+note+title+genericChart(state.rows)+tablePanel();
   if(state.tab===0&&state.module==='conditions')$('content').insertAdjacentHTML('afterbegin',findingSummary('difficulty'));
  }
  if(token!==state.loadToken)return;drawTable();
  if(unsupported.length)$('content').insertAdjacentHTML('afterbegin',placeholder('当前筛选不适用于此表','未展示全表数字以免误导；更换明细表或清空不兼容条件。'));
 }catch(e){if(token===state.loadToken)$('content').innerHTML=placeholder('该模块读取失败',e.message+'；其它模块仍可查看。');}
 finally{if(token===state.loadToken){$('content').dataset.ready=state.module;if(state.metricNotice)$('notice').insertAdjacentHTML('beforeend',`<div class="info">${esc(state.metricNotice)}</div>`);}}
}
async function qualityFocus(row,host,token){
 if(!host)return;const focusToken=String(Number(host.dataset.focusToken||0)+1);host.dataset.focusToken=focusToken;const imageId=row.image_id||C.value(row,'image');if(!imageId){host.innerHTML=placeholder('该行不是逐作答记录','请在作答明细中选择带object_id和image_id的记录查看几何。');return;}
 const image=await imageDetail(imageId);if(token!==state.loadToken||!host.isConnected||host.dataset.focusToken!==focusToken)return;
 const answer=image.annotations.find(a=>a.object_id===row.object_id),ref=image.references.find(r=>r.target_id===(row.rescore_target_id||answer?.target_id));
 state.focusObject=row.object_id;
 const keys=['object_id','image_id','worker_id','condition','rescore_target_id','reference_id','reference_version','calculation_status','quality_usable','B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','diagnostic_B8L2','diagnostic_D10','quality_exclusion_reasons'];
 host.innerHTML=`<div class="split"><div id="answerGeometry"></div><section class="panel"><h2>作答、参考与测量</h2><div class="actions"><button data-jump="images" data-image="${esc(image.image_id)}" data-object="${esc(row.object_id)}">图片与空间</button><button data-jump="workers" data-worker="${esc(row.worker_id)}">人员画像</button></div>${fieldList(Object.fromEntries(keys.filter(k=>Object.hasOwn(row,k)).map(k=>[k,row[k]])))}<details><summary>分项解释与限制</summary><p>底面IoU、底边偏差、方向残差与高度误差按冻结评分引擎解释。Hmean／Hcenter 不是米制高度；IoU3D100为既定平均高度棱柱定义。非线性分项不能当作可相加的百分比扣分。</p><p>参考切换只用于看图；当前数值始终绑定本行参考。</p></details>${answer&&!answer.geometry_compatible?`<div class="warning">几何与消费快照绑定不一致：${esc(answer.geometry_binding_reasons.join('、'))}</div>`:''}</section></div>`;
 if(answer?.evidence)host.insertAdjacentHTML('beforeend',`<details class="panel"><summary>坐标处理、参考绑定、时间、Semi、scope及审核证据</summary>${fieldList(answer.evidence)}</details>`);
 WorkbenchGeometry.mount(host.querySelector('#answerGeometry'),image,answer,ref);
}
function profile(row){const host=$('focusPanel');if(!host)return;state.focusWorker=row.worker_id||'';
 const keys=['worker_id','metric','fold','Q_effect','Q_group','T_source_effect','T_group','QT_group','Q_contexts','Q_buildings','Q_supported','T_source_contexts','T_source_buildings','T_target_effect','canonical_submissions','individually_reviewed_records','original_review_exclusions','strong_defect_opportunities','strong_defect_unchanged','strong_defect_edited_outcome_unknown','reviewer_residual_after_edit_statements','semi_without_strong_defect_gold','missing_reason'];
 host.innerHTML=`<h2>当前人员 · ${esc(row.worker_id||'—')}</h2><div class="actions"><button data-jump="data" data-worker="${esc(row.worker_id||'')}">该人员作答</button><button data-jump="fusion">人员组合研究</button></div><p class="scope-label">当前表 ${esc(state.meta.id)}；原始均值、相对Q和效率分开，既有二分／四格不称永久能力类型。</p>${fieldList(Object.fromEntries(keys.filter(k=>Object.hasOwn(row,k)).map(k=>[k,row[k]])))}<details><summary>本行全部原字段</summary>${fieldList(row)}</details>${placeholder('分场景／关系组画像','使用“难度与场景”“门洞专项”或表内字段筛选查看现成分层。未发布的图或模型不生成模拟画像。')}`;
}
async function renderImages(token){
 let eligibleObjects=null;let list=assets.images.filter(i=>C.matchesImage(i,state.filters));
 if(['condition','worker','target','analysis','search'].some(k=>state.filters[k])){const records=await table('quality__shared_records');if(token!==state.loadToken)return;const matching=C.filterRows(records,state.filters,imageMap).rows;eligibleObjects=new Set(matching.map(r=>r.object_id));const ids=new Set(matching.map(r=>r.image_id));list=list.filter(i=>ids.has(i.image_id));}
 const image= list.find(i=>[i.image_id,i.image_code].includes(state.focusImage))||list[0];
 $('content').innerHTML=`<p class="scope-label">当前 ${list.length} 张图片；列表、空间目标和作答分别计数。<button data-act="filters">展开高级筛选</button></p><div class="imagework"><div class="imagelist">${list.map(i=>`<button data-image-select="${esc(i.image_id)}" class="${i===image?'active':''}">${esc(i.image_code)}<small>${esc(i.difficulty.label)} · 保留${i.counts.retained_people}人 · ${i.spaces.length}个目标／参考</small></button>`).join('')}</div><div id="imageFocus"></div></div>`;
 state.rows=list;state.meta={id:'image_resources',columns:Object.keys(list[0]||{}),path:'workbench-data/index.json'};
 if(!image){$('imageFocus').innerHTML=placeholder('当前没有匹配图片','请修改筛选，不删除未知或特殊场景来凑结果。');return;}
 state.focusImage=image.image_id;const detail=await imageDetail(image.image_id);if(token!==state.loadToken)return;
 const candidates=detail.annotations.filter(a=>!eligibleObjects||eligibleObjects.has(a.object_id));const answer=C.selectAnnotation(candidates,state.focusObject);
 const reference=detail.references.find(r=>r.target_id===state.viewTarget)||detail.references.find(r=>r.target_id===answer?.target_id)||detail.references.find(r=>r.current)||detail.references[0];
 state.focusObject=answer?.object_id||'';
 $('imageFocus').innerHTML=`<section class="panel"><h2>${esc(image.image_code)} · 当前查看对象</h2><div class="toolbar">${select('answerSelect',candidates.map(a=>[a.object_id,`${a.worker_id} · ${a.condition} · ${a.object_id}${a.retained?'':' · 已移出'}`]),answer?.object_id,'个人作答（保留与移出均可查）')}${select('targetSelect',detail.references.map(r=>[r.target_id,r.label]),reference?.target_id,'查看空间／参考（不重评分）')}</div>${reference?.target_id!==answer?.target_id?'<div class="warning">当前查看参考与该作答评分绑定目标不同；这里只对照几何，不把旧分数当新参考评价。</div>':''}<div id="imageGeometry"></div></section><div class="split equal">${panel('范围、GT与房间依据',fieldList({图片:image.image_code,难度:image.difficulty,场景:image.scene,图级标记:image.flags,空间候选:detail.spaces,备注:image.notes}))}${panel('该图全部人员作答',`<div class="tablewrap"><table><thead><tr><th>人员</th><th>条件</th><th>目标</th><th>计算状态</th><th>质量用途</th><th>B8L2</th><th>打开</th></tr></thead><tbody>${detail.annotations.map(a=>`<tr><td>${esc(a.worker_id)}</td><td>${esc(a.condition)}</td><td title="${esc(a.target_id)}">${esc(a.target_id?.split(':')[0]||'待定')}</td><td>${esc(a.calculation_status)}</td><td>${a.quality_usable?'主质量':'非主质量'}</td><td>${fmt(a.quality?.B8L2)}</td><td><button data-object-open="${esc(a.object_id)}">核验</button></td></tr>`).join('')}</tbody></table></div>`)}</div>${placeholder('裁切点／冗余点逐点依据','已有目标、底面和原始点可查看；当前页面未提供逐点裁切与冗余判定。本页不把候选边界当作真实墙角，也不补未知顶界。')}`;
 WorkbenchGeometry.mount($('imageGeometry'),detail,answer,reference);
}
async function pairFocus(row,token){const host=$('focusPanel');if(!host)return;const a=row.image_a||row.image_id_a,b=row.image_b||row.image_id_b;
 if(!a||!b){host.innerHTML=placeholder('当前表为关系／汇总粒度','选择原答图对或同成员过程记录，可进入双视角几何。');return;}
 if(!imageMap.has(a)||!imageMap.has(b)){host.innerHTML=placeholder('该关系至少一侧不在当前作答图片清单','直接关系保留；缺少当前作答的一侧不生成双侧几何或配对分数。请选择有共同人员支持的记录。')+panel('关系记录与实际支持',fieldList(row));return;}
 const [ia,ib]=await Promise.all([imageDetail(a),imageDetail(b)]);if(token!==state.loadToken)return;
 const specified=C.tokens(row.worker_id||row.paired_workers||row.worker_ids_a||row.member_workers_a);
 const common=(specified.length?specified:[...new Set(ia.annotations.map(x=>x.worker_id))]).filter(w=>ia.annotations.some(x=>x.worker_id===w)&&ib.annotations.some(x=>x.worker_id===w));const worker=row.worker_id&&common.includes(row.worker_id)?row.worker_id:common.includes(state.pairWorker)?state.pairWorker:common[0];
 const choose=(image,side)=>{const ids=C.tokens(row['object_ids_'+side]||row['member_object_ids_'+side]);if(ids.length)return image.annotations.find(x=>x.worker_id===worker&&ids.includes(x.object_id));
  const condition=row['condition_'+side]||row.condition,target=row['current_target_'+side]||row['reference_id_'+side];
  return image.annotations.find(x=>x.worker_id===worker&&x.retained&&(!condition||x.condition===condition)&&(!target||x.target_id===target));};
 const aa=choose(ia,'a'),ab=choose(ib,'b');
 host.innerHTML=`<section class="panel"><h2>当前图对 · ${esc(ia.image_code)} ↔ ${esc(ib.image_code)}</h2><div class="toolbar">${select('pairWorker',common.map(w=>[w,w]),worker,'两侧均有作答的人员')}<span class="muted">几何查看与源表的质量资格分别保留；不把同建筑推为同房。</span></div><div class="geopair"><div><h3>视角A</h3><div id="pairA"></div></div><div><h3>视角B</h3><div id="pairB"></div></div></div><details><summary>当前图对的范围、支持量、时间及来源原字段</summary>${fieldList(row)}</details>${row.pool_id_a?`<button data-pool-jump="${esc(row.pool_id_a)}" data-path="${esc(row.path_id_a)}" data-k="${row.k}">打开A侧真实过程</button>`:''}${row.pool_id_b?`<button data-pool-jump="${esc(row.pool_id_b)}" data-path="${esc(row.path_id_b)}" data-k="${row.k}">打开B侧真实过程</button>`:''}</section>`;
 WorkbenchGeometry.mount($('pairA'),ia,aa,ia.references.find(r=>r.target_id===aa?.target_id));WorkbenchGeometry.mount($('pairB'),ib,ab,ib.references.find(r=>r.target_id===ab?.target_id));state.pairRow=row;
}
async function processFocus(token){const host=$('processFocus');if(!host)return;
 host.dataset.k='';
 const pools=[...new Set(state.rows.map(r=>r.pool_id))],pool=pools.includes(state.pool)?state.pool:pools[0];state.pool=pool;
 if(!pool){host.innerHTML=placeholder('当前没有真实过程节点','修改筛选或查看完整率／失败记录。');return;}
 const paths=[...new Set(state.rows.filter(r=>r.pool_id===pool).map(r=>r.path_id))],path=paths.includes(state.path)?state.path:paths[0];state.path=path;
 const rows=state.rows.filter(r=>r.pool_id===pool&&r.path_id===path).sort((a,b)=>a.k-b.k);const current=rows.find(r=>r.k===state.k)||rows[rows.length-1];state.k=current.k;
 host.innerHTML=`<section class="panel"><h2>当前图片／真实路径</h2><div class="toolbar">${select('poolSelect',pools.map(v=>[v,v]),pool,'图片与人员池')}${select('pathSelect',paths.map(v=>[v,v]),path,'实际路径／顺序')}${select('kSelect',rows.map(r=>[r.k,'k='+r.k]),state.k,'当前节点')}</div><p>成员：${esc(current.member_workers)} · 子集：${esc(current.subset)}</p><p class="muted">R来自当前成员原答的两两差异；同k换组V在独立页签中查看参与集合，不归给单一路径。</p></section><div class="split"><div>${lineChart(rows,'R_union_normalized','R · 当前k原答两两差异')}${lineChart(rows,state.metric,`${state.metric} · 固定参考质量`)}${lineChart(rows,'source_active_seconds','累计来源活动时间（秒）')}</div><div><div id="processGeometry"></div><section class="panel"><h3>当前节点状态与支持</h3>${fieldList(Object.fromEntries(['pool_id','path_id','k','member_workers','reference_id','reference_version','geometry_status','order_status','complete_evaluable','main_comparison_allowed','B8L2','D10','source_time_available','source_active_seconds','geometry_reason','reasons'].map(k=>[k,current[k]])))}</section></div></div>`;
 const meta=assets.pools.find(p=>p.pool_id===pool);if(!meta?.detail){$('processGeometry').innerHTML=placeholder('该池没有可用的保存几何',meta?.status||'未接入');return;}
 const saved=await geometry(dataset.resourcesBase+meta.detail);const image=await imageDetail(meta.image_id);if(token!==state.loadToken||state.pool!==pool||state.path!==path||state.k!==current.k)return;
 const node=saved.states.find(n=>n.subset===current.subset),candidate=node?.candidate;
 if(!candidate){$('processGeometry').innerHTML=placeholder('该节点没有保存几何','不从成员重新融合，也不从其它节点复制。');return;}
 const ids=C.tokens(current.member_object_ids),chosen=ids.includes(state.processMember)?state.processMember:ids[0],answer=image.annotations.find(a=>a.object_id===chosen);const ref={points:saved.reference.points_1024x512,floor:saved.reference.floor_xz_h};
 const order=saved.orders.find(o=>o.path_id===path);
 $('processGeometry').innerHTML=`<section class="panel"><h3>实际进入顺序</h3><p>${esc(order?.workers?.join(' → ')||'该路径未保存顺序')}</p>${select('processMember',ids.map(id=>[id,(image.annotations.find(a=>a.object_id===id)?.worker_id||id)+' · '+id]),chosen,'当前节点原答成员')}</section><div id="nodeGeometry"></div>`;
 WorkbenchGeometry.mount($('nodeGeometry'),image,answer,ref,{...candidate,connected:C.truth(current.connection_available)&&C.truth(current.complete_floor_evaluable)});
 host.dataset.k=String(current.k);
}
async function semiFocus(row,token){const host=$('focusPanel');if(!host)return;
 if(dataset.release==='v2'){
  host.innerHTML=`<p class="info">有实际初始化绑定的记录，可在下方几何图勾选Semi初始化层；新批报告标志不生成初始坐标。增益资格、研究者修订与已确认纠错分别解释。</p><div id="semiFinal"></div>${panel('当前初始化与净改善证据',fieldList(row))}`;
  const score=scoreMap.get(row.object_id);if(score)await qualityFocus(score,$('semiFinal'),token);return;
 }
 host.innerHTML=`<div class="split equal">${placeholder('实际初始化几何待适配','初始化来源和兼容测量已接入；尚未把已恢复的初始化坐标打包进离线查看器。不使用模型重推结果代替。')}<div id="semiFinal"></div></div>${panel('初始化、最终与参考的同口径计量',fieldList(Object.fromEntries(Object.entries(row).filter(([k])=>/object_id|worker_id|reference|initial_B8L2|final_B8L2|gain_B8L2|initial_D10|final_D10|gain_D10|compatib|unavailable|source_time/.test(k)))))}${placeholder('修改量与确认错误的逐位置对应','确认错误机会、未改动和编辑后未知在“确认错误与未知”页签查看；未发布的局部修复测量不算作成功。')}`;
 const score=scoreMap.get(row.object_id);if(score)await qualityFocus(score,$('semiFinal'),token);else $('semiFinal').innerHTML=placeholder('最终作答未关联','消费快照没有同对象。');
}
async function teamFocus(row,token){
 const host=$('teamFocus');if(!host)return;const focusToken=String(Number(host.dataset.focusToken||0)+1);host.dataset.focusToken=focusToken;
 const requests=[row.target_request||row.target_request_left||row.request_id_fixed||row.request_id,row.random_request||row.target_request_right||row.request_id_reselected].filter(Boolean);
 if(!requests.length){host.innerHTML=placeholder('当前是构成／换人／稳定性汇总','汇总明细已接入；逐对成员与几何的关联尚未适配。可使用“团队成员与几何”或“真实人数过程”查看已保存具体结果，不推断缺失的对照。');return;}
 const teams=await table('workers__team_results');if(token!==state.loadToken||host.dataset.focusToken!==focusToken)return;
 const picked=requests.map(id=>teams.find(t=>t.request_id===id));
 host.innerHTML=`<section class="panel"><h2>当前同图同k团队对照</h2><p class="scope-label">${row.members_changed!==undefined?'成员是否改变：'+fmt(row.members_changed)+'；固定成员换分和重新选人须分别解释。':'左／右对应当前源表的策略／随机或两种人员策略。'}</p><div class="geopair">${picked.map((t,i)=>`<div><h3>${i===0?'A':'B'} · ${esc(requests[i])}</h3>${t?fieldList(Object.fromEntries(['image_code','k','worker_ids','status','main_comparison_allowed','reference_id','B8L2','D10','source_active_seconds'].filter(k=>Object.hasOwn(t,k)).map(k=>[k,t[k]]))):placeholder('请求结果未接入','保留请求ID，不补团队或分数。')}<div id="teamGeom${i}"></div></div>`).join('')}</div><details><summary>比较口径与源记录</summary>${fieldList(row)}</details></section>`;
 for(let i=0;i<picked.length;i++){const t=picked[i];if(!t)continue;const meta=assets.pools.find(p=>p.pool_id===t.pool_id),slot=$('teamGeom'+i);
  if(!meta?.detail){slot.innerHTML=placeholder('几何未保存／快照不匹配',meta?.status||'没有对应池');continue;}
  const [saved,image]=await Promise.all([geometry(dataset.resourcesBase+meta.detail),imageDetail(meta.image_id)]);
  if(token!==state.loadToken||host.dataset.focusToken!==focusToken||!slot.isConnected)return;
  const candidate=saved.states.find(s=>s.subset===t.subset)?.candidate;
  if(!candidate){slot.innerHTML=placeholder('该成员子集未保存几何','不重新融合补图。');continue;}
  WorkbenchGeometry.mount(slot,image,null,{points:saved.reference.points_1024x512,floor:saved.reference.floor_xz_h},{...candidate,connected:C.truth(t.connection_available)&&C.truth(t.floor_evaluable)});
 }
}
function renderOverview(){
 if(dataset.release==='v1'){
  const s=assets.image_summary;
  $('content').innerHTML=(window.ResearchEvidence?ResearchEvidence.overviewHTML({release:dataset.release,snapshot:SNAPSHOT}):'')+metricCards([['作答总数',s.raw_records,'份；包含非主质量记录'],['研究图片',s.images,'张；不是过程池数'],['当前质量可用',s.quality_records,'份；各专题的统计范围另列'],['保留人员',s.retained_people,'人；不是画像训练人数']])+`<div class="info">这里保留 v1 的冻结概要；筛选只作用于明细模块。</div><div class="cards">${overview.sections.map(s=>`<section class="panel finding"><h2>${esc(s.title)}</h2><p>${esc(s.finding)}</p><p class="scope-label">${esc(s.support)}</p><details><summary>解释限制与反例</summary><p>${esc(s.counterexample)}</p></details><div class="actions">${s.tables.map(t=>`<button data-table-jump="${esc(t.id)}">${esc(t.label)}</button>`).join('')}</div></section>`).join('')}</div>`;
  state.rows=[];return;
 }
 const summary=assets.image_summary;
 const cards=overview.sections.map((item,i)=>`<section class="panel briefing-step"><p class="eyebrow">${esc(item.title)}</p><h2>${esc(item.finding)}</h2><figure>${item.visual?`<a href="${esc(item.visual)}" target="_blank" rel="noopener"><img class="briefing-visual" src="${esc(item.visual)}" alt="${esc(item.visual_alt)}" loading="lazy"></a>`:''}<figcaption>${esc(item.example||'查看保存实例')} · 固定保存实例，不随明细筛选变化。${item.visual?` <a href="${esc(item.visual)}" target="_blank" rel="noopener">查看原尺寸图片 ↗</a>`:''}</figcaption></figure><p class="scope-label"><strong>支持范围：</strong>${esc(item.support)}</p><p class="scope-label"><strong>例外：</strong>${esc(item.counterexample)}</p><div class="actions"><a href="${esc(item.href||'#release=v2&module='+(item.module||'data')+'&tab='+(item.tab||0)+(item.case?'&case='+item.case:''))}">查看实例与图表</a>${item.tables.map(t=>`<button data-table-jump="${esc(t.id)}">${esc(t.label)}</button>`).join('')}</div></section>`).join('');
 $('content').innerHTML=`<div class="briefing-intro"><p class="eyebrow">研究发现总览 · ${esc(dataset.release)} · ${esc(SNAPSHOT)}</p><h2>本轮的主要发现与对应证据</h2><p>按钮会打开同一研究台的原表和几何。导览用的是固定保存的证据，不随明细筛选重新计算。</p><div class="actions"><button class="primary" data-module="images">打开图片与原答</button><button data-module="data">进入数据浏览</button><a href="oos-review.html">OOS 独立统计与复核工作台</a></div><p class="hint-glossary">提示用法：悬浮或键盘聚焦看短释义，点击 ? 看详细说明，Esc 关闭。</p><p class="hint-glossary">同名符号依上下文：几何自遮挡 H ${hintButton('occlusion_h')} / 高度损失 H ${hintButton('height_loss_h')}；方向残差 D ${hintButton('direction_d')} / 共同背景 D ${hintButton('background_d')}；源历史人数 k ${hintButton('source_k')} / 融合团队人数 k ${hintButton('team_k')}。</p></div>`+
 metricCards([['作答总数',summary.raw_records,'份；包含非主质量记录'],['研究图片',summary.images,'张；不是过程池数'],['当前质量可用',summary.quality_records,'份；各专题的统计范围另列'],['保留人员',summary.retained_people,'人；不是画像训练人数']])+
 `<div class="info">${esc(overview.personnel_status||'人员分类展示按来源阶段解释。')} <button data-module="case_story">直接查看跨专题案例的原答与保存融合</button> <button data-module="personnel_main">进入人员标法与团队</button>历史分类页仍可从侧栏进入。</div><div class="briefing-grid">${cards}</div>`;
 state.rows=[];
}
function renderPlan(){const plans=assets.supplement_plan?.plans;
 $('content').innerHTML=plans?panel('已有补人计划 · 只读',`<p class="scope-label">读取构建时的独立计划，不修改原服务存储，也不启动采集。</p><div class="tablewrap"><table><thead><tr><th>图片</th><th>计划补人数</th><th>备注</th><th>记录时间</th></tr></thead><tbody>${Object.entries(plans).map(([id,p])=>`<tr><td><button data-jump="images" data-image="${esc(id)}">${esc(imageMap.get(id)?.image_code||id)}</button></td><td>${fmt(p.additional_people)}</td><td>${esc(p.note)}</td><td>${esc(p.updated_at||'未填写')}</td></tr>`).join('')}</tbody></table></div>`):placeholder('补人计划未接入','未找到已有计划文件，不创建新计划。');state.rows=plans?Object.entries(plans).map(([image_id,p])=>({image_id,...p})):[];state.meta={id:'supplement_plan'};
}
function renderSources(){
 $('content').innerHTML=`<section class="panel"><h2>数据与方法范围</h2><p>当前数据版本：${esc(dataset.release)}。Manual与Semi分别分析，门洞单列，OOS在独立页面讨论。库存、质量可用、完整可评和全部尝试使用各自分母；缺失不填0。</p><p>图表和几何来自已保存实验。页面选择用于查看固定结果，不重新形成分类或融合团队。人员、图片、条件和参考的绑定保持不变。</p><div class="actions"><button data-module="evidence">指标与方法解释</button><button data-module="personnel_main">人员与团队研究</button><a href="oos-review.html">OOS独立研究</a></div></section><section class="panel"><h2>统计表与支持范围</h2><p>以下可打开完整明细；记录行数不是独立图片或人员数，按各表声明的统计单位解释。</p><div class="doclist">${index.tables.map(t=>`<details><summary>${esc(t.title||t.id)} · ${t.row_count}行</summary><p>${esc(t.caveats?.join('；')||'样本、指标与缺失状态分别保留。')}</p><p>字段：${esc(t.columns.map(label).join('、'))}</p><button data-table-jump="${esc(t.id)}">查看统计明细</button></details>`).join('')}</div></section>`;state.rows=[];
}

function setTable(id){state.chartField='';route({table:id,where:null});}
async function openRow(row){
 if(!row)return;
 if(state.module==='workers'&&row.worker_id){profile(row);return;}
 if(state.module==='quality'&&row.object_id){await qualityFocus(row,$('focusPanel'),state.loadToken);return;}
 if(state.module==='same_room'&&(row.image_a||row.image_id_a)){await pairFocus(row,state.loadToken);return;}
 if(state.module==='time'&&state.tab===0&&row.object_id){await semiFocus(row,state.loadToken);return;}
 if(state.module==='fusion'&&row.pool_id&&row.path_id&&row.k){state.pool=row.pool_id;state.path=row.path_id;state.k=row.k;await processFocus(state.loadToken);return;}
 if(state.module==='fusion'&&$('teamFocus')){await teamFocus(row,state.loadToken);return;}
 $('recordTitle').textContent=String(row.object_id||row.worker_id||row.request_id||'源表记录');
 const links=[];const image=C.value(row,'image'),worker=C.value(row,'worker');
 if(image)links.push(`<button data-jump="images" data-image="${esc(image)}">图片与空间</button>`);
 if(worker&&typeof worker==='string'&&!worker.includes('|'))links.push(`<button data-jump="workers" data-worker="${esc(worker)}">人员画像</button>`);
 if(row.object_id)links.push(`<button data-object-open="${esc(row.object_id)}">作答几何核验</button>`);
 if(row.image_id&&state.module==='fusion')links.push(`<button data-jump="fusion" data-image="${esc(row.image_id)}" data-process>真实人数过程</button>`);
 if(row.image_id&&state.module==='data')links.push(`<button data-jump="fusion" data-image="${esc(row.image_id)}" data-process>该图真实人数过程</button>`);
 $('recordBody').innerHTML=`<div class="actions">${links.join('')}<button data-act="notes">此上下文笔记</button><button data-act="source">表来源</button></div><div id="modalGeometry"></div>${fieldList(row)}`;
 if(!$('recordDialog').open)$('recordDialog').showModal();state.currentRecord=row;
 if(row.object_id&&scoreMap.has(row.object_id)){
  try{await qualityFocus(scoreMap.get(row.object_id),$('modalGeometry'),state.loadToken);}catch(e){$('modalGeometry').innerHTML=placeholder('几何未接入',e.message);}
 }
}
function notes(){const focus=state.module==='workers'?state.focusWorker:state.module==='fusion'?[state.pool,state.path,state.k].join(':'):state.currentRecord?.object_id||state.focusObject||'';lastNoteKey=[state.module,state.meta?.id||'',focus,JSON.stringify(state.filters)].join('|');
 $('noteText').value=state.notes[lastNoteKey]?.text||'';$('allNotes').innerHTML=Object.entries(state.notes).map(([k,v])=>`<details><summary>${esc(k)}</summary><p>${esc(v.text)}</p><small>${esc(v.updated_at)}</small></details>`).join('');
 if(!$('notesDialog').open)$('notesDialog').showModal();
}
async function click(e){
 const target=e.target.closest('button,a[data-module],circle[data-k],tr[data-row]');if(!target)return;
 try{
  if(target.dataset.hint){e.preventDefault();if(hintPinned&&activeHint===target)hideHint();else showHint(target,true);return;}
  if(target.dataset.module){e.preventDefault();route({module:target.dataset.module,tab:0,table:null,where:null});return;}
  if(target.dataset.close){$(target.dataset.close).close();return;}
  if(target.dataset.tab!==undefined){state.chartField='';state.currentRecord=null;route({tab:target.dataset.tab,table:null,where:null});return;}
  if(target.dataset.imageSelect){state.viewTarget='';state.focusObject='';route({image:target.dataset.imageSelect,object:null});return;}
  if(target.dataset.tableJump){route({module:'data',table:target.dataset.tableJump,tab:0,where:null});return;}
  if(target.dataset.poolJump){$('recordDialog').close();state.pool=target.dataset.poolJump;state.path=target.dataset.path;state.k=Number(target.dataset.k);route({module:'fusion',tab:4,table:null,where:null});return;}
  if(target.dataset.objectOpen){$('recordDialog').close();route({module:'quality',tab:0,table:null,object:target.dataset.objectOpen,where:null});return;}
  if(target.dataset.jump){$('recordDialog').close();const patch={module:target.dataset.jump,tab:0,table:null,where:null};
   if(target.dataset.image){patch.image=target.dataset.image;patch.f_image=target.dataset.image;}
   if(target.dataset.object)patch.object=target.dataset.object;
   if(target.dataset.worker){patch.worker=target.dataset.worker;patch.f_worker=target.dataset.worker;}
   if(target.hasAttribute('data-process'))patch.tab=4;route(patch);return;
  }
  if(target.dataset.remove){route({['f_'+target.dataset.remove]:null});return;}
  if(target.dataset.whereRemove!==undefined){const next=state.where.filter((_,i)=>i!==Number(target.dataset.whereRemove));route({where:next.length?next:null});return;}
  if(target.dataset.sort){const key=target.dataset.sort;state.sort={key,asc:state.sort?.key===key?!state.sort.asc:true};drawTable();return;}
  if(target.dataset.page){state.page+=Number(target.dataset.page);drawTable();return;}
  if(target.dataset.support){exportRows(supportSets.get(target.dataset.support),'chart-support');return;}
  if(target.dataset.k){state.k=Number(target.dataset.k);await processFocus(state.loadToken);return;}
  if(target.dataset.row!==undefined&&!e.target.matches('input')){await openRow(state.viewRows[Number(target.dataset.row)]);return;}
  switch(target.dataset.act){
   case 'filters':openFilters();break;
   case 'clearDraft':$('filterFields').querySelectorAll('input,select').forEach(x=>x.value='');break;
   case 'reset':{const patch={where:null};Object.keys(state.filters).forEach(k=>patch['f_'+k]=null);route(patch);break;}
    case 'export':exportRows(state.rows,'filtered');break;
   case 'source':$('recordTitle').textContent='当前表的来源与字段';$('recordBody').innerHTML=state.meta?fieldList({统计表:state.meta.title||state.meta.id,记录数:state.meta.row_count,字段:state.meta.columns?.map(label),说明:state.meta.caveats}):placeholder('无当前表','请打开具体明细表或来源页。');if(!$('recordDialog').open)$('recordDialog').showModal();break;
   case 'addWhere':{const op=$('whereOp').value,val=$('whereVal').value,max=$('whereMax').value;if(op==='range'&&(val===''||max===''||!Number.isFinite(Number(val))||!Number.isFinite(Number(max))||Number(val)>Number(max))){toast('数值区间需要有效且有序的上下界');break;}route({where:[...state.where,{field:$('whereField').value,op,val,max}]});break;}
   case 'compare':{const selected=state.rows.filter(r=>state.selected.has(rowKey(r)));if(!selected.length){toast('先勾选需要并排比较的记录');break;}
    const cols=[...new Set(selected.flatMap(r=>Object.keys(r)))];$('recordTitle').textContent=`批量比较 · ${selected.length}项`;$('recordBody').innerHTML=`<p>当前详情对象不会因勾选而改变。以下为选中记录原字段，不拟合新综合分数。</p><div class="tablewrap"><table><thead><tr><th>字段</th>${selected.map((r,i)=>`<th>${esc(r.worker_id||r.object_id||r.request_id||i+1)}</th>`).join('')}</tr></thead><tbody>${cols.map(k=>`<tr><th>${esc(label(k))}</th>${selected.map(r=>`<td title="${esc(fmt(r[k]))}">${esc(fmt(r[k]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;$('recordDialog').showModal();break;}
   case 'notes':notes();break;
   case 'saveNote':state.notes[lastNoteKey]={text:$('noteText').value,updated_at:new Date().toISOString(),snapshot:SNAPSHOT};try{localStorage.setItem('research-workbench:'+SNAPSHOT,JSON.stringify(state.notes));$('noteStatus').textContent='已保存在当前浏览器。';}catch{$('noteStatus').textContent='浏览器未允许持久保存；笔记仍在本次页面内，请导出。';}break;
   case 'exportNotes':download('research-notes-'+dataset.release+'.json',JSON.stringify({snapshot:SNAPSHOT,notes:state.notes},null,2),'application/json');break;
  }
 }catch(error){toast(error.message);}
}
async function change(e){try{
 const el=e.target;
 if(el.dataset.check!==undefined){const row=state.viewRows[Number(el.dataset.check)],key=rowKey(row);if(el.checked)state.selected.add(key);else state.selected.delete(key);drawTable();return;}
 if(el.dataset.facet){const field=el.dataset.facet;route({where:[...state.where.filter(w=>!(w.facet&&w.field===field)),{field,op:el.value===''?'any':'eq',val:el.value,facet:true}]});return;}
 switch(el.id){
  case 'release':{const chosen=window.RESEARCH_DATASETS.find(d=>d.release===el.value);if(!chosen?.available){toast('该数据源尚未接入');return;}location.hash=new URLSearchParams({module:'overview',release:chosen.release}).toString();location.reload();break;}
  case 'tableSelect':setTable(el.value);break;
  case 'metricSelect':state.chartField='';route({metric:el.value});break;
  case 'chartField':state.chartField=el.value;await render();break;
  case 'pageSize':state.pageSize=Number(el.value);state.page=0;drawTable();break;
  case 'answerSelect':state.viewTarget='';route({object:el.value});break;
  case 'targetSelect':state.viewTarget=el.value;await render();break;
  case 'pairWorker':state.pairWorker=el.value;await pairFocus(state.pairRow,state.loadToken);break;
  case 'poolSelect':state.pool=el.value;state.path='';state.k=null;await processFocus(state.loadToken);break;
  case 'pathSelect':state.path=el.value;state.k=null;await processFocus(state.loadToken);break;
  case 'kSelect':state.k=Number(el.value);await processFocus(state.loadToken);break;
  case 'processMember':state.processMember=el.value;await processFocus(state.loadToken);break;
 }
 }catch(error){toast(error.message);}}

async function init(){
 try{if(!dataset?.available)throw Error('该数据版本尚未接入；请选择已发布数据源。');
  document.querySelector('.versions>span').textContent=dataset.analysisLabel;
  $('release').title='切换数据源会重新加载并重置当前筛选';
  $('release').innerHTML=window.RESEARCH_DATASETS.map(d=>`<option value="${d.release}" ${d.release===dataset.release?'selected':''} ${!d.available?'disabled':''}>${esc(d.label)}</option>`).join('');
  [index,assets,overview]=await Promise.all([read(dataset.tablesIndex),read(dataset.resourcesIndex),read(dataset.overview)]);
  if(index.snapshot_id!==SNAPSHOT||assets.snapshot_id!==SNAPSHOT||overview.metadata?.snapshot_id!==SNAPSHOT||index.data_release!==dataset.release||assets.data_release!==dataset.release)throw Error('数据版本、消费索引、资源与概要快照不一致，停止混合加载。');
  if(dataset.release==='v2'){for(const [id,tabs] of Object.entries(index.module_tabs))modules[id][2]=tabs;modules.workers[1]='绝对 Q、同任务相对 Q、作答用时和不同难度下的表现都是探索性画像。Semi 和 Scope 只在有记录的范围内统计；10-20 的人员工作标签仅作研究参照，不是生产分类。';modules.fusion[1]='v2 已接入低人数到30/35/满员的自然人数结果、类别块替换、普通图及门洞失败几何；各入口保留各自成员、参考与支持。';}
  if(dataset.release==='v2'){
   const personnel=PersonnelMain.loadDocs(index);
   modules.personnel_main[2]=personnel.api.groups.map(g=>[g.title,null]);
   for(const term of personnel.glossary.terms){metricHints[term.id]=[term.short,[term.detail,term.unit&&`单位：${term.unit}`,term.denominator_or_support&&`支持/分母：${term.denominator_or_support}`,term.avoid_confusion&&`注意：${term.avoid_confusion}`].filter(Boolean).join(' ')];metricHintLabels[term.id]=term.label;}
  }
  for(const image of assets.images){imageMap.set(image.image_id,image);imageMap.set(image.image_code,image);}
  const scores=await table('quality__shared_records');scoreMap=new Map(scores.map(r=>[r.object_id,r]));
  try{state.notes=JSON.parse(localStorage.getItem('research-workbench:'+SNAPSHOT)||'{}');}catch{state.notes={};}
  const primary=['overview','personnel_main','evidence','conditions','same_room','profiles','data'];
  const navGroups=[['原答、团队与方法明细',['case_story','images','patterns','method_supplements','fusion','multiview']],['其它研究与数据说明',['workers','benefits','taxonomy','mechanisms','quality','same_room_review','time','coverage','sources']]];
 const groupedIds=new Set([...primary,...navGroups.flatMap(([,ids])=>ids)]);
  const navLink=id=>modules[id]?`<a href="#module=${id}" data-module="${id}">${modules[id][0]}</a>`:'';
 $('navigation').innerHTML=primary.map(navLink).join('')+'<a href="oos-review.html">OOS独立研究</a>'+navGroups.map(([title,ids])=>`<details class="nav-more"><summary>${esc(title)}</summary>${ids.map(navLink).join('')}</details>`).join('')+Object.keys(modules).filter(id=>!groupedIds.has(id)).map(navLink).join('');

  hintPopover=document.createElement('div');hintPopover.id='metricHint';hintPopover.className='metric-hint';hintPopover.setAttribute('role','tooltip');hintPopover.hidden=true;document.body.append(hintPopover);
  document.addEventListener('pointerover',e=>{const trigger=e.target.closest?.('[data-hint]');if(trigger&&!hintPinned)showHint(trigger,false);});
  document.addEventListener('pointerout',e=>{if(!hintPinned&&activeHint&&e.target.closest?.('[data-hint]')===activeHint)hideHint();});
  document.addEventListener('focusin',e=>{const trigger=e.target.closest?.('[data-hint]');if(trigger&&!hintPinned)showHint(trigger,false);});
  document.addEventListener('focusout',e=>{if(!hintPinned&&activeHint&&e.target===activeHint)hideHint();});
  document.addEventListener('click',e=>{if(hintPinned&&!e.target.closest?.('[data-hint],#metricHint'))hideHint();});
  document.addEventListener('click',click);document.addEventListener('change',change);document.addEventListener('keydown',e=>{if(e.key==='Escape')hideHint();if(e.key==='Enter'&&e.target.matches('tr[data-row]'))openRow(state.viewRows[Number(e.target.dataset.row)]);});
  $('filterForm').onsubmit=e=>{e.preventDefault();const patch={};for(const key of Object.keys(filterLabels))patch['f_'+key]=$('f-'+key).value||null;$('filters').close();route(patch);};
  window.addEventListener('hashchange',()=>{readRoute();render();});readRoute();await render();
 }catch(e){$('content').innerHTML=placeholder('工作台暂时无法打开','当前页面数据未能读取，请确认展示包完整后重新打开。')+'<a href="index.html">重新打开已发布数据源</a>';$('title').textContent='研究工作台';}
}
init();
})();
