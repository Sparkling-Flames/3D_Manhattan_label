/* Read-only method and evidence: saved measurements, saved geometry, no scoring or fusion. */
window.ResearchEvidence = (() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
  const numeric = value => typeof value === 'number' && Number.isFinite(value);
  const fmt = (value, digits = 2) => numeric(value) ? value.toLocaleString('zh-CN', {
    maximumFractionDigits: digits, minimumFractionDigits: digits
  }) : value == null || value === '' ? '未保存' : String(value);
  const list = value => Array.isArray(value) ? value : value ? [value] : [];
  const sessions = new WeakMap();
  const payloads = new Map();
  const tabs = ['任务与门洞', '质量度量', '融合机制', '研究支持'];
  const statuses = {
    compatible: ['可表述', '本矩形示意中，拍摄点位严格在左室内部；靠近门洞不妨碍该目标的表示。'],
    ambiguous: ['范围多解', '封闭门洞或延伸到相邻空间，可能得到不同目标；先确定任务。'],
    incompatible: ['表示不兼容', '边界视点或多层顶界可能超出既定表示，需独立几何证据。'],
    unknown: ['待核验', '仅凭门框居中或同时看到两室，不能确认相机落在分界平面。']
  };
  const themes = [
    { id: 'quality', n: '01', title: '质量分数的含义与验证', status: '已有证据', level: 'supported',
      text: '冻结分项、控制案例与反例一起读，检查指标对哪些几何变化敏感。', tab: 1,
      limit: '工作指数及其验证边界；不当作正确概率。' },
    { id: 'consensus', n: '02', title: '完整布局共识的形成过程', status: '已有证据', level: 'supported',
      text: '沿真实保存路径，区分身份变化、支持门槛、位置聚合和连接。', tab: 2,
      limit: '精选状态不代表所有人数路径都已可视化。' },
    { id: 'doorway', n: '03', title: '任务范围与表示限制', status: '已有条件证据', level: 'supported',
      text: '把门洞范围歧义、视点退化与单层表示限制分别记录。', tab: 0,
      limit: '图示是几何示意；真实相机位置仍需核验。' },
    { id: 'people', n: '04', title: '人员标注方式与团队构成', status: '已有证据', level: 'supported',
      text: '从同图原答进入已有类别与真实团队，保留未知人员和反例。', module: 'personnel_main',
      limit: 'Manual／Semi分别研究；普通场景类别不自动跨条件成立。' },
    { id: 'uncertainty', n: '05', title: '不确定性的来源', status: '已有条件证据', level: 'supported',
      text: '分别看原答分歧、参考限制、换人敏感和结构跳变。', tab: 2,
      limit: '观察到共同变化，尚不能单独确认因果机制。' },
    { id: 'transfer', n: '06', title: '同房结构迁移的适用范围', status: '多数规律已验证', level: 'supported',
      text: '123直接图对中105对人员排序正相关；严格混合队61/78图对跨类幅度更大，具体收益仍有波动。', module: 'same_room',
      limit: '个人质量预测、团队曲线、局部结构是不同结果。' }
  ];
  const stages = [
    { key: 'annotations', title: '原始标注', question: '本次实际纳入了谁？',
      text: '先核对同图、同条件、同参考与真实成员。人员点号只对应自己的数组，不代表跨人角点身份。' },
    { key: 'identities', title: '角点身份', question: '哪些观察被归到同一结构？',
      text: '查看保存的身份组与成员分配。新增一人可能改变组的对应关系；不能默认前后节点一一相同。' },
    { key: 'support', title: '支持门槛', question: '哪些身份得到足够支持？',
      text: '身份支持与本次门槛决定结构是否保留。票数、支持人数和角点数不是同一个分母。' },
    { key: 'positions', title: '位置聚合', question: '保留下来的点移到了哪里？',
      text: '只读已有聚合位置。节点数不变时几何仍可移动；位置更稳定也不保证更接近参考。' },
    { key: 'connections', title: '连接与完整性', question: '节点是否组成完整结构？',
      text: '检查保存的连边候选、选择与失败原因。角点保留、连成环、接近参考应分别报告。' }
  ];
  const metricFields = [
    ['iou_2d', '底面 IoU', '0–1 · 参考范围重叠'],
    ['S_bottom_deg', '球面底边误差', '° · 底边位置'],
    ['dir', '方向残差', '° · 作答自身正交性'],
    ['Hmean', '整体高度误差', '冻结引擎定义 · 非米'],
    ['Hcenter', '局部高度误差', '冻结引擎定义 · 非米'],
    ['IoU3D100', '均高棱柱 IoU', '×100 · 三维代理量']
  ];
  function navigationPatch(patch) {
    const cleared = Object.fromEntries(['tab', 'table', 'where', 'object', 'case', 'image', 'condition', 'team', 'worker',
      'reference', 'snapshot', 'cmp_scheme', 'cmp_class', 'cmp_layer', 'cmp_pair', 'cmp_blind',
      'group', 'stage', 'view'].map(key => [key, null]));
    // An explicit comparison option also resets the comparison module's own cached selection.
    if (patch.module === 'patterns' || patch.module === 'multiview') cleared.cmp_blind = '0';
    return { module: patch.module, ...cleared, ...patch };
  }
  function routeLink(text, target, cls = 're-link') {
    const patch = navigationPatch(target);
    const query = Object.entries(patch).filter(([, value]) => value != null && value !== '')
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`).join('&');
    return `<a class="${esc(cls)}" href="#${esc(query)}" data-evidence-route="${esc(JSON.stringify(patch))}">${esc(text)}<span aria-hidden="true"> ↗</span></a>`;
  }
  function safeSource(source) {
    const path = typeof source === 'string' ? source : source?.path || source?.url || '';
    if (!path || /^(?:javascript|data|vbscript):/i.test(path) || path.startsWith('//')) return null;
    if (/^https?:\/\//i.test(path) || path.startsWith('#') || path.startsWith('../') || path.startsWith('./')) return path;
    return '../../../' + path.replace(/^\/+/, '');
  }
  function sourceLink(source, defaultLabel = '查看保存来源') {
    const url = safeSource(source);
    return url ? `<a href="${esc(url)}">${esc(typeof source === 'object' ? source.label || defaultLabel : defaultLabel)}</a>` : '';
  }
  function sourceFooter(item) {
    const sources = item?.sources ? list(item.sources) : [item?.source, item?.score_source].filter(Boolean);
    return sources.length ? `<div class="re-sources">${sources.map(s => sourceLink(s)).filter(Boolean).join(' · ')}</div>` : '';
  }
  function missing(title, text) {
    return `<div class="re-empty"><strong>${esc(title)}</strong><p>${esc(text)}</p></div>`;
  }
  function badge(text, level = 'neutral') {
    return `<span class="re-badge re-${esc(level)}">${esc(text)}</span>`;
  }
  function select(key, label, choices, selected) {
    return `<label class="re-select">${esc(label)}<select data-evidence-select="${esc(key)}">${choices.map(([value, title]) =>
      `<option value="${esc(value)}"${String(value) === String(selected) ? ' selected' : ''}>${esc(title)}</option>`).join('')}</select></label>`;
  }
  function overviewHTML(options = {}) {
    if (options.release && options.release !== 'v2') return '';
    return `<section class="re-overview" aria-labelledby="re-overview-title"><div class="re-heading"><div><p class="re-kicker">研究问题、保存证据与适用边界</p><h2 id="re-overview-title">六项研究问题</h2></div><p>以下为已完成研究的条件规律；任意新人、新房间的普遍推广仍需另验。</p></div>
      <div class="re-theme-grid">${themes.map(theme => `<article class="re-theme"><div class="re-theme-top"><span class="re-number">${theme.n}</span>${badge(theme.status, theme.level)}</div><h3>${esc(theme.title)}</h3><p>${esc(theme.text)}</p><small>${esc(theme.limit)}</small>${routeLink('查看证据', theme.module ? { module: theme.module } : { module: 'evidence', tab: theme.tab })}</article>`).join('')}</div></section>`;
  }
  function contextHTML(options, data) {
    const f = options.filters || {}, active = Object.entries(f).filter(([, value]) => value !== '' && value != null);
    const names = { image: '图片', worker: '人员', condition: '条件', building: '建筑', target: '参考', relation: '关系组',
      difficulty: '难度', doorway: '门洞', oos: 'OOS', scope: '范围', gt: '参考标记', analysis: '用途', search: '检索' };
    return `<div class="re-context"><span>${badge('只读保存结果')}</span><p>当前快照：${esc(data?.snapshot || data?.snapshot_id || options.snapshot || '未接入')}<br><small>${active.length ? '全局条件：' + active.map(([key, value]) => `${esc(names[key] || key)}=${esc(value)}`).join(' · ') : '全局条件：无附加筛选'}。本页为固定证据面板，案例不随全局筛选重新统计；以下各案例的条件单列，不裁剪保存团队。</small></p></div>`;
  }
  function heading(kicker, title, text) {
    return `<header class="re-heading re-hero"><div><p class="re-kicker">${esc(kicker)}</p><h2>${esc(title)}</h2><p>${esc(text)}</p></div></header>`;
  }
  function doorwayFrameFigure() {
    const path = '../../difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/oos_statistics_20261024/figures/DOORWAY_spatial_boundary';
    return `<a href="${path}.svg" target="_blank" rel="noopener"><img class="re-spatial-diagram" src="${path}.svg?v=3d-outline-20261025-r2" role="img" alt="相邻两室、门洞上方实体、拍摄点位和人为封闭面的三维构造示意；非实测"/></a><p class="re-muted"><a href="${path}.pdf" target="_blank" rel="noopener">PDF 矢量图</a> · <a href="${path}.svg" target="_blank" rel="noopener">SVG 矢量图</a> · <a href="${path}.png" target="_blank" rel="noopener">高清 PNG</a>；在新标签打开后可另存为。</p>`;
  }
  function doorwaySchematic(status = 'compatible') {
    const selected = statuses[status] ? status : 'unknown';
    const cx = selected === 'compatible' ? 140 : selected === 'ambiguous' ? 174 : 230;
    const camera = selected === 'unknown'
      ? `<ellipse cx="230" cy="171" rx="31" ry="19" fill="#fef3c7" stroke="#b45309" stroke-dasharray="5 4"/><text x="230" y="176" text-anchor="middle" fill="#92400e">位置待核验</text>`
      : `<circle cx="${cx}" cy="171" r="8" fill="#087f8c" stroke="white" stroke-width="3"/><text x="${cx}" y="199" text-anchor="middle">拍摄点位 c（水平投影）</text>`;
    return `<div class="re-schematic-grid"><figure class="re-schematic"><svg viewBox="0 0 460 300" role="img" aria-label="门洞俯视几何示意，非任何案例实测坐标">
      <rect x="34" y="40" width="392" height="218" rx="12" fill="#f4f7fb"/>
      <path d="M230 131V65H58V238H230V211" fill="#e0f2f1" stroke="#087f8c" stroke-width="4"/>
      <path d="M230 65H402V238H230V211M230 131V65" fill="#eef2ff" stroke="#64748b" stroke-width="4"/>
      <path d="M230 131V211" stroke="#b45309" stroke-width="3" stroke-dasharray="7 5"/>
      ${selected === 'ambiguous' ? '<rect x="58" y="65" width="344" height="173" fill="none" stroke="#7c3aed" stroke-width="3" stroke-dasharray="7 5"/><text x="230" y="52" text-anchor="middle">紫色虚线：两室联合候选</text>' : ''}
      <text x="137" y="98" text-anchor="middle">候选目标：左室</text><text x="316" y="98" text-anchor="middle">相邻空间</text>
      ${selected === 'unknown' ? '' : `<g aria-label="向右的示意射线；橙色截面右侧超出左室目标"><path d="M${cx + 12} 171H350" stroke="#b91c1c" stroke-width="2" stroke-dasharray="4 3"/>${cx < 230 ? `<path d="M${cx + 12} 171H230" stroke="#087f8c" stroke-width="3"/>` : ''}<path d="M350 171l-9 -5v10Z" fill="#b91c1c"/></g>`}
      ${camera}<text x="237" y="225" fill="#92400e">门洞封闭截面</text><text x="230" y="282" text-anchor="middle">BEV 示意 · 无测量比例</text>
      </svg><figcaption>实线是墙边；橙色虚线是人为选定的封闭截面，不是实体墙。${selected === 'compatible' ? '靠近门洞仍可能满足内部视点条件，不能仅因接近边界就判不可标。以左室为目标，绿色段在室内，红色虚线段已越过封闭截面。' : selected === 'ambiguous' ? '左室目标与紫色虚线所示的两室联合目标不同；绿色射线段在左室内，红段在左室外。选择联合目标时还需处理内部隔墙及遮挡，不能直接把外框当成最终布局。' : selected === 'incompatible' ? '假定相机拍摄点位恰在门口封闭边界上：朝右一看就已经在左室之外，无法在这个方向给左室画出正的内部距离。' : '位置待核验标记只是占位，不表示拍摄点位一定在门洞。全景中的视觉居中不能替代位姿或平面图证据。'}</figcaption></figure>
      <figure class="re-schematic">${doorwayFrameFigure()}<figcaption>蓝灰色为门洞实体；橙色半透明面是人为选定的封闭边界，不是实体墙。门洞上方构件底面低于房间顶界，不代表整间房有第二层天花板。三维图固定展示内部点位情形；左图按钮另示不同情况。</figcaption></figure></div>`;
  }
  function doorwayHTML(data, state) {
    const section = data?.doorway || {}, cases = list(section.cases), status = state.doorway || 'compatible';
    return heading('任务定义', '门洞附近房间的目标范围与几何判分', '判断时要分开三件事：标哪一间房、相机在哪、用哪种布局表示。左图切换拍摄点位与目标关系，右图用三维构造解释两室、门洞实体与封闭面，两图均非真实场景测量。不会给真实图片重新判类。') +
      `<section class="re-panel"><div class="re-heading"><h3>四种需要分开的研究状态</h3>${badge('示意，非实测', 'exploratory')}</div><div class="re-state-picker" role="group" aria-label="切换门洞概念示意">${Object.entries(statuses).map(([key, value]) =>
        `<button type="button" data-evidence-doorway="${key}" aria-pressed="${key === status}" class="${key === status ? 'active' : ''}">${esc(value[0])}</button>`).join('')}</div>
      <p class="re-state-description" role="status">${esc(statuses[status]?.[1] || statuses.unknown[1])}</p>${doorwaySchematic(status)}
      <div class="re-note"><strong>门洞交界为什么要单列？</strong>先确定目标房间，再判断拍摄点位与目标边界的关系。若将门洞封闭，封闭截面属于目标定义，并非新增实体墙；若延伸到相邻房间，则是另一目标。拍摄点位严格位于内部，意味着从这里向任意方向先走一小段仍在目标房间内；若射线离开目标后又重新进入，或门楣后方还有不同顶界，一对上下边界点未必能完整表示。因此应检查目标、拍摄点位和表示，而不是把门洞都判为不可标。<br><strong>与 OOS 的区别：</strong>门洞交界关注目标范围、拍摄点位和可见结构的关系；OOS 关注真实目标构造超出标注标准。门洞案例可以不是 OOS，也可以同时存在斜墙或多层顶／底面等 OOS 因素。</div></section>
      <div class="re-grid re-two"><section class="re-panel"><h3>真实案例的核查顺序</h3><ol class="re-checklist"><li><strong>目标与封闭规则</strong><span>标哪一室？门洞按哪个截面闭合？</span></li><li><strong>拍摄点位的位置证据</strong><span>位姿、平面图或三维几何能否证明严格在内部？</span></li><li><strong>表示是否足够</strong><span>若目标包含门楣及其后方顶界，现有上下边界表示能否同时表达？是否出现同一方向多段结构？</span></li><li><strong>独立记录判断</strong><span>理由与证据位置单列；不自动修改 OOS、参考或质量资格。</span></li></ol></section>
      <section class="re-panel"><h3>研究解释的边界</h3><ul class="re-bullets"><li>门框居中不证明相机位于门平面；墙厚还可能形成连接体积。</li><li>看到门楣不自动证明投影冲突，需要逐例检查。</li><li>几何机制不限定于某一数据集；采集位置频率需另行统计。</li><li>已有开口范围歧义研究；不能仅凭这个现象宣称首创。</li></ul>${sourceFooter(section)}</section></div>
      ${window.ResearchComparison?.failureOverviewHTML(data.failure_summary)||''}${doorwayCasesHTML(section, state)}`;
  }
  function doorwayCasesHTML(section, state) {
    const cases = list(section.cases), selected = cases.find(c => c.image_id === state.doorwayCase) || cases[0];
    if (selected) state.doorwayCase = selected.image_id;
    return `<section class="re-panel"><div class="re-heading"><div><h3>已有门洞观察</h3>${badge(`${cases.length} 条接入记录`)}<p class="re-muted">包含非OOS ${esc(section.non_oos_images ?? '未注明')} 图；既有OOS状态独立保留。</p></div>${cases.length ? select('doorwayCase', '选择真实图片', cases.map(c => [c.image_id, c.title || c.image_code]), state.doorwayCase) : ''}</div><p class="re-muted">没有位姿证据时显示“待核验”，不由图级门洞／OOS标签推断。</p>${selected ? doorwayCaseHTML(selected) : missing('尚无真实案例裁定', '概念示意已可阅读；当前载荷未接入带位置证据的案例，不补示例标签。')}</section>`;
  }
  function doorwayCaseHTML(c) {
    const evidence = c.evidence || {};
    return `<article class="re-case"><div class="re-heading"><h4>${esc(c.title || c.image_code || c.image_id)}</h4>${badge(statuses[c.observation_status]?.[0] || '待核验', c.observation_status === 'compatible' ? 'supported' : 'exploratory')}</div><p>${esc(c.reason || c.summary || '当前保存资料未建立相机与门洞封闭截面的精确位置关系。')}</p>
      ${typeof evidence === 'string' ? `<p>${esc(evidence)}</p>` : `<ul class="re-bullets">${list(evidence.existing_notes).map(note => `<li>${esc(note)}</li>`).join('')}</ul><p class="re-muted">原门洞标签：${esc(evidence.doorway_status || '未记录')} · 原目标几何状态：${esc(evidence.existing_target_geometry || '未记录')} · ${c.is_oos === true ? '原标签为OOS' : '原标签非OOS'}。原记录不替代严格位置核验。</p>`}
      ${c.counts ? `<p class="re-muted">${esc(c.condition || '')} · ${esc(c.counts.records)} 份记录 · ${esc(c.counts.workers)} 人 · ${esc(c.counts.quality_records)} 份主质量记录</p>` : ''}
      ${c.image_id ? routeLink('查看该图与原答', c.is_oos ? { module: 'images', image: c.image_id } : { module: 'patterns', image: c.image_id, condition: c.condition || 'manual', cmp_layer: 'doorway' }) : ''}${sourceFooter(c)}</article>`;
  }
  function caseId(item, index) { return String(item?.id || item?.case_id || index); }
  function recordsFor(item) { return list(item?.answers || item?.records || item?.variants || item?.measurements); }
  function measurements(record) { return { ...(record?.quality || {}), ...(record?.components || {}), ...record }; }
  function qualityTable(records) {
    const fields = [['B8L2', 'B8L2'], ['D10', 'D10'], ...metricFields.map(([key, label]) => [key, label]), ['nodes', '节点数'], ['ref_node_recall_9', '参考节点覆盖（9°）'], ['ref_edge_recall_9', '参考边覆盖（9°）'], ['saved_direction_zero_B8L2', '固定其他项 d=0 诊断']];
    const available = fields.filter(([key]) => records.some(record => measurements(record)[key] != null));
    if (!available.length) return missing('没有已保存分项', '该案例只保留说明，未补算分数或用零值代替缺失。');
    return `<div class="re-table-scroll"><table class="re-table"><caption>冻结测量对照；分项不可解读为相加的扣分比例</caption><thead><tr><th scope="col">保存对象</th>${available.map(([, label]) => `<th scope="col">${esc(label)}</th>`).join('')}</tr></thead><tbody>${records.map((record, i) => `<tr><th scope="row">${esc(record.label || record.title || record.worker_id || record.object_id || `对象 ${i + 1}`)}</th>${available.map(([key]) => `<td>${esc(fmt(measurements(record)[key], key === 'iou_2d' ? 4 : 2))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  function qualityHTML(data, state) {
    const cases = list(data?.quality?.cases);
    const selected = cases.find((item, i) => caseId(item, i) === state.qualityCase) || cases[0];
    if (selected) state.qualityCase = caseId(selected, cases.indexOf(selected));
    const records = recordsFor(selected);
    return heading('测量范围', '质量指标与已知反例', 'B8L2 同时反映与参考的接近程度和作答自身的几何一致性。D10 只改变方向尺度；分数变化不代表几何变好。') +
      (window.MethodDiagrams?.quality() || '') +
      `<div class="re-grid re-two"><section class="re-panel re-accent"><h3>B8L2：冻结的联合工作指数</h3><p>底面范围与球面底边进入一块损失，自身方向残差进入另一块；两块以 L2 组合，整体及局部高度损失另外相加。</p><div class="re-factor-line"><span>范围／底边</span><span>方向</span><span>整体高度</span><span>局部高度</span></div><p class="re-muted">不绘制“各项贡献百分比”：非线性组合不能当作可加总的扣分。</p></section>
      <section class="re-panel"><h3>均高棱柱代理 ≠ 一般三维体积</h3><p>当前 IoU3D100 使用角点均值高度形成棱柱，再计算其重叠。它不保留所有局部顶界形状，也不是任意连续三维实体的精确 IoU。</p><p class="re-muted">均高相同仍可能有局部高低差；底面 IoU 高也不能单独证明细小必要结构正确。</p></section></div>
      <section class="re-panel"><div class="re-heading"><div><h3>保存案例对照</h3><p class="re-muted">案例、控制与来源保持原身份。每个数值只对应其绑定输入和参考。</p></div>${cases.length ? select('qualityCase', '选择案例', cases.map((c, i) => [caseId(c, i), `${c.id || c.case_id} · ${c.title || ''}`]), state.qualityCase) : ''}</div>
      ${selected ? `<div class="re-case-summary">${badge(selected.kind === 'synthetic' || selected.synthetic === true ? '保存控制实验 · 非真实作答' : selected.evidence_type || '保存证据')}<h4>${esc(selected.title || selected.id)}</h4><p>${esc(selected.summary || selected.description || '')}</p><p class="re-muted">${esc([selected.image_code || selected.image_id, selected.condition, selected.reference_id ? '参考：' + selected.reference_id : '', selected.snapshot_id ? '来源快照：' + selected.snapshot_id : ''].filter(Boolean).join(' · '))}</p></div>${qualityTable(records)}${records.some(r => numeric(r.saved_direction_zero_B8L2)) ? '<p class="re-note">d=0列是来源保存的诊断控制：固定其余测量，仅置方向残差为零。它不是修复后的真实几何，也不表示独立因果贡献。</p>' : ''}<div class="re-geometry-grid" data-evidence-quality-geometries></div>${list(selected.limitations).length ? `<ul class="re-bullets re-note">${list(selected.limitations).map(text => `<li>${esc(text)}</li>`).join('')}</ul>` : ''}${sourceFooter(selected)}${selected.image_id ? `<div class="re-actions">${routeLink('继续看同图原答', { module: 'patterns', image: selected.image_id, condition: selected.condition || 'manual', reference: selected.reference_id || '', snapshot: selected.snapshot_id || '' })}</div>` : ''}` : missing('质量案例载荷尚未接入', 'S1／S2／S3等案例必须来自保存测量；没有数据时保留方法说明，不生成曲线、几何或分数。')}</section>
      ${sensitivityHTML(data?.quality?.saved_sensitivity_controls)}<div class="re-grid re-three">${metricFields.map(([, label, meaning]) => `<section class="re-mini"><h3>${esc(label)}</h3><p>${esc(meaning)}</p></section>`).join('')}</div>
      <section class="re-panel"><h3>比较前，先核对四项绑定</h3><div class="re-factor-line"><span>同一图片</span><span>同一采集条件</span><span>同一评分参考</span><span>同一评分版本</span></div><p>诊断分单独保留；参考存在问题时，得分不承担视觉正确性结论。需要看局部结构时回到原图、BEV与3D证据。</p><div class="re-actions">${routeLink('查看逐作答质量与分项', { module: 'quality' })}${routeLink('查看参考与用途', { module: 'images' })}</div>${sourceFooter(data?.quality)}</section>`;
  }
  function sensitivityHTML(controls) {
    if (!list(controls).length) return '';
    return `<section class="re-panel"><details><summary>保存的底边像素敏感性控制 · ${controls.length} 例</summary><p class="re-muted">以下是来源已计算的 ±2 像素控制。不是新作答，不生成新几何，也不将联动分项解释为独立贡献。</p><div class="re-grid re-two">${controls.map(c => `<article class="re-case"><h4>${esc(c.image)} · 点对 ${esc(c.pair_index)}</h4><p class="re-muted">${esc(c.object_id)} · 原 bottom-y ${esc(fmt(c.original_bottom_y_px))} px</p>${qualityTable(list(c.trials).map(row => ({ ...row, label: `底边 Δy=${row.dy_px} px`, iou_2d: row.floor_IoU, dir: row.direction_deg })))}</article>`).join('')}</div></details></section>`;
  }
  function fusionSelection(item, state) {
    const nodes = list(item?.nodes || item?.states).filter(n => n && typeof n === 'object' && n.k != null).slice().sort((a, b) => a.k - b.k);
    if (!nodes.length) return { nodes, current: item?.after, previous: item?.before };
    let current = nodes.find(n => String(n.k) === String(state.fusionK));
    if (!current) current = nodes.find(n => item?.after?.team_key && n.team_key === item.after.team_key) || nodes.find(n => n.k === item?.after?.k) || nodes[nodes.length - 1];
    state.fusionK = String(current.k);
    return { nodes, current, previous: nodes[nodes.indexOf(current) - 1] || null };
  }
  function stageRows(item, stage, node) {
    if (node) {
      if (stage === 'annotations') return list(node.assignments).map(row => ({ worker_id: row.worker, object_id: row.id,
        feature_ids: row.feature_ids, source_order_status: row.source_order_status, source_ring_confirmed: row.source_ring_confirmed }));
      if (stage === 'identities') return list(node.identity_groups).map(row => ({ feature_id: row.feature_id, support: row.support,
        selected: row.selected, source_observations: list(row.members).map(m => `${m.worker} / ${m.id} / 点对${m.source_pair_index ?? m.pair_index}`) }));
      if (stage === 'support') return list(node.identity_groups).map(row => ({ feature_id: row.feature_id, support: row.support,
        threshold: node.minimum_support, selected: row.selected, top_support: row.top_support, bottom_support: row.bottom_support, joint_support: row.joint_support }));
      if (stage === 'positions') return list(node.node_consensus?.nodes).map(row => ({ feature_id: row.feature_id,
        support: row.support, points: row.points, source_observations: list(row.members).map(m => `${m.worker} / ${m.id} / 点对${m.pair_index}`) }));
      if (stage === 'connections') return list(node.ring_diagnostics?.edges);
    }
    const savedStage = list(item?.stages).find(s => s.key === stage);
    if (savedStage?.rows) return savedStage.rows;
    if (Array.isArray(savedStage?.data)) return savedStage.data;
    const fields = {
      annotations: ['members', 'annotations', 'assignments'],
      identities: ['identity_groups', 'identities', 'nodes'],
      support: ['support_rows', 'nodes', 'identity_groups'],
      positions: ['positions', 'nodes'],
      connections: ['edges', 'edge_candidates', 'connections']
    };
    for (const key of fields[stage] || []) if (Array.isArray(item?.[key])) return item[key];
    return [];
  }
  function shortValue(value) {
    if (value == null || value === '') return '未保存';
    if (typeof value === 'boolean') return value ? '是' : '否';
    if (Array.isArray(value) && value.every(v => typeof v !== 'object')) return value.join('；');
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }
  function ledgerHTML(rows, title) {
    if (!rows.length) return missing('逐项来源未接入', '此保存案例没有可显示的该阶段台账；不由最终线框反推中间身份、票数或连边。');
    const objects = rows.map(row => typeof row === 'object' && row !== null ? row : { value: row });
    const priority = ['stage', 'k', 'worker_id', 'object_id', 'node_id', 'identity_id', 'group_id', 'support', 'support_count',
      'threshold', 'retained', 'source_node', 'target_node', 'selected', 'reason', 'source'];
    const keys = [...new Set(objects.flatMap(Object.keys))];
    const columns = [...priority.filter(key => keys.includes(key)), ...keys.filter(key => !priority.includes(key))].slice(0, 12);
    const labels = { worker_id: '人员', object_id: '作答 ID', feature_id: '身份 ID', feature_ids: '身份序列／端点', support: '支持人数',
      threshold: '本节点门槛', selected: '已选中', top_support: '顶点支持', bottom_support: '底点支持', joint_support: '联合支持',
      source_observations: '来源人员／作答／点对', source_order_status: '原环序状态', source_ring_confirmed: '原环序人工确认',
      direct_support: '直接边支持', direct_workers: '直接来源人员', projected_support: '投影边支持', projected_workers: '投影来源人员',
      points: '保存 ERP 坐标', group: '新身份组', total_support: '全部支持', old13_observations: '原13票分配' };
    return `<div class="re-table-scroll"><table class="re-table re-ledger"><caption>${esc(title)} · 保存 ${rows.length} 行${rows.length > 100 ? '，此处展示前100行；完整内容见来源' : ''}</caption><thead><tr>${columns.map(key => `<th scope="col">${esc(labels[key] || key)}</th>`).join('')}</tr></thead><tbody>${objects.slice(0, 100).map(row => `<tr>${columns.map(key => `<td>${esc(shortValue(row[key]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  function fusionHTML(data, state) {
    const cases = list(data?.fusion?.cases), selected = cases.find((c, i) => caseId(c, i) === state.fusionCase) || cases[0];
    if (selected) state.fusionCase = caseId(selected, cases.indexOf(selected));
    const stage = stages.find(item => item.key === state.stage) || stages[0]; state.stage = stage.key;
    const selection = fusionSelection(selected, state);
    const savedStage = list(selected?.stages).find(item => item.key === stage.key);
    return heading('融合过程', '融合过程里的成员、身份、位置与连接', '沿实际保存团队，分别查看成员、身份、支持和位置、连接的变化。切换步骤只展开已有证据，不在浏览器里重新融合。') +
      (window.ResearchComparison?.failureOverviewHTML(data.failure_summary)||'') + (window.MethodDiagrams?.fusion() || '') +
      `<section class="re-panel"><div class="re-heading"><h3>选择保存事件</h3>${cases.length ? select('fusionCase', '保存案例', cases.map((c, i) => [caseId(c, i), c.title || c.id || c.case_id]), state.fusionCase) : ''}${selection.nodes.length ? select('fusionK', '当前保存人数节点', selection.nodes.map(node => [String(node.k), `k=${node.k} · B8L2 ${fmt(node.B8L2)}`]), state.fusionK) : ''}</div>${selected ? `<div class="re-case-summary"><h4>${esc(selected.title || selected.id)}</h4><p>${esc(selected.summary || selected.description || '')}</p><p class="re-muted">${esc([selected.image_code || selected.image_id, selected.condition, selected.group_id, selected.reference_id ? '参考：' + selected.reference_id : ''].filter(Boolean).join(' · '))}</p></div>${fusionNodeSummary(selection)}${identityControlHTML(selected, selection.current)}` : missing('保存事件尚未接入', 'q9／G046／G057 等案例只能使用已有路径与几何。当前未读到载荷，不补演示团队。')}
      <div class="re-steps" role="tablist" aria-label="融合证据步骤">${stages.map((item, i) => `<button type="button" id="re-step-${item.key}" role="tab" aria-controls="re-stage-panel" aria-selected="${item.key === stage.key}" tabindex="${item.key === stage.key ? '0' : '-1'}" data-evidence-stage="${item.key}"><span>${i + 1}</span><strong>${esc(item.title)}</strong></button>`).join('')}</div>
      <div class="re-stage" id="re-stage-panel" role="tabpanel" aria-labelledby="re-step-${stage.key}"><p class="re-kicker">${esc(stage.title)}</p><h3>${esc(stage.question)}</h3><p>${esc(savedStage?.description || stage.text)}</p>${selected ? ledgerHTML(stageRows(selected, stage.key, selection.current), `${stage.title}来源台账${selection.current ? ' · k=' + selection.current.k : ''}`) : ''}</div>
      ${selected ? `<div class="re-geometry-grid" data-evidence-fusion-geometries></div>${list(selected.limitations).length ? `<ul class="re-bullets re-note">${list(selected.limitations).map(text => `<li>${esc(text)}</li>`).join('')}</ul>` : ''}${sourceFooter(selected)}<div class="re-actions">${selected.image_id ? routeLink('查看原答与保存团队', { module: 'patterns', image: selected.image_id, case: selected.comparison_case_id || '', condition: selected.condition || 'manual', reference: selected.reference_id || '' }) : ''}${selected.group_id || selected.multiview_group ? routeLink('查看同房多视角', { module: 'multiview', group: selected.multiview_group || selected.group_id }) : ''}</div>` : ''}</section>
      <div class="re-grid re-three"><section class="re-mini"><h3>R · 原答分歧</h3><p>成员之间的原答差异，不是融合误差。</p></section><section class="re-mini"><h3>V · 同人数换组差异</h3><p>保持人数再换成员，检查结果敏感性。</p></section><section class="re-mini"><h3>Q · 相对绑定参考</h3><p>稳定、完整、接近参考要分别验证。</p></section></div>
      <section class="re-panel"><h3>当前链条能支持什么</h3><p>保存事件可帮助定位结构改变发生在哪一环。若没有冻结身份、固定成员或局部控制，不能把伴随变化直接说成某个因素的独立因果效应。</p><div class="re-actions">${routeLink('查看已有融合统计与人数路径', { module: 'fusion' })}${routeLink('查看类别与成员构成', { module: 'patterns' })}</div>${sourceFooter(data?.fusion)}</section>`;
  }
  function fusionNodeSummary({ nodes, current, previous }) {
    if (!current) return '';
    const count = record => record?.node_consensus?.nodes?.length ?? (Array.isArray(record?.points) ? record.points.length / 2 : null);
    return `<div class="re-grid re-three re-node-summary"><div class="re-mini"><h3>保存人数</h3><strong>${previous ? esc(previous.k) + ' → ' : ''}${esc(current.k)}</strong><p>${nodes.length} 个已接入节点；前态为上一保存节点。</p></div><div class="re-mini"><h3>输出节点数</h3><strong>${previous ? esc(fmt(count(previous), 0)) + ' → ' : ''}${esc(fmt(count(current), 0))}</strong><p>支持门槛 ${previous ? esc(fmt(previous.minimum_support, 0)) + ' → ' : ''}${esc(fmt(current.minimum_support, 0))} 人</p></div><div class="re-mini"><h3>B8L2 保存测量</h3><strong>${previous ? esc(fmt(previous.B8L2)) + ' → ' : ''}${esc(fmt(current.B8L2))}</strong><p>${esc(current.score_status || '用途未注明')} · 环序${current.ring_confirmed === true ? '已确认' : '未人工确认'}</p></div></div><details><summary>当前真实成员与保存身份</summary><p>${esc(list(current.workers).join('、'))}</p><p class="re-muted">${esc(current.team_key)}<br>${esc(current.geometry_reason || current.order_status || '')}</p></details>`;
  }
  function identityControlHTML(item, current) {
    const control = item?.saved_identity_control;
    if (!control || current?.k !== control.new_n) return '';
    return `<div class="re-note"><strong>这个保存事件不只是门槛升高。</strong>原身份的 ${esc(control.old_support)} 票在新分组中被拆开；新门槛为 ${esc(control.new_threshold)}。来源还保存了冻结旧组、位置与环序的诊断控制，B8L2为 ${esc(fmt(control.control_B8L2))}，自动结果为 ${esc(fmt(control.automatic_B8L2))}。诊断控制没有给新增观察重新分配身份，不是替代融合算法，也不证明相近观察必属同一真实墙角。${ledgerHTML(list(control.old13_allocation), '原支持在新组中的保存分配')}</div>`;
  }
  function supportHTML(data, state) {
    const support = data?.support || {};
    return heading('支持范围', '共同支持与各项结论的分母', '记录数、人员数、图片数、关系数和保存状态数分别报告。不同条件、用途和参考的结果不合并成一个总均分。') +
      `<div class="re-grid re-three"><section class="re-panel"><span class="re-number">01</span><h3>图片 × 人员 × 条件</h3><p>Manual 与 Semi 分别建立研究画像。条件间叠图是附加观察，不能代替另一条件的类型验证。</p>${routeLink('人员画像', { module: 'workers' })}${routeLink('同图类别与原答', { module: 'patterns' })}</section><section class="re-panel"><span class="re-number">02</span><h3>成员 × 人数 × 路径</h3><p>同人数换人、沿路径增人、最终全员结果是不同比较。只显示保存节点，缺失阶段不连成完整链。</p>${routeLink('保存融合路径', { module: 'fusion' })}</section><section class="re-panel"><span class="re-number">03</span><h3>关系 × 视角 × 建筑</h3><p>同房图对会共享图片与人员。未知关系不是确认异房；局部结构迁移也不等同个人质量预测。</p>${routeLink('同房统计与预测', { module: 'same_room' })}${routeLink('同人／同团队多视角', { module: 'multiview' })}</section></div>
      ${supportCountsHTML(support)}${supportMatrixHTML(support, state, data?.snapshot_id)}
      <section class="re-panel"><h3>已经回答的问题与结果边界</h3><div class="re-grid re-two"><div><h4>已完成的研究</h4><ul class="re-bullets"><li>质量分项、3D IoU与人工判断的对照：不同指标保留的信息不同。</li><li>类别配比、类内换人和跨类替换：构成差异与具体成员波动同时存在。</li><li>低人数至满员过程：质量、P10、几何波动和失败并非同步变化。</li><li>同房跨视角：平均表现及部分配比趋势可重复，具体调整收益未必重复。</li></ul></div><div><h4>阅读时分别判断</h4><ul class="re-bullets"><li>分类有解释价值，不要求每位成员普遍可互换。</li><li>结构变化可以升质或降质，不以升质作为唯一有效结果。</li><li>多数与条件规律保留，同时展示反例及实际支持范围。</li><li>结果对应当前人员池、参考和融合算法；各实验的实际支持范围分别查看。</li></ul></div></div><div class="re-actions">${routeLink('质量与方法验证', { module: 'method_supplements', tab: 2 })}${routeLink('人员完整研究', { module: 'personnel_main' })}${routeLink('查看数据覆盖与缺失', { module: 'coverage' })}${routeLink('查看全部来源', { module: 'sources' })}</div></section>${overviewHTML()}`;
  }
  function supportCountsHTML(support) {
    const names = { records: '全部作答', images: '独立图片', workers: '全部人员', buildings: '建筑', reference_bindings: '参考绑定', quality_records: '主质量记录', independent_vote_records: '独立投票记录' };
    const totals = support.totals || {};
    const fields = ['records', 'images', 'workers', 'buildings', 'quality_records'];
    const counts = fields.filter(key => numeric(totals[key]));
    if (!counts.length) return missing('分母摘要尚未接入', '请从数据覆盖与各专题源表查看当前支持范围；不以存储总行数代替独立样本数。');
    const conditions = list(support.by_condition), cohorts = list(support.constant_support_cohorts);
    return `<section class="re-panel"><h3>冻结数据的几类分母</h3><dl class="re-facts">${counts.map(key => `<div><dt>${names[key]}</dt><dd>${esc(fmt(totals[key], 0))}</dd></div>`).join('')}</dl><p class="re-muted">全部人员 ${esc(fmt(totals.workers, 0))} 人；清洗保留 ${esc(fmt(support.retained?.workers, 0))} 人。条件表中的图片和人员有重叠，不能相加成独立总数。</p>
      ${conditions.length ? `<div class="re-table-scroll"><table class="re-table"><caption>按原始条件分别报告；此表不合并拟合 Manual 与 Semi</caption><thead><tr><th scope="col">条件</th>${fields.map(key => `<th scope="col">${names[key]}</th>`).join('')}</tr></thead><tbody>${conditions.map(row => `<tr><th scope="row">${esc(row.condition)}</th>${fields.map(key => `<td>${esc(fmt(row[key], 0))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : ''}
      ${cohorts.length ? `<details><summary>固定最低人数要求，对应多少图可进入共同支持范围？</summary><p class="re-muted">每图同条件、同参考下独立支持人数的准入描述。各图并非同一批人员，也不是已跑完的固定人数曲线。</p><div class="re-table-scroll"><table class="re-table"><caption>冻结共同支持面板；Manual／Semi分列</caption><thead><tr><th scope="col">条件</th><th scope="col">最低人数</th><th scope="col">图片</th><th scope="col">建筑</th><th scope="col">图×参考绑定</th></tr></thead><tbody>${cohorts.map(row => `<tr><th scope="row">${esc(row.condition)}</th><td>${esc(row.minimum_people)}</td><td>${esc(row.images)}</td><td>${esc(row.buildings)}</td><td>${esc(row.image_reference_bindings)}</td></tr>`).join('')}</tbody></table></div></details>` : ''}${sourceFooter(support)}</section>`;
  }
  function supportMatrixHTML(support, state, snapshot) {
    const matrix = list(support.matrix);
    if (!matrix.length) return '';
    state.supportCondition ||= 'manual'; state.supportMinimum ||= '0';
    const conditions = [...new Set(matrix.map(row => row.condition))].sort();
    const rows = matrix.filter(row => (state.supportCondition === 'all' || row.condition === state.supportCondition) &&
      row.independent_vote_workers >= Number(state.supportMinimum));
    return `<section class="re-panel"><div class="re-heading"><div><h3>图片 × 条件 × 参考支持矩阵</h3><p class="re-muted">以下筛选只展示冻结记录，不重跑评分或融合。满足条件 ${rows.length} 个绑定。</p></div>${select('supportCondition', '矩阵条件', [['all', '全部条件'], ...conditions.map(c => [c, c])], state.supportCondition)}${select('supportMinimum', '最低独立投票人数', [0, 2, 4, 8, 12, 16, 20, 24, 30, 35].map(n => [String(n), n ? `${n} 人` : '不限制']), state.supportMinimum)}</div>
      ${rows.length ? `<div class="re-table-scroll"><table class="re-table re-support-matrix"><caption>每行一个图×条件×绑定参考；显示前 ${Math.min(rows.length, 60)} 行，完整矩阵保留在载荷来源</caption><thead><tr><th scope="col">图片</th><th scope="col">条件</th><th scope="col">参考版本</th><th scope="col">人员</th><th scope="col">独立投票</th><th scope="col">主质量记录</th><th scope="col">场景／限制</th></tr></thead><tbody>${rows.slice(0, 60).map(row => `<tr><th scope="row">${routeLink(row.image_code, row.is_oos ? { module: 'images', image: row.image_id, f_condition: row.condition, f_target: row.reference_id } : { module: 'patterns', image: row.image_id, condition: row.condition, reference: row.reference_id, snapshot })}</th><td>${esc(row.condition)}</td><td title="${esc(row.reference_id)}">${esc(row.reference_version || row.reference_id)}</td><td>${esc(row.worker_count)}</td><td>${esc(row.independent_vote_workers)}</td><td>${esc(row.quality_records)}</td><td>${esc([row.is_oos ? 'OOS' : '', row.is_doorway ? '门洞' : '', ...list(row.missing_reasons)].filter(Boolean).join('；') || '无上述标记')}</td></tr>`).join('')}</tbody></table></div>` : missing('当前矩阵筛选无支持', '请降低最低人数或切换条件；缺失不补零。')}
      <ul class="re-bullets re-note">${list(support.limitations).map(text => `<li>${esc(text)}</li>`).join('')}</ul>${sourceFooter(support)}</section>`;
  }
  function geometryBinding(image, record, item) {
    const expectedReference = record?.reference_id || record?.rescore_target_id || item?.reference_id || item?.reference?.target_id;
    const reference = record?.reference || item?.reference ||
      image?.references?.find(ref => [ref.reference_id, ref.target_id, ref.id].includes(expectedReference));
    if (image?.image_id && item?.image_id && image.image_id !== item.image_id) return { reason: '图片绑定不一致，已隔离该案例几何。' };
    for (const field of ['image_id', 'condition', 'reference_id', 'snapshot_id']) {
      if (record?.[field] && item?.[field] && record[field] !== item[field]) return { reason: `${field} 绑定不一致，已隔离该案例几何。` };
    }
    if (reference && expectedReference && ![reference.target_id, reference.reference_id, reference.id].includes(expectedReference)) {
      return { reason: '保存参考与测量绑定不一致，已隔离该案例几何。' };
    }
    const stored = record?.geometry || record;
    if (stored?.points || stored?.footprint || stored?.floor) {
      if (!reference) return { reason: '没有找到案例绑定参考，不使用当前参考替代。' };
      return { answer: stored, reference, explicit: true };
    }
    const annotation = image?.annotations?.find(a => a.object_id === record?.object_id &&
      (!item?.condition || a.condition === item.condition));
    if (!annotation) return { reason: '没有与此保存测量逐项绑定的几何。' };
    const actualReference = annotation.quality?.rescore_target_id || annotation.quality?.reference_id ||
      annotation.rescore_target_id || annotation.reference_id;
    if (expectedReference && actualReference !== expectedReference) return { reason: '当前作答几何与该案例评分参考未确认一致，暂不叠画。' };
    if (!reference) return { reason: '没有找到案例绑定的参考几何，暂不使用当前参考替代。' };
    if (annotation.geometry_compatible === false) return { reason: '坐标绑定核查未通过，保留测量记录并隔离几何。' };
    return { answer: annotation, reference };
  }
  async function mountGeometries(host, data, state, options, alive) {
    const isFusion = Number(options.tab || 0) === 2;
    const section = isFusion ? data?.fusion : data?.quality;
    const key = isFusion ? state.fusionCase : state.qualityCase;
    const selected = list(section?.cases).find((c, i) => caseId(c, i) === key);
    const target = host.querySelector(isFusion ? '[data-evidence-fusion-geometries]' : '[data-evidence-quality-geometries]');
    if (!selected || !target) return;
    const selectedNodes = fusionSelection(selected, state);
    let records = isFusion ? [selectedNodes.previous, selectedNodes.current].filter(Boolean) : recordsFor(selected);
    records = records.filter(r => r && (r.points || r.geometry || r.footprint || r.floor || r.object_id)).slice(0, 4);
    if (!records.length) {
      target.innerHTML = missing('该案例没有可绑定的保存几何', '上方数值与台账仍保留；不由摘要或分数合成形状。'); return;
    }
    if (!window.WorkbenchGeometry?.mount) {
      target.innerHTML = missing('几何组件未加载', '保存测量可查；请从已有图片或融合专题查看几何。'); return;
    }
    let image = null;
    if (selected.image_id && options.loadImage) {
      try { image = await options.loadImage(selected.image_id); } catch (_) { /* Saved explicit geometry can remain useful. */ }
      if (!alive()) return;
    }
    target.innerHTML = records.map((record, index) => `<section class="re-geometry-card"><h4>${esc(record.label || record.title || record.worker_id || (isFusion ? ['保存前态', '保存后态'][index] : '') || record.object_id || `保存对象 ${index + 1}`)}</h4><p class="re-muted">${esc([record.k != null ? '人数 k=' + record.k : '', record.node_count != null || record.nodes != null ? '节点=' + (record.node_count ?? record.nodes) : '', record.B8L2 != null ? 'B8L2 ' + fmt(record.B8L2) : '', record.D10 != null ? 'D10 ' + fmt(record.D10) : ''].filter(Boolean).join(' · '))}</p><div data-evidence-geometry="${index}"></div></section>`).join('');
    records.forEach((record, index) => {
      const box = target.querySelector(`[data-evidence-geometry="${index}"]`), bound = geometryBinding(image, record, selected);
      if (bound.reason) { box.innerHTML = missing('几何留缺', bound.reason); return; }
      const geometry = bound.answer, reference = bound.reference || {};
      if (record.order_status || record.ring_confirmed === false) box.insertAdjacentHTML('beforebegin', `<p class="re-muted re-geometry-status">保存环序：${esc(record.order_status || '未注明')} · ${record.ring_confirmed === true ? '来源已确认' : '未人工确认'}。连线仅重放来源候选，不代表本轮几何裁定。</p>`);
      if (isFusion || record.team_key || list(record.workers).length > 1) window.WorkbenchGeometry.mount(box, image, null, reference, {
        ...geometry, footprint: geometry.footprint || geometry.floor, connected: geometry.connected === true || record.connected === true
      });
      else if (geometry.points) window.WorkbenchGeometry.mount(box, image, geometry, reference);
      else window.WorkbenchGeometry.mount(box, image, null, reference, null, { layers: [{
        id: 'saved-evidence', label: esc(record.label || '保存几何'), points: geometry.points,
        floor: geometry.footprint || geometry.floor, confirmed: geometry.connected === true, color: '#087f8c'
      }] });
    });
  }
  async function loadPayload(options) {
    if (options.data) return options.data;
    if (!options.read) return null;
    const path = (options.resourcesBase || 'v2-resources/').replace(/\/?$/, '/') + 'research_evidence.json';
    const key = [options.release, options.snapshot, path].join('|');
    if (!payloads.has(key)) payloads.set(key, Promise.resolve().then(() => options.read(path)).catch(error => {
      payloads.delete(key); throw error;
    }));
    return payloads.get(key);
  }
  function bindEvents(host, state, options, redraw) {
    host.onclick = event => {
      const link = event.target.closest('[data-evidence-route]');
      if (link && options.navigate && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey && event.button === 0) {
        event.preventDefault(); options.navigate(JSON.parse(link.dataset.evidenceRoute)); return;
      }
      const doorway = event.target.closest('[data-evidence-doorway]');
      if (doorway) { state.doorway = doorway.dataset.evidenceDoorway; redraw('doorway', state.doorway); }
      const stage = event.target.closest('[data-evidence-stage]');
      if (stage) { state.stage = stage.dataset.evidenceStage; redraw('stage', state.stage); }
    };
    host.onchange = event => {
      const key = event.target.dataset.evidenceSelect;
      if (key) { state[key] = event.target.value; if (key === 'fusionCase') state.fusionK = ''; redraw('select', key); }
    };
    host.onkeydown = event => {
      const tab = event.target.closest('[data-evidence-stage]');
      if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const current = stages.findIndex(item => item.key === state.stage);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? stages.length - 1 :
        (current + (event.key === 'ArrowRight' ? 1 : -1) + stages.length) % stages.length;
      state.stage = stages[next].key; redraw('stage', state.stage);
    };
  }
  async function render(host, options = {}) {
    let state = sessions.get(host);
    if (!state) { state = { generation: 0, doorway: 'compatible', stage: 'annotations' }; sessions.set(host, state); }
    const generation = ++state.generation;
    const alive = () => host.isConnected !== false && sessions.get(host)?.generation === generation &&
      host.dataset.evidenceGeneration === String(generation) && (!options.isCurrent || options.isCurrent());
    host.dataset.evidenceGeneration = String(generation);
    let data = null, loadError = '';
    if (options.release && options.release !== 'v2') {
      host.innerHTML = `<div class="research-evidence">${missing('方法与证据使用 v2 消费载荷', '历史版本继续保留原有专题，不把当前精选案例混入历史快照。')}</div>`; return;
    }
    try {
      data = await loadPayload(options);
      if (data && options.snapshot && data.snapshot_id !== options.snapshot) {
        data = null; loadError = '研究证据载荷与当前快照不匹配，保存案例和几何已隔离。方法示意仍可阅读。';
      }
    } catch (_) { loadError = '本地研究证据载荷未读到。方法示意仍可阅读；保存案例与分母暂留缺。'; }
    if (!alive()) return;
    const tab = Math.max(0, Math.min(3, Number(options.tab) || 0));
    const renderers = [doorwayHTML, qualityHTML, fusionHTML, supportHTML];
    host.innerHTML = `<div class="research-evidence" data-evidence-tab="${tab}">${contextHTML(options, data)}${loadError ? `<p class="re-note" role="status">${esc(loadError)}</p>` : ''}${renderers[tab](data, state)}</div>`;
    const redraw = async (focusKind, focusKey) => {
      try {
        await render(host, options);
        const selector = focusKind === 'stage' ? `[data-evidence-stage="${focusKey}"]` :
          focusKind === 'doorway' ? `[data-evidence-doorway="${focusKey}"]` : `[data-evidence-select="${focusKey}"]`;
        host.querySelector(selector)?.focus({ preventScroll: true });
      } catch (_) {
        if (alive()) host.innerHTML = missing('证据面板读取中断', '请重新打开此页；当前保存源文件没有改动。');
      }
    };
    bindEvents(host, state, options, redraw);
    if (tab === 1 || tab === 2) await mountGeometries(host, data, state, { ...options, tab }, alive);
    if (alive()) host.dataset.evidenceReady = tabs[tab];
  }
  return { render, overviewHTML, tabs, themes, geometryBinding, stageRows, fusionSelection, navigationPatch, safeSource, qualityTable, doorwaySchematic };
})();
