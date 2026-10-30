/* 门洞交界 · 空间审核 —— 交互逻辑（本地重建版）
 *
 * 依赖（按 index.html 的加载顺序）：
 *   window.WorkbenchCore / window.WorkbenchGeometry（俯视/原图叠线公共组件，可选）
 *   window.DOORWAY_DATA：doorway_review_v2，20 图逐图预切
 *
 * 坐标约定（与数据一致，改动前请先核对）：
 *   原图 ERP：1024×512；数据里的 points 就是该坐标系。页面 canvas 按 1.5 倍显示为 1536×768。
 *   俯视 BEV：米制 (x,z)；相机在原点、朝 -z；floor 为原参考底面多边形。
 *   STOPLINE：BEV 直线 + side。法向 n = normalize(-dz, dx)；保留 side * cross(A,B,p) >= 0 的一侧。
 *             side=+1 保留法向正侧，side=-1 保留法向负侧。
 *
 * 说明：本文件是本机重建的交互实现；原页面只下发了 index.html 与 data.js。
 *       行为以页面原有文案为准：俯视图两点切分 / 彩色方块拖动停止边 / 原图地面两点定位 /
 *       翻转保留侧 / 恢复预切 / 撤销 / 恢复待切分 / 导出导入审核 / 选择即保存。
 */
'use strict';
(function () {
  var RESULT_SCHEMA = 'doorway_review_result_v2';
  var STORE_KEY = 'doorwaySplitReview.v2';
  var ERP_W = 1024, ERP_H = 512;
  var PHOTO_W = 1536, PHOTO_H = 768, PHOTO_SCALE = PHOTO_W / ERP_W;
  var C1 = '#087f8c', C2 = '#b45309', CREF = '#7c3aed', CGRAY = '#94a3b8';
  var SPACES = [{ color: C1, name: '空间1' }, { color: C2, name: '空间2' }];
  var VERDICTS = [
    { id: 'pass', label: '可用' },
    { id: 'fix', label: '需修正' },
    { id: 'unsure', label: '无法判断' }
  ];
  var D = window.DOORWAY_DATA;
  var $ = function (s) { return document.querySelector(s); };

  /* ---------------------------------------------------------------- 基础工具 */
  function now() { return new Date().toISOString(); }
  function fmt(v) { return Number(v).toFixed(3); }
  function cloneCuts(cuts) {
    var arr = (Array.isArray(cuts) ? cuts : []).map(function (cut) {
      if (!cut || !cut.line || cut.line.length < 2) return null;
      return { line: [[+cut.line[0][0], +cut.line[0][1]], [+cut.line[1][0], +cut.line[1][1]]], side: cut.side >= 0 ? 1 : -1 };
    });
    while (arr.length < 2) arr.push(null);
    return arr.slice(0, 2);
  }
  function cutsHash(s) { return JSON.stringify((s.cuts || []).map(function (c) { return c ? [c.line, c.side] : null; })); }
  function cutsEqual(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
  function setMessage(text, kind) {
    var el = $('#message'); if (!el) return;
    el.textContent = text || '';
    el.style.color = kind === 'error' ? '#a33' : kind === 'ok' ? '#087f8c' : '';
    clearTimeout(setMessage._t);
    setMessage._t = setTimeout(function () { el.textContent = ''; el.style.color = ''; }, 6000);
  }
  function downloadText(name, text) {
    var blob = new Blob([text], { type: 'application/json;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
  }

  /* ------------------------------------------------------------ 投影 / 直线几何 */
  // BEV(x,z) -> ERP(u,v)：与 WorkbenchCore.projectFloor 同一约定（相机高 1 单位）
  function erpFromFloor(x, z) {
    var u = ((Math.atan2(x, -z) / (2 * Math.PI) + 0.5) * ERP_W + ERP_W) % ERP_W;
    var v = (0.5 + Math.atan2(1, Math.hypot(x, z)) / Math.PI) * ERP_H;
    return [u, v];
  }
  // ERP(u,v) -> 地面 BEV：v 在地平线以下才有解
  function floorFromErp(u, v) {
    var phi = (v / ERP_H - 0.5) * Math.PI;
    if (!(phi > 0.002)) return null;
    var r = 1 / Math.tan(phi);
    if (!Number.isFinite(r)) return null;
    var theta = (u / ERP_W - 0.5) * 2 * Math.PI;
    return [r * Math.sin(theta), -r * Math.cos(theta)];
  }
  function cutNormal(cut) {
    var a = cut.line[0], b = cut.line[1];
    var dx = b[0] - a[0], dz = b[1] - a[1];
    var len = Math.hypot(dx, dz) || 1;
    return [-dz / len, dx / len];
  }
  function crossValue(cut, x, z) {
    var a = cut.line[0], b = cut.line[1];
    return (b[0] - a[0]) * (z - a[1]) - (b[1] - a[1]) * (x - a[0]);
  }
  // 0 = 相机几乎落在停止边上（门洞内），1 = 相机在保留侧，-1 = 相机不在保留侧
  function cameraSide(cut) {
    var v = crossValue(cut, 0, 0);
    if (Math.abs(v) <= 0.02) return 0;
    return v * cut.side >= 0 ? 1 : -1;
  }
  function cameraKept(cut) { return cameraSide(cut) >= 0; }
  function footPoint(cut) {
    var a = cut.line[0], b = cut.line[1];
    var dx = b[0] - a[0], dz = b[1] - a[1];
    var den = dx * dx + dz * dz;
    if (den < 1e-12) return [a[0], a[1]];
    var t = ((0 - a[0]) * dx + (0 - a[1]) * dz) / den;
    return [a[0] + dx * t, a[1] + dz * t];
  }
  function lineInfoRaw(cut) {
    var a = cut.line[0], b = cut.line[1];
    var dx = b[0] - a[0], dz = b[1] - a[1];
    var len = Math.hypot(dx, dz) || 1;
    var n = [-dz / len, dx / len];
    var tol = 1e-6 * Math.max(1, len, Math.abs(a[0]), Math.abs(a[1]));
    if (Math.abs(dz) <= tol && Math.abs(dx) > tol) {
      return { axis: 'h', c: a[1], n: n, kept: cut.side * n[1] > 0 ? '≥' : '≤' };
    }
    if (Math.abs(dx) <= tol && Math.abs(dz) > tol) {
      return { axis: 'v', c: a[0], n: n, kept: cut.side * n[0] > 0 ? '≥' : '≤' };
    }
    return { axis: 'g', n: n };
  }
  function lineInfo(cut) {
    if (!cut) return '待切分';
    var r = lineInfoRaw(cut);
    if (r.axis === 'h') return '水平线 z = ' + fmt(r.c) + '，保留 z ' + r.kept + ' ' + fmt(r.c);
    if (r.axis === 'v') return '垂直线 x = ' + fmt(r.c) + '，保留 x ' + r.kept + ' ' + fmt(r.c);
    var a = cut.line[0], b = cut.line[1];
    var deg = Math.atan2(b[0] - a[0], -(b[1] - a[1])) * 180 / Math.PI;
    return '斜线（方位 ' + deg.toFixed(0) + '°），保留法向' + (cut.side > 0 ? '正' : '负') + '侧';
  }
  function normalizeLine(cut) {
    var a = cut.line[0], b = cut.line[1];
    var dx = b[0] - a[0], dz = b[1] - a[1];
    var line;
    if (Math.abs(dz) <= 1e-9 * Math.max(1, Math.abs(dx), Math.abs(a[1]))) line = [[-100, a[1]], [100, a[1]]];
    else if (Math.abs(dx) <= 1e-9 * Math.max(1, Math.abs(dz), Math.abs(a[0]))) line = [[a[0], -100], [a[0], 100]];
    else line = [[+a[0], +a[1]], [+b[0], +b[1]]];
    return { line: line, side: cut.side >= 0 ? 1 : -1 };
  }
  // 半平面裁剪：保留 side*cross >= 0
  function clipPolyHalf(poly, cut) {
    if (!poly || poly.length < 3) return [];
    var out = [];
    for (var i = 0; i < poly.length; i++) {
      var p = poly[i], q = poly[(i + 1) % poly.length];
      var fp = crossValue(cut, p[0], p[1]) * cut.side;
      var fq = crossValue(cut, q[0], q[1]) * cut.side;
      var ip = fp >= -1e-12, iq = fq >= -1e-12;
      if (ip) out.push([p[0], p[1]]);
      if (ip !== iq) {
        var t = fp / (fp - fq);
        out.push([p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]);
      }
    }
    return out.length >= 3 ? out : [];
  }
  // Liang–Barsky：直线 a->b 与矩形求交
  function clipLineToRect(a, b, rect) {
    var x0 = rect[0], z0 = rect[1], x1 = rect[2], z1 = rect[3];
    var dx = b[0] - a[0], dz = b[1] - a[1];
    var t = [0, 1];
    var p = [-dx, dx, -dz, dz];
    var q = [a[0] - x0, x1 - a[0], a[1] - z0, z1 - a[1]];
    for (var i = 0; i < 4; i++) {
      if (Math.abs(p[i]) < 1e-12) {
        if (q[i] < 0) return null;
      } else {
        var r = q[i] / p[i];
        if (p[i] < 0) { if (r > t[1]) return null; if (r > t[0]) t[0] = r; }
        else { if (r < t[0]) return null; if (r < t[1]) t[1] = r; }
      }
    }
    return [
      [a[0] + dx * t[0], a[1] + dz * t[0]],
      [a[0] + dx * t[1], a[1] + dz * t[1]]
    ];
  }
  function gapInfo(cuts) {
    var a = cuts && cuts[0], b = cuts && cuts[1];
    if (!a || !b) return null;
    var ra = lineInfoRaw(a), rb = lineInfoRaw(b);
    if (ra.axis === 'h' && rb.axis === 'h') {
      var fa = footPoint(a);
      return { value: Math.abs(ra.c - rb.c), x: fa[0], z: (ra.c + rb.c) / 2 };
    }
    if (ra.axis === 'v' && rb.axis === 'v') {
      var fb = footPoint(a);
      return { value: Math.abs(ra.c - rb.c), x: (ra.c + rb.c) / 2, z: fb[1] };
    }
    return null;
  }

  /* ------------------------------------------------------------------- 状态 */
  if (!D || !Array.isArray(D.cases) || !D.cases.length) {
    setMessage('data.js 未加载：window.DOORWAY_DATA 为空。');
    return;
  }
  var state = {
    index: 0, recordIndex: 0, space: 0, orth: true,
    pendingPlan: null, pendingPhoto: null, drag: null, planGeom: null
  };
  var states = D.cases.map(function (c) {
    return {
      cuts: cloneCuts(c.cuts),
      cut: (c.cut === undefined ? null : c.cut),
      note: '', mark: null, reviewed: false,
      verdicts: {}, history: [], updatedAt: null
    };
  });
  var cases = D.cases;
  function cur() { return cases[state.index]; }
  function cst() { return states[state.index]; }
  function recordsOf(c) { return (c && c.records) || []; }
  function reviewedCount() { var n = 0; for (var i = 0; i < cases.length; i++) if (isReviewed(i)) n++; return n; }
  function isReviewed(i) {
    var s = states[i], c = cases[i];
    if (s.mark === 'done') return true;
    if (s.mark === 'todo') return false;
    if (!s.cuts[0] && !s.cuts[1]) return false;      // 待切分不计入已审
    return !!(s.note && String(s.note).trim()) ||
      Object.keys(s.verdicts || {}).length > 0 ||
      !cutsEqual(s.cuts, cloneCuts(c.cuts));
  }
  function floorOf(c) {
    if (Array.isArray(c.floor) && c.floor.length >= 3) return c.floor.map(function (p) { return [+p[0], +p[1]]; });
    var pts = c.points || [], ring = [];
    for (var i = 1; i < pts.length; i += 2) {
      var g = floorFromErp(pts[i][0], pts[i][1]);
      if (g) ring.push(g);
    }
    return ring.length >= 3 ? ring : null;
  }
  // 视野只由底面与相机决定（固定），保证编辑过程中点击位置与画面对应关系稳定。
  function planRect(poly) {
    var pts = poly && poly.length >= 3 ? poly : [[-2, -2], [2, 2]];
    var x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
    function add(x, z) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); z0 = Math.min(z0, z); z1 = Math.max(z1, z); }
    pts.forEach(function (p) { add(p[0], p[1]); });
    add(0, 0);
    var m = Math.max(x1 - x0, z1 - z0) * 0.06 + 0.15;
    return [x0 - m, z0 - m, x1 + m, z1 + m];
  }
  function pointInPoly(poly, x, z) {
    var inside = false;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      var a = poly[i], b = poly[j];
      if ((a[1] > z) !== (b[1] > z) && x < (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
    }
    return inside;
  }
  // 两个空间保留区在底面内的重叠面积（网格估计，m²）
  function keptOverlapArea(cuts, poly) {
    if (!cuts || !cuts[0] || !cuts[1] || !poly || poly.length < 3) return 0;
    var k1 = clipPolyHalf(poly, cuts[0]);
    var k2 = clipPolyHalf(poly, cuts[1]);
    if (k1.length < 3 || k2.length < 3) return 0;
    var x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
    poly.forEach(function (p) {
      x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]);
      z0 = Math.min(z0, p[1]); z1 = Math.max(z1, p[1]);
    });
    var N = 36, dx = (x1 - x0) / N, dz = (z1 - z0) / N;
    var hit = 0;
    for (var i = 0; i < N; i++) {
      for (var j = 0; j < N; j++) {
        var px = x0 + (i + 0.5) * dx, pz = z0 + (j + 0.5) * dz;
        if (pointInPoly(k1, px, pz) && pointInPoly(k2, px, pz)) hit++;
      }
    }
    return hit * dx * dz;
  }
  function polyCentroid(poly) {
    if (!poly || poly.length < 3) return null;
    var a = 0, cx = 0, cz = 0;
    for (var i = 0; i < poly.length; i++) {
      var p = poly[i], q = poly[(i + 1) % poly.length];
      var cr = p[0] * q[1] - q[0] * p[1];
      a += cr; cx += (p[0] + q[0]) * cr; cz += (p[1] + q[1]) * cr;
    }
    if (Math.abs(a) < 1e-9) {
      var sx = 0, sz = 0;
      poly.forEach(function (p) { sx += p[0]; sz += p[1]; });
      return [sx / poly.length, sz / poly.length];
    }
    a *= 0.5;
    return [cx / (6 * a), cz / (6 * a)];
  }
  function polyArea(poly) {
    if (!poly || poly.length < 3) return 0;
    var a = 0;
    for (var i = 0; i < poly.length; i++) {
      var p = poly[i], q = poly[(i + 1) % poly.length];
      a += p[0] * q[1] - q[0] * p[1];
    }
    return Math.abs(a) / 2;
  }
  function projectRing(poly) {
    if (!poly || poly.length < 3) return [];
    var out = poly.map(function (p) { return erpFromFloor(p[0], p[1]); });
    out.push(out[0]);
    return out;
  }

  /* --------------------------------------------------------------- 本地存储 */
  function storeSnapshot() {
    return {
      schema: RESULT_SCHEMA, saved_at: now(), orth: state.orth,
      cases: cases.map(function (c, i) {
        var s = states[i];
        return {
          image_id: c.image_id,
          cuts: cloneCuts(s.cuts).map(function (v) { return v ? { line: v.line, side: v.side } : null; }),
          cut: s.cut === undefined ? null : s.cut,
          note: s.note || '',
          mark: s.mark || null,
          updated_at: s.updatedAt || null,
          verdicts: Object.keys(s.verdicts || {}).map(function (id) {
            var v = s.verdicts[id];
            return { record_id: id, value: v.value, cuts_hash: v.cutsHash || null, at: v.at || null };
          })
        };
      })
    };
  }
  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(storeSnapshot())); }
    catch (err) { /* 本地存储不可用时仍可导出 */ }
  }
  function loadStore() {
    var obj = null;
    try {
      var raw = localStorage.getItem(STORE_KEY);
      if (raw) obj = JSON.parse(raw);
    } catch (err) { obj = null; }
    if (!obj || obj.schema !== RESULT_SCHEMA) return;
    if (typeof obj.orth === 'boolean') { state.orth = obj.orth; var orth = $('#orth'); if (orth) orth.checked = obj.orth; }
    (obj.cases || []).forEach(function (row) {
      if (!row || !row.image_id) return;
      var idx = -1;
      for (var i = 0; i < cases.length; i++) if (cases[i].image_id === row.image_id) { idx = i; break; }
      if (idx < 0) return;
      var s = states[idx];
      if (Array.isArray(row.cuts)) s.cuts = cloneCuts(row.cuts);
      if (Object.prototype.hasOwnProperty.call(row, 'cut')) s.cut = row.cut === undefined ? null : row.cut;
      if (typeof row.note === 'string') s.note = row.note;
      if (row.mark) s.mark = row.mark;
      if (Array.isArray(row.verdicts)) {
        s.verdicts = {};
        row.verdicts.forEach(function (v) {
          if (v && v.record_id && v.value) s.verdicts[v.record_id] = { value: v.value, cutsHash: v.cuts_hash || null, at: v.at || null };
        });
      }
      if (row.updated_at) s.updatedAt = row.updated_at;
    });
  }

  /* ------------------------------------------------------------- 俯视图（plan） */
  function planToBev(ev) {
    var svg = $('#plan'); if (!svg || !state.planGeom) return [0, 0];
    var pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
    var m = svg.getScreenCTM(); if (!m) return [0, 0];
    var q = pt.matrixTransform(m.inverse());
    var g = state.planGeom;
    return [(q.x - g.ox) / g.s, (q.y - g.oy) / g.s];
  }
  function renderPlan() {
    var svg = $('#plan'); if (!svg) return;
    var c = cur(), s = cst();
    var poly = floorOf(c);
    var rect = planRect(poly);
    var W = 450, H = 400, pad = 26;
    var w = rect[2] - rect[0], h = rect[3] - rect[1];
    var scl = Math.min((W - 2 * pad) / Math.max(w, 1e-6), (H - 2 * pad) / Math.max(h, 1e-6));
    var ox = (W - w * scl) / 2 - rect[0] * scl;
    var oy = (H - h * scl) / 2 - rect[1] * scl;
    state.planGeom = { rect: rect, s: scl, ox: ox, oy: oy };
    function P(x, z) { return [ox + x * scl, oy + z * scl]; }
    function toPoly(pts) { return pts.map(function (p) { var q = P(p[0], p[1]); return q[0].toFixed(1) + ',' + q[1].toFixed(1); }).join(' '); }
    function num(v) { return Number(v).toFixed(1); }

    var out = '';
    out += '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#f6f8fa" data-bg="1"/>';
    var bboxPoly = [[rect[0], rect[1]], [rect[2], rect[1]], [rect[2], rect[3]], [rect[0], rect[3]]];

    // 只在原参考底面内着色保留区，不把整幅画布染色
    if (poly && poly.length >= 3) {
      s.cuts.forEach(function (cut, i) {
        if (!cut) return;
        var kept = clipPolyHalf(poly, cut);
        if (kept.length >= 3) out += '<polygon points="' + toPoly(kept) + '" fill="' + SPACES[i].color + '" opacity="0.16" pointer-events="none"/>';
      });
      out += '<polygon points="' + toPoly(poly) + '" fill="none" stroke="' + CREF + '" stroke-width="1.6" opacity="0.9" pointer-events="none"/>';
    }

    // 停止边（可点击选中）+ 透明加宽命中区
    s.cuts.forEach(function (cut, i) {
      if (!cut) return;
      var seg = clipLineToRect(cut.line[0], cut.line[1], rect);
      if (!seg) return;
      var a = P(seg[0][0], seg[0][1]), b = P(seg[1][0], seg[1][1]);
      var active = i === state.space;
      out += '<g data-space="' + i + '" style="cursor:pointer">' +
        '<line x1="' + num(a[0]) + '" y1="' + num(a[1]) + '" x2="' + num(b[0]) + '" y2="' + num(b[1]) + '" stroke="transparent" stroke-width="16"/>' +
        '<line x1="' + num(a[0]) + '" y1="' + num(a[1]) + '" x2="' + num(b[0]) + '" y2="' + num(b[1]) + '" stroke="' + SPACES[i].color + '" stroke-width="' + (active ? 3.2 : 1.6) + '" stroke-dasharray="' + (active ? '' : '5 4') + '" opacity="' + (active ? 1 : 0.62) + '"/>' +
        '</g>';
    });

    // 拖动方块（当前空间更大更实心）
    s.cuts.forEach(function (cut, i) {
      if (!cut) return;
      var seg = clipLineToRect(cut.line[0], cut.line[1], rect);
      if (!seg) return;
      var mx = (seg[0][0] + seg[1][0]) / 2, mz = (seg[0][1] + seg[1][1]) / 2;
      var q = P(mx, mz);
      var active = i === state.space;
      out += '<rect data-handle="1" data-space="' + i + '" x="' + num(q[0] - (active ? 6 : 5)) + '" y="' + num(q[1] - (active ? 6 : 5)) + '" width="' + (active ? 12 : 10) + '" height="' + (active ? 12 : 10) + '" rx="2" fill="' + (active ? SPACES[i].color : '#ffffff') + '" stroke="' + SPACES[i].color + '" stroke-width="1.6" style="cursor:grab"/>';
    });

    // 相机与朝向
    var cam = P(0, 0), fwd = P(0, -0.5);
    out += '<line x1="' + num(cam[0]) + '" y1="' + num(cam[1]) + '" x2="' + num(fwd[0]) + '" y2="' + num(fwd[1]) + '" stroke="#111111" stroke-width="1.3" opacity="0.6" pointer-events="none"/>';
    out += '<circle cx="' + num(cam[0]) + '" cy="' + num(cam[1]) + '" r="4.2" fill="#111111" stroke="#ffffff" stroke-width="1.4" pointer-events="none"/>';
    out += '<text x="' + num(Math.max(58, cam[0] - 9)) + '" y="' + num(cam[1] - 9) + '" font-size="10" text-anchor="end" fill="#334155" pointer-events="none">拍摄点位</text>';

    // 空间标签：放在各自“裁后保留区”的质心；区域太小时退回停止边靠保留侧
    s.cuts.forEach(function (cut, i) {
      if (!cut) return;
      var kept = poly && poly.length >= 3 ? clipPolyHalf(poly, cut) : [];
      var lp = null;
      if (kept.length >= 3 && polyArea(kept) >= 0.06) {
        var cen = polyCentroid(kept);
        if (cen) lp = cen;
      }
      if (!lp) {
        var f = footPoint(cut), n = cutNormal(cut);
        lp = [f[0] + n[0] * cut.side * 0.45, f[1] + n[1] * cut.side * 0.45];
      }
      // 保留区很窄时把标签沿法向推开，避免压住停止边/拖动柄
      var la = cut.line[0], lb = cut.line[1];
      var llen = Math.hypot(lb[0] - la[0], lb[1] - la[1]) || 1;
      var ldist = Math.abs(crossValue(cut, lp[0], lp[1])) / llen;
      var need = 34 / scl;
      if (ldist < need) {
        var nn = cutNormal(cut);
        lp = [lp[0] + nn[0] * cut.side * (need - ldist), lp[1] + nn[1] * cut.side * (need - ldist)];
      }
      var q = P(lp[0], lp[1]);
      q[0] = Math.max(30, Math.min(W - 30, q[0]));
      q[1] = Math.max(16, Math.min(H - 10, q[1]));
      out += '<text x="' + num(q[0]) + '" y="' + num(q[1]) + '" font-size="12" font-weight="600" text-anchor="middle" fill="' + SPACES[i].color + '" pointer-events="none">' + SPACES[i].name + '</text>';
    });

    // 门框厚度区（放到不遮挡相机/拖动柄的位置）
    var gap = gapInfo(s.cuts);
    if (gap) {
      var ra = lineInfoRaw(s.cuts[0]), rb = lineInfoRaw(s.cuts[1]);
      var gx, gz, anchor;
      if (ra.axis === 'h' && rb.axis === 'h') {
        var camScreenX = P(0, 0)[0];
        if (camScreenX < W * 0.5) { gx = rect[2] - w * 0.10; anchor = 'end'; }
        else { gx = rect[0] + w * 0.10; anchor = 'start'; }
        gz = (ra.c + rb.c) / 2;
      } else if (ra.axis === 'v' && rb.axis === 'v') {
        gx = (ra.c + rb.c) / 2; gz = rect[1] + h * 0.06; anchor = 'middle';
      } else {
        gx = gap.x; gz = gap.z; anchor = 'middle';
      }
      var gq = P(gx, gz);
      out += '<text x="' + num(gq[0]) + '" y="' + num(gq[1] - 4) + '" font-size="10" text-anchor="' + anchor + '" fill="#546573" pointer-events="none">门框厚度区 ' + gap.value.toFixed(3) + ' m</text>';
    }

    // 待定点
    if (state.pendingPlan && state.pendingPlan.space === state.space) {
      state.pendingPlan.pts.forEach(function (p) {
        var q = P(p[0], p[1]);
        out += '<circle cx="' + num(q[0]) + '" cy="' + num(q[1]) + '" r="4.2" fill="#ffffff" stroke="' + SPACES[state.space].color + '" stroke-width="2" pointer-events="none"/>';
      });
    }

    out += '<text x="10" y="' + (H - 8) + '" font-size="9" fill="#7b8a99" pointer-events="none">紫＝原参考底面　彩色实线＝当前空间停止边　虚线＝另一空间　方块可拖动</text>';
    svg.innerHTML = out;
  }

  /* ----------------------------------------------------------- 原图（photo） */
  var photoCache = new Map();
  function photoFor(c) {
    if (!c.photo) return null;
    if (!photoCache.has(c.photo)) {
      var im = new Image();
      im.decoding = 'async';
      im.onload = function () { if (cur() === c) drawPhoto(); };
      im.onerror = function () {
        var el = $('#photoStatus');
        if (el) el.textContent = '原图缺失：' + c.photo;
      };
      im.src = c.photo;
      photoCache.set(c.photo, im);
    }
    return photoCache.get(c.photo);
  }
  function yaw() { var el = $('#yaw'); return el ? Number(el.value) || 0 : 0; }
  function erpUnwrap(u, prev) { var d = u - prev; return prev + d - Math.round(d / ERP_W) * ERP_W; }
  function drawErpPolyline(ctx, pts, shift, width, color, alpha, dash) {
    if (!pts || pts.length < 2) return;
    ctx.save();
    ctx.globalAlpha = alpha == null ? 1 : alpha;
    ctx.strokeStyle = color; ctx.lineWidth = width;
    ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    if (dash && dash.length) ctx.setLineDash(dash);
    for (var k = -2; k <= 2; k++) {
      ctx.beginPath();
      var prev = null;
      for (var i = 0; i < pts.length; i++) {
        var u = pts[i][0] + shift, v = pts[i][1];
        if (prev !== null) u = erpUnwrap(u, prev);
        if (i === 0) ctx.moveTo(u + k * ERP_W, v); else ctx.lineTo(u + k * ERP_W, v);
        prev = u;
      }
      ctx.stroke();
    }
    ctx.restore();
  }
  function sampleCutToErp(seg, n) {
    var out = [];
    for (var i = 0; i <= n; i++) {
      var t = i / n;
      out.push(erpFromFloor(seg[0][0] + (seg[1][0] - seg[0][0]) * t, seg[0][1] + (seg[1][1] - seg[0][1]) * t));
    }
    return out;
  }
  function drawPhoto() {
    var cv = $('#photo'); if (!cv) return;
    var c = cur(), s = cst();
    if (cv.width !== PHOTO_W || cv.height !== PHOTO_H) { cv.width = PHOTO_W; cv.height = PHOTO_H; }
    var ctx = cv.getContext('2d');
    var shift = (yaw() / 360) * ERP_W;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, PHOTO_W, PHOTO_H);
    ctx.fillStyle = '#e9eef3';
    ctx.fillRect(0, 0, PHOTO_W, PHOTO_H);
    ctx.setTransform(PHOTO_SCALE, 0, 0, PHOTO_SCALE, 0, 0);
    var img = photoFor(c);
    if (img && img.complete && img.naturalWidth) {
      for (var k = -2; k <= 2; k++) {
        var x = shift + k * ERP_W;
        if (x + ERP_W > 0 && x < ERP_W) ctx.drawImage(img, x, 0, ERP_W, ERP_H);
      }
    }
    var poly = floorOf(c);
    var rect = planRect(poly);

    // 细线：裁后底面轮廓
    if (poly && poly.length >= 3) {
      var hasCut = s.cuts.some(Boolean);
      if (!hasCut) {
        drawErpPolyline(ctx, projectRing(poly), shift, 1.1, CGRAY, 0.85);
      } else {
        s.cuts.forEach(function (cut, i) {
          if (!cut) {
            drawErpPolyline(ctx, projectRing(poly), shift, 1.0, CGRAY, 0.7);
            return;
          }
          var kept = clipPolyHalf(poly, cut);
          if (kept.length >= 3) drawErpPolyline(ctx, projectRing(kept), shift, 1.15, i === 0 ? '#0e7490' : '#d97706', 0.9);
        });
      }
    }

    // 粗实线：停止边（沿地面投影成曲线）
    s.cuts.forEach(function (cut, i) {
      if (!cut) return;
      var seg = clipLineToRect(cut.line[0], cut.line[1], rect);
      if (!seg) return;
      drawErpPolyline(ctx, sampleCutToErp(seg, 180), shift, 2.6, i === 0 ? C1 : C2, 1);
    });

    // 原图两点编辑的待定点
    if (state.pendingPhoto && state.pendingPhoto.space === state.space) {
      ctx.save();
      ctx.lineWidth = 2;
      state.pendingPhoto.pts.forEach(function (p) {
        var erp = erpFromFloor(p[0], p[1]);
        var u = ((erp[0] + shift) % ERP_W + ERP_W) % ERP_W;
        for (var k = -1; k <= 1; k++) {
          ctx.beginPath();
          ctx.arc(u + k * ERP_W, erp[1], 5, 0, Math.PI * 2);
          ctx.fillStyle = '#ffffff';
          ctx.strokeStyle = SPACES[state.space].color;
          ctx.fill(); ctx.stroke();
        }
      });
      ctx.restore();
    }
    updatePhotoStatus();
  }
  function photoToGround(ev) {
    var cv = $('#photo'); if (!cv) return null;
    var r = cv.getBoundingClientRect();
    if (!r.width || !r.height) return null;
    var px = (ev.clientX - r.left) / r.width * PHOTO_W;
    var py = (ev.clientY - r.top) / r.height * PHOTO_H;
    var v = py / PHOTO_SCALE;
    if (v <= ERP_H * 0.5 + 1.5) { setMessage('请点在原图的地面（地平线以下）。', 'error'); return null; }
    var shift = (yaw() / 360) * ERP_W;
    var u = (((px / PHOTO_SCALE) - shift) % ERP_W + ERP_W) % ERP_W;
    var phi = (v / ERP_H - 0.5) * Math.PI;
    var dist = 1 / Math.tan(phi);
    if (!Number.isFinite(dist) || dist > 30) { setMessage('点太靠近地平线（地面点过远），请点近一些。', 'error'); return null; }
    var theta = (u / ERP_W - 0.5) * 2 * Math.PI;
    return [dist * Math.sin(theta), -dist * Math.cos(theta)];
  }

  /* ------------------------------------------------------- 切分编辑 / 历史 */
  function pushHistory(s, prevCuts) {
    if (cutsEqual(prevCuts, s.cuts)) return;
    s.history.push(prevCuts);
    if (s.history.length > 50) s.history.shift();
  }
  function defaultSide(space, cut) {
    var v = crossValue(cut, 0, 0);
    var cameraSide = v >= 0 ? 1 : -1;
    return space === 0 ? cameraSide : -cameraSide;
  }
  function applyTwoPoint(space, pts, source) {
    var s = cst();
    if (!pts || pts.length < 2) return;
    var p1 = pts[0], p2 = pts[1];
    if (Math.hypot(p2[0] - p1[0], p2[1] - p1[1]) < 0.05) { setMessage('两点太近，请重新点选。', 'error'); return; }
    var line;
    if (state.orth) {
      var dx = p2[0] - p1[0], dz = p2[1] - p1[1];
      if (Math.abs(dx) >= Math.abs(dz)) {
        var z = (p1[1] + p2[1]) / 2;
        line = [[-100, z], [100, z]];
      } else {
        var x = (p1[0] + p2[0]) / 2;
        line = [[x, -100], [x, 100]];
      }
    } else {
      var ddx = p2[0] - p1[0], ddz = p2[1] - p1[1];
      var len = Math.hypot(ddx, ddz) || 1;
      var ux = ddx / len, uz = ddz / len;
      var mid = [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2];
      line = [[mid[0] - ux * 100, mid[1] - uz * 100], [mid[0] + ux * 100, mid[1] + uz * 100]];
    }
    var prev = cloneCuts(s.cuts);
    var old = s.cuts[space];
    var side = old ? old.side : defaultSide(space, { line: line, side: 1 });
    s.cuts[space] = normalizeLine({ line: line, side: side });
    pushHistory(s, prev);
    s.mark = null;
    s.updatedAt = now();
    save();
    setMessage('已' + (source === 'photo' ? '在原图' : '在俯视图') + '更新' + SPACES[space].name + '停止边。', 'ok');
    refreshAfterEdit();
  }
  function refreshAfterEdit() {
    syncImages();
    renderSplitStatus();
    renderMark();
    renderAnswersMeta();
    renderPlan();
    drawPhoto();
    updatePhotoStatus();
    renderChoices();
  }

  /* ------------------------------------------------------------- 文本渲染 */
  function renderSplitStatus() {
    var s = cst(), parts = [];
    [0, 1].forEach(function (i) {
      var cut = s.cuts[i];
      if (!cut) parts.push(SPACES[i].name + '：待切分');
      else {
        var cs = cameraSide(cut);
        parts.push(SPACES[i].name + '：' + lineInfo(cut) + '（' + (cs === 0 ? '相机位于停止边上' : cs > 0 ? '相机在保留侧' : '相机不在保留侧') + '）');
      }
    });
    var gap = gapInfo(s.cuts);
    if (gap) parts.push('门框厚度区 ' + gap.value.toFixed(3) + ' m');
    if (!s.cuts[0] && !s.cuts[1]) parts.push('本图待切分：请先选空间1或空间2，再点两点定义停止边');
    var poly = floorOf(cur());
    var overlap = keptOverlapArea(s.cuts, poly);
    if (overlap > 0.03) parts.push('⚠ 两空间保留区重叠 ' + overlap.toFixed(2) + ' m²，切分可能无效');
    $('#splitstatus').textContent = parts.join('　｜　');
  }
  function renderProposal() {
    var c = cur();
    var pre = (c.cuts || []).map(function (cut, i) {
      return cut ? SPACES[i].name + ' ' + lineInfo(cut) : null;
    }).filter(Boolean).join('；');
    $('#proposal').textContent = '预切说明：' + (c.proposal_note || '（无）') + (pre ? '　预切：' + pre : '');
  }
  function renderMark() {
    if (!renderMark._bound) return;
    var reviewed = isReviewed(state.index);
    var btn = $('#markReviewed'), st = $('#reviewState');
    if (btn) btn.textContent = reviewed ? '取消“已审”标记' : '标记本图已审';
    if (st) st.textContent = reviewed ? '本图计入已审。' : '本图尚未计入已审。';
  }
  function renderTitle() {
    var c = cur();
    $('#title').textContent = String(state.index + 1).padStart(2, '0') + '/' + cases.length + ' · ' + c.image + ' · ' + c.status + ' · ' + c.image_id;
  }
  function syncImages() {
    var sel = $('#images'); if (!sel) return;
    sel.innerHTML = cases.map(function (c, i) {
      return '<option value="' + i + '">' + String(i + 1).padStart(2, '0') + ' · ' + c.image + ' · ' + c.status + (isReviewed(i) ? ' ✓' : '') + '</option>';
    }).join('');
    sel.value = String(state.index);
    $('#prev').disabled = state.index <= 0;
    $('#next').disabled = state.index >= cases.length - 1;
  }
  function renderAnswersMeta() {
    var c = cur(), s = cst(), recs = recordsOf(c);
    var sel = $('#answers'); if (!sel) return;
    sel.innerHTML = recs.map(function (r, i) {
      var judged = s.verdicts && s.verdicts[r.id];
      return '<option value="' + i + '">' + String(i + 1).padStart(2, '0') + ' · ' + r.worker + ' · ' + r.status + ' · ' + ((r.points || []).length) + '点' + (judged ? ' · 已判定' : '') + '</option>';
    }).join('');
    sel.value = String(state.recordIndex);
    var judged = recs.filter(function (r) { return s.verdicts && s.verdicts[r.id]; }).length;
    $('#progress').textContent = '已审 ' + reviewedCount() + '/' + cases.length + ' 图 · 本图标注 ' + (recs.length ? state.recordIndex + 1 : 0) + '/' + recs.length + ' · 已判定 ' + judged + '/' + recs.length;
    $('#aprev').disabled = state.recordIndex <= 0;
    $('#anext').disabled = state.recordIndex >= recs.length - 1;
  }
  function verdictLabel(v) {
    var hit = VERDICTS.filter(function (o) { return o.id === v; })[0];
    return hit ? hit.label : String(v || '');
  }
  function renderChoices() {
    var c = cur(), s = cst(), rec = recordsOf(c)[state.recordIndex], host = $('#choices');
    if (!host) return;
    if (!rec) { host.innerHTML = '<p class="muted">本图没有可核查的标注。</p>'; return; }
    var v = s.verdicts[rec.id];
    var hash = cutsHash(s);
    var stale = !!(v && v.cutsHash && v.cutsHash !== hash);
    var pts = (rec.points || []).length;
    var html = '<p class="muted">核查第 ' + (state.recordIndex + 1) + ' 份标注：<b>' + rec.worker + '</b> · ' + rec.status + ' · ' + pts + ' 点' +
      (pts ? '' : '（坐标不可用，只能判“无法判断”）') + '。按当前空间1/2 切分判断该份标注能否作为该图布局依据。</p>';
    html += '<p>' + VERDICTS.map(function (o) {
      return '<button type="button" data-verdict="' + o.id + '" class="' + (v && v.value === o.id ? 'active' : '') + '">' + o.label + '</button>';
    }).join('') + '<button type="button" data-verdict="clear">清除判定</button></p>';
    if (v) html += '<p class="muted">当前判定：' + verdictLabel(v.value) + (stale ? ' · <b style="color:#b45309">边界已改，旧判定需重看</b>' : '') + '</p>';
    host.innerHTML = html;
    host.querySelectorAll('[data-verdict]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var val = btn.dataset.verdict;
        if (val === 'clear') delete s.verdicts[rec.id];
        else s.verdicts[rec.id] = { value: val, cutsHash: hash, at: now() };
        s.mark = null;
        s.updatedAt = now();
        save();
        renderChoices(); renderAnswersMeta(); renderMark(); syncImages();
      });
    });
  }
  function updatePhotoStatus() {
    var el = $('#photoStatus'); if (!el) return;
    var s = cst(), cut = s.cuts[state.space];
    var txt = '当前' + SPACES[state.space].name + '：' + (cut ? lineInfo(cut) : '待切分') + '。粗实线＝停止边，细线＝裁后底面轮廓。';
    if ($('#photoEdit') && $('#photoEdit').checked) {
      txt += (state.pendingPhoto && state.pendingPhoto.space === state.space) ? '已点 1 点，请在地面再点一点。' : '在原图地面点两点即可重新定位当前空间停止边。';
    } else {
      txt += '勾选“在原图地面点两点调整当前空间停止边”可在这里改。';
    }
    el.textContent = txt;
  }
  function renderViewer() {
    var c = cur(), rec = recordsOf(c)[state.recordIndex], host = $('#viewer');
    if (!host) return;
    host.innerHTML = '';
    if (!window.WorkbenchGeometry || !window.WorkbenchCore) {
      host.innerHTML = '<p class="muted">几何查看器（geometry-view.js / workbench-core.js）未加载。</p>';
      return;
    }
    try {
      var answer = rec && rec.points && rec.points.length >= 6
        ? { points: rec.points, color: C1, highlight: true, order_status: rec.status }
        : { color: C1 };
      window.WorkbenchGeometry.mount(host, { photo: c.photo }, answer, { points: c.points, floor: c.floor }, null, { layers: [] });
      // 逐份作答查看器默认 BEV 俯视（只改默认视图，不动其他逻辑）
      var viewSel = host.querySelector('[data-view]');
      if (viewSel) {
        viewSel.value = 'bev';
        if (typeof viewSel.onchange === 'function') viewSel.onchange({ target: viewSel });
      }
    } catch (err) {
      host.innerHTML = '<p class="muted">几何查看器渲染失败：' + String(err && err.message ? err.message : err) + '</p>';
    }
  }

  /* --------------------------------------------------------------- 导入导出 */
  function buildExport() {
    var out = {
      schema: RESULT_SCHEMA,
      source_schema: D.schema || 'doorway_review_v2',
      exported_at: now(),
      reviewer: 'local',
      counts: { total: cases.length, reviewed: reviewedCount(), verdicts: 0 },
      cases: []
    };
    cases.forEach(function (c, i) {
      var s = states[i];
      var verdicts = Object.keys(s.verdicts || {}).map(function (id) {
        var v = s.verdicts[id];
        return { record_id: id, value: v.value, cuts_hash: v.cutsHash || null, at: v.at || null };
      });
      out.counts.verdicts += verdicts.length;
      out.cases.push({
        image: c.image, image_id: c.image_id, status: c.status,
        photo: c.photo, reference_id: c.reference_id,
        cuts: cloneCuts(s.cuts).map(function (v) { return v ? { line: v.line, side: v.side } : null; }),
        cut: s.cut === undefined ? null : s.cut,
        note: s.note || '',
        mark: s.mark || null,
        reviewed: isReviewed(i),
        verdicts: verdicts,
        precut: cloneCuts(c.cuts).map(function (v) { return v ? { line: v.line, side: v.side } : null; }),
        proposal_note: c.proposal_note || '',
        updated_at: s.updatedAt || null
      });
    });
    return out;
  }
  function exportReview() {
    var out = buildExport();
    var t = new Date();
    var p = function (n) { return String(n).padStart(2, '0'); };
    var name = 'doorway_split_review_' + t.getFullYear() + p(t.getMonth() + 1) + p(t.getDate()) + '_' + p(t.getHours()) + p(t.getMinutes()) + '.json';
    downloadText(name, JSON.stringify(out, null, 1));
    setMessage('已导出审核：' + out.counts.reviewed + '/' + out.counts.total + ' 图已审，' + out.counts.verdicts + ' 份标注判定。', 'ok');
  }
  function validCut(v) {
    if (v === null || v === undefined) return null;
    if (!v || !Array.isArray(v.line) || v.line.length !== 2) return undefined;
    var ok = v.line.every(function (p) {
      return Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
    });
    if (!ok) return undefined;
    if (v.side !== 1 && v.side !== -1) return undefined;   // 只接受 ±1，非法 side 拒绝
    return { line: [[+v.line[0][0], +v.line[0][1]], [+v.line[1][0], +v.line[1][1]]], side: v.side };
  }
  function importReview(file) {
    var rd = new FileReader();
    rd.onload = function () {
      var obj;
      try { obj = JSON.parse(String(rd.result)); }
      catch (err) { setMessage('导入失败：不是合法 JSON。', 'error'); return; }
      if (!obj || obj.schema !== RESULT_SCHEMA || !Array.isArray(obj.cases)) {
        setMessage('导入失败：schema 必须为 ' + RESULT_SCHEMA + '。', 'error');
        return;
      }
      var applied = 0, skipped = 0;
      obj.cases.forEach(function (row) {
        if (!row || !row.image_id) { skipped++; return; }
        var idx = -1;
        for (var i = 0; i < cases.length; i++) if (cases[i].image_id === row.image_id) { idx = i; break; }
        if (idx < 0) { skipped++; return; }
        var s = states[idx];
        if (Array.isArray(row.cuts)) {
          var next = cloneCuts([]);
          for (var k = 0; k < 2; k++) {
            var cut = validCut(row.cuts[k]);
            if (cut === undefined) { skipped++; return; }
            next[k] = cut;
          }
          s.cuts = next;
        }
        if (Object.prototype.hasOwnProperty.call(row, 'cut')) s.cut = row.cut === undefined ? null : row.cut;
        if (typeof row.note === 'string') s.note = row.note;
        if (row.mark === 'done' || row.mark === 'todo') s.mark = row.mark;
        if (Array.isArray(row.verdicts)) {
          s.verdicts = {};
          row.verdicts.forEach(function (v) {
            if (v && v.record_id && v.value) s.verdicts[v.record_id] = { value: v.value, cutsHash: v.cuts_hash || null, at: v.at || null };
          });
        }
        s.updatedAt = row.updated_at || s.updatedAt || null;
        applied++;
      });
      save();
      renderAll();
      if (!applied) {
        setMessage('导入失败：没有可应用的审核记录（跳过 ' + skipped + ' 条）。请检查 image_id / cuts / side 是否合法。', 'error');
      } else {
        setMessage('已导入 ' + applied + ' 图审核记录' + (skipped ? '，跳过 ' + skipped + ' 条' : '') + '。', 'ok');
      }
    };
    rd.onerror = function () { setMessage('导入失败：文件读取错误。', 'error'); };
    rd.readAsText(file, 'utf-8');
  }

  /* --------------------------------------------------------------- 主渲染 */
  function renderAll() {
    state.pendingPlan = null;
    state.pendingPhoto = null;
    syncImages();
    renderTitle();
    var noteEl = $('#note'); if (noteEl && noteEl.value !== (cst().note || '')) noteEl.value = cst().note || '';
    renderProposal();
    renderMark();
    renderSplitStatus();
    renderAnswersMeta();
    renderPlan();
    drawPhoto();
    updatePhotoStatus();
    renderChoices();
    renderViewer();
  }
  function goImage(i) {
    if (i < 0 || i >= cases.length) return;
    state.index = i;
    state.recordIndex = 0;
    state.space = 0;
    state.pendingPlan = null;
    state.pendingPhoto = null;
    state.drag = null;
    var sel = $('#space'); if (sel) sel.value = '0';
    var note = $('#note'); if (note) note.value = cst().note || '';
    renderAll();
  }
  function goRecord(i) {
    var recs = recordsOf(cur());
    if (i < 0 || i >= recs.length) return;
    state.recordIndex = i;
    renderAnswersMeta();
    renderChoices();
    renderViewer();
  }

  /* --------------------------------------------------------------- 事件绑定 */
  function setSpace(i) {
    state.space = i;
    state.pendingPlan = null;
    state.pendingPhoto = null;
    var sel = $('#space'); if (sel) sel.value = String(i);
    renderPlan();
    renderSplitStatus();
    updatePhotoStatus();
    drawPhoto();
  }
  function bindEvents() {
    $('#prev').addEventListener('click', function () { goImage(state.index - 1); });
    $('#next').addEventListener('click', function () { goImage(state.index + 1); });
    $('#images').addEventListener('change', function (e) { goImage(Number(e.target.value)); });

    $('#space').addEventListener('change', function (e) { setSpace(Number(e.target.value)); });
    $('#orth').addEventListener('change', function (e) { state.orth = !!e.target.checked; save(); });
    $('#flip').addEventListener('click', function () {
      var s = cst(), cut = s.cuts[state.space];
      if (!cut) { setMessage(SPACES[state.space].name + '还没有停止边，请先点两点切分。', 'error'); return; }
      var prev = cloneCuts(s.cuts);
      s.cuts[state.space] = { line: cut.line, side: -cut.side };
      pushHistory(s, prev);
      s.mark = null; s.updatedAt = now();
      save(); refreshAfterEdit();
      setMessage('已翻转' + SPACES[state.space].name + '的保留侧。', 'ok');
    });
    $('#reset').addEventListener('click', function () {
      var s = cst();
      var prev = cloneCuts(s.cuts);
      s.cuts = cloneCuts(cur().cuts);
      s.mark = null;
      pushHistory(s, prev);
      s.updatedAt = now();
      save(); refreshAfterEdit();
      setMessage('已恢复本图预切。', 'ok');
    });
    $('#undo').addEventListener('click', function () {
      var s = cst();
      if (!s.history.length) { setMessage('没有可撤销的切分记录。', 'error'); return; }
      s.cuts = cloneCuts(s.history.pop());
      s.mark = null;
      s.updatedAt = now();
      save(); refreshAfterEdit();
      setMessage('已撤销上一步切分。', 'ok');
    });
    $('#clear').addEventListener('click', function () {
      var s = cst();
      var prev = cloneCuts(s.cuts);
      s.cuts = [null, null];
      s.cut = null;
      s.mark = null;
      pushHistory(s, prev);
      s.updatedAt = now();
      save(); refreshAfterEdit();
      setMessage('已恢复待切分：请分别为空间1、空间2点两点定义停止边。', 'ok');
    });

    var noteEl = $('#note');
    noteEl.addEventListener('input', function (e) {
      var s = cst();
      s.note = String(e.target.value || '');
      s.mark = null;
      s.updatedAt = now();
      clearTimeout(noteEl._t);
      noteEl._t = setTimeout(function () { save(); syncImages(); renderMark(); renderAnswersMeta(); }, 250);
    });
    $('#yaw').addEventListener('input', function () { drawPhoto(); });
    $('#photoEdit').addEventListener('change', function () {
      state.pendingPhoto = null;
      drawPhoto();
    });

    $('#aprev').addEventListener('click', function () { goRecord(state.recordIndex - 1); });
    $('#anext').addEventListener('click', function () { goRecord(state.recordIndex + 1); });
    $('#answers').addEventListener('change', function (e) {
      state.recordIndex = Number(e.target.value);
      renderAnswersMeta();
      renderChoices();
      renderViewer();
    });

    $('#export').addEventListener('click', exportReview);
    $('#import').addEventListener('change', function (e) {
      var f = e.target.files && e.target.files[0];
      if (f) importReview(f);
      e.target.value = '';
    });

    // 俯视图交互
    var svg = $('#plan');
    svg.addEventListener('pointerdown', function (ev) {
      if (ev.button !== 0) return;
      var t = ev.target;
      var handle = t.closest ? t.closest('[data-handle]') : null;
      if (handle) {
        var i = Number(handle.dataset.space);
        setSpace(i);
        var s = cst(); var cut = s.cuts[i];
        if (!cut) return;
        state.drag = { space: i, prev: cloneCuts(s.cuts), orig: cloneCuts([cut])[0], start: planToBev(ev), moved: false };
        try { svg.setPointerCapture(ev.pointerId); } catch (err) { /* ignore */ }
        ev.preventDefault();
        return;
      }
      var pend = state.pendingPlan;
      if (pend && pend.space === state.space) {
        state.pendingPlan = null;
        applyTwoPoint(state.space, [pend.pts[0], planToBev(ev)], 'plan');
        return;
      }
      var lineEl = t.closest ? t.closest('[data-space]') : null;
      if (lineEl) { setSpace(Number(lineEl.dataset.space)); return; }
      if (!(t === svg || (t.dataset && t.dataset.bg))) return;
      state.pendingPlan = { space: state.space, pts: [planToBev(ev)] };
      renderPlan();
      setMessage('已点第 1 点，请在俯视图再点第 2 点确定' + SPACES[state.space].name + '停止边。');
    });
    svg.addEventListener('pointermove', function (ev) {
      if (!state.drag) return;
      var s = cst();
      var i = state.drag.space;
      var cut = s.cuts[i];
      if (!cut) return;
      var p = planToBev(ev);
      var n = cutNormal(state.drag.orig);
      var d = (p[0] - state.drag.start[0]) * n[0] + (p[1] - state.drag.start[1]) * n[1];
      if (Math.abs(d) > 1e-9) state.drag.moved = true;
      s.cuts[i] = normalizeLine({
        line: state.drag.orig.line.map(function (q) { return [q[0] + n[0] * d, q[1] + n[1] * d]; }),
        side: state.drag.orig.side
      });
      renderPlan();
      renderSplitStatus();
    });
    function endDrag() {
      if (!state.drag) return;
      var drag = state.drag;
      state.drag = null;
      var s = cst();
      if (drag.moved) {
        pushHistory(s, drag.prev);
        s.mark = null;
        s.updatedAt = now();
        save();
      }
      renderPlan();
      drawPhoto();
      renderSplitStatus();
      renderMark();
      renderAnswersMeta();
      syncImages();
      renderChoices();
    }
    svg.addEventListener('pointerup', endDrag);
    svg.addEventListener('pointercancel', endDrag);

    // 原图交互
    var cv = $('#photo');
    cv.addEventListener('pointerdown', function (ev) {
      if (ev.button !== 0) return;
      if (!$('#photoEdit').checked) return;
      var p = photoToGround(ev);
      if (!p) return;
      ev.preventDefault();
      var pend = state.pendingPhoto;
      if (pend && pend.space === state.space) {
        state.pendingPhoto = null;
        applyTwoPoint(state.space, [pend.pts[0], p], 'photo');
      } else {
        state.pendingPhoto = { space: state.space, pts: [p] };
        drawPhoto();
        updatePhotoStatus();
        setMessage('已点第 1 个地面点，请在原图再点一点。');
      }
    });

    // 键盘：左右切换图（输入控件内不拦截）；Esc 取消未完成的两点
    document.addEventListener('keydown', function (ev) {
      var tag = (ev.target && ev.target.tagName) || '';
      if (/INPUT|SELECT|TEXTAREA/.test(tag)) return;
      if (ev.key === 'Escape') {
        if (state.pendingPlan || state.pendingPhoto) {
          state.pendingPlan = null; state.pendingPhoto = null;
          renderPlan(); drawPhoto(); updatePhotoStatus();
          setMessage('已取消未完成的两点。');
        }
        return;
      }
      if (ev.key === 'ArrowLeft') { ev.preventDefault(); goImage(state.index - 1); }
      else if (ev.key === 'ArrowRight') { ev.preventDefault(); goImage(state.index + 1); }
      // 逐份作答快捷键：1 可用 / 2 需修正 / 3 无法判断 / N 或空格 下一份
      else if (ev.key === '1' || ev.key === '2' || ev.key === '3') {
        var vmap = { '1': 'pass', '2': 'fix', '3': 'unsure' };
        var vbtn = document.querySelector('#choices [data-verdict="' + vmap[ev.key] + '"]');
        if (vbtn) { ev.preventDefault(); vbtn.click(); }
      }
      else if (ev.key === 'n' || ev.key === 'N' || ev.key === ' ') {
        var nx = $('#anext');
        if (nx && !nx.disabled) { ev.preventDefault(); nx.click(); }
      }
    });
  }

  /* --------------------------------------------------------------- 启动 */
  function init() {
    if (!D || !D.cases || !D.cases.length) return;
    // 动态补一个“标记本图已审”按钮（原 HTML 未提供该控件）
    var proposal = $('#proposal');
    if (proposal && !$('#markReviewed')) {
      var p = document.createElement('p');
      p.className = 'muted';
      p.id = 'markWrap';
      p.style.marginTop = '6px';
      p.innerHTML = '<button type="button" id="markReviewed">标记本图已审</button> <span id="reviewState"></span>';
      proposal.insertAdjacentElement('afterend', p);
      $('#markReviewed').addEventListener('click', function () {
        var s = cst();
        s.mark = isReviewed(state.index) ? 'todo' : 'done';
        s.updatedAt = now();
        save();
        renderMark(); syncImages(); renderAnswersMeta();
      });
      renderMark._bound = true;
    }
    renderMark._bound = true;
    // 快捷键提示（只加一行说明，不改按钮逻辑）
    var prog = $('#progress');
    if (prog && !$('#shortcutHint')) {
      var hint = document.createElement('span');
      hint.id = 'shortcutHint';
      hint.className = 'muted';
      hint.style.marginLeft = '10px';
      hint.textContent = '快捷键：1 可用 · 2 需修正 · 3 无法判断 · N/空格 下一份';
      prog.insertAdjacentElement('afterend', hint);
    }
    bindEvents();
    loadStore();
    var note = $('#note'); if (note) note.value = cst().note || '';
    renderAll();
    if (typeof setMessage === 'function') setMessage('20 图已逐图预切；选择即保存到浏览器本地。导出 JSON 可交回。', 'ok');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
