// ==UserScript==
// @name         HoHoNet Helper Debug Staff
// @namespace    http://tampermonkey.net/
// @version      0.23-debug
// @description  调试/巡检版：连接 Label Studio 与 HoHoNet 3D 查看器，可本地禁用 active_time
// @author       HoHoNet
// @match        http://175.178.71.217:8080/*
// @match        https://175.178.71.217:8080/*
// @match        http://localhost:8080/*
// @match        https://localhost:8080/*
// @match        http://127.0.0.1:8080/*
// @match        https://127.0.0.1:8080/*
// ==/UserScript==

(function () {
  "use strict";

  // 防止在 iframe 中运行 (避免重复的调试面板)
  if (window.top !== window.self) return;

  // 防止同一页面同时运行多个 HoHoNet userscript（例如旧版+新版同时启用）
  // 这会导致重复热键注册、重复观察器与状态树报错。
  if (window.__HOHONET_HELPER_ACTIVE__) {
    console.warn("HoHoNet Helper: 检测到已存在运行实例，当前脚本跳过初始化。");
    return;
  }
  window.__HOHONET_HELPER_ACTIVE__ = true;

  // 运行时再做一道闸门：不是 Label Studio 页面就立刻退出。
  // 这样即使 @match 写得太宽，也不会在非标注/非 LS 页面计时或发日志。
  function isLikelyLabelStudioPage() {
    try {
      // 常见的 Label Studio 根节点/结构
      if (
        document.querySelector("#label-studio") ||
        document.querySelector(".ls-room") ||
        document.querySelector(".lsf-main-view") ||
        document.querySelector(".ls-main-view")
      ) {
        return true;
      }
      // 兜底：存在 LabelStudio 全局实例
      if (window.LabelStudio && window.LabelStudio.instances) return true;
    } catch (e) {}
    return false;
  }

  // 区分“进入了 LS 网站” vs “正在标注任务页面”
  function isLikelyAnnotationPage() {
    try {
      // URL 带 task 参数，或路径包含 /tasks/<id>
      const params = new URLSearchParams(window.location.search);
      if (params.get("task")) return true;
      if (/\/tasks\/\d+/.test(window.location.pathname)) return true;
      // 有主标注图像也认为是标注页
      const img = findMainImage?.();
      if (img) return true;
    } catch (e) {}
    return false;
  }

  // v0.20 修复: 不在此处做早期检查，让 tick 自己决定是否运行
  // 这样可以处理页面延迟加载和 SPA 切换的情况

  const IFRAME_ID = "hohonet-iframe";
  const BUTTON_ID = "hohonet-refresh-btn";
  const WRAPPER_ID = "hohonet-wrapper";
  const DEBUG_ID = "hohonet-debug-panel";
  const OVERLAY_ID = "hohonet-overlay";
  const TOGGLE_BTN_ID = "hohonet-toggle-labels-btn";
  const LABELS_VISIBLE_KEY = "hohonet_labels_visible"; // sessionStorage

  // ---- 部署配置（中文）----
  // 推荐在浏览器控制台设置（一次即可）：
  //   localStorage.setItem('HOHONET_HELPER_BASE_URL', 'http://175.178.71.217:8000');
  // 如果你把 /tools 和 /log_time 反代到 LS 同源，也可设置为：
  //   localStorage.setItem('HOHONET_HELPER_BASE_URL', location.origin);
  function getHelperBaseUrl() {
    try {
      return (
        window.localStorage.getItem("HOHONET_HELPER_BASE_URL") ||
        "http://175.178.71.217:8000"
      );
    } catch (e) {
      return "http://175.178.71.217:8000";
    }
  }

  // Optional: protect /log_time from public abuse.
  // Set once in browser console:
  //   localStorage.setItem('HOHONET_LOG_TOKEN', '<your-secret>')
  function getLogToken() {
    try {
      return window.localStorage.getItem("HOHONET_LOG_TOKEN") || "";
    } catch (e) {
      return "";
    }
  }

  // 3D viewer 可单独指定基址；若已把 /tools 反代到 LS 同源，建议设为 location.origin。
  function getViewerBaseUrl() {
    try {
      return (
        window.localStorage.getItem("HOHONET_VIEWER_BASE_URL") ||
        getHelperBaseUrl()
      );
    } catch (e) {
      return getHelperBaseUrl();
    }
  }

  // debug/staff 脚本默认不计时。
  // 若确实需要在调试脚本下临时开启计时：
  //   localStorage.setItem('HOHONET_ENABLE_DEBUG_ACTIVE_TIME', '1')
  // 如需强制关闭：
  //   localStorage.setItem('HOHONET_DISABLE_ACTIVE_TIME', '1')
  function isActiveTimeLoggingDisabled() {
    try {
      const forcedDisable =
        window.localStorage.getItem("HOHONET_DISABLE_ACTIVE_TIME") === "1";
      const explicitEnable =
        window.localStorage.getItem("HOHONET_ENABLE_DEBUG_ACTIVE_TIME") === "1";
      return forcedDisable || !explicitEnable;
    } catch (e) {
      return true;
    }
  }

  function maskToken(t) {
    if (!t) return "";
    const s = String(t);
    if (s.length <= 6) return "***";
    return `${s.slice(0, 3)}***${s.slice(-3)}`;
  }

  const HOHONET_VIS_3D_URL = (sessionId) =>
    `${getViewerBaseUrl()}/tools/vis_3d.html?v=${sessionId}`;
  const HOHONET_LOG_TIME_URL = () => `${getHelperBaseUrl()}/log_time`;
  const HOHONET_ASSET_URL = (filename) =>
    `${getHelperBaseUrl()}/assets/${filename}`;

  // 右下角调试面板默认关闭（避免每秒更新造成“闪”）。
  // 需要时手动开启：
  //   localStorage.setItem('HOHONET_DEBUG_PANEL', '1')
  // 关闭：
  //   localStorage.removeItem('HOHONET_DEBUG_PANEL')
  function isDebugPanelEnabled() {
    try {
      return window.localStorage.getItem("HOHONET_DEBUG_PANEL") === "1";
    } catch (e) {
      return false;
    }
  }

  // 清理现有的 UI 以防止重新加载时重复
  const existingWrapper = document.getElementById(WRAPPER_ID);
  if (existingWrapper) existingWrapper.remove();
  const existingDebug = document.getElementById(DEBUG_ID);
  if (existingDebug) existingDebug.remove();
  const existingOverlay = document.getElementById(OVERLAY_ID);
  if (existingOverlay) existingOverlay.remove();

  const SCRIPT_VERSION = "0.23-debug";
  console.log(`HoHoNet Helper: 已加载 (v${SCRIPT_VERSION})`);
  console.log(
    "HoHoNet debug active_time: disabled by default; enable with localStorage.HOHONET_ENABLE_DEBUG_ACTIVE_TIME=1",
  );
  console.log(
    "HoHoNet viewer base: set localStorage.HOHONET_VIEWER_BASE_URL = location.origin when /tools is reverse-proxied on LS origin",
  );

  // --- 调试面板 ---
  function updateDebug(msg) {
    if (!isDebugPanelEnabled()) {
      const existing = document.getElementById(DEBUG_ID);
      if (existing) existing.remove();
      return;
    }
    let panel = document.getElementById(DEBUG_ID);
    if (!panel) {
      panel = document.createElement("div");
      panel.id = DEBUG_ID;
      panel.style.cssText =
        "position: fixed; bottom: 10px; right: 10px; background: rgba(0,0,0,0.8); color: #0f0; padding: 10px; z-index: 9999; font-family: monospace; font-size: 12px; pointer-events: none; white-space: pre-wrap;";
      document.body.appendChild(panel);
    }
    panel.innerText = `HoHoNet 调试 (v${SCRIPT_VERSION}):\n` + msg;
  }

  function getLabelsVisible() {
    try {
      const v = window.sessionStorage.getItem(LABELS_VISIBLE_KEY);
      if (v === null) return true;
      return v === "1";
    } catch (e) {
      return true;
    }
  }

  function setLabelsVisible(visible) {
    try {
      window.sessionStorage.setItem(LABELS_VISIBLE_KEY, visible ? "1" : "0");
    } catch (e) {}
  }

  function applyToggleBtnState(toggleBtn, visible) {
    if (!toggleBtn) return;
    if (visible) {
      toggleBtn.innerText = "🏷️ 隐藏标签";
      toggleBtn.style.background = "#6c757d";
    } else {
      toggleBtn.innerText = "🏷️ 显示标签";
      toggleBtn.style.background = "#28a745";
    }
  }

  function ensureOverlay(img) {
    let overlay = document.getElementById(OVERLAY_ID);
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = OVERLAY_ID;
      overlay.style.cssText =
        "position: fixed; pointer-events: none; z-index: 999999; overflow: hidden;";
      document.body.appendChild(overlay);
    } else {
      // 保证老的 overlay 也按新规则裁剪
      overlay.style.overflow = "hidden";
    }

    // 由 tick/刷新统一控制显示状态
    positionOverlayToImage(img, overlay);
    return overlay;
  }

  function intersectRects(a, b) {
    if (!a || !b) return null;
    const left = Math.max(a.left, b.left);
    const top = Math.max(a.top, b.top);
    const right = Math.min(a.right, b.right);
    const bottom = Math.min(a.bottom, b.bottom);
    if (right <= left || bottom <= top) return null;
    return {
      left,
      top,
      right,
      bottom,
      width: right - left,
      height: bottom - top,
    };
  }

  function computeVisibleRectForImage(img) {
    // imgRect: 图片渲染后的矩形（可能包含被父容器裁剪掉的部分）
    // visibleRect: imgRect 与所有“裁剪型祖先”(overflow!=visible) 的交集
    try {
      const imgRect = img.getBoundingClientRect();
      if (!imgRect || imgRect.width <= 1 || imgRect.height <= 1) {
        return { imgRect: null, visibleRect: null };
      }

      let visible = {
        left: imgRect.left,
        top: imgRect.top,
        right: imgRect.right,
        bottom: imgRect.bottom,
        width: imgRect.width,
        height: imgRect.height,
      };

      // 向上找可能裁剪图片的容器（zoom/pan 通常发生在这里）
      let el = img.parentElement;
      while (el && el !== document.body && el !== document.documentElement) {
        const style = getComputedStyle(el);
        const overflowX = style.overflowX;
        const overflowY = style.overflowY;
        const isClipping =
          overflowX !== "visible" ||
          overflowY !== "visible" ||
          style.overflow === "hidden";

        if (isClipping) {
          const r = el.getBoundingClientRect();
          // 过滤掉异常的 0 尺寸容器
          if (r && r.width > 0 && r.height > 0) {
            const next = intersectRects(visible, r);
            if (!next) break;
            visible = next;
          }
        }

        el = el.parentElement;
      }

      return { imgRect, visibleRect: visible };
    } catch (e) {
      return { imgRect: null, visibleRect: null };
    }
  }

  function positionOverlayToImage(img, overlay) {
    try {
      const { imgRect, visibleRect } = computeVisibleRectForImage(img);
      const rect = visibleRect;
      if (!imgRect || !rect || rect.width <= 1 || rect.height <= 1) {
        overlay.style.left = "0px";
        overlay.style.top = "0px";
        overlay.style.width = "0px";
        overlay.style.height = "0px";
        overlay.dataset.imgLeft = "";
        overlay.dataset.imgTop = "";
        overlay.dataset.imgWidth = "";
        overlay.dataset.imgHeight = "";
        return null;
      }

      overlay.style.left = `${rect.left}px`;
      overlay.style.top = `${rect.top}px`;
      overlay.style.width = `${rect.width}px`;
      overlay.style.height = `${rect.height}px`;
      // 存下来，用于 badge 从“图片坐标系”映射到“可视区域坐标系”
      overlay.dataset.imgLeft = String(imgRect.left);
      overlay.dataset.imgTop = String(imgRect.top);
      overlay.dataset.imgWidth = String(imgRect.width);
      overlay.dataset.imgHeight = String(imgRect.height);
      return rect;
    } catch (e) {
      return null;
    }
  }

  function positionOverlayBadges(overlay, rect) {
    if (!overlay || !rect) return;
    const imgLeft = parseFloat(overlay.dataset.imgLeft);
    const imgTop = parseFloat(overlay.dataset.imgTop);
    const imgWidth = parseFloat(overlay.dataset.imgWidth);
    const imgHeight = parseFloat(overlay.dataset.imgHeight);
    if (
      ![imgLeft, imgTop, imgWidth, imgHeight].every((v) => Number.isFinite(v))
    ) {
      return;
    }

    const children = Array.from(overlay.children);
    children.forEach((badge) => {
      const pctX = parseFloat(badge.dataset.pctx);
      const pctY = parseFloat(badge.dataset.pcty);
      if (Number.isFinite(pctX) && Number.isFinite(pctY)) {
        // 超出图片范围的点不显示（例如 1/5/6 这类跑到框外的）
        if (pctX < 0 || pctX > 100 || pctY < 0 || pctY > 100) {
          badge.style.display = "none";
          return;
        }

        // 先算点在 viewport 的绝对位置（基于完整图片矩形）
        const absX = imgLeft + (pctX * imgWidth) / 100;
        const absY = imgTop + (pctY * imgHeight) / 100;

        // 如果点不在“图片可视区域”内，隐藏
        if (
          absX < rect.left ||
          absX > rect.right ||
          absY < rect.top ||
          absY > rect.bottom
        ) {
          badge.style.display = "none";
          return;
        }

        // 映射到 overlay 内部坐标
        const x = absX - rect.left;
        const y = absY - rect.top;

        badge.style.display = "block";
        badge.style.left = `${x}px`;
        badge.style.top = `${y}px`;
      }
    });
  }

  // --- Store 发现 (查找 Label Studio 实例) ---
  function getStore() {
    // 1. 标准全局变量
    if (
      window.LabelStudio &&
      window.LabelStudio.instances &&
      window.LabelStudio.instances.length > 0
    ) {
      return window.LabelStudio.instances[0].store;
    }
    // 2. 旧版全局变量
    if (window.H) return window.H;

    // 3. React 内部属性 (终极手段)
    const root =
      document.querySelector(".ls-room") ||
      document.querySelector("#label-studio") ||
      document.querySelector(".lsf-main-view");
    if (root) {
      for (const key in root) {
        if (key.startsWith("__reactFiber")) {
          // 向上遍历以在 props 或 context 中找到 store
          let fiber = root[key];
          while (fiber) {
            if (
              fiber.stateNode &&
              fiber.stateNode.props &&
              fiber.stateNode.props.store
            ) {
              return fiber.stateNode.props.store;
            }
            if (fiber.memoizedProps && fiber.memoizedProps.store) {
              return fiber.memoizedProps.store;
            }
            fiber = fiber.return;
          }
        }
      }
    }

    return null;
  }

  function normalizeChoiceToken(raw) {
    const s = String(raw || "").trim();
    const l = s.toLowerCase();
    if (!s) return "";

    if (l === "trivial" || l.includes("(trivial)") || s.includes("非常简单"))
      return "trivial";
    if (
      l === "acceptable" ||
      l.includes("acceptable") ||
      s.includes("模型标注质量好")
    )
      return "acceptable";

    return l;
  }

  function matchesFieldName(actual, expected) {
    const a = String(actual || "")
      .trim()
      .toLowerCase();
    const e = String(expected || "")
      .trim()
      .toLowerCase();
    if (!a || !e) return false;
    if (a === e) return true;
    if (a.endsWith(`.${e}`) || a.endsWith(`:${e}`) || a.endsWith(`/${e}`))
      return true;
    if (a.includes(e)) return true;
    return false;
  }

  function isTrivialToken(token) {
    const t = String(token || "")
      .trim()
      .toLowerCase();
    return t === "trivial" || t.includes("trivial") || t.includes("非常简单");
  }

  function isAcceptableToken(token) {
    const t = String(token || "")
      .trim()
      .toLowerCase();
    return (
      t === "acceptable" ||
      t.includes("acceptable") ||
      t.includes("模型标注质量好")
    );
  }

  function isMetaGuardDebugEnabled() {
    try {
      return (
        window.localStorage.getItem("HOHONET_META_GUARD_DEBUG") === "1" ||
        window.localStorage.getItem("HOHONET_DEBUG_META_GUARD") === "1" ||
        window.localStorage.getItem("HOHONET_META_DEBUG") === "1"
      );
    } catch (e) {
      return false;
    }
  }

  function metaGuardDebug(...args) {
    if (!isMetaGuardDebugEnabled()) return;
    console.log("[HoHoNet MetaGuard]", ...args);
  }

  function toArrayFromMaybeObservable(value) {
    try {
      if (!value) return [];
      if (Array.isArray(value)) return value;
      if (typeof value.toJSON === "function") {
        const j = value.toJSON();
        if (Array.isArray(j)) return j;
      }
      if (typeof value[Symbol.iterator] === "function") {
        return Array.from(value);
      }
    } catch (e) {}
    return [];
  }

  function collectSelectedResults(store) {
    const out = [];
    try {
      const selected = store?.annotationStore?.selected;
      if (!selected) return out;

      if (typeof selected?.serializeCompletion === "function") {
        const ser = selected.serializeCompletion();
        const serRes = toArrayFromMaybeObservable(ser?.result);
        if (serRes.length) out.push(...serRes);
      }

      if (typeof selected?.toJSON === "function") {
        const j = selected.toJSON();
        const jRes = toArrayFromMaybeObservable(j?.result || j?.results);
        if (jRes.length) out.push(...jRes);
      }

      const direct = toArrayFromMaybeObservable(selected?.results);
      if (direct.length) out.push(...direct);
    } catch (e) {
      metaGuardDebug("collectSelectedResults error", e);
    }
    return out;
  }

  function extractChoicesFromResult(result) {
    try {
      if (!result || typeof result !== "object") return [];
      const candidates = [
        result?.value,
        result?.area?.value,
        result?.origin?.value,
        result,
        result?.area,
        result?.origin,
      ];

      const out = [];
      for (const source of candidates) {
        if (!source || typeof source !== "object") continue;
        const choices = Array.isArray(source.choices) ? source.choices : [];
        if (!choices.length) continue;
        const normalized = choices
          .map((x) => normalizeChoiceToken(x))
          .filter(Boolean);
        for (const v of normalized) {
          if (!out.includes(v)) out.push(v);
        }
      }
      return out;
    } catch (e) {
      return [];
    }
  }

  function getResultFromName(result) {
    try {
      return String(
        result?.from_name ||
          result?.value?.from_name ||
          result?.area?.from_name ||
          result?.area?.value?.from_name ||
          result?.origin?.from_name ||
          result?.origin?.value?.from_name ||
          "",
      ).trim();
    } catch (e) {
      return "";
    }
  }

  function collectFromDomContainer(container) {
    const out = [];
    if (!container) return out;

    const checkedInputs = container.querySelectorAll(
      "input[type='checkbox']:checked, input[type='radio']:checked",
    );
    checkedInputs.forEach((input) => {
      let text = "";
      const id = input.getAttribute("id");
      if (id) {
        const label = container.querySelector(`label[for='${id}']`);
        if (label && label.innerText) text = label.innerText;
      }
      if (!text) {
        const near = input.closest("label,li,div,span");
        text = near?.innerText || input?.value || "";
      }
      const token = normalizeChoiceToken(text);
      if (token && !out.includes(token)) out.push(token);
    });

    const ariaChecked = container.querySelectorAll(
      "[role='checkbox'][aria-checked='true'], [role='radio'][aria-checked='true']",
    );
    ariaChecked.forEach((node) => {
      const token = normalizeChoiceToken(
        node?.innerText || node?.textContent || "",
      );
      if (token && !out.includes(token)) out.push(token);
    });

    return out;
  }

  function findMetaSectionContainer(fieldName) {
    const probes = Array.from(
      document.querySelectorAll("h1,h2,h3,h4,h5,h6,div,span,label"),
    );
    const patterns =
      fieldName === "difficulty"
        ? [/困难因素/, /difficulty/i]
        : [/模型初始化问题/, /model\s*issue/i];

    for (const el of probes) {
      const txt = String(el?.innerText || "").trim();
      if (!txt || txt.length > 180) continue;
      if (!patterns.some((re) => re.test(txt))) continue;
      const container = el.closest("section,fieldset,div");
      if (container) return container;
    }
    return null;
  }

  function getSelectedChoicesByFieldFromDom(fieldName) {
    const container = findMetaSectionContainer(fieldName);
    return collectFromDomContainer(container);
  }

  function isFieldPresent(store, fieldName) {
    try {
      const results = collectSelectedResults(store);
      for (const r of results) {
        const fromName = getResultFromName(r);
        if (matchesFieldName(fromName, fieldName)) return true;
      }
      return !!findMetaSectionContainer(fieldName);
    } catch (e) {
      return !!findMetaSectionContainer(fieldName);
    }
  }

  function getSelectedChoicesByField(store, fieldName) {
    try {
      const results = collectSelectedResults(store);
      const out = [];
      for (const r of results) {
        const fromName = getResultFromName(r);
        if (!matchesFieldName(fromName, fieldName)) continue;
        const vals = extractChoicesFromResult(r);
        for (const v of vals) {
          if (v && !out.includes(v)) out.push(v);
        }
      }

      if (out.length > 0) {
        metaGuardDebug(`${fieldName} from store`, out);
        return out;
      }

      const domVals = getSelectedChoicesByFieldFromDom(fieldName);
      metaGuardDebug(`${fieldName} from DOM fallback`, domVals);
      return domVals;
    } catch (e) {
      metaGuardDebug(`getSelectedChoicesByField error for ${fieldName}`, e);
      return [];
    }
  }

  function getTaskCondition(store) {
    const paths = [
      store?.taskStore?.selected?.data?.condition,
      store?.task?.data?.condition,
      store?.annotationStore?.selected?.task?.data?.condition,
    ];
    for (const p of paths) {
      if (p !== undefined && p !== null && String(p).trim()) {
        return String(p).trim();
      }
    }
    return "";
  }

  const META_GUARD_REJECT_LOG_KEY = "HOHONET_META_GUARD_REJECTIONS";
  const META_GUARD_REJECT_STATS_KEY = "HOHONET_META_GUARD_REJECT_STATS";
  const META_GUARD_REJECT_LOG_MAX = 200;

  function loadJsonFromLocalStorage(key, fallback) {
    try {
      const raw = window.localStorage.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch (e) {
      return fallback;
    }
  }

  function saveJsonToLocalStorage(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {}
  }

  function recordMetaGuardRejection({ store, errs, difficulty, modelIssue }) {
    try {
      const now = Date.now();
      const taskId = getTaskId?.() || "unknown";
      const projectId = getProjectId?.() || "unknown";
      const projectName = getProjectName?.() || "unknown";
      const annotatorId = getAnnotatorId?.() || "unknown";
      const condition = getTaskCondition(store);

      const event = {
        timestamp: now,
        task_id: taskId,
        project_id: projectId,
        project_name: projectName,
        annotator_id: annotatorId,
        session_id: sessionId,
        script_version: SCRIPT_VERSION,
        condition,
        reject_reasons: Array.isArray(errs) ? errs.slice(0, 20) : [],
        difficulty: Array.isArray(difficulty) ? difficulty.slice(0, 50) : [],
        model_issue: Array.isArray(modelIssue) ? modelIssue.slice(0, 50) : [],
      };

      const log = loadJsonFromLocalStorage(META_GUARD_REJECT_LOG_KEY, []);
      const nextLog = Array.isArray(log) ? log : [];
      nextLog.push(event);
      if (nextLog.length > META_GUARD_REJECT_LOG_MAX) {
        nextLog.splice(0, nextLog.length - META_GUARD_REJECT_LOG_MAX);
      }
      saveJsonToLocalStorage(META_GUARD_REJECT_LOG_KEY, nextLog);

      const stats = loadJsonFromLocalStorage(META_GUARD_REJECT_STATS_KEY, {
        total_rejected: 0,
        by_reason: {},
        last_reject_ts: 0,
      });
      const nextStats =
        stats && typeof stats === "object" && !Array.isArray(stats)
          ? stats
          : { total_rejected: 0, by_reason: {}, last_reject_ts: 0 };
      nextStats.total_rejected = (nextStats.total_rejected || 0) + 1;
      nextStats.last_reject_ts = now;
      if (!nextStats.by_reason || typeof nextStats.by_reason !== "object") {
        nextStats.by_reason = {};
      }
      for (const r of Array.isArray(errs) ? errs : []) {
        const k = String(r || "").trim();
        if (!k) continue;
        nextStats.by_reason[k] = (nextStats.by_reason[k] || 0) + 1;
      }
      saveJsonToLocalStorage(META_GUARD_REJECT_STATS_KEY, nextStats);
    } catch (e) {
      metaGuardDebug("recordMetaGuardRejection error", e);
    }
  }

  function validateMetaChoices(store) {
    const errors = [];
    const hasDifficultyField = isFieldPresent(store, "difficulty");
    const hasModelIssueField = isFieldPresent(store, "model_issue");
    const difficulty = getSelectedChoicesByField(store, "difficulty");
    const modelIssue = hasModelIssueField
      ? getSelectedChoicesByField(store, "model_issue")
      : [];
    const condition = getTaskCondition(store).toLowerCase();
    metaGuardDebug("validateMetaChoices", {
      hasDifficultyField,
      hasModelIssueField,
      difficulty,
      modelIssue,
      condition,
    });

    const hasTrivial = difficulty.some((x) => isTrivialToken(x));
    const hasNonTrivial = difficulty.some((x) => !isTrivialToken(x));
    const hasAcceptable = modelIssue.some((x) => isAcceptableToken(x));
    const hasNonAcceptable = modelIssue.some((x) => !isAcceptableToken(x));
    metaGuardDebug("meta-eval", {
      difficulty,
      hasTrivial,
      hasNonTrivial,
      modelIssue,
      hasAcceptable,
      hasNonAcceptable,
      condition,
    });

    if (hasDifficultyField && hasTrivial && hasNonTrivial) {
      errors.push("Difficulty 冲突：trivial 不能与其他困难标签共存");
    }
    if (hasModelIssueField && hasAcceptable && hasNonAcceptable) {
      errors.push("Model Issue 冲突：acceptable 不能与其他 issue 共存");
    }

    return errors;
  }

  function shouldGuardAction(target) {
    if (!target) return false;
    const text = String(
      target.innerText || target.textContent || "",
    ).toLowerCase();
    const aria = String(
      target.getAttribute?.("aria-label") || "",
    ).toLowerCase();
    const title = String(target.getAttribute?.("title") || "").toLowerCase();
    const testid = String(
      target.getAttribute?.("data-testid") || "",
    ).toLowerCase();
    const merged = `${text} ${aria} ${title} ${testid}`;
    if (!merged.trim()) return false;
    const keys = ["submit", "update", "完成", "提交", "更新"];
    return keys.some((k) => merged.includes(k));
  }

  function installMetaSubmitGuard() {
    if (window.__HOHONET_META_GUARD_INSTALLED__) return;
    window.__HOHONET_META_GUARD_INSTALLED__ = true;

    const isGuardEnabled = () => {
      try {
        return window.localStorage.getItem("HOHONET_STRICT_META_GUARD") !== "0";
      } catch (e) {
        return true;
      }
    };

    const runCheck = () => {
      const store = getStore();
      if (!store) return true;
      const errs = validateMetaChoices(store);
      if (!errs.length) return true;

      // 过程性证据：记录每次被硬阻断的原因/次数（不影响交互）
      try {
        const difficulty = getSelectedChoicesByField(store, "difficulty");
        const hasModelIssueField = isFieldPresent(store, "model_issue");
        const modelIssue = hasModelIssueField
          ? getSelectedChoicesByField(store, "model_issue")
          : [];
        recordMetaGuardRejection({ store, errs, difficulty, modelIssue });
      } catch (e) {}

      const msg = [
        "提交被拦截：检测到元标签不合规。",
        "请修正后再提交：",
        ...errs.map((x) => `- ${x}`),
      ].join("\n");
      alert(msg);
      console.warn("HoHoNet Meta Guard blocked submit:", errs);
      return false;
    };

    document.addEventListener(
      "click",
      (event) => {
        if (!isGuardEnabled() || !isLikelyAnnotationPage()) return;
        const node = event.target?.closest?.("button,[role='button']");
        if (!shouldGuardAction(node)) return;
        if (!runCheck()) {
          event.preventDefault();
          event.stopImmediatePropagation();
        }
      },
      true,
    );

    document.addEventListener(
      "keydown",
      (event) => {
        if (!isGuardEnabled() || !isLikelyAnnotationPage()) return;
        const isSubmitHotkey =
          (event.ctrlKey || event.metaKey) && event.key === "Enter";
        if (!isSubmitHotkey) return;
        if (!runCheck()) {
          event.preventDefault();
          event.stopImmediatePropagation();
        }
      },
      true,
    );

    console.log(
      "HoHoNet Meta Guard: enabled (disable: localStorage.HOHONET_STRICT_META_GUARD=0)",
    );
    console.log(
      "HoHoNet Meta Guard debug keys: HOHONET_META_GUARD_DEBUG=1 or HOHONET_DEBUG_META_GUARD=1",
    );
    console.log(
      "HoHoNet Meta Guard audit: localStorage.HOHONET_META_GUARD_REJECTIONS (capped) and HOHONET_META_GUARD_REJECT_STATS",
    );
  }

  function findSectionContainer() {
    const headers = Array.from(document.querySelectorAll("h3"));
    const header = headers.find(
      (h) => h.textContent && h.textContent.includes("3D Layout Preview"),
    );
    if (!header) return null;
    let sibling = header.nextElementSibling;
    if (
      sibling &&
      (sibling.classList.contains("lsf-object") ||
        sibling.classList.contains("lsf-richtext"))
    ) {
      return sibling;
    }
    return null;
  }

  function findMainImage() {
    // 1. 尝试在主标注区域内查找图像
    // Label Studio 结构通常有 .lsf-main-view 或 .ls-main-view
    const mainView =
      document.querySelector(".lsf-main-view") ||
      document.querySelector(".ls-main-view");
    if (mainView) {
      const imgs = Array.from(mainView.querySelectorAll("img"));
      // 过滤掉图标/缩略图等小图片
      const candidates = imgs.filter(
        (img) => img.naturalWidth > 200 || img.width > 200,
      );
      if (candidates.length > 0) {
        // 返回面积最大的图片
        return candidates.reduce((a, b) =>
          (a.naturalWidth || 0) * (a.naturalHeight || 0) >
          (b.naturalWidth || 0) * (b.naturalHeight || 0)
            ? a
            : b,
        );
      }
    }

    // 2. 备选方案：在整个页面上查找最大的图像
    const allImgs = Array.from(document.querySelectorAll("img"));
    if (allImgs.length > 0) {
      return allImgs.reduce((a, b) => {
        const areaA = (a.naturalWidth || 0) * (a.naturalHeight || 0);
        const areaB = (b.naturalWidth || 0) * (b.naturalHeight || 0);
        return areaA > areaB ? a : b;
      });
    }
    return null;
  }

  function getImageUrlFromStore() {
    try {
      const store = getStore();
      const data = store && store.task && store.task.data;
      if (!data || typeof data !== "object") return null;

      // Common keys first
      const preferredKeys = [
        "image",
        "img",
        "pano",
        "pano_url",
        "panoUrl",
        "url",
        "src",
        "file",
      ];
      for (const k of preferredKeys) {
        const v = data[k];
        if (typeof v === "string" && v.length > 0) return v;
      }

      // Fallback: first string-ish url in task data
      for (const v of Object.values(data)) {
        if (typeof v === "string" && v.length > 0) {
          if (
            v.startsWith("http://") ||
            v.startsWith("https://") ||
            v.startsWith("/")
          ) {
            return v;
          }
        }
      }
    } catch (e) {}
    return null;
  }

  function rewriteTextureUrlForViewer(originalUrl) {
    if (!originalUrl) return originalUrl;
    try {
      const helperBase = new URL(getHelperBaseUrl(), window.location.href);
      const u = new URL(originalUrl, window.location.href);

      // Already same-origin as helper (e.g. both on port 8000)
      if (u.origin === helperBase.origin) return u.toString();

      // Same host but different port (e.g. image is on 8080, helper is on 8000)
      // Route through nginx /ls/ to make it same-origin with the 3D viewer
      if (u.hostname === helperBase.hostname) {
        // Only proxy if it's NOT already on the helper port
        return `${helperBase.origin}/ls${u.pathname}${u.search}`;
      }
      return u.toString();
    } catch (e) {
      return originalUrl;
    }
  }

  function withCacheBust(url) {
    if (!url) return url;
    try {
      const u = new URL(url, window.location.href);
      u.searchParams.set("_hohonet_ts", String(Date.now()));
      return u.toString();
    } catch (e) {
      return url;
    }
  }

  // 生成会话 ID 以防止 iframe 缓存
  const SESSION_ID = Date.now();

  // --- 2D overlay 生命周期管理 ---
  // 修复: 在切任务/切页面时，旧的黄色角点标签(overlay badges)不会自动清理，导致残留。
  let lastTaskIdForOverlay = null;
  let lastAnnotationIdForOverlay = null;

  function getEffectiveState() {
    try {
      const store = getStore();
      const taskId = store?.task?.id ? String(store.task.id) : null;
      const annId = store?.annotationStore?.selected?.id
        ? String(store.annotationStore.selected.id)
        : null;

      // 如果 Store 还没准备好，回退到 URL
      if (!taskId) {
        const params = new URLSearchParams(window.location.search);
        const q = params.get("task");
        return { taskId: q || "unknown", annId: "unknown" };
      }
      return { taskId, annId };
    } catch (e) {
      return { taskId: "unknown", annId: "unknown" };
    }
  }

  function clearOverlay() {
    const overlay = document.getElementById(OVERLAY_ID);
    if (overlay) {
      console.log("HoHoNet: 状态变化 (Task/Annotation)，清理残留标签");
      overlay.remove();
    }
  }

  function tick() {
    let status = "";

    // v0.20 修复: 每次 tick 都检查是否在标注页面
    // 这样可以应对 SPA 导航和延迟加载
    if (!isLikelyLabelStudioPage()) {
      // 非 LS 页面：清理UI但继续运行（以便后续页面切换时能恢复）
      const wrapper = document.getElementById(WRAPPER_ID);
      if (wrapper) wrapper.style.display = "none";
      return;
    }

    if (!isLikelyAnnotationPage()) {
      // 在 LS 网站内，但不是标注页面：隐藏UI
      const wrapper = document.getElementById(WRAPPER_ID);
      if (wrapper) wrapper.style.display = "none";
      status += "页面类型: 非标注页面\n";
      updateDebug(status);
      return;
    }

    // 确保wrapper可见（可能之前被隐藏了）
    const existingWrapper = document.getElementById(WRAPPER_ID);
    if (existingWrapper) existingWrapper.style.display = "block";

    // v0.11 修复: 延迟 store 查找直到交互，以避免 React 干扰
    // let store = getStore(); // 从 tick 中移除

    // --- URL 解析 ---
    let url = null;

    // 检测任务或标注切换
    const stateNow = getEffectiveState();
    if (
      stateNow.taskId !== lastTaskIdForOverlay ||
      stateNow.annId !== lastAnnotationIdForOverlay
    ) {
      lastTaskIdForOverlay = stateNow.taskId;
      lastAnnotationIdForOverlay = stateNow.annId;
      clearOverlay();
    }

    const img = findMainImage();
    if (img) {
      status += "图像: 已找到\n";
      // v0.17 修复: 添加缓存破坏参数
      url = HOHONET_VIS_3D_URL(SESSION_ID);
      if (img.naturalWidth) {
        url += `&w=${img.naturalWidth}&h=${img.naturalHeight}`;
      }

      // 如果已存在覆盖层，持续跟随图片位置（解决缩放/平移偏移）
      const overlay = document.getElementById(OVERLAY_ID);
      if (overlay) {
        const rect = positionOverlayToImage(img, overlay);
        const visible = getLabelsVisible();
        overlay.style.display = visible ? "block" : "none";
        positionOverlayBadges(overlay, rect);
      }
    } else {
      status += "图像: 未找到\n";
    }

    if (url) {
      status += "目标 URL: 就绪\n";
    } else {
      status += "目标 URL: 缺失\n";
    }

    // --- 注入 ---
    const container = findSectionContainer();
    if (!container) {
      updateDebug(status + "容器: 未找到");
      return;
    }

    try {
      // 隐藏原始子元素
      Array.from(container.children).forEach((child) => {
        if (child.id !== WRAPPER_ID) {
          child.style.display = "none";
        }
      });

      // 包装器
      let wrapper = document.getElementById(WRAPPER_ID);
      if (!wrapper) {
        wrapper = document.createElement("div");
        wrapper.id = WRAPPER_ID;
        container.appendChild(wrapper);
      }

      // Iframe
      let iframe = document.getElementById(IFRAME_ID);
      if (!iframe) {
        iframe = document.createElement("iframe");
        iframe.id = IFRAME_ID;
        iframe.style.cssText =
          "width: 100%; height: 400px; border: none; background: #000;";
        wrapper.appendChild(iframe);
      }

      // 更新 URL
      if (url && iframe.dataset.src !== url) {
        if (
          !iframe.dataset.src ||
          (url.includes("data=") && !iframe.dataset.src.includes("data="))
        ) {
          iframe.dataset.src = url;
          iframe.src = url;
        } else if (!iframe.dataset.src) {
          iframe.dataset.src = url;
          iframe.src = url;
        }
      }

      // 按钮
      let btn = document.getElementById(BUTTON_ID);
      if (!btn) {
        btn = document.createElement("button");
        btn.id = BUTTON_ID;
        btn.innerText = "🔄 刷新 3D 视图";
        btn.style.cssText =
          "margin-top: 10px; padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;";

        btn.onclick = function () {
          // v0.11 修复: 仅在点击时查找 store
          const store = getStore();
          if (!store) {
            alert("无法连接到 Label Studio Store。请等待编辑器完全加载。");
            return;
          }
          if (!store.annotationStore || !store.annotationStore.selected) {
            alert("请先选择一个标注。");
            return;
          }

          const results = store.annotationStore.selected.results;
          const points = [];

          // 尺寸
          let W = 1024;
          let H = 512;
          try {
            const urlObj = new URL(iframe.src);
            const params = new URLSearchParams(urlObj.search);
            const pW = parseInt(params.get("w"));
            const pH = parseInt(params.get("h"));
            if (!isNaN(pW)) W = pW;
            if (!isNaN(pH)) H = pH;
          } catch (e) {}

          console.log("HoHoNet: 处理结果:", results);

          // v0.9 修复: 彻底解包
          const clean = (obj) => {
            try {
              return JSON.parse(JSON.stringify(obj));
            } catch (e) {
              return obj;
            }
          };

          // v0.15 修复: 分离关键点和多边形
          const keypoints = [];
          const polyPoints = [];

          results.forEach((r, idx) => {
            // v0.10 修复: 优先检查 r.area
            let source = r;
            if (r.area) source = r.area;

            // 解包
            let val = clean(source);
            if (!val) val = source.toJSON ? source.toJSON() : source;

            console.log(`HoHoNet: 结果 ${idx} (已清理):`, val);

            // 确定类型 (检查 r 和 val)
            const type = r.type || val.type;

            // 1. 关键点 (角点)
            // 兼容: keypointlabels, keypointregion
            if (type === "keypointlabels" || type === "keypointregion") {
              let x, y;
              if (val.x !== undefined) {
                x = val.x;
                y = val.y;
              } else if (val.value && val.value.x !== undefined) {
                x = val.value.x;
                y = val.value.y;
              }

              if (typeof x === "number" && typeof y === "number") {
                const px = (x * W) / 100;
                const py = (y * H) / 100;
                keypoints.push({ x: px, y: py, pctX: x, pctY: y });
              }
            }
            // 2. 多边形 (墙面/表面)
            // 兼容: polygonlabels, polygonregion
            else if (type === "polygonlabels" || type === "polygonregion") {
              let pts = [];
              if (val.points) pts = val.points;
              else if (val.value && val.value.points) pts = val.value.points;

              if (pts && pts.length > 0) {
                // 解析点
                const parsedPts = pts
                  .map((pt) => {
                    if (Array.isArray(pt)) return { x: pt[0], y: pt[1] };
                    if (typeof pt === "object" && pt !== null)
                      return { x: pt.x, y: pt.y };
                    return null;
                  })
                  .filter((p) => p);

                // 将所有点添加到 polyPoints (转换为像素)
                parsedPts.forEach((p) => {
                  polyPoints.push({ x: (p.x * W) / 100, y: (p.y * H) / 100 });
                });
              }
            }
            // 3. 矩形
            // 兼容: rectanglelabels, rectangleregion
            else if (type === "rectanglelabels" || type === "rectangleregion") {
              let x, y, w, h;
              const src = val.value || val;
              x = src.x;
              y = src.y;
              w = src.width;
              h = src.height;

              if ([x, y, w, h].every((v) => typeof v === "number")) {
                const corners = [
                  { x: x, y: y },
                  { x: x + w, y: y },
                  { x: x + w, y: y + h },
                  { x: x, y: y + h },
                ];
                corners.forEach((pt) => {
                  keypoints.push({
                    x: (pt.x * W) / 100,
                    y: (pt.y * H) / 100,
                    pctX: pt.x,
                    pctY: pt.y,
                  });
                });
              }
            }
          });

          // 决策: 优先使用关键点
          if (keypoints.length > 0) {
            console.log("HoHoNet: 使用关键点进行 3D 几何构建");
            points.push(...keypoints);
          } else if (polyPoints.length > 0) {
            console.log("HoHoNet: 未找到关键点，回退到多边形");
            // v0.16 修复: 如果回退到密集多边形则警告用户
            if (polyPoints.length > 20) {
              alert(
                "警告: 未找到 'Corner' (角点)！正在使用密集的墙面线条进行 3D 视图，这可能会导致显示变形。\n\n请确保您的标注中存在 'Corner' 点。",
              );
            }
            points.push(...polyPoints);
          } else {
            alert("未找到点！请绘制关键点、多边形或矩形。");
            return;
          }

          console.log("HoHoNet: 原始点:", points);

          points.sort((a, b) => a.x - b.x);
          const paired = [];
          const used = new Array(points.length).fill(false);
          const threshold = W * 0.05;

          for (let i = 0; i < points.length; i++) {
            if (used[i]) continue;
            let bestJ = -1;
            // 寻找最佳匹配点 (X 轴最近)
            let minDiff = Infinity;

            for (let j = i + 1; j < points.length; j++) {
              if (!used[j]) {
                const diff = Math.abs(points[j].x - points[i].x);
                if (diff < threshold && diff < minDiff) {
                  minDiff = diff;
                  bestJ = j;
                }
              }
            }
            if (bestJ !== -1) {
              used[i] = true;
              used[bestJ] = true;
              paired.push({
                x: (points[i].x + points[bestJ].x) / 2,
                y_ceiling: Math.min(points[i].y, points[bestJ].y),
                y_floor: Math.max(points[i].y, points[bestJ].y),
                originalPoints: [points[i], points[bestJ]],
              });
            }
          }

          console.log("HoHoNet: 配对角点:", paired);

          // --- 2D 覆盖层逻辑 (修复: 缩放/平移后不偏移 + 隐藏状态持久) ---
          try {
            const img = findMainImage();
            if (img) {
              const overlay = ensureOverlay(img);
              // 清空旧标签
              overlay.innerHTML = "";

              const visible = getLabelsVisible();
              overlay.style.display = visible ? "block" : "none";

              // 同步按钮状态（不要在刷新时强制显示）
              const tBtn = document.getElementById(TOGGLE_BTN_ID);
              if (tBtn) applyToggleBtnState(tBtn, visible);

              const rect = positionOverlayToImage(img, overlay);

              paired.forEach((pair, idx) => {
                const label = (idx + 1).toString();
                pair.originalPoints.forEach((p) => {
                  if (p.pctX !== undefined && p.pctY !== undefined) {
                    const badge = document.createElement("div");
                    badge.innerText = label;
                    badge.dataset.pctx = String(p.pctX);
                    badge.dataset.pcty = String(p.pctY);
                    badge.style.cssText = `
                      position: absolute;
                      transform: translate(-50%, -150%);
                      background: rgba(255, 255, 0, 0.9);
                      color: black;
                      font-weight: bold;
                      padding: 2px 6px;
                      border-radius: 4px;
                      font-size: 12px;
                      border: 1px solid black;
                      box-shadow: 0 2px 4px rgba(0,0,0,0.5);
                    `;
                    overlay.appendChild(badge);
                  }
                });
              });

              // 初次定位一次
              positionOverlayBadges(overlay, rect);
            }
          } catch (e) {
            console.error("HoHoNet: 覆盖层错误", e);
          }

          if (paired.length === 0) {
            alert(
              `找到 ${points.length} 个点，但无法配对任何垂直边！请尝试绘制更直的垂直线。`,
            );
            return;
          }

          // 获取用于纹理的图像 URL
          const img = findMainImage();
          let imageUrl = img ? img.src : null;
          if (!imageUrl) {
            imageUrl = getImageUrlFromStore();
          }

          // 关键修复：不依赖 /assets/，用 nginx 的 /ls/ 同源代理来加载 Label Studio 图片
          const textureUrl = rewriteTextureUrlForViewer(imageUrl);
          const textureUrlFinal = withCacheBust(textureUrl || imageUrl);
          if (imageUrl && textureUrl && textureUrl !== imageUrl) {
            console.log(
              `HoHoNet: textureUrl rewritten via /ls proxy: ${textureUrl}`,
            );
          }
          iframe.contentWindow.postMessage(
            {
              type: "update_layout",
              corners: paired,
              width: W,
              height: H,
              imageUrl: textureUrlFinal,
            },
            "*",
          );
        };
        wrapper.appendChild(btn);
      }

      // 切换标签按钮
      let toggleBtn = document.getElementById(TOGGLE_BTN_ID);
      if (!toggleBtn) {
        toggleBtn = document.createElement("button");
        toggleBtn.id = TOGGLE_BTN_ID;
        toggleBtn.style.cssText =
          "margin-top: 10px; margin-left: 10px; padding: 8px 16px; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;";

        applyToggleBtnState(toggleBtn, getLabelsVisible());

        toggleBtn.onclick = function () {
          const overlay = document.getElementById(OVERLAY_ID);
          if (overlay) {
            const nowVisible = overlay.style.display === "none";
            setLabelsVisible(nowVisible);
            overlay.style.display = nowVisible ? "block" : "none";
            applyToggleBtnState(toggleBtn, nowVisible);
          } else {
            alert("请先点击 '刷新 3D 视图' 以生成标签。");
          }
        };
        wrapper.appendChild(toggleBtn);
      }
    } catch (e) {
      status += "错误: " + e.message;
    }

    updateDebug(status);
  }

  // --- 活动时间跟踪 (新功能) ---
  let activeSeconds = 0;
  let lastActivityTime = 0; // v0.21: init to 0, require real user interaction
  // 修改: 将空闲阈值降低到 15s 以获得更精确的“活动”测量
  const IDLE_THRESHOLD = 15 * 1000;
  let currentTaskId = null;

  // v0.21: cumulative seconds per task within same session (fix A->B->A undercount)
  const taskCumulativeSeconds = new Map();

  let isPageVisible = true;
  let pageHiddenTime = null;
  const PAGE_HIDDEN_THRESHOLD = 6 * 1000; // 页面被切出超过6秒后才停止计时（可调整此参数）

  function resetCurrentActiveTimeSegment() {
    activeSeconds = 0;
    lastActivityTime = 0;
  }

  // 检测页面可见性（仅在隐藏超过阈值时停止计时，允许短暂切换）
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      // 页面被隐藏，记录隐藏开始时间
      pageHiddenTime = Date.now();
      isPageVisible = false;
    } else {
      // 页面重新显示
      if (pageHiddenTime !== null) {
        const hiddenDuration = Date.now() - pageHiddenTime;
        if (hiddenDuration >= PAGE_HIDDEN_THRESHOLD) {
          // v0.21: 隐藏时长超过阈值 => lastActivityTime=0
          // 要求用户下一次真实交互才重新开始计时
          // (旧版设 Date.now() 会导致切回后 0-15s 被误计)
          lastActivityTime = 0;
        }
        // 否则继续计时，不重置（允许短暂切换）
      }
      pageHiddenTime = null;
      isPageVisible = true;
    }
  });

  // 监听用户活动（只在页面可见时更新）
  ["mousemove", "keydown", "click", "scroll", "wheel"].forEach((evt) => {
    window.addEventListener(
      evt,
      () => {
        if (isPageVisible) {
          lastActivityTime = Date.now();
        }
      },
      true,
    );
  });

  // 累积活动时间的计时器
  // v0.21 修复: 仅在「页面可见 + 标注任务页面 + 有近期交互」时累积
  setInterval(() => {
    if (isActiveTimeLoggingDisabled()) {
      resetCurrentActiveTimeSegment();
    }

    if (
      !isActiveTimeLoggingDisabled() &&
      isPageVisible &&
      isLikelyAnnotationPage() &&
      lastActivityTime > 0 &&
      Date.now() - lastActivityTime < IDLE_THRESHOLD
    ) {
      activeSeconds += 1;
    }

    // 更新 UI
    const totalForTask =
      currentTaskId && taskCumulativeSeconds.has(currentTaskId)
        ? taskCumulativeSeconds.get(currentTaskId) + activeSeconds
        : activeSeconds;
    if (isDebugPanelEnabled()) {
      const debugPanel = document.getElementById(DEBUG_ID);
      if (debugPanel) {
        const activeTimeStatus = isActiveTimeLoggingDisabled()
          ? "活动时间: 已禁用"
          : `活动时间: ${totalForTask}s (本段${activeSeconds}s)`;
        debugPanel.innerText = `${activeTimeStatus} | 更新于 ${new Date().toLocaleTimeString()}`;
      }
    }
  }, 1000);

  // 尝试从 URL 或 UI 提取任务 ID
  function getTaskId() {
    // 1. URL 参数
    const params = new URLSearchParams(window.location.search);
    if (params.get("task")) return params.get("task");

    // 2. URL 路径 (例如 /projects/1/data/import?task=123)
    // 或 /projects/1/tasks/123
    const match = window.location.pathname.match(/tasks\/(\d+)/);
    if (match) return match[1];

    return "unknown";
  }

  // 尝试从 URL 提取项目 ID
  function getProjectId() {
    // URL 路径 (例如 /projects/1/data/import?task=123)
    const match = window.location.pathname.match(/projects\/(\d+)/);
    if (match) return match[1];
    return "unknown";
  }

  // 尝试提取项目名称
  function getProjectName() {
    // 1. 尝试 Store (如果可用，最可靠)
    const store = getStore();
    if (store && store.project && store.project.title) {
      return store.project.title;
    }
    // 2. DOM 回退 (面包屑)
    // 查找类似 /projects/123 的链接
    const crumbs = Array.from(
      document.querySelectorAll("a[href*='/projects/']"),
    );
    const projectLink = crumbs.find((a) =>
      a.getAttribute("href").match(/\/projects\/\d+$/),
    );
    if (projectLink && projectLink.innerText) return projectLink.innerText;

    return "unknown";
  }

  // 尝试从 Label Studio 提取标注者/用户 ID
  function getAnnotatorId() {
    try {
      const store = getStore();
      const candidates = [
        store && store.user && store.user.id,
        store && store.currentUser && store.currentUser.id,
        store &&
          store.authStore &&
          store.authStore.user &&
          store.authStore.user.id,
        store &&
          store.userStore &&
          store.userStore.currentUser &&
          store.userStore.currentUser.id,
      ];
      for (const c of candidates) {
        if (c !== undefined && c !== null && String(c).length > 0) {
          return String(c);
        }
      }
    } catch (e) {}

    // 回退 (尽力而为)
    try {
      if (
        window.LabelStudio &&
        window.LabelStudio.user &&
        window.LabelStudio.user.id
      ) {
        return String(window.LabelStudio.user.id);
      }
    } catch (e) {}

    return "unknown";
  }

  // 【关键修复】立即上报（flush）当前任务的累积时间
  // v0.21: 支持累积秒数 (taskCumulativeSeconds + 当前片段)
  async function flushActiveTime(
    forceTaskId = null,
    forcedActiveSeconds = null,
  ) {
    if (isActiveTimeLoggingDisabled()) {
      resetCurrentActiveTimeSegment();
      return;
    }

    if (!isLikelyAnnotationPage()) {
      return;
    }

    const reportTaskId = forceTaskId || getTaskId();
    const projectId = getProjectId();
    const projectName = getProjectName();
    const annotatorId = getAnnotatorId();

    // 当前片段的活跃秒数
    const currentFragment =
      forcedActiveSeconds !== null ? forcedActiveSeconds : activeSeconds;

    // v0.21: 累积秒数 = 之前已 flush 的片段总和 + 当前片段
    const previousCumulative = taskCumulativeSeconds.get(reportTaskId) || 0;
    const reportSeconds = previousCumulative + currentFragment;

    if (reportSeconds <= 0 || reportTaskId === "unknown") {
      return;
    }

    // 更新累积记录
    taskCumulativeSeconds.set(reportTaskId, reportSeconds);

    try {
      const tokenNow = getLogToken();
      const response = await fetch(HOHONET_LOG_TIME_URL(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(tokenNow ? { "X-HOHONET-TOKEN": tokenNow } : {}),
        },
        body: JSON.stringify({
          task_id: reportTaskId,
          project_id: projectId,
          project_name: projectName,
          annotator_id: annotatorId,
          session_id: sessionId,
          active_seconds: reportSeconds,
          active_seconds_fragment: currentFragment, // v0.21: 仅当前片段
          timestamp: Date.now(),
          is_manual_flush: true,
          script_version: SCRIPT_VERSION, // v0.21: 审计追溯
          page_type: isLikelyAnnotationPage() ? "annotation" : "other", // v0.21
        }),
      });
      if (!response.ok) {
        console.warn(
          `[FLUSH] 上报异常: ${response.status} ${response.statusText}`,
        );
        if (response.status === 403) {
          console.warn(
            `[FLUSH] 403 Forbidden. helperBase=${getHelperBaseUrl()} token=${maskToken(tokenNow)} (len=${String(tokenNow || "").length})`,
          );
        }
      } else {
        console.log(
          `[FLUSH] 已立即上报任务 ${reportTaskId} 的 ${reportSeconds}s 活动时间`,
        );
      }
    } catch (e) {
      console.warn(`[FLUSH] 上报失败:`, e);
    }
  }

  // 会话 ID (每个标签页) 用于区分并发客户端
  const SESSION_STORAGE_KEY = "hohonet_ls_session_id";
  const sessionId = (() => {
    try {
      let sid = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (!sid) {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
          sid = window.crypto.randomUUID();
        } else {
          sid = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        }
        window.sessionStorage.setItem(SESSION_STORAGE_KEY, sid);
      }
      return sid;
    } catch (e) {
      return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }
  })();

  // 【独立的任务切换检测器】每秒检测一次任务ID变化，立即上报
  // 这是一个独立的机制，不依赖30秒周期，保证任务切换时立即上报
  setInterval(() => {
    if (!isLikelyAnnotationPage()) {
      return;
    }

    if (isActiveTimeLoggingDisabled()) {
      resetCurrentActiveTimeSegment();
      return;
    }

    const taskId = getTaskId();

    if (taskId === "unknown") {
      return;
    }

    // 检测到任务切换：立即flush前一个任务
    if (
      currentTaskId !== undefined &&
      currentTaskId !== null &&
      taskId !== currentTaskId &&
      activeSeconds > 0
    ) {
      const secondsToReport = activeSeconds;
      const cumulativeTotal =
        (taskCumulativeSeconds.get(currentTaskId) || 0) + secondsToReport;
      console.log(
        `[TASK_SWITCH] ${currentTaskId} -> ${taskId}，上报片段${secondsToReport}s (累积${cumulativeTotal}s)`,
      );
      flushActiveTime(currentTaskId, secondsToReport); // 传入当前片段值，flush内部会加上累积
      activeSeconds = 0;
      lastActivityTime = 0; // v0.21: 切换后需要新交互才开始计时
    }

    // 初始化或更新任务ID
    if (currentTaskId === null && taskId !== "unknown") {
      console.log(`[TASK_INIT] 初始化任务ID: ${taskId}`);
    }
    currentTaskId = taskId;
  }, 1000); // 每秒检测一次，保证任务切换时立即响应

  // 每 30 秒发送一次日志 (从 10 秒修改以减少流量)
  setInterval(() => {
    // 只在“标注页面”尝试记日志，避免在项目列表/首页等页面误计时/误上报。
    if (!isLikelyAnnotationPage()) {
      return;
    }

    const taskId = getTaskId();
    const projectId = getProjectId();
    const projectName = getProjectName();
    const annotatorId = getAnnotatorId();

    // 配置:
    // - ENABLE_LOGGING: 总开关。为 false 时，脚本不会发送日志。
    //   当你想开始记录时 (例如正式标注开始时) 设置为 true。
    // - TARGET_PROJECTS: 当 ENABLE_LOGGING === true 时:
    //     [] (空) => 记录所有项目
    //     ['15','28'] => 仅记录这些项目 ID
    // 示例:
    //   const ENABLE_LOGGING = false;
    //   const TARGET_PROJECTS = ['15', '28'];
    const ENABLE_LOGGING = true; // 开启日志记录
    const TARGET_PROJECTS = [];

    if (!ENABLE_LOGGING) {
      return; // 全局禁用日志
    }

    if (isActiveTimeLoggingDisabled()) {
      resetCurrentActiveTimeSegment();
      return;
    }

    if (TARGET_PROJECTS.length > 0 && !TARGET_PROJECTS.includes(projectId)) {
      return; // 如果不在目标项目中，跳过日志记录
    }

    // 周期性上报当前任务的累积时间
    // v0.21: active_seconds 改为累积值 (之前片段 + 当前片段)
    if (activeSeconds > 0 && taskId !== "unknown") {
      const previousCumulative = taskCumulativeSeconds.get(taskId) || 0;
      const totalSeconds = previousCumulative + activeSeconds;
      const tokenNow = getLogToken();
      fetch(HOHONET_LOG_TIME_URL(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(tokenNow ? { "X-HOHONET-TOKEN": tokenNow } : {}),
        },
        body: JSON.stringify({
          task_id: taskId,
          project_id: projectId,
          project_name: projectName,
          annotator_id: annotatorId,
          session_id: sessionId,
          active_seconds: totalSeconds,
          active_seconds_fragment: activeSeconds, // v0.21: 仅当前片段
          timestamp: Date.now(),
          is_manual_flush: false,
          script_version: SCRIPT_VERSION, // v0.21: 审计追溯
          page_type: "annotation", // v0.21: 走到这里一定是标注页
        }),
      })
        .then((r) => {
          if (!r.ok) {
            console.warn(`[LOG] 上报异常: ${r.status} ${r.statusText}`);
            if (r.status === 403) {
              console.warn(
                `[LOG] 403 Forbidden. helperBase=${getHelperBaseUrl()} token=${maskToken(tokenNow)} (len=${String(tokenNow || "").length})`,
              );
            }
          }
          return r;
        })
        .catch((e) => console.warn("Log failed", e));
    }
  }, 30000);

  setInterval(tick, 1000);

  // v0.20 新增: 监听 DOM 变化，以便在 SPA 导航时重新激活
  // 当 Label Studio 切换任务/页面时，强制触发一次 tick
  const observer = new MutationObserver((mutations) => {
    // 检测到重要的 DOM 变化时，延迟执行 tick 让 DOM 稳定
    for (const mutation of mutations) {
      if (mutation.addedNodes.length > 0) {
        // 检查是否添加了标注相关的节点
        for (const node of mutation.addedNodes) {
          if (node.nodeType === 1) {
            // Element node
            if (
              node.classList &&
              (node.classList.contains("lsf-main-view") ||
                node.classList.contains("ls-main-view") ||
                (node.querySelector && node.querySelector('img[src*="pano"]')))
            ) {
              console.log("HoHoNet: 检测到页面变化，重新激活");
              setTimeout(tick, 500);
              return;
            }
          }
        }
      }
    }
  });

  // 监听整个 body 的子树变化
  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });

  // 提交前元标签合规拦截（best-effort）：阻止空选/互斥冲突进入后端。
  installMetaSubmitGuard();

  // 监听 URL 变化（用于 SPA 导航）
  let lastUrl = location.href;
  setInterval(() => {
    const currentUrl = location.href;
    if (currentUrl !== lastUrl) {
      console.log("HoHoNet: URL 变化，重新激活");
      lastUrl = currentUrl;
      // 清理可能残留的状态
      lastTaskIdForOverlay = null;
      lastAnnotationIdForOverlay = null;
      clearOverlay();
      // 延迟执行以确保新页面DOM已加载
      setTimeout(tick, 500);
    }
  }, 1000);
})();
