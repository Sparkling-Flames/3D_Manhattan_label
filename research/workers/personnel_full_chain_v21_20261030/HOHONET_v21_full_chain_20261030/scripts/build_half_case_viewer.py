"""Standalone, exact-data case reader for every latest half-team exception."""
from pathlib import Path
import base64,collections,gzip,hashlib,html,io,json,math
import numpy as np
import pandas as pd
from PIL import Image
from complete_half_traces import read,clean,write
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage01_half_team'
def fmt(x,n=3):return '不可评' if pd.isna(x) else f'{x:+.{n}f}'
def main():
    images=pd.read_csv(OUT/'ALL_36_EXCEPTION_NUMERIC_AND_MECHANISM_INDEX.csv')
    events=pd.read_csv(OUT/'EVENTS_METRIC_SPECIFIC_SUPPORT.csv.gz',low_memory=False)
    facts=pd.read_csv(OUT/'mechanism_tables/ARM_MECHANISM_FACTS.csv')
    refs=pd.read_csv(OUT/'mechanism_tables/REFERENCE_NEAR_GROUP_DIAGNOSTIC.csv')
    original_receipts={x['image_code']:x for x in read(OUT/'originals/ORIGINALS_VERIFICATION.json')}
    selected=[];caseindex=[];payload={'images':{},'events':{},'teams':{},'pools':{},'metadata':{'commit':'13a7861334749805a86dc19e9ea79fcaa71020c0','classification':'TARGET K3为冻结工作分析对象，最终方法尚未选定','Q_missing':'缺失保持null；按原score_status展示','event_weight':'背景→替换块→池→图等权；页面每个选项是实际原事件'}}
    md=['# 最新14/7全部反例与机制索引','','当前综合197事件、85张登记图、83张共同可评图。GA非正22图，GS非正21图，C−B非正7图，共同Q缺失2图，四类数值并集32图，另纳入4张逐图均值可评但部分原事件不可评的图片，共36图。类别工作安排不代表最终选型。','','本索引逐图给出数值关系与已取得的轨迹事实；“高分”“C在A/B之间”“分项反向”是可重叠的数值描述，不能独自证明投票原因。全部事件和原答可在独立HTML查看器中切换。','']
    for row in images.sort_values('image').to_dict('records'):
        im=row['image'];es=events[(events.image==im)&events.n.isin([14,20])].copy();half=es[es.n==14].copy()
        focus='gap_sym' if row['nonpositive_symmetric'] else 'gap_A' if row['nonpositive_same_origin'] else 'CB'
        if row['no_joint_Q'] or row['partial_event_status_only']:anchor=half[half.gap_A.isna()].sort_values('event_id').iloc[0]
        else:
            half['anchor_distance']=(half[focus]-row[focus]).abs();anchor=half.sort_values(['anchor_distance','event_id']).iloc[0]
        eid=anchor.event_id;pid=anchor.pool_id;pool=read(OUT/'case_inputs'/(pid+'.json.gz'))
        af=facts[facts.event_id==eid].set_index('arm')
        flags=[]
        for col,name in [('nonpositive_same_origin','同起点幅度非正'),('nonpositive_symmetric','对称幅度非正'),('C_not_better_than_B','C−B不升质'),('no_joint_Q','三队共同Q不可评'),('partial_event_status_only','部分事件不可评，逐图数值非反例')]:
            if row[col]:flags.append(name)
        numerical=[f"逐图G_A {fmt(row['gap_A'])}，G_S {fmt(row['gap_sym'])}，C−B {fmt(row['CB'])}。",
                   f"14/7登记{len(half)}事件；其中三队Q共同可评{int(half.gap_A.notna().sum())}，B/C共同可评{int(half.CB.notna().sum())}。"]
        if pd.notna(row['all_Q_at_least_90']):numerical.append(f"三队Q均≥90的设计权重占{row['all_Q_at_least_90']:.1%}；C位于A/B分数之间占{row['C_between_A_B']:.1%}；C−B三项loss出现相反方向占{row['opposed_CB_loss_components']:.1%}。")
        t=half.record_time_CB_pct_source_matched.dropna()
        numerical.append(f"C−B合法同源劳动事件{len(t)}/{len(half)}；逐图劳动变化{fmt(row.get('record_time_CB_pct_source_matched',np.nan))}%。")
        mechanism=[]
        for arm,block in zip('ABC','XYZ'):
            f=af.loc[arm]
            mechanism.append(f"{arm}队：{int(f.selected_groups)}个入选/{int(f.all_groups)}个候选，{int(f.exact_threshold_selected_groups)}个恰达{int(f.minimum_support)}票；该端点分组内D票数达门槛{int(f.background_alone_reaches_groups)}组、{block}票数达门槛{int(f.replacement_alone_reaches_groups)}组；完整投影原环{int(f.source_complete_projected_rings)}份；状态{f.score_status}。")
        if (af.selected_disjoint_support_pairs>0).any():mechanism.append('有同时入选却无共同原答观察者的候选组对。此为明确票账事实；是否属于物理上互斥的表达仍须看原图和完整原答。')
        if (af.reference_near_group_below_threshold_n>0).any():mechanism.append('存在距某参考底角≤5°、但未达票的最近候选组；索引给出具体参考角及候选，不能把未入选直接解释成没有人画。')
        if af.selected_unresolved_locations.eq(0).all():mechanism.append('该锚点三队的已选组均有位置估计；若完整环缺失，不能归因于已选节点位置为空。')
        rr=refs[refs.event_id==eid].sort_values(['nearest_group_bottom_deg','arm'],ascending=[False,True]).iloc[0]
        pair=json.loads(rr.reference_point_pair_json);check=f"看{im}的正式参考角#{int(rr.reference_corner_1based)}（底点约x={pair[1][0]:.1f}, y={pair[1][1]:.1f}，1024×512坐标）。锚点{rr.arm}队最近组{rr.nearest_group}，底角距{rr.nearest_group_bottom_deg:.2f}°、{int(rr.nearest_group_support)}票、{'入选' if rr.nearest_group_selected else '未入选'}。人工判断该处可见墙角/短折及目标范围；数值不自动判断哪种表达语义正确。"
        info={'image':im,'pool_id':pid,'difficulty':row['difficulty'],'flags':flags,'gap_A':row['gap_A'],'gap_sym':row['gap_sym'],'CB':row['CB'],'anchor_event':eid,'selection_rule':'all requested exception images retained; anchor nearest its image-level relevant signed statistic, lexical tie break; missing image first event; all events remain selectable','numerical_notes':numerical,'trace_notes':mechanism,'human_check':check,'event_ids':es.sort_values(['n','event_id']).event_id.tolist()}
        original=OUT/'originals'/(im+'.png')
        with Image.open(original) as img:
            img=img.convert('RGB');img.thumbnail((1536,768));b=io.BytesIO();img.save(b,format='JPEG',quality=90)
        info['preview']='data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode();info['original_sha256']=original_receipts[im]['sha256'];payload['images'][im]=clean(info)
        payload['pools'][pid]=pool
        for ev in es.to_dict('records'):
            # One preserved event, its endpoint keys and exact D/X/Y/Z.
            keep=['event_id','image','pool_id','building','n','m','D','X','Y','Z','source_class','target_class','source_stage','block_id','background_id','A_team_key','B_team_key','C_team_key','gap_A','gap_sym','CB','record_time_CB_pct_source_matched']
            payload['events'][ev['event_id']]=clean({k:ev[k] for k in keep})
            for arm in 'ABC':
                key=ev[arm+'_team_key']
                if key in payload['teams']:continue
                tr=read(OUT/'trace_endpoints'/(key+'.json.gz'))
                fields=['team_key','member_workers','member_object_ids','score_status','B8L2','D10','nodes','minimum_support','geometry','full_state','fusion_turn_n','fusion_short_turn_edges','ref_node_recall_5','ref_edge_recall_5','boundary_loss','direction_loss','height_loss','geometry_area_h2','height_mean_h','source_time_total_seconds','recorded_time_eligible','record_time_by_kind_json']
                payload['teams'][key]={k:tr.get(k) for k in fields}
        selected.append({'image':im,'anchor_event':eid,'focus_metric':focus,'rule':info['selection_rule']})
        caseindex.append({'image':im,'difficulty':row['difficulty'],'flags':'；'.join(flags),'GA':row['gap_A'],'GS':row['gap_sym'],'CB':row['CB'],'anchor_event':eid,'human_check':check,'numeric_evidence':' '.join(numerical),'trace_evidence':' '.join(mechanism),'all_events':len(es),'original_file':'originals/'+im+'.png','trace_index':'MECHANISM_EVENT_INDEX.csv'})
        md += [f"## {im}（{row['difficulty']}）",'','**'+ '；'.join(flags)+'**','']+numerical+['',f'逐事件锚点：`{eid}`。']+mechanism+['','**人工查看点：** '+check,'']
    pd.DataFrame(selected).to_csv(OUT/'CASE_ANCHOR_SELECTION.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(caseindex).to_csv(OUT/'ALL_36_CASE_READING_INDEX.csv',index=False,encoding='utf-8-sig')
    (OUT/'ALL_36_CASES_ZH.md').write_text('\n\n'.join(md)+'\n')
    script=(ROOT/'scripts/half_case_viewer.js').read_text()
    data=json.dumps(clean(payload),ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('</',r'<\/')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HOHONET v2.1 最新半队全部反例</title><style>body{margin:0;background:#f3f5f8;color:#142235;font:15px/1.55 system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:24px}h1{font-size:28px;margin:0 0 8px}h2{font-size:20px}section{background:white;border:1px solid #d8e0e9;border-radius:8px;padding:18px;margin:14px 0}.controls{display:flex;gap:14px;flex-wrap:wrap}select,button{font:inherit;padding:7px;max-width:100%}label{display:block}.muted{color:#536479}.grid{display:grid;grid-template-columns:2fr 1fr;gap:18px}canvas{width:100%;background:#eef1f6;border:1px solid #bbc5d3}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid #d8e0e9;padding:6px;text-align:left}tbody tr:hover{background:#edf3ff}#notes p{margin:7px 0}.pill{display:inline-block;padding:3px 8px;border-radius:4px;background:#e9edf5;margin:2px}#rawlabel{max-width:500px}.scroll{overflow:auto;max-height:370px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 monospace}.legend{font-weight:600}.A{color:#176fbc}.B{color:#8551b6}.C{color:#d34931}@media(max-width:850px){.grid{grid-template-columns:1fr}}</style><main><h1>HOHONET v2.1 最新半队全部反例</h1><div class="muted">197事件综合口径 · 36张图完整索引 · 全部相关原事件含20/7对照 · 精确原团队轨迹。TARGET K3是本轮工作分析对象，最终分类尚未选定。</div><section class="controls"><label>图片<select id="image"></select></label><label>原事件<select id="event"></select></label><label>显示团队<select id="arm"><option>A</option><option>B</option><option selected>C</option></select></label><label>完整原答<select id="raw"></select></label><label><input type="checkbox" id="allraw">叠加该队全部原答</label><label><input type="checkbox" id="groups" checked>显示全部候选组与票数</label></section><section id="notes"></section><section><div class="legend">黑色：冻结参考　<span class="A">蓝：A</span>　<span class="B">紫：B</span>　<span class="C">红：C</span>　橙色：所选原答。空心候选未达票，实心候选已入选。</div><div class="grid"><div><canvas id="pano" width="1536" height="768"></canvas><p class="muted">原图保持原来源；页面内预览转换为JPEG，完整PNG和校验值在结果包 originals。仅complete_conditional共识绘制完整连接；其它状态只画已选角点，不绘候选环。参考和完整原答仍按原环顺序在3D边上采样后投影，未按横坐标重排。</p></div><canvas id="floor" width="650" height="650"></canvas></div><div id="scores"></div></section><section><h2>当前队全部候选身份组</h2><p class="muted">D及X/Y/Z票数按本事件真实成员计算。半队7人只有全部支持同一候选组才会给该组7票。点击一行突出显示；局部node编号不能用于跨队认同一结构。</p><div class="scroll" id="votes"></div><h2>节点、原环与连接</h2><pre id="detail"></pre><button id="download">下载当前事件完整原答与三队轨迹JSON</button></section><section><h2>来源与定义</h2><p>原始综合事件、当前楼外标签、正式主目标参考、原答和冻结融合均来自提交 <code>13a7861334749805a86dc19e9ea79fcaa71020c0</code>。GA=|C−A|−|B−A|；GS=(|C−A|+|C−B|)/2−|B−A|。二者是幅度差，C−B才是质量方向。缺Q保持缺失，各指标使用自己的有效支持。</p><p>数值描述与机制事实分开。无共同观察者的两组均过票，不自动证明物理互斥；距参考角近且未入选，不自动证明参考语义正确。每图提供具体人工查看点。</p></section></main><script id="data" type="application/json">'''+data+'''</script><script>'''+script+'''</script></html>'''
    dest=OUT/'HOHONET_latest_half_all36_viewer_ZH.html';dest.write_text(page)
    write(OUT/'VIEWER_DATA_VALIDATION.json',{'images':len(payload['images']),'events':len(payload['events']),'teams':len(payload['teams']),'full_raw_pool_answers':sum(len(x['records']) for x in payload['pools'].values()),'all_original_previews_embedded':True,'all_unselected_votes_embedded':True,'external_dependencies':0,'html_bytes':dest.stat().st_size,'original_pngs_crc_verified':len(payload['images'])})
    print(dest,len(payload['teams']),dest.stat().st_size)
if __name__=='__main__':main()
