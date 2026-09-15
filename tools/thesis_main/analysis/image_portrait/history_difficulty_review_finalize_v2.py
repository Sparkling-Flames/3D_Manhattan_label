"""Versioned reviewer packet. Previous results and user tags remain unchanged."""
from __future__ import annotations
import base64,hashlib,html,importlib.metadata,itertools,json,re,sys
from pathlib import Path
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import OUT,PREV,B,ROOT,csv,js

REFS=[
 dict(author='Christian Hennig',year=2007,title='Cluster-wise assessment of cluster stability',venue='Computational Statistics & Data Analysis 52(1):258–271',doi='10.1016/j.csda.2006.11.025',url='https://www.sciencedirect.com/science/article/pii/S0167947306004622',access='核对出版社摘要；出版社正文403，未声称通读全文。具体算法说明另读作者官方手册。'),
 dict(author='Christian Hennig',year=2026,title='fpc: Flexible Procedures for Clustering, version 2.2-14; clusterboot section',venue='CRAN official package reference manual, pp.41–46',doi='',url='https://cran.r-project.org/web/packages/fpc/fpc.pdf',access='已读相关段落并核看PDF第44页；0.75/0.85指引针对bootstrap，不能不经校准照搬为本项目LOO或子集的有效性定理。'),
 dict(author='Ellie Pavlick and Tom Kwiatkowski',year=2019,title='Inherent Disagreements in Human Textual Inferences',venue='Transactions of the Association for Computational Linguistics 7:677–694',doi='10.1162/tacl_a_00293',url='https://aclanthology.org/Q19-1043.pdf',access='已读官方PDF解析原文§4.1：留出10个真实判断、比较单高斯与训练侧选择混合成分的模型；截图服务Cache miss，未依赖图表像素读取结果。'),
 dict(author='Anne Chao and Lou Jost',year=2012,title='Coverage-based rarefaction and extrapolation: standardizing samples by completeness rather than size',venue='Ecology 93(12):2533–2547',doi='10.1890/11-1952.1',url='https://esajournals.onlinelibrary.wiley.com/doi/10.1890/11-1952.1',access='核对出版社索引文本及官方补充材料目录；正文直连403，未声称取得完整PDF。仅借鉴按样本完整度考虑稀有模式的方向，不照搬生态推断。')]

def cleanformat(df):
 d=df.copy()
 for c in d:
  if pd.api.types.is_float_dtype(d[c]):d[c]=d[c].map(lambda x:''if pd.isna(x)else f'{x:.3f}')
 return d.fillna('')

class Report:
 def __init__(self):self.md=[];self.ht=[]
 def head(self,t,level=2):self.md.append('#'*level+' '+t+'\n');self.ht.append(f'<h{level}>{html.escape(t)}</h{level}>')
 def para(self,t):
  self.md.append(t+'\n');s=html.escape(t);s=re.sub(r'\*\*(.*?)\*\*',r'<strong>\1</strong>',s);s=re.sub(r'`(.*?)`',r'<code>\1</code>',s);self.ht.append('<p>'+s+'</p>')
 def table(self,d):
  d=cleanformat(d);cols=[str(c)for c in d.columns];self.md.append('| '+' | '.join(cols)+' |\n| '+' | '.join(['---']*len(cols))+' |\n'+'\n'.join('| '+' | '.join(str(v).replace('|','／').replace('\n',' ')for v in r)+' |'for r in d.itertuples(index=False,name=None))+'\n');self.ht.append(d.to_html(index=False,escape=True))
 def fig(self,n,cap):
  p=OUT/'figures'/n;b64=base64.b64encode(p.read_bytes()).decode();self.md.append(f'![{cap}](figures/{n})\n');self.ht.append(f'<figure><img src="data:image/png;base64,{b64}"><figcaption>{html.escape(cap)}</figcaption></figure>')
 def save(self):
  (OUT/'REPORT_ZH.md').write_text('\n'.join(self.md),encoding='utf-8')
  sty='body{font-family:Arial,"Noto Sans CJK SC",sans-serif;max-width:1180px;margin:32px auto;padding:0 24px;line-height:1.75;color:#18212b}h1{font-size:30px}h2{font-size:23px;margin-top:40px;border-bottom:1px solid #ccc}table{border-collapse:collapse;display:block;overflow-x:auto;margin:20px 0;font-size:14px}th,td{padding:9px;border:1px solid #ddd;text-align:left;vertical-align:top}th{background:#f3f5f7}img{width:100%;height:auto}code{word-break:break-all}figcaption{font-size:14px;color:#555}p{overflow-wrap:anywhere}'
  (OUT/'REPORT_ZH.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>中等与困难候选复核</title><style>'+sty+'</style><body>'+''.join(self.ht)+'</body></html>',encoding='utf-8')

def main():
 p=pd.read_csv(OUT/'proposal/conditional_supported_mode_adjudication.csv');sub=pd.read_csv(OUT/'extra/clusterwise_80pct_distinct_person_subsets.csv')
 s=sub[sub.cut==.1].groupby(['image_id','condition']).agg(min_sub80_jaccard=('mean_jaccard_conditional','min'),min_sub80_prob_retains_two=('prob_retains_two_people','min')).reset_index();p=p.merge(s,on=['image_id','condition'],how='left')
 p['review_draft_grade']=p.draft_grade.fillna('');p['review_draft_reason']=p.draft_reason
 failed=(p.draft_grade=='medium_candidate')&((p.min_sub80_jaccard<.75)|p.min_sub80_jaccard.isna())
 p.loc[failed,'review_draft_grade']='';p.loc[failed,'review_draft_reason']='cluster_recovery_under_80pct_subsets_insufficient;not_automatically_difficult'
 p['near_order_fraction_boundary']=p.full_p_by_8.between(.75,.85)|p.core15_p_by_19.between(.75,.85)
 p['user_final_grade']='';p['user_decision_reason']='';p['user_cluster_semantics']='';p['user_singleton_assessment']=''
 csv('proposal/final_review_draft_per_image.csv',p)
 fp=p[p.expert_tag.isin(['中等','困难'])];csv('expert/final_medium_hard_focus.csv',fp)
 csv('proposal/final_old_hard_reassessment.csv',p[p.previous_grade=='difficult_candidate'])
 # All new candidates can be adjudicated; the focused queue remains separately preserved.
 cols=['image_id','condition','expert_tag','n_observed','n_valid','n_excluded','n_reviewed_retained','sizes_descending','total_clusters','supported_clusters','singletons','singleton_share','min_supported_loo_jaccard','min_sub80_jaccard','weakly_separated_supported_pair','full_p_by_8','core15_p_by_19','core_tail_15','late_quarter_new','review_draft_grade','review_draft_reason','user_final_grade','user_decision_reason','user_cluster_semantics','user_singleton_assessment']
 cn=['image_id','条件','用户原tag','原作答人数','有效独立人数','单列无效人数','保留已确认修正数','各簇人数_含单人','总簇数','支持簇数','单人簇数','单人比例','最小LOO_Jaccard','最小80pct子集Jaccard','同点数簇分离需审图','前8人完整后缀比例','至观察窗口支持核心稳定比例','支持核心尾段稳定比例','后四分段新标法率','建议粗类_非最终','判定说明','用户最终粗类','用户裁决原因','簇语义裁决','单人标法裁决']
 csv('USER_DECISION_TABLE.csv',p[cols].set_axis(cn,axis=1))
 oldq=pd.read_csv(OUT/'local_image_review_queue.csv');ids=set(oldq.image_id)|set(p[p.review_draft_grade!=''].image_id)
 cl=pd.read_csv(OUT/'structure/per_cluster_stability.csv');mem=pd.read_csv(OUT/'structure/real_mode_memberships.csv.gz');q=[]
 for _,r in p[p.image_id.isin(ids)].iterrows():
  mm=mem[(mem.image_id==r.image_id)&(mem.condition==r.condition)&(mem.cut==.1)];cc=cl[(cl.image_id==r.image_id)&(cl.condition==r.condition)&(cl.cut==.1)]
  questions=[]
  if r.supported_clusters>=2:questions.append('各支持簇代表的空间范围/点数/转角解释是否真正不同且合理？')
  if r.weakly_separated_supported_pair:questions.append('多数跨簇几何配对仍兼容，是连续定位波动被切开还是语义不同？不要自动合并。')
  if r.singletons:questions.append('单人标法是合理少数/尚未获得重复支持，还是可指出具体错误？')
  if r.n_excluded:questions.append('已确认修正继续保留，其余无效已单列；有效子集结论如何限定？')
  if r.expert_tag=='困难':questions.append('原困难判断中的“不收敛”指不能统一，还是支持模式集合/份额仍变化？')
  if r.n_valid<10:questions.append('少人数仅作有限观察证据，不据此排除未来少数标法。')
  q.append(dict(image_id=r.image_id,condition=r.condition,priority=1 if r.expert_tag in('中等','困难')and r.n_valid>=10 else 2 if r.previous_grade=='difficult_candidate'else 3,expert_tag=r.expert_tag,review_draft_grade=r.review_draft_grade,n_valid=r.n_valid,sizes_descending=r.sizes_descending,question='；'.join(questions),worker_ids=';'.join(mm.worker_id.astype(str)),canonical_ids=';'.join(mm.canonical_annotation_id.astype(str)),medoid_canonical_ids=';'.join(cc.medoid_canonical_id.astype(str)),affected_conclusion='中等/困难初步边界；数字簇是否具有合理空间解释；整体和支持核心的收敛是否混淆',user_verdict=''))
 csv('ALL_CANDIDATE_LOCAL_REVIEW_QUEUE.csv',q)
 # Audit data version and geometry parity, without looking at unused difficulty values.
 known={'metadata/images.jsonl':'02eebd582fc33aee5936fe69dd45d1853408e803','metadata/relationships.jsonl':'9a6e2c9922ac0dd88797e005e0ba7187b4160b57','metadata/spatial_history.jsonl.gz':'676ddba4e9330ed6b6d484b0cfb03bf377dbf0fd','metadata/spatial_provenance.json':'0d60a109e5ffbf9f7ed4355c017cc3e374fbe2df','human/responses.jsonl.gz':'6261c30d1abf2d7ad0e71702348fc81819e783ad'}
 input_files=[]
 for rel,expected in known.items():
  data=(B/rel).read_bytes();git=hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest();assert git==expected
  input_files.append(dict(path=str((B/rel).relative_to(ROOT)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),git_blob=git,latest_commit_blob_match=True))
 prev=pd.read_csv(PREV/'targets/primary_with_robustness.csv');st=pd.read_csv(OUT/'structure/per_image_all_cuts.csv');v=st[st.cut==.1].merge(prev,on=['image_id','condition'],suffixes=('','_old'));checks=[]
 for new,old in [('n_valid','n_valid_old'),('total_clusters','n_modes'),('supported_clusters','n_supported_modes'),('singletons','n_singletons')]:
  a=v[[new,old]].dropna();checks.append(dict(field=new,compared=len(a),mismatches=int((np.abs(a[new]-a[old])>1e-9).sum())))
 csv('audit/previous_static_parity.csv',checks)
 js('audit/INPUT_METHOD_MANIFEST.json',dict(input_branch='codex/image-portrait-20260914',verified_latest_commit='c0069628141dd078626c42ba574fd699c7661f55',artifact_run=34932323300,artifact_id=10381788487,artifact_note='previous full delivery recovered; actual raw bytes checked against current c0069628 Git blobs, not assumed current by name',input_files=input_files,method_version='history_difficulty_review_v2_valid_only_cluster_local_20260915',new_image_inference=False,original_images_accessed=False,legacy_experimental_difficulty_used=False,user_tags_unchanged=True,raw_geometry_unchanged=True,proposed_thresholds_not_frozen=True,field_use='whitelisted identity, verified effective geometry, task condition; user tags/comments comparison only',subsampling='actual different people, no replication',python=sys.version,packages={k:importlib.metadata.version(k)for k in['numpy','pandas','scipy','shapely','matplotlib','pytest']}))
 js('literature/verified_sources.json',REFS)
 cov=json.loads((OUT/'audit/coverage.json').read_text());cnt=p.groupby(['condition','review_draft_grade']).size().reset_index(name='图片条件数');js('FINAL_SUMMARY.json',dict(coverage=cov,refined_draft_counts=cnt.to_dict('records'),old_hard_changes=p[p.previous_grade=='difficult_candidate'].groupby('review_draft_grade').size().to_dict(),focus_image_conditions=len(fp),focus_unique_images=fp.image_id.nunique(),all_review_queue=len(q),all_review_unique_images=len(set(a['image_id']for a in q)),new_per_order_rows=len(pd.read_csv(OUT/'process/per_order_onsets.csv.gz')),new_terminal_rows=len(st),new_grades_have_not_been_used_to_refit_models=True))
 report=Report();report.head('中等与困难候选重审：稳定类、单人模式与观察人数',1)
 report.para('研究主线仍是不确定性及其随真实人员增加的收敛。本文是接续 mainspace_history / history_difficulty 的定向重算；不是新独立验证，所有粗类都等待用户裁决。输入核对至 c0069628141dd078626c42ba574fd699c7661f55；新结果独立保存，旧报告和用户106张tag均不改写。本轮不重拟合图片模型。')
 report.head('1. 结论先行')
 report.para('旧规则确实不适合直接承担当前“中等”的含义。具体问题是：①把支持簇自身的复现与全体模式比例稳定绑成同一门；②单人比例超过10%时，旧程序直接跳过稳定起点计算；③一条无效作答使整图失去粗分类资格；④稀有双人模式的发现等待被计入“较晚才能稳定”。但核查发现，旧表并没有将用户11张有Manual历史的中等图直接判为困难；主要是漏分到未分类。')
 report.para('本次从真实有效几何重新聚类和逐前缀回放。总簇数必须保留，但中等与困难仍有重叠。最终建议是：先用总簇数、支持簇数、单人数量及逐簇恢复筛出结构候选，再把模式份额/几何的时间稳定作为独立证据级别。不能把“30个中等结构初筛候选”写成“30图整体已收敛”。')
 report.head('2. 人员排除、奇数点与输入核对')
 report.para('2501条canonical中，排除W019/W026后有Manual 1634条、Semi 538条、统一OOS规则任务216条。W011历史保留。几何有效作答为Manual 1620、Semi 532；其余20条单列，涉及12个Manual和4个Semi图×条件单元。OOS规则任务不混入几何难度分层，Manual/Semi中的Scope意见也不等于最终难度或GT。')
 report.para('主Manual/Semi有17条原始奇数点：5条有明确用户修正来源（3条确认删点、2条确认补点）继续使用；其余12条未获可用修正而排除。还存在8条其他无效几何。没有自动补删点。含无效作答的图片继续计算有效子集过程，并保留原人数/无效人数；这不是宣称整张图所有作答有效。')
 report.para('敏感性只额外移除2条已确认补点，主分析仍保留：q9v…9c9图24→23人，总簇17→17，支持簇5→4，单人12→13；uNb9…978图23→22人，总簇10→9，支持簇4→4，单人6→5。关键碎片化现象不能只归因于保留这两条修正。详见audit/与extra/confirmed_addition_sensitivity.csv。')
 report.head('3. 用户中等、困难锚点的真实结构')
 anchors=p[p.expert_tag.isin(['中等','困难'])&(p.n_valid>=10)].sort_values(['expert_tag','image_id']).copy();anchors['代码']=['M1','M2','M3','M4','H1','H2','H3','H4'];tab=anchors[['代码','image_id','expert_tag','n_valid','sizes_descending','total_clusters','supported_clusters','singletons']].rename(columns={'expert_tag':'用户tag','n_valid':'有效人数','sizes_descending':'各簇人数','total_clusters':'总簇','supported_clusters':'支持簇','singletons':'单人簇'})
 report.table(tab);report.fig('anchor_cluster_counts.png','图1｜同样阈值0.10下的8张高人数锚点；总簇包含单人簇。')
 report.para('16张用户困难图有11张具有Manual历史，其中仅4张达到至少10名有效人员；41张用户中等图有11张Manual历史及2个Semi条件记录，中等高人数Manual同样仅4张。8张高人数锚点只来自3个楼宇，4张中等全来自uNb9QFRL6hY。它们适合制定待裁决初稿，不足以校准全648图的通用阈值。')
 report.para('M2与H1都有6个总簇、4个支持簇、2个单人簇，故无法仅凭这三个终点计数分开。M3的用户tag为中等，组评论却写“这场景较难”；这两层表述都原样保留，不擅自纠正。H1评论“这张图历史的分歧都有点大”、H2“这个标注出现不收敛了”、H3“这可能不太收敛”是重要预期/历史知情记录，而非独立盲评真值。')
 report.head('4. 相同人数与相同人员后，差异是否还在')
 report.para('8张高人数图有完全相同的18名有效人员交集：W001、W006、W008、W010、W011、W012、W013、W015、W017、W029、W030、W031、W032、W033、W034、W035、W036、W037。使用该同一名单重算，并让8图使用相同的人员进入顺序。中等4图总簇数为3、5、9、6，困难4图为6、8、9、9；中位数分别5.5与8.5，单人簇中位数2与3.5。')
 report.fig('common18_cluster_counts.png','图2｜固定同一18人后仍有方向差异，也仍有重叠；不声称因果或独立统计显著。')
 report.para('这支持用户判断包含部分真实差异，而不是完全由观察人数或名单造成。但楼宇、房间、阶段与选图混杂仍在；中等M3依然较碎片化，困难H1仍能形成四个重复支持簇。不能利用总簇数把这8图无误地排成两类。')
 report.head('5. 10%不是数学错误，但作为唯一硬门不合适')
 report.para('固定比例有时可表示允许的尾部质量，因此并非“所有统一比例都错误”。这里的问题是，经验单人簇比例受到有限人数、稀有模式、几何阈值和聚类分区共同影响，并没有被校准为真实错误率。旧代码还将它用作不计算稳定性的前置门。19人出现2个单人簇为10.53%而被拒，20人同样2个为10%却通过；5–8人只出现1个单人簇就一律超过10%。')
 report.fig('singleton_thresholds.png','图3｜百分比转成整数后的跳变。分段数量只是审阅初稿，也不能冒充统计公认阈值。')
 report.para('本次并列保留固定10%、绝对至多2个、分段计数、较宽松分段计数。建议先用4–8人≤1个、9–16人≤2个、17–24人≤3个作为“少量单人”的审阅起点，并同时显示f1/n和真实人数。中间人数区间缺少用户高支持中等锚点，≤2只是插值式工作规则，尚未校准。宽松边界另报17–24人≤4个。任何超过门的图片都不能因此自动归困难。')
 report.head('6. 一个更深的限制：稀有模式的发现上界')
 report.para('M1有23人，簇人数为18/2/2/1。在以最终模式作为回顾性参照的定义中，前19人必须恰好包含两个双人簇的全部4人，才能称两种少数模式都获重复支持；其上限为 C(19,4)/C(23,4)=0.437719。即使这两簇本身完全可复现，也不可能有80%的重排在前19人都看齐这4人。因此，“19人前80%稳定”同时惩罚模式发现等待，并不等价于模式本身不稳。')
 report.fig('support_discovery_ceiling.png','图4｜精确超几何上界与实测核心稳定比例分开。最终簇仅作回顾性评价，不泄漏给前缀聚类。')
 report.para('H1有19名有效人员及两个双人簇。在n−1=18人时，全部支持模式出现两次的上限为15/19=78.95%，同样低于80%。本轮其实际对应比例为77%，而在已看齐各模式两人的那批相同顺序中，支持核心的份额/几何后缀通过率为100%。后者是有条件稳定，不能抹去未看齐模式的顺序，也不是整体未来保证。')
 report.head('7. 稳定类、稳定比例、稳定整体：分别给证据')
 report.para('逐簇恢复首先逐一移除真实人员，比较簇成员Jaccard；再进行200次80%不同人员子集检查，分别报告“还保留至少2个该簇成员的比例”和有资格时的Jaccard。不能把因抽样只剩1人而不可评价，解释为簇消失或工人错误。全体比例的回放不再预筛10%，支持核心则单独匹配已支持簇、条件比例和簇内几何。')
 report.para('M1在LOO中最弱支持簇Jaccard仍有0.915，但80%子集检查有一个双人簇降至0.672；跨某两个支持簇97.22%的几何配对仍处于0.10兼容范围内。故它可以是用户中等预期，但当前数字分区还不能证明三种清晰自然模式。M2的80%子集最小Jaccard为0.907，较支持重复模式，但0.10下跨簇兼容比例仍达70.37%；分离含义应审图。')
 report.para('H2的5个支持簇在80%子集、保留双人支持的条件下均为Jaccard=1；这些簇对应不同点数，恢复率的一部分由按点数强制分层保证，不能单凭Jaccard=1当作独立的几何或语义有效性证据。额外过程证据是：支持核心尾段通过率89%，到19人的累计核心通过率81%。因此它不支持“什么模式都形成不了”的解释。它仍有3个单人模式，整体分布/未来新解释未被证明稳定；原困难tag继续保留，供用户裁决“不收敛”的具体含义。')
 report.para('H3和H4则同时有较多总簇、单人模式及明显后段新标法：H3为11总簇/5支持/6单人，最后四分段新标法率15.08%；H4为10/6/4，对应21.08%。这些更符合当前观察内的困难候选，但仍不等于永不收敛。')
 report.fig('geometry_cut_sensitivity.png','图5｜阈值改变时的模式数变化。不能按与用户标签相符程度挑选唯一距离阈值。')
 report.head('8. 供用户裁决的初步规则与实际名单')
 report.table(pd.DataFrame([
 {'档位':'简单候选','工作规则':'支持簇1–2、总簇≤3、少量单人；按2…8人分别计算完整模式后缀，当前展示80%门；实际n和剩余观察保留','不能声称':'4–6人范围内稳定不等于24人或未来仍稳定'},
 {'档位':'中等结构候选','工作规则':'2–4支持簇、总簇≤6、分段单人数量门；最弱支持簇LOO J≥.85，并要求80%子集条件J≥.75','不能声称':'类可复现不等于其出现概率/整体分布已收敛；小n与分离问题另标'},
 {'档位':'困难候选','工作规则':'至少10有效人、总簇≥10、单人≥4、最后四分段新几何≥.15、核心尾段通过率<.8','不能声称':'数量多本身不够；≥5支持模式且核心稳定的图保持单独状态，不写永不收敛'},
 {'档位':'暂不分档','工作规则':'无效全缺、人数/模式支持不足、分区敏感、边界或三档不适配；用户决定是否调整','不能声称':'不得默认困难，也不修改人工tag'}]))
 report.para('这些阈值是本次在历史数据与用户概念对照后拟议的筛查表，不是先验预注册标准。总簇≤7、17–24人单人≤4等宽松边界以及严格累计过程版均已执行；不能因为哪个方案填满中等或更好预测而选它。')
 report.table(cnt.rename(columns={'condition':'条件','review_draft_grade':'复核后初步建议'}))
 report.para('先用LOO筛查得到Manual 30张、Semi 11张中等结构候选；80%子集复核进一步将3张Manual和2张Semi退回分区待审，最终是27/9。这些不是36张“整体已收敛”。如果额外坚持“19人内无条件累计核心通过率≥80%”，仍只有Manual 2张、Semi 1张；而先看齐重复模式再评价稳定，则对应另一种有条件结论，不能替换无条件量。全部版本和分母都保留。')
 report.para('旧11个困难候选中，8个仍在新困难候选内；2个Manual与1个Semi退回单人尾部/数量边界，不自动改成中等。新规则另纳入4个此前未分类的Manual图，其中包含过去被整图无效门阻断者，因此新困难候选总数12，不是为了让困难总量单调减少。9张在0.075/0.10/0.125三尺度下均保留困难候选，3张阈值敏感。没有把这些规则当作最终难度真值。')
 report.head('9. 文献实际怎么做，与本项目的差别')
 report.para('Hennig的逐簇稳定性思想是检查“哪些具体簇能在扰动中恢复”，而非要求整张分区都同样稳定。作者fpc手册给出平均Jaccard约0.75、0.85等解释指引，同时强调稳定并不保证簇有效；这些数主要面向bootstrap。本轮用不放回真实人员子集，0.75/0.85仅作为可审阅的对应尺度，不能称为文献认证的中等难度阈值。')
 report.para('Pavlick与Kwiatkowski的NLI研究把每题10个真实判断留出，比较训练侧单高斯和混合分布对未参与拟合判断的预测似然；他们并非“几个簇以上就困难”。该研究支持检查多模式能否在其他判断上复现，但任务是标量文本判断，不能直接套其高斯模型到不同点数的布局。我们此次没有假装已经拟合这些模型。')
 report.para('Chao与Jost讨论按样本完整度而非只按样本量比较物种丰富度。其启发是把稀有模式及未发现质量放进解释；生态固定物种/抽样假设不等于异质人群和数据依赖的几何簇。本轮只计算精确有限池稀释、发现上界及描述性覆盖代理，没有从f1/n直接推断“未来错误率”或无法收敛概率。核对的这些文献没有给出“总簇≥x且单人超过10%便属困难”的统一标准。')
 for ref in REFS:
  report.para(f"{ref['author']} ({ref['year']}). {ref['title']}. {ref['venue']}. DOI: {ref['doi'] or '官方软件手册'}. {ref['url']} 阅读范围：{ref['access']}")
 report.head('10. 用户最终裁决应具体落在哪里')
 report.para('先看8个高人数锚点及旧困难候选的代表作答：确认同点数簇是否真是不同空间解释、单人记录是否合理、是否因遮挡/凸起/门洞改变了目标范围。再确定“中等”的主含义是有限个稳定解释类，还是连模式比例也必须已稳定。前者有数据基础；后者需要同时处理稀有模式发现上限，不能继续把两个问题藏在同一门里。')
 report.para('USER_DECISION_TABLE.csv含全部230个图×条件单元，最后四列留给用户填写。ALL_CANDIDATE_LOCAL_REVIEW_QUEUE.csv绑定image_id、真实worker、canonical作答与各簇代表，聚焦队列另保留。原图留本地，本轮没有阅读、下载或调用模型；所有关于哪种标法合理的判断仍是待裁决，而非多数票、公共参考或模型输出能替代的事实。')
 report.head('11. 复算、边界与未执行事项')
 report.para('实际执行：源字段/修正审计、230个图条件的六尺度终点聚类、逐簇LOO、焦点及候选的80%不放回子集复核、逐前缀重聚类、完整与支持核心两类后缀、精确支持发现上界、固定同一18人比较、两条确认补点敏感性、旧/新候选变类和审图清单。所有曲线均为有限历史人员池重排，不还原真实日历顺序。主版本200顺序，其他指定尺度100顺序；55,300条主/补充顺序结果不是独立数据样本。')
 report.para('旧实验difficulty及同义risk分组没有参与新几何、阈值计算或分型；106专家tag/评论只在分析后作对照并用于明确此次概念修订的背景。许多评论已知晓历史表现，因此不是新的盲化验证。本轮没有重拟合图片/模型预测，没有修改采集安排或Paper A正式合同；新的粗类须经用户确定含义后才适合继续作为后续探索目标。')
 report.para('测试、输入哈希、参数与源代码随包提供。独立解压测试验证代码约束和关键数值；不得把它说成在新人员/新图片上再次实验。Jaccard、距离、比例、数量和重排门均未正式冻结。边界附近的200次Monte Carlo比例还有数值误差，review表专门标出接近80%的记录；不能将它们解释成经验人数增加后的总体收敛概率。')
 report.save()
 readme='''# 本轮复算\n\n在包内repo目录执行；建议单独Python虚拟环境。原图和视觉权重不需要。\n\n```bash\npython -m pip install -r requirements-review.txt\nexport OPENBLAS_NUM_THREADS=1\nexport OMP_NUM_THREADS=1\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 --orders 200\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_summary_v2\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_panel_v2\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_summary_v2\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_extra_v2\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_discovery_v2\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_figures_v2\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_finalize_v2\npython -m pytest tests/test_history_difficulty_review_v2.py -q\n```\n\nWindows可省略export或用PowerShell的`$env:OPENBLAS_NUM_THREADS="1"`。当前环境Python3.13；完整原始回放约8分钟，补充子集/18人比较再需数分钟，其他机器时间不同。\n\n新输出固定写入 `analysis_results/image_portrait_20260914_v1/cloud/history_difficulty_review_20260915_v2/run_c0069628/`，不会覆盖上一轮。默认重新运行会重写本轮自身输出；需要保留多个实验时先复制本轮目录/修改OUT版本。\n\n原始responses.jsonl.gz被完整保留，仅选择白名单字段；不能将内含但未使用的旧difficulty字段误称为新算法输入。主空间/模型A–E未在本轮重拟合，上一轮成绩不能声称对应新初稿。\n\n本地输入字节与c0069628最新GitHub的raw/metadata blob完全一致，详见audit/INPUT_METHOD_MANIFEST.json。\n'''
 (OUT/'REPRODUCE.md').write_text(readme,encoding='utf-8')
 print('FINAL',cnt.to_dict('records'),'queue',len(q),flush=True)
if __name__=='__main__':main()
