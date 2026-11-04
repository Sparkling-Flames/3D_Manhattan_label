"""Build a standalone current-DSTRUCT AC atlas from exact saved evidence.

The stable geometry drawing functions come from the pinned existing AC viewer.
This wrapper replaces its historical cohort/labor text with the current audited
definitions and adds observation-anchor navigation plus an existing-ABC appendix.
"""
from __future__ import annotations
import argparse,base64,html,io,json,os,re,sys
from pathlib import Path
from mechanism_core import ROOT,OUT,read_json,save_json,sha
sys.path.insert(0,str(ROOT/'research/workers/personnel_ac_v21_20261030/stage06_cases/code'))
from build_ac_case_viewer import HTML as BASE

NOTES={
 'AC01':dict(title='C1→C2：同为4节点，底面与方向改善',points=[
  '20/7、简单卧室；Q 95.476→98.830。稳定D对应、全部20人完整来源环均保持，没有跨票或新增转折。',
  '底面IoU 0.9665→0.9917，底边偏差0.388→0.166°、方向偏差0.945→0.230°。几何定位改善即可产生数分变化。',
  '这是接近该方向正向逐图中位的存量实现；同预算同难度的负向图片见AC02。']),
 'AC02':dict(title='C1→C2反例：相同简单层，也可能下降',points=[
  '20/7、简单通行场景；Q 74.209→71.576。两端均4节点；稳定对应无跨票。',
  '底面IoU 0.7665→0.7473、方向偏差1.334→1.778°，面积8.643→8.403 h²。上下边界并非全都变差，需看完整分项。',
  '同预算同难度只匹配这两项条件；场景、图片与基线分数仍不同，不能单独归因为用途差异。']),
 'AC03':dict(title='C1→C3：同节点几何改善的普通实例',points=[
  '20/7、简单起居场景；Q 92.144→94.520，4节点保持。',
  '底面IoU 0.9446→0.9611，方向偏差0.586→0.295°，上下参考边界偏差同时减小。',
  '当前存量C1↔C3支持很少；本例说明方向怎样实现，不能代表全部建筑或困难图。']),
 'AC04':dict(title='C1→C3小变化：两端已接近参考',points=[
  '20/7、简单卫浴；Q 97.347→97.426，只变化+0.079。4节点、20个完整来源环均保持。',
  '底面IoU约0.977，A/C底面间距1−IoU为0.00747，质心移动0.00241 h。高分接近伴随小几何差异。',
  '固定规则未找到适合的同层负向图片/同图负向实现，保留小效应例而不制造反例。']),
 'AC05':dict(title='C2→C3：不增节点也可同时改善几何',points=[
  '20/7、简单卧室；Q 84.344→87.452，两端均6节点且未检测到稳定锚点跨票。',
  '底面IoU 0.9030→0.9194，底边偏差1.151→0.953°，方向偏差1.416→1.172°。',
  '整体上边界偏差也减小，平均高度误差略增，提示Q提升可伴随某个分项轻微恶化。']),
 'AC06':dict(title='C2→C3小变化：分项方向可以抵消',points=[
  '20/7、简单卫浴；Q 97.793→97.800，只变化+0.007。4节点和支持覆盖保持。',
  '方向偏差减小，但底面IoU略降、底边偏差略增。Q接近不代表所有分项完全相同。',
  '本图也用于AC04，但比较块与背景不同；两例不能作为C1/C2的额外受控对照。']),
 'AC07':dict(title='过票后保留凹角：一处结构可改变整体方向与范围',points=[
  '14/7、困难卧室。A g005与C g001由同一2个D原答角点锚定，支持4→9；名义门槛始终7票。替换块支持2→7。',
  'A遗漏中间凹角形成较长斜边，C保留后5→6节点，参考角点召回5/6→6/6；Q 46.212→81.647，IoU 0.7699→0.9361，方向偏差13.240→3.202°。',
  'D分组未改变。合法同单一来源记录劳动3028.213→4065.972秒，增加1037.759秒；它是历史总记录劳动，不是新实验耗时或达到共识的时间。']),
 'AC08':dict(title='同层反例：召回更多角点，整体Q仍下降',points=[
  '同为14/7、C2→C3、困难。稳定锚点有5处上跨、1处下跨，同时存在D观察分组改变；不能把歧义组认作精确同节点。',
  '5→9节点、参考角点召回5/14→9/14，却Q 55.668→45.990，IoU 0.8731→0.7497、方向偏差8.215→12.933°。保存C环仍遗漏若干参考转折，其中g009到g005是一条长斜连边。',
  '上下边界匹配误差和高度误差有改善，结构召回与整体范围、方向发生权衡。本例不否定跨票与大变化相关，也不支持“增节点必升质”。']),
 'AC09':dict(title='20票、4节点、相同连接：定位足以改变全几何',points=[
  '20/7、简单通行场景。4个组各自均20票，所有13个D观察在对应组中保持，所选组和环邻接均一致。不存在票门槛改变或已检测的跨票。',
  'Q 77.408→92.579；IoU 0.9544→0.9827、方向偏差3.873→1.865°，上下边界和水平位置偏差均下降。面积6.423→6.259 h²、质心移0.06646 h。',
  '远端g003底点y 284.258→285.079像素，底面(-5.685,-0.531)→(-5.522,-0.501)。这显示远端投影敏感性；全队还有其他角点变化，不把15.171分全归因于这一个点。合法同源记录劳动减少302.001秒。']),
 'AC10':dict(title='双高分近零：分数空间与几何实证同时查看',points=[
  '20/7、简单卧室；Q 96.571→96.064，变化−0.507，4节点和20个完整来源环均保持。',
  'A/C底面间距1−IoU仅0.00983、质心移0.00342 h。方向偏差稍降，但底面IoU与底边偏差稍差。',
  '两端Q≥90本来就限制|ΔQ|≤10，这一数学界限不是独立的机制验证；页末既有ABC展示非高分下也有同类变化更大。']),
 'AC11':dict(title='各局部半票可入选，但没有一条完整来源环',points=[
  '14/7、中等通行场景。两个稳定局部组g004/g005各从1→7票；g003从13→7票，仍达到固定7票门槛。',
  'C中支持g003的7人和支持g004/g005的7人两组分开，没有一个原答的投影顺序恰好一次覆盖全部6个入选组。原生完整来源环计数从A的13降为0，reason为no_source_ring_covering_all_selected_nodes。',
  '这说明当前source-ring连接规则没有输出，不能泛称不存在可能的拓扑。C的Q为空，不能写作−80.060分；此具体团队未命中57个已批准人工排序结果，保留无连接状态。']),
 'AC12':dict(title='过票不是大跳变的充分条件',points=[
  '20/7、困难卧室。固定门槛10票；g003/g004均9→10，g005 10→9，D观察分组保持。9→10节点，Q仅47.674→45.660。',
  '底面IoU 0.8597→0.8864、底边偏差2.011→1.283°有所改善；方向偏差12.328→15.134°变差，上下边界部分也变差。',
  '跨票改变结构，但不同分项相抵后总分变化小于5。它限定“跨票常伴随大变化”的适用强度，不把规律全盘否定。'])
}

EXTRAS=r'''
function renderCurrentMetrics(){
 const m=chosen.current_metrics;const defs=[['B8L2','Q / B8L2'],['D10','D10'],['IoU3D100','3D IoU ×100'],['iou_2d','底面IoU'],['S_bottom_deg','底边角偏差 S（°）'],['dir','方向偏差 D（°）'],['Hmean','整体高度误差 Hmean'],['Hcenter','局部高度误差 Hcenter'],['nodes','入选节点'],['fusion_turn_n','有效转折'],['fusion_short_turn_edges','短结构边'],['fusion_redundancy_n','冗余节点'],['ref_node_recall_9','参考节点召回（9°）'],['ref_edge_recall_9','参考边召回（9°）'],['matched_ref_pair_fraction','边界匹配覆盖比例'],['matched_ref_horizontal_abs_deg','匹配参考水平位置偏差（°）'],['matched_ref_top_abs_deg','匹配参考上边界偏差（°）'],['matched_ref_bottom_abs_deg','匹配参考下边界偏差（°）'],['geometry_area_h2','底面面积（h²）'],['centroid_x_h','质心 x / h'],['centroid_z_h','质心 z / h'],['bounds_min_x_h','最小 x / h'],['bounds_max_x_h','最大 x / h'],['bounds_min_z_h','最小 z / h'],['bounds_max_z_h','最大 z / h'],['height_mean_h','平均高度 / h'],['height_min_h','最小高度 / h'],['height_max_h','最大高度 / h'],['minimum_support','固定MV50票门槛']];
 $('metrics').replaceChildren();for(const [key,label]of defs){const a=('A_'+key in m)?m['A_'+key]:chosen.arms.A[key],c=('C_'+key in m)?m['C_'+key]:chosen.arms.C[key];const tr=node('tr');[label,num(a),num(c),num(typeof a==='number'&&typeof c==='number'?c-a:null)].forEach(x=>tr.append(node('td',x)));$('metrics').append(tr)}
 for(const [label,a,c,delta]of[['已知完整记录劳动（秒）',m.A_recorded_labor_total,m.C_recorded_labor_total,m.dT_whole],['换出X / 换入Z记录劳动（秒）',m.X_recorded_labor_total,m.Z_recorded_labor_total,m.dT_blocks]]){const tr=node('tr');[label,num(a),num(c),num(delta)].forEach(x=>tr.append(node('td',x)));$('metrics').append(tr)}
 $('time_note').textContent=`全部成员时间完整且同单一来源：${truth(m.time_whole_single_source)?'是':'否'}；替换块同单一来源：${truth(m.time_blocks_single_source)?'是':'否'}。A来源计数 ${m.A_time_source_counts}；C来源计数 ${m.C_time_source_counts}。劳动差值仅采用相应合法同源支持；空值不填0。总记录劳动是既有标注记录之和，既不是新实验实际耗时，也不是达到共识所需时间。匹配参考边界均值仅在已匹配部分计算，须同时看匹配覆盖。`;
}
function renderRaw(){const D=new Set(list(chosen.event.D_workers)),X=new Set(list(chosen.event.X_workers)),Z=new Set(list(chosen.event.Z_workers)),box=$('rawdetails');box.replaceChildren();for(const r of chosen.pool.records.filter(r=>D.has(r.worker_id)||X.has(r.worker_id)||Z.has(r.worker_id))){const block=D.has(r.worker_id)?'D':X.has(r.worker_id)?'X':'Z',label=chosen.frozen_lobo_labels[r.worker_id]||{},t=chosen.current_record_labor.find(t=>t.worker_id===r.worker_id&&t.object_id===r.object_id);const d=node('details');d.append(node('summary',`${block} · ${r.worker_id} · 当前楼外类 ${truth(label.known)?label.class_id:'未知'} · 原答${r.points.length/2}角点对 · 个人Q ${num(r.B8L2)} · 记录T ${num(t?.source_active_time_seconds)}秒`));d.append(button('仅看此人完整原答',()=>{visible=new Set([r.worker_id]);syncWorkerChecks();draw();setFocus('all')}));d.append(node('pre',JSON.stringify({original_preprocessed_full_answer:r,current_outside_building_label:label,current_legal_recorded_labor:t},null,2)));box.append(d)}}
function setFocus(value){const selected=chosen.D_anchor_links.filter(r=>r.link_type==='exact_same_nonempty_D_observations');const r=value==='all'?null:selected[Number(value)];for(const arm of['A','C']){const panel=$(arm.toLowerCase()+'_svg');let view='0 0 1024 512';if(r){const p=JSON.parse(r[arm+'_center_json']||'null');if(p){const x=Math.max(0,Math.min(864,(p[0][0]+p[1][0])/2-80));let y=Math.max(0,Math.min(232,(p[0][1]+p[1][1])/2-140));view=`${x} ${y} 160 280`}}panel.setAttribute('viewBox',view)}$('focus').value=value}
function renderExtras(){
 const e=chosen.event,m=chosen.current_metrics,s=chosen.mechanisms;
 $('title').textContent=`${e.case_id} · ${e.image} · 当前DSTRUCT ${e.class_pair.replace('_','→')}`;
 $('meta').textContent=`n=${e.n}，m=${e.m}；同图、同参考、固定D、等人数替换。难度 ${m.official_difficulty}；用途 ${m.room_type}\nD类别构成 ${e.current_D_class_counts}；D=${e.D_workers}\nX（换出${e.source_class_current}）=${e.X_workers}\nZ（换入${e.target_class_current}）=${e.Z_workers}\n存量团队上的当前标签条件分析；原事件 ${e.event_id}；原始方向符号 ${e.orientation_sign}\n参考：${e.reference_id} / ${e.reference_version}\n自动结果：A ${chosen.arms.A.score_status}；C ${chosen.arms.C.score_status}；精确匹配已批准人工端点：A=${chosen.approved_manual_order_match.A.approved_result_available}、C=${chosen.approved_manual_order_match.C.approved_result_available}`;
 $('case_notes').replaceChildren(node('h2',chosen.interpretation.title));chosen.interpretation.points.forEach(p=>$('case_notes').append(node('p',p)));
 renderCurrentMetrics();const focus=$('focus');focus.replaceChildren();let all=node('option','完整原图');all.value='all';focus.append(all);
 const stable=chosen.D_anchor_links.filter(r=>r.link_type==='exact_same_nonempty_D_observations');stable.forEach((r,i)=>{const o=node('option',`${r.A_group} → ${r.C_group} / ${r.A_support}→${r.C_support}票`);o.value=i;focus.append(o)});setFocus('all');
 const ar=chosen.D_anchor_links.map(r=>({cells:[r.link_type==='exact_same_nonempty_D_observations'?'精确相同D观察集合':'D观察集合拆分/重组',r.A_group+' → '+r.C_group,String(r.common_D_observations),r.A_support+' → '+r.C_support,(r.A_selected?'入选':'未选')+' → '+(r.C_selected?'入选':'未选'),num(r.horizontal_shift_deg),num(r.top_vertical_shift_deg),num(r.bottom_vertical_shift_deg)]}));
 $('anchor_table').replaceChildren(table(['对应可靠度','A组 → C组','共同D观察','票数','选择状态','水平移°','上边界移°','下边界移°'],ar));
 $('anchor_summary').textContent=`名义门槛 ${s.minimum_support_A}→${s.minimum_support_C}；稳定对应组 ${s.stable_anchored_groups}；歧义对应链接 ${s.ambiguous_anchor_links}；未获稳定对应的入选组 A=${s.A_selected_groups_without_stable_anchor} / C=${s.C_selected_groups_without_stable_anchor}。D共组关系改变：${s.D_partition_changed}。完整所选锚点与环可比较：${s.ring_topology_comparable}；可比较时环邻接改变：${s.ring_topology_changed===null?'不适用':s.ring_topology_changed}。`;
 $('provenance').textContent=JSON.stringify({event:e,selection:chosen.selection,source_provenance:chosen.provenance,approved_manual_order_match:chosen.approved_manual_order_match,full_anchor_links:chosen.D_anchor_links,reference_metadata:chosen.pool.meta,interpretation_limits:chosen.interpretation_limits},null,2);
}
function render(){renderBase();renderExtras()}
function renderAppendix(){const c=DATA.appendix,holder=$('abc_panels');holder.replaceChildren();for(const arm of['A','B','C']){const r=c.endpoints[arm],pane=node('div');pane.className='pane';pane.append(node('h3',`${arm} · Q ${num(r.B8L2)} · ${r.nodes}节点`));const s=svg('svg',{viewBox:'0 0 1024 512',class:'pano'});s.append(svg('image',{href:DATA.images[c.image],x:0,y:0,width:1024,height:512}));outline(s,c.reference.points_1024x512,'#111',1.7,1,'5 3');outline(s,r.geometry.points,{A:'#2471a3',B:'#008777',C:'#d95f28'}[arm],2,1);pane.append(s,node('p','成员：'+r.member_workers.join('、')));holder.append(pane)}$('abc_text').textContent=`第12批原事件 ${c.event_id}，n=8,m=4；原保存逐图GS=${num(c.image_mean_GS)}。原代表事件A/B/C均未达90分，B具有6节点、A/C各4节点，可直接看到局部结构差异。GS是原逐图统计，不能冒充所示单一事件的GS。该例不纳入本轮248对诊断，不重新融合、评分或计算GS。`;const details=node('details');details.append(node('summary','第12批完整来源与原保存几何'),node('pre',JSON.stringify(c,null,2)));$('abc_data').replaceChildren(button('下载既有ABC引用数据',()=>download('APPENDIX_EXISTING_ABC.json',JSON.stringify(c,null,2))),details)}
'''

def font_file(argument):
    for p in [argument,os.environ.get('HOHONET_CJK_FONT'),str(OUT/'source/NotoSansCJKsc-Regular.otf'),
              'C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']:
        if p and Path(p).is_file():return Path(p)
    return None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--font');a=ap.parse_args()
    cases=[read_json(p) for p in sorted((OUT/'cases').glob('AC[0-9][0-9].json.gz'))]
    for c in cases:c['interpretation']=NOTES[c['case_id']]
    save_json(OUT/'CASE_INTERPRETATIONS_ZH.json',NOTES)
    appendix=read_json(OUT/'cases/APPENDIX_EXISTING_ABC.json.gz')
    images={}
    for code in sorted({c['event']['image'] for c in cases}|{appendix['image']}):
        images[code]='data:image/png;base64,'+base64.b64encode((OUT/'originals'/(code+'.png')).read_bytes()).decode()
    template=BASE
    template=template.replace('HOHONET v2.1：不同人群如何改变同一张图的共识','当前 DSTRUCT 直接 AC：逐人原答、局部票账与全几何')
    template=template.replace('直接 A/C、整类替换与类别联盟的精确证据。可以逐人打开完整原答，查看同一目标参考、两队输出、所有候选对应组与连接记录。缺失质量分数保留为空。',
        '本轮固定的12个存量AC案例，另附第12批既有ABC引用。每对固定同图、参考、人数、替换人数与共同背景D；当前标签按目标建筑楼外折绑定。支持正例、反例与无输出状态同页检查。')
    template=template.replace('<section class="box"><h2>原图、完整原答与融合候选</h2>',
        '<section class="box" id="case_notes"></section><section class="box"><h2>原图、完整原答与融合候选</h2>')
    template=template.replace('<button id="blockonly">只显示替换块X/Z</button>',
        '<button id="blockonly">只显示替换块X/Z</button><label>局部D锚点 <select id="focus"><option value="all">完整原图</option></select></label>')
    template=template.replace('<section class="box"><h2>来源顺序与连接记录</h2>',
        '<section class="box"><h2>跨队D观察对应与实际跨票</h2><p id="anchor_summary" class="note"></p><p class="note">精确对应只要求同一非空D原答object_id+source_pair_index集合，不能由局部组编号、位置近似或参考角点相近代替。水平角差按ERP环绕取最短差；上/下y增量按图像坐标方向记号，正数表示下移。歧义组不做精确跨票或位置差判定。</p><div class="scroll" id="anchor_table"></div></section><section class="box"><h2>来源顺序与连接记录</h2>')
    template=template.replace('本页保留完整source assignment、直接边/投影边支持与备选环。局部 g编号只在该队内部有意义，跨队应通过原答object_id和source_pair_index追踪。没有共同观察者本身不能证明两种结构在物理上互斥。',
        '完整来源环计数：对每份实际原答的已保存顺序，投影到本队入选组，恰好覆盖全部组一次，且至少3组。此计数为0是当前source-ring规则没有候选，不代表不存在其他可能连接。直接边、投影边、备选环和原生reason均保留。局部g编号只在本队有意义。')
    template=template.replace('</section></main>',
        '</section><section class="box"><h2>引用第12批既有严格ABC：高分解释的边界</h2><p id="abc_text"></p><div id="abc_panels" class="three"></div><div id="abc_data"></div></section></main>')
    template=template.replace('.two{display:grid;', '.three{display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px}.two{display:grid;')
    template=template.replace('@media(max-width:950px){.two{','@media(max-width:950px){.three{grid-template-columns:1fr}.two{')
    template=template.replace('function render(){const e=chosen.event;', 'function renderBase(){const e=chosen.event;')
    template=template.replace('function renderRaw(){const D=', 'function renderRawLegacyUnused(){const D=')
    anchor='DATA.cases.forEach((c,i)=>'
    assert anchor in template
    template=template.replace(anchor,EXTRAS+'\n'+anchor)
    template=template.replace("$('blockonly').onclick=()=>{visible=new Set([...list(chosen.event.X_workers),...list(chosen.event.Z_workers)]);syncWorkerChecks();draw()};render();",
        "$('blockonly').onclick=()=>{visible=new Set([...list(chosen.event.X_workers),...list(chosen.event.Z_workers)]);syncWorkerChecks();draw()};$('focus').onchange=()=>setFocus($('focus').value);render();renderAppendix();")
    data=json.dumps(dict(cases=cases,images=images,appendix=appendix),ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c').replace('>','\\u003e')
    font=font_file(a.font);font_css='';font_meta=None
    if font:
        from fontTools import subset
        from fontTools.ttLib import TTFont
        f=TTFont(font,fontNumber=0)
        license_text=' '.join(n.toUnicode() for n in f['name'].names if n.nameID==13)
        # The delivered Noto subset is redistributable. A local Windows font
        # can render the scientific figures without being copied into HTML.
        if 'SIL Open Font License' in license_text:
            sub=subset.Subsetter();sub.populate(text=template+json.dumps(cases,ensure_ascii=False)+json.dumps(appendix,ensure_ascii=False));sub.subset(f)
            b=io.BytesIO();f.save(b);raw=b.getvalue()
            font_css="@font-face{font-family:HohonetEvidence;src:url(data:font/otf;base64,"+base64.b64encode(raw).decode()+") format('opentype');font-weight:100 900;font-style:normal;font-display:block}"
            font_meta=dict(source_filename=font.name,source_sha256=sha(font),embedded_subset_bytes=len(raw),license='SIL Open Font License 1.1')
            template=template.replace('system-ui,"Noto Sans CJK SC",sans-serif','HohonetEvidence,system-ui,"Noto Sans CJK SC",sans-serif')
            license_file=OUT/'source/FONT_LICENSE.txt'
            if license_file.exists():template=template.replace('</main>', '<details class="box"><summary>嵌入字体版权与许可</summary><p>© 2014–2021 Adobe；Noto Sans CJK SC 的展示子集。</p><pre>'+html.escape(license_file.read_text())+'</pre></details></main>')
        f.close()
    final=template.replace('__DATA__',data).replace('__FONT_FACE__',font_css)
    dest=OUT/'CURRENT_DSTRUCT_AC_ATLAS.html';tmp=dest.with_name(dest.name+'.writing')
    with tmp.open('w',encoding='utf-8') as f:f.write(final);f.flush();os.fsync(f.fileno())
    tmp.replace(dest)
    save_json(OUT/'ATLAS_RECEIPT.json',dict(path=dest.name,sha256=sha(dest),bytes=dest.stat().st_size,
        AC_cases=len(cases),existing_ABC_appendices=1,unique_originals=len(images),all_original_photos_embedded_unchanged=True,
        all_full_original_answers_embedded=True,all_native_identity_votes_assignments_rings_embedded=True,
        D_observation_anchors_embedded=True,current_LOBO_labels_and_legal_recorded_labor_embedded=True,
        external_network_requests=0,new_fusion_calls=0,new_score_calls=0,font=font_meta))
    print(f'Atlas: {dest.stat().st_size:,} bytes; 12 AC cases + existing ABC appendix.')

if __name__=='__main__':main()
