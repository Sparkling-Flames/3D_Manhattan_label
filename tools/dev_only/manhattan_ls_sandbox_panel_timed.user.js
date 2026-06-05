// ==UserScript==
// @name         HOHONET Manhattan LS Sandbox Panel Timed
// @namespace    hohonet-dev-only
// @version      m13.2-dev-only-timed-0.1.1
// @description  dev-only sandbox-only read-only Manhattan panel; timed variant with sandbox-excluded active_time telemetry.
// @match        http://175.178.71.217:8080/*
// @match        https://175.178.71.217:8080/*
// @grant        none
// ==/UserScript==

/*
 * HOHONET Manhattan LS Sandbox Panel Timed
 *
 * dev-only
 * sandbox-only
 * expert/developer tester only
 * not official userscript
 * not worker-facing
 * no annotation writeback
 * no submit
 * no routing
 * no formal g_t
 * no P1/C1/C2/T1/V1 artifact
 *
 * This timed variant may POST sandbox telemetry to /log_time. Every payload
 * is tagged for exclusion from primary active_time and thesis evidence.
 */

(function () {
  "use strict";

  if (window.top !== window.self) {
    return;
  }

  const WINDOW_GUARD = "__HOHONET_M8_SANDBOX_PANEL_ACTIVE__";
  if (window[WINDOW_GUARD]) {
    return;
  }
  window[WINDOW_GUARD] = { script_variant: "timed" };

  const PANEL_ID = "hohonet-manhattan-sandbox-panel";
  const PANEL_VERSION = "m13.2-dev-only-timed-0.1.1";
  const TOOLBAR_ID = "hohonet-m13-primary-toolbar";
  const TOOLBAR_BODY_ID = "hohonet-m13-primary-toolbar-body";
  const DEBUG_DRAWER_TOGGLE_ID = "hohonet-m13-debug-drawer-toggle";
  const OFFICIAL_IFRAME_ID = "hohonet-iframe";
  const OFFICIAL_WRAPPER_ID = "hohonet-wrapper";
  const OFFICIAL_BUTTON_ID = "hohonet-refresh-btn";
  const TOGGLE_LABELS_BUTTON_ID = "hohonet-m8-toggle-labels-btn";
  const GUIDE_BANDS_BUTTON_ID = "hohonet-m13-guide-bands-btn";
  const OVERLAY_ID = "hohonet-m8-preview-order-overlay";
  const LABELS_VISIBLE_KEY = "hohonet_m8_preview_labels_visible";
  const GUIDE_BANDS_VISIBLE_KEY = "hohonet_m13_guide_bands_visible";
  const GUIDE_MODE = "issue_only";
  const PREVIEW_PANEL_ID = "hohonet-m8-preview-order-panel";
  const PREVIEW_PANEL_HEADER_ID = "hohonet-m8-preview-order-panel-header";
  const PREVIEW_PANEL_STATUS_ID = "hohonet-m8-preview-order-status";
  const PREVIEW_PANEL_PAIR_INPUT_ID = "hohonet-m8-preview-order-pair-input";
  const PREVIEW_PANEL_SWAP_INPUT_ID = "hohonet-m8-preview-order-swap-input";
  const PREVIEW_PANEL_POSITION_KEY = "hohonet_m8_preview_order_panel_position";
  const DEFAULT_WIDTH = 1024;
  const DEFAULT_HEIGHT = 512;
  const START_TIME_MS = Date.now();
  const HEARTBEAT_INTERVAL_MS = 15000;
  const IDLE_THRESHOLD_MS = 15000;
  const PAGE_HIDDEN_THRESHOLD_MS = 6000;
  const DUPLICATE_KEYPOINT_THRESHOLD_RATIO = 0.01;
  const SESSION_STORAGE_KEY = "hohonet_m8_sandbox_session_id";
  let lastTelemetryMs = START_TIME_MS;
  let activeSeconds = 0;
  let lastTelemetryActiveSeconds = 0;
  let lastActivityTime = 0;
  let isPageVisible = !document.hidden;
  let isWindowFocused = document.hasFocus();
  let pageHiddenTime = null;
  let lastHiddenDurationMs = 0;
  let currentPreviewBasePairs = [];
  let currentPreviewOrder = [];
  let currentPreviewSelectedPairIndex = 0;
  let currentDiagnosisAffectedPairIndex = null;
  let currentSandboxState = null;
  let currentPageSignature = null;
  const highlightState = {
    status: "not_applied",
    affectedPairIndex: "none",
    rowFound: false,
    overlayLabelsFound: 0,
  };
  const guideState = {
    status: "hidden",
    mode: GUIDE_MODE,
    component: "unavailable",
    affectedPairIndex: "unavailable",
    visibleItems: "none",
    explanation: "Visual reference lines are hidden.",
    scope: "2D panorama overlay only",
    guardrail: "Guide bands are visual references only. No target x/y, no point movement, no annotation writeback.",
  };
  const telemetryState = {
    status: "not_sent",
    lastEvent: "none",
    lastHttpStatus: "none",
    lastError: "none",
  };
  const GUARDRAILS = [
    "dev-only sandbox-only panel",
    "expert/developer tester only",
    "not official userscript",
    "not worker-facing",
    "no annotation writeback",
    "no submit",
    "no routing",
    "no formal g_t",
    "no P1/C1/C2/T1/V1 artifact",
    "no correctness label",
    "no worker tier",
    "no axis snapping",
    "no adjustment vector",
    "no automated edits",
    "timed variant: sandbox telemetry only",
  ];

  function text(value) {
    return document.createTextNode(String(value));
  }

  function makeRow(label, value) {
    const row = document.createElement("div");
    row.className = "hohonet-m8-row";
    const key = document.createElement("span");
    key.className = "hohonet-m8-key";
    key.appendChild(text(label));
    const val = document.createElement("span");
    val.className = "hohonet-m8-value";
    val.appendChild(text(value));
    row.appendChild(key);
    row.appendChild(val);
    return row;
  }

  function makeMutableRow(label, value, id) {
    const row = makeRow(label, value);
    const val = row.querySelector(".hohonet-m8-value");
    if (val) val.id = id;
    return row;
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = String(value);
  }

  function getLabelsVisible() {
    try {
      const stored = window.sessionStorage.getItem(LABELS_VISIBLE_KEY);
      return stored === null ? true : stored === "1";
    } catch (e) {
      return true;
    }
  }

  function setLabelsVisible(visible) {
    try {
      window.sessionStorage.setItem(LABELS_VISIBLE_KEY, visible ? "1" : "0");
    } catch (e) {}
  }

  function getGuideBandsVisible() {
    try {
      return window.sessionStorage.getItem(GUIDE_BANDS_VISIBLE_KEY) === "1";
    } catch (e) {
      return false;
    }
  }

  function setGuideBandsVisible(visible) {
    try {
      window.sessionStorage.setItem(GUIDE_BANDS_VISIBLE_KEY, visible ? "1" : "0");
    } catch (e) {}
  }

  function applyToggleBtnState(button, visible) {
    if (!button) return;
    button.textContent = visible ? "Hide corner order" : "Show corner order";
    button.style.background = visible ? "#6c757d" : "#28a745";
  }

  function applyGuideBtnState(button, visible) {
    if (!button) return;
    button.textContent = visible ? "Hide guide bands" : "Show guide bands";
    button.style.background = visible ? "#6c757d" : "#28a745";
  }

  function normalizeChoiceToken(raw) {
    const textValue = String(raw || "").trim();
    const lower = textValue.toLowerCase();
    if (!textValue) return "";
    if (lower === "trivial" || lower.includes("trivial") || textValue.includes("非常简单")) {
      return "trivial";
    }
    if (lower === "acceptable" || lower.includes("acceptable") || textValue.includes("质量好")) {
      return "acceptable";
    }
    return lower;
  }

  function matchesFieldName(actual, expected) {
    const a = String(actual || "").trim().toLowerCase();
    const e = String(expected || "").trim().toLowerCase();
    if (!a || !e) return false;
    return a === e || a.endsWith(`.${e}`) || a.endsWith(`:${e}`) || a.endsWith(`/${e}`) || a.includes(e);
  }

  function isTrivialToken(token) {
    const normalized = normalizeChoiceToken(token);
    return normalized === "trivial" || normalized.includes("trivial");
  }

  function isAcceptableToken(token) {
    const normalized = normalizeChoiceToken(token);
    return normalized === "acceptable" || normalized.includes("acceptable");
  }

  function numericAttr(element, names) {
    for (const name of names) {
      const raw = element.getAttribute(name);
      if (raw === null || raw === "") {
        continue;
      }
      const value = Number(raw);
      if (Number.isFinite(value)) {
        return value;
      }
    }
    return null;
  }

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

  function getLogToken() {
    try {
      return window.localStorage.getItem("HOHONET_LOG_TOKEN") || "";
    } catch (e) {
      return "";
    }
  }

  function logTimeUrl() {
    return `${getHelperBaseUrl()}/log_time`;
  }

  const sessionId = (() => {
    try {
      let sid = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (!sid) {
        sid = `m8-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
        window.sessionStorage.setItem(SESSION_STORAGE_KEY, sid);
      }
      return sid;
    } catch (e) {
      return `m8-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    }
  })();

  function getStore() {
    if (
      window.LabelStudio &&
      window.LabelStudio.instances &&
      window.LabelStudio.instances.length > 0
    ) {
      return window.LabelStudio.instances[0].store;
    }
    if (window.H) return window.H;
    const roots = [
      document.querySelector(".ls-room"),
      document.querySelector("#label-studio"),
      document.querySelector(".lsf-main-view"),
      document.querySelector(".ls-main-view"),
      document.body,
    ].filter(Boolean);
    const scoped = Array.from(
      document.querySelectorAll(
        "#label-studio, .ls-room, .lsf-main-view, .ls-main-view, [class*='lsf'], [class*='label']",
      ),
    );
    for (const root of roots.concat(scoped)) {
      for (const key in root) {
        if (!key.startsWith("__reactFiber") && !key.startsWith("__reactProps")) continue;
        let fiber = root[key];
        while (fiber) {
          if (fiber.stateNode?.props?.store) return fiber.stateNode.props.store;
          if (fiber.memoizedProps?.store) return fiber.memoizedProps.store;
          if (fiber.pendingProps?.store) return fiber.pendingProps.store;
          fiber = fiber.return;
        }
      }
    }
    return null;
  }

  function knownText(value) {
    if (value === undefined || value === null) return "unknown";
    const textValue = String(value).trim();
    return textValue || "unknown";
  }

  function getTaskId() {
    try {
      const storeTaskId = getStore()?.task?.id;
      if (storeTaskId !== undefined && storeTaskId !== null) {
        return knownText(storeTaskId);
      }
      const params = new URLSearchParams(window.location.search);
      const queryTaskId = params.get("task") || params.get("task_id");
      if (queryTaskId) return knownText(queryTaskId);
      const match = window.location.pathname.match(/\/tasks\/(\d+)/);
      if (match) return match[1];
    } catch (e) {}
    return "unknown";
  }

  function getProjectId() {
    try {
      const store = getStore();
      const candidates = [
        store?.project?.id,
        store?.task?.project,
        store?.task?.projectId,
        store?.task?.data?.project_id,
      ];
      for (const candidate of candidates) {
        if (candidate !== undefined && candidate !== null && String(candidate).trim()) {
          return knownText(candidate);
        }
      }
      const match = window.location.pathname.match(/\/projects\/(\d+)/);
      if (match) return match[1];
    } catch (e) {}
    return "unknown";
  }

  function getProjectName() {
    try {
      const store = getStore();
      const candidates = [
        store?.project?.title,
        store?.project?.name,
        store?.task?.data?.project_name,
      ];
      for (const candidate of candidates) {
        if (candidate !== undefined && candidate !== null && String(candidate).trim()) {
          return knownText(candidate);
        }
      }
      const crumbs = Array.from(document.querySelectorAll("a, span, div"))
        .map((node) => node.textContent?.trim())
        .filter(Boolean);
      const projectsIndex = crumbs.findIndex((value) => value === "Projects");
      if (projectsIndex >= 0 && crumbs[projectsIndex + 1]) {
        return knownText(crumbs[projectsIndex + 1]);
      }
      if (document.title) return knownText(document.title);
    } catch (e) {}
    return "unknown";
  }

  function getAnnotatorId() {
    try {
      const store = getStore();
      const candidates = [
        store?.user?.id,
        store?.user?.pk,
        store?.currentUser?.id,
        store?.task?.data?.annotator_id,
      ];
      for (const candidate of candidates) {
        if (candidate !== undefined && candidate !== null && String(candidate).trim()) {
          return knownText(candidate);
        }
      }
      const profileText = document.querySelector("[data-testid*='user'], [class*='user']")?.textContent;
      if (profileText) return knownText(profileText);
    } catch (e) {}
    return "unknown";
  }

  function getPageType() {
    return /\/labeling\/?/.test(window.location.pathname) ||
      Boolean(document.querySelector(".lsf-main-view, .ls-main-view"))
      ? "annotation"
      : "other";
  }

  function isLikelyAnnotationPage() {
    return getPageType() === "annotation";
  }

  function toArrayFromMaybeObservable(value) {
    try {
      if (!value) return [];
      if (Array.isArray(value)) return value;
      if (typeof value.toJSON === "function") {
        const json = value.toJSON();
        if (Array.isArray(json)) return json;
      }
      if (typeof value[Symbol.iterator] === "function") {
        return Array.from(value);
      }
      if (typeof value.forEach === "function") {
        const out = [];
        value.forEach((item) => out.push(item));
        return out;
      }
    } catch (e) {}
    return [];
  }

  function collectSelectedResults(store) {
    const out = [];
    try {
      const selected = store?.annotationStore?.selected;
      if (!selected) return out;
      if (typeof selected.serializeCompletion === "function") {
        const serialized = selected.serializeCompletion();
        out.push(...toArrayFromMaybeObservable(serialized?.result));
      }
      if (typeof selected.toJSON === "function") {
        const json = selected.toJSON();
        out.push(...toArrayFromMaybeObservable(json?.result || json?.results));
      }
      out.push(...toArrayFromMaybeObservable(selected?.results));
    } catch (e) {}
    return out;
  }

  function extractChoicesFromResult(result) {
    try {
      if (!result || typeof result !== "object") return [];
      const candidates = [result?.value, result?.area?.value, result?.origin?.value, result, result?.area, result?.origin];
      const out = [];
      for (const source of candidates) {
        if (!source || typeof source !== "object") continue;
        const choices = Array.isArray(source.choices) ? source.choices : [];
        choices.map(normalizeChoiceToken).filter(Boolean).forEach((choice) => {
          if (!out.includes(choice)) out.push(choice);
        });
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
    container.querySelectorAll("input[type='checkbox']:checked, input[type='radio']:checked").forEach((input) => {
      const id = input.getAttribute("id");
      const label = id ? container.querySelector(`label[for='${id}']`) : null;
      const near = input.closest("label,li,div,span");
      const token = normalizeChoiceToken(label?.innerText || near?.innerText || input?.value || "");
      if (token && !out.includes(token)) out.push(token);
    });
    container
      .querySelectorAll("[role='checkbox'][aria-checked='true'], [role='radio'][aria-checked='true']")
      .forEach((node) => {
        const token = normalizeChoiceToken(node?.innerText || node?.textContent || "");
        if (token && !out.includes(token)) out.push(token);
      });
    return out;
  }

  function findMetaSectionContainer(fieldName) {
    const probes = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6,div,span,label"));
    const patterns =
      fieldName === "difficulty"
        ? [/困难因素/, /difficulty/i]
        : [/模型.*问题/, /model\s*issue/i];
    for (const element of probes) {
      const label = String(element?.innerText || "").trim();
      if (!label || label.length > 180) continue;
      if (!patterns.some((pattern) => pattern.test(label))) continue;
      const container = element.closest("section,fieldset,div");
      if (container) return container;
    }
    return null;
  }

  function isFieldPresent(store, fieldName) {
    try {
      if (collectSelectedResults(store).some((result) => matchesFieldName(getResultFromName(result), fieldName))) {
        return true;
      }
    } catch (e) {}
    return !!findMetaSectionContainer(fieldName);
  }

  function getSelectedChoicesByField(store, fieldName) {
    const out = [];
    for (const result of collectSelectedResults(store)) {
      if (!matchesFieldName(getResultFromName(result), fieldName)) continue;
      extractChoicesFromResult(result).forEach((choice) => {
        if (choice && !out.includes(choice)) out.push(choice);
      });
    }
    if (out.length) return out;
    return collectFromDomContainer(findMetaSectionContainer(fieldName));
  }

  function validateMetaChoices(store) {
    const difficulty = getSelectedChoicesByField(store, "difficulty");
    const hasModelIssueField = isFieldPresent(store, "model_issue");
    const modelIssue = hasModelIssueField ? getSelectedChoicesByField(store, "model_issue") : [];
    const errors = [];
    if (isFieldPresent(store, "difficulty") && difficulty.some(isTrivialToken) && difficulty.some((x) => !isTrivialToken(x))) {
      errors.push("difficulty_conflict_trivial_with_non_trivial");
    }
    if (hasModelIssueField && modelIssue.some(isAcceptableToken) && modelIssue.some((x) => !isAcceptableToken(x))) {
      errors.push("model_issue_conflict_acceptable_with_issue");
    }
    return {
      status: errors.length ? "blocked" : "pass",
      errors,
      difficulty,
      model_issue: modelIssue,
    };
  }

  function shouldGuardAction(target) {
    if (!target) return false;
    const merged = String(
      [
        target.innerText,
        target.textContent,
        target.getAttribute?.("aria-label"),
        target.getAttribute?.("title"),
        target.getAttribute?.("data-testid"),
      ]
        .filter(Boolean)
        .join(" "),
    ).toLowerCase();
    return ["submit", "update", "完成", "提交", "更新"].some((keyword) => merged.includes(keyword));
  }

  function installSandboxMetaGuard() {
    if (window.__HOHONET_M8_SANDBOX_META_GUARD__) return;
    window.__HOHONET_M8_SANDBOX_META_GUARD__ = true;
    const runCheck = () => {
      const result = validateMetaChoices(getStore());
      updateMetaGuardPanel(result);
      if (result.status !== "pass") {
        window.alert(`Sandbox meta-label guard blocked action:\n${result.errors.join("\n")}`);
        return false;
      }
      return true;
    };
    document.addEventListener(
      "click",
      (event) => {
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
        if (!((event.ctrlKey || event.metaKey) && event.key === "Enter")) return;
        if (!runCheck()) {
          event.preventDefault();
          event.stopImmediatePropagation();
        }
      },
      true,
    );
  }

  function cleanResult(value) {
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (e) {
      return value;
    }
  }

  function readPercentPoint(result) {
    const source = result?.area || result;
    const cleaned = cleanResult(source);
    const type = result?.type || cleaned?.type;
    if (type !== "keypointlabels" && type !== "keypointregion") {
      return null;
    }
    const candidates = [cleaned?.value, cleaned, result?.value, result];
    for (const candidate of candidates) {
      const x = candidate?.x;
      const y = candidate?.y;
      if (typeof x === "number" && typeof y === "number") {
        return { pctX: x, pctY: y };
      }
    }
    return null;
  }

  function extractKeypointsFromStore(store, width, height) {
    const results = collectSelectedResults(store);
    const keypoints = [];
    for (const result of results) {
      const point = readPercentPoint(result);
      if (!point) continue;
      keypoints.push({
        x: (point.pctX * width) / 100,
        y: (point.pctY * height) / 100,
        pctX: point.pctX,
        pctY: point.pctY,
        source: "label-studio-store",
      });
    }
    return { keypoints, result_count: results.length };
  }

  function getImageUrlFromStore() {
    try {
      const data = getStore()?.task?.data;
      if (!data || typeof data !== "object") return null;
      for (const key of ["image", "img", "pano", "pano_url", "panoUrl", "url", "src", "file"]) {
        const value = data[key];
        if (typeof value === "string" && value) return value;
      }
    } catch (e) {}
    return null;
  }

  function findMainImage() {
    const mainView =
      document.querySelector(".lsf-main-view") ||
      document.querySelector(".ls-main-view") ||
      document;
    const images = Array.from(mainView.querySelectorAll("img")).filter(
      (img) => img.naturalWidth > 200 || img.width > 200,
    );
    if (!images.length) return null;
    return images.reduce((a, b) =>
      (a.naturalWidth || a.width || 0) * (a.naturalHeight || a.height || 0) >
      (b.naturalWidth || b.width || 0) * (b.naturalHeight || b.height || 0)
        ? a
        : b,
    );
  }

  function rewriteTextureUrlForViewer(originalUrl) {
    if (!originalUrl) return originalUrl;
    try {
      const helperBase = new URL(getHelperBaseUrl(), window.location.href);
      const url = new URL(originalUrl, window.location.href);
      if (url.origin === helperBase.origin) return url.toString();
      if (url.hostname === helperBase.hostname) {
        return `${helperBase.origin}/ls${url.pathname}${url.search}`;
      }
      return url.toString();
    } catch (e) {
      return originalUrl;
    }
  }

  function withCacheBust(url) {
    if (!url) return url;
    try {
      const parsed = new URL(url, window.location.href);
      parsed.searchParams.set("_hohonet_ts", String(Date.now()));
      return parsed.toString();
    } catch (e) {
      return url;
    }
  }

  function buildPreviewPairs(points, width) {
    const sorted = points.slice().sort((a, b) => a.x - b.x);
    const used = new Array(sorted.length).fill(false);
    const threshold = width * 0.05;
    const pairs = [];
    for (let i = 0; i < sorted.length; i += 1) {
      if (used[i]) continue;
      let bestJ = -1;
      let minDiff = Infinity;
      for (let j = i + 1; j < sorted.length; j += 1) {
        if (used[j]) continue;
        const diff = Math.abs(sorted[j].x - sorted[i].x);
        if (diff < threshold && diff < minDiff) {
          minDiff = diff;
          bestJ = j;
        }
      }
      if (bestJ !== -1) {
        used[i] = true;
        used[bestJ] = true;
        pairs.push({
          x: (sorted[i].x + sorted[bestJ].x) / 2,
          y_ceiling: Math.min(sorted[i].y, sorted[bestJ].y),
          y_floor: Math.max(sorted[i].y, sorted[bestJ].y),
          originalPoints: [sorted[i], sorted[bestJ]],
        });
      }
    }
    return pairs;
  }

  function clamp(value, minValue, maxValue) {
    return Math.min(maxValue, Math.max(minValue, value));
  }

  function formatMetric(value) {
    return Number.isFinite(value) ? value.toFixed(3) : "unavailable";
  }

  function formatLsCoord(value) {
    return Number.isFinite(value) ? value.toFixed(2) : "unavailable";
  }

  function pointPctX(point) {
    return Number.isFinite(point?.pctX) ? point.pctX : (Number(point?.x) / DEFAULT_WIDTH) * 100;
  }

  function pointPctY(point) {
    return Number.isFinite(point?.pctY) ? point.pctY : (Number(point?.y) / DEFAULT_HEIGHT) * 100;
  }

  function pairLsCoordSummary(pair) {
    const points = Array.isArray(pair?.originalPoints) ? pair.originalPoints : [];
    if (points.length >= 2) {
      const sortedByY = points.slice().sort((a, b) => a.y - b.y);
      return {
        top: { x: pointPctX(sortedByY[0]), y: pointPctY(sortedByY[0]) },
        bottom: { x: pointPctX(sortedByY[sortedByY.length - 1]), y: pointPctY(sortedByY[sortedByY.length - 1]) },
        derived: false,
      };
    }
    return {
      top: {
        x: Number.isFinite(pair?.x_ls) ? pair.x_ls : (Number(pair?.x) / DEFAULT_WIDTH) * 100,
        y: Number.isFinite(pair?.ceiling_y_ls) ? pair.ceiling_y_ls : (Number(pair?.y_ceiling) / DEFAULT_HEIGHT) * 100,
      },
      bottom: {
        x: Number.isFinite(pair?.x_ls) ? pair.x_ls : (Number(pair?.x) / DEFAULT_WIDTH) * 100,
        y: Number.isFinite(pair?.floor_y_ls) ? pair.floor_y_ls : (Number(pair?.y_floor) / DEFAULT_HEIGHT) * 100,
      },
      derived: true,
    };
  }

  function hasNearDuplicateKeypoint(points, width, height) {
    const threshold = Math.max(width, height) * DUPLICATE_KEYPOINT_THRESHOLD_RATIO;
    for (let i = 0; i < points.length; i += 1) {
      for (let j = i + 1; j < points.length; j += 1) {
        const dx = points[i].x - points[j].x;
        const dy = points[i].y - points[j].y;
        if (Math.sqrt(dx * dx + dy * dy) < threshold) {
          return true;
        }
      }
    }
    return false;
  }

  function buildPreviewPairDiagnostics(points, width) {
    const sorted = points.slice().sort((a, b) => a.x - b.x);
    const used = new Array(sorted.length).fill(false);
    const threshold = width * 0.05;
    const pairs = [];
    for (let i = 0; i < sorted.length; i += 1) {
      if (used[i]) continue;
      let bestJ = -1;
      let minDiff = Infinity;
      for (let j = i + 1; j < sorted.length; j += 1) {
        if (used[j]) continue;
        const diff = Math.abs(sorted[j].x - sorted[i].x);
        if (diff < threshold && diff < minDiff) {
          minDiff = diff;
          bestJ = j;
        }
      }
      if (bestJ === -1) continue;
      used[i] = true;
      used[bestJ] = true;
      pairs.push({
        x: (sorted[i].x + sorted[bestJ].x) / 2,
        y_ceiling: Math.min(sorted[i].y, sorted[bestJ].y),
        y_floor: Math.max(sorted[i].y, sorted[bestJ].y),
        vertical_x_delta: Math.abs(sorted[i].x - sorted[bestJ].x),
        top_x: sorted[i].y <= sorted[bestJ].y ? sorted[i].x : sorted[bestJ].x,
        bottom_x: sorted[i].y <= sorted[bestJ].y ? sorted[bestJ].x : sorted[i].x,
      });
    }
    return {
      pairs,
      unpaired: sorted.filter((_, index) => !used[index]),
    };
  }

  function range(values) {
    if (!values.length) return null;
    return Math.max(...values) - Math.min(...values);
  }

  function median(values) {
    if (!values.length) return null;
    const sorted = values.slice().sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 === 1 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  }

  function deviationLevel(score) {
    if (!Number.isFinite(score)) return "unavailable";
    if (score < 5) return "low";
    if (score < 15) return "medium";
    return "high";
  }

  function unavailableDeviation(nKeypoints, reason, nPairs = 0) {
    return {
      compatibility_status: "incompatible",
      exclusion_reason: reason,
      n_keypoints: nKeypoints,
      n_pairs: nPairs,
      vertical_pair_x_residual: null,
      ceiling_y_range: null,
      floor_y_range: null,
      wall_height_range: null,
      manhattan_deviation_score: null,
      deviation_level: "unavailable",
      primary_issue_type: "unavailable",
      primary_issue_severity: "unavailable",
      primary_issue_explanation: `Unavailable: ${reason}.`,
      affected_pair_index: "unavailable",
      affected_wall_index: "unavailable",
      pair_x_alignment_summary: "Unavailable because layout is not preview-compatible.",
      ceiling_alignment_summary: "Unavailable because layout is not preview-compatible.",
      floor_alignment_summary: "Unavailable because layout is not preview-compatible.",
      wall_height_summary: "Unavailable because layout is not preview-compatible.",
      hint_status: "unavailable",
      hint_component: "unavailable",
      direction_hint: "Unavailable because layout is not preview-compatible.",
      alternative_anchor_hint: "Unavailable because layout is not preview-compatible.",
      hint_guardrail: "Direction-only hint. Inspect visually; no target x/y, no point movement, no annotation writeback.",
      hint_direction_type: "unavailable",
      guide_status: "unavailable",
      guide_mode: GUIDE_MODE,
      guide_component: "unavailable",
      guide_affected_pair_index: "unavailable",
      guide_visible_items: "none",
      guide_explanation: "No visual reference lines are shown because the layout is not preview-compatible.",
      guide_scope: "2D panorama overlay only",
      guide_guardrail: "Guide bands are visual references only. No target x/y, no point movement, no annotation writeback.",
    };
  }

  function severityFromNormalized(value) {
    if (!Number.isFinite(value) || value <= 0) return "low";
    if (value < 0.05) return "low";
    if (value < 0.15) return "medium";
    return "high";
  }

  function maxByAbsolute(values) {
    let bestIndex = 0;
    let bestValue = -1;
    values.forEach((value, index) => {
      const absValue = Math.abs(value);
      if (absValue > bestValue) {
        bestValue = absValue;
        bestIndex = index;
      }
    });
    return { index: bestIndex, value: values[bestIndex] };
  }

  function directionOnlyHint(primaryIssueType, xLargest, ceilingLargest, floorLargest, wallLargest) {
    const base = {
      hint_status: primaryIssueType === "none" ? "no_action" : "available",
      hint_component: primaryIssueType,
      direction_hint: "No dominant residual needs a direction-only hint.",
      alternative_anchor_hint: "No inspection anchor is suggested.",
      hint_guardrail: "Direction-only hint. Inspect visually; no target x/y, no point movement, no annotation writeback.",
      hint_direction_type: "none",
    };
    if (primaryIssueType === "pair_x_alignment") {
      if (xLargest.value < 0) {
        return {
          ...base,
          direction_hint: "Top point is left of bottom point; aligning left/right would reduce this residual.",
          alternative_anchor_hint: "Inspect top point to the right, or inspect bottom point to the left. Choose by visual evidence.",
          hint_direction_type: "top_right_or_bottom_left",
        };
      }
      return {
        ...base,
        direction_hint: "Top point is right of bottom point; aligning left/right would reduce this residual.",
        alternative_anchor_hint: "Inspect top point to the left, or inspect bottom point to the right. Choose by visual evidence.",
        hint_direction_type: "top_left_or_bottom_right",
      };
    }
    if (primaryIssueType === "ceiling_alignment") {
      return {
        ...base,
        direction_hint:
          ceilingLargest.value < 0
            ? "Ceiling point is above the median band; inspecting it downward would reduce this residual."
            : "Ceiling point is below the median band; inspecting it upward would reduce this residual.",
        alternative_anchor_hint: "Choose by visual evidence before changing any annotation.",
        hint_direction_type: ceilingLargest.value < 0 ? "ceiling_down" : "ceiling_up",
      };
    }
    if (primaryIssueType === "floor_alignment") {
      return {
        ...base,
        direction_hint:
          floorLargest.value < 0
            ? "Floor point is above the median band; inspecting it downward would reduce this residual."
            : "Floor point is below the median band; inspecting it upward would reduce this residual.",
        alternative_anchor_hint: "Choose by visual evidence before changing any annotation.",
        hint_direction_type: floorLargest.value < 0 ? "floor_down" : "floor_up",
      };
    }
    if (primaryIssueType === "wall_height_consistency") {
      if (wallLargest.value > 0) {
        return {
          ...base,
          direction_hint: "Wall height is larger than the median wall height; reducing the height would reduce this residual.",
          alternative_anchor_hint: "Inspect ceiling downward or floor upward. Choose by visual evidence.",
          hint_direction_type: "height_reduce",
        };
      }
      return {
        ...base,
        direction_hint: "Wall height is smaller than the median wall height; increasing the height would reduce this residual.",
        alternative_anchor_hint: "Inspect ceiling upward or floor downward. Choose by visual evidence.",
        hint_direction_type: "height_increase",
      };
    }
    return base;
  }

  function guideVisibleItems(component) {
    if (component === "pair_x_alignment") return "affected_pair_axis";
    if (component === "ceiling_alignment") return "ceiling_reference_band,affected_ceiling_point";
    if (component === "floor_alignment") return "floor_reference_band,affected_floor_point";
    if (component === "wall_height_consistency") return "height_check_bracket,affected_pair_axis,low_opacity_context_bands";
    return "none";
  }

  function guideExplanation(component) {
    if (component === "pair_x_alignment") return "Issue-only mode shows only the affected pair vertical axis.";
    if (component === "ceiling_alignment") return "Issue-only mode shows the ceiling reference band and affected ceiling point.";
    if (component === "floor_alignment") return "Issue-only mode shows the floor reference band and affected floor point.";
    if (component === "wall_height_consistency") return "Issue-only mode shows the affected wall-height bracket with low-opacity ceiling and floor context.";
    return "No issue-specific visual reference lines are shown.";
  }

  function computeDirectionOnlyDiagnosis(pairs, width, height, residuals) {
    if (!pairs.length) {
      return unavailableDeviation(0, "missing_pairs");
    }
    const componentValues = {
      pair_x_alignment: residuals.vertical_pair_x_residual / Math.max(width, 1),
      ceiling_alignment: residuals.ceiling_y_range / Math.max(height, 1),
      floor_alignment: residuals.floor_y_range / Math.max(height, 1),
      wall_height_consistency: residuals.wall_height_range / Math.max(height, 1),
    };
    let primaryIssueType = "none";
    let primaryValue = 0;
    Object.keys(componentValues).forEach((key) => {
      if (componentValues[key] > primaryValue) {
        primaryIssueType = key;
        primaryValue = componentValues[key];
      }
    });

    const xDeltas = pairs.map((pair) => pair.top_x - pair.bottom_x);
    const ceilingValues = pairs.map((pair) => pair.y_ceiling);
    const floorValues = pairs.map((pair) => pair.y_floor);
    const wallHeights = pairs.map((pair) => pair.y_floor - pair.y_ceiling);
    const ceilingMedian = median(ceilingValues);
    const floorMedian = median(floorValues);
    const wallHeightMedian = median(wallHeights);
    const xLargest = maxByAbsolute(xDeltas);
    const ceilingLargest = maxByAbsolute(ceilingValues.map((value) => value - ceilingMedian));
    const floorLargest = maxByAbsolute(floorValues.map((value) => value - floorMedian));
    const wallLargest = maxByAbsolute(wallHeights.map((value) => value - wallHeightMedian));
    const pairXDirection = xLargest.value < 0 ? "top point is left of bottom point" : "top point is right of bottom point";
    const ceilingDirection = ceilingLargest.value < 0 ? "ceiling point is above median band" : "ceiling point is below median band";
    const floorDirection = floorLargest.value < 0 ? "floor point is above median band" : "floor point is below median band";
    const wallDirection = wallLargest.value < 0 ? "wall height is smaller than median" : "wall height is larger than median";
    const pairXSummary = `Pair ${xLargest.index + 1} has the largest vertical x mismatch; ${pairXDirection}.`;
    const ceilingSummary = `Ceiling point at pair ${ceilingLargest.index + 1} is farthest from the median ceiling band; ${ceilingDirection}.`;
    const floorSummary = `Floor point at pair ${floorLargest.index + 1} is farthest from the median floor band; ${floorDirection}.`;
    const wallSummary = `Wall pair ${wallLargest.index + 1} has the largest height deviation from the median wall height; ${wallDirection}.`;

    const issueMap = {
      pair_x_alignment: {
        index: xLargest.index + 1,
        explanation: pairXSummary,
      },
      ceiling_alignment: {
        index: ceilingLargest.index + 1,
        explanation: ceilingSummary,
      },
      floor_alignment: {
        index: floorLargest.index + 1,
        explanation: floorSummary,
      },
      wall_height_consistency: {
        index: wallLargest.index + 1,
        explanation: wallSummary,
      },
      none: {
        index: "none",
        explanation: "No dominant Manhattan residual component is visible in the current preview-compatible layout.",
      },
    };
    const selected = issueMap[primaryIssueType];
    const hint = directionOnlyHint(primaryIssueType, xLargest, ceilingLargest, floorLargest, wallLargest);
    const guideAffectedPairIndex = Number.isInteger(Number(selected.index)) ? selected.index : "unavailable";
    return {
      primary_issue_type: primaryIssueType,
      primary_issue_severity: severityFromNormalized(primaryValue),
      primary_issue_explanation: selected.explanation,
      affected_pair_index: selected.index,
      affected_wall_index: primaryIssueType === "wall_height_consistency" ? selected.index : "none",
      pair_x_alignment_summary: pairXSummary,
      ceiling_alignment_summary: ceilingSummary,
      floor_alignment_summary: floorSummary,
      wall_height_summary: wallSummary,
      guide_status: primaryIssueType === "none" ? "no_action" : "available",
      guide_mode: GUIDE_MODE,
      guide_component: primaryIssueType,
      guide_affected_pair_index: guideAffectedPairIndex,
      guide_visible_items: guideVisibleItems(primaryIssueType),
      guide_explanation: guideExplanation(primaryIssueType),
      guide_scope: "2D panorama overlay only",
      guide_guardrail: "Guide bands are visual references only. No target x/y, no point movement, no annotation writeback.",
      ...hint,
    };
  }

  function computeManhattanDeviation(points, width = DEFAULT_WIDTH, height = DEFAULT_HEIGHT) {
    if (!points.length) return unavailableDeviation(0, "missing_keypoints");
    if (points.length % 2 === 1) {
      return unavailableDeviation(points.length, "compatibility_failure_odd_keypoint");
    }
    if (hasNearDuplicateKeypoint(points, width, height)) {
      return unavailableDeviation(points.length, "compatibility_failure_duplicate");
    }
    const pairing = buildPreviewPairDiagnostics(points, width);
    if (!pairing.pairs.length) {
      return unavailableDeviation(points.length, "compatibility_failure_no_valid_vertical_pairs");
    }
    if (pairing.unpaired.length) {
      return unavailableDeviation(points.length, "compatibility_failure_unpaired_keypoints", pairing.pairs.length);
    }

    const vertical_pair_x_residual =
      pairing.pairs.reduce((acc, pair) => acc + pair.vertical_x_delta, 0) / pairing.pairs.length;
    const ceiling_y_range = range(pairing.pairs.map((pair) => pair.y_ceiling));
    const floor_y_range = range(pairing.pairs.map((pair) => pair.y_floor));
    const wall_height_range = range(pairing.pairs.map((pair) => pair.y_floor - pair.y_ceiling));
    const normalized = [
      vertical_pair_x_residual / Math.max(width, 1),
      ceiling_y_range / Math.max(height, 1),
      floor_y_range / Math.max(height, 1),
      wall_height_range / Math.max(height, 1),
    ];
    const score = clamp((normalized.reduce((acc, value) => acc + value, 0) / normalized.length) * 100, 0, 100);
    const residuals = {
      vertical_pair_x_residual,
      ceiling_y_range,
      floor_y_range,
      wall_height_range,
    };
    const diagnosis = computeDirectionOnlyDiagnosis(pairing.pairs, width, height, residuals);
    return {
      compatibility_status: "compatible",
      exclusion_reason: "none",
      n_keypoints: points.length,
      n_pairs: pairing.pairs.length,
      vertical_pair_x_residual,
      ceiling_y_range,
      floor_y_range,
      wall_height_range,
      manhattan_deviation_score: score,
      deviation_level: deviationLevel(score),
      ...diagnosis,
    };
  }

  function updateManhattanDeviationPanel(deviation) {
    setText(`${PANEL_ID}-compatibility-status`, deviation.compatibility_status);
    setText(`${PANEL_ID}-deviation-n-keypoints`, deviation.n_keypoints);
    setText(`${PANEL_ID}-deviation-n-pairs`, deviation.n_pairs);
    setText(`${PANEL_ID}-vertical-pair-x-residual`, formatMetric(deviation.vertical_pair_x_residual));
    setText(`${PANEL_ID}-ceiling-y-range`, formatMetric(deviation.ceiling_y_range));
    setText(`${PANEL_ID}-floor-y-range`, formatMetric(deviation.floor_y_range));
    setText(`${PANEL_ID}-wall-height-range`, formatMetric(deviation.wall_height_range));
    setText(`${PANEL_ID}-manhattan-deviation-score`, formatMetric(deviation.manhattan_deviation_score));
    setText(`${PANEL_ID}-deviation-level`, deviation.deviation_level);
    setText(`${PANEL_ID}-deviation-reason`, deviation.exclusion_reason);
    updateManhattanDiagnosisPanel(deviation);
  }

  function updateManhattanDiagnosisPanel(deviation) {
    setText(`${PANEL_ID}-primary-issue-type`, deviation.primary_issue_type);
    setText(`${PANEL_ID}-primary-issue-severity`, deviation.primary_issue_severity);
    setText(`${PANEL_ID}-primary-issue-explanation`, deviation.primary_issue_explanation);
    setText(`${PANEL_ID}-affected-pair-index`, deviation.affected_pair_index);
    setText(`${PANEL_ID}-affected-wall-index`, deviation.affected_wall_index);
    setText(`${PANEL_ID}-pair-x-alignment-summary`, deviation.pair_x_alignment_summary);
    setText(`${PANEL_ID}-ceiling-alignment-summary`, deviation.ceiling_alignment_summary);
    setText(`${PANEL_ID}-floor-alignment-summary`, deviation.floor_alignment_summary);
    setText(`${PANEL_ID}-wall-height-summary`, deviation.wall_height_summary);
    updateDirectionOnlyHintPanel(deviation);
  }

  function updateDirectionOnlyHintPanel(deviation) {
    setText(`${PANEL_ID}-hint-status`, deviation.hint_status);
    setText(`${PANEL_ID}-hint-component`, deviation.hint_component);
    setText(`${PANEL_ID}-hint-affected-pair-index`, deviation.affected_pair_index);
    setText(`${PANEL_ID}-direction-hint`, deviation.direction_hint);
    setText(`${PANEL_ID}-alternative-anchor-hint`, deviation.alternative_anchor_hint);
    setText(`${PANEL_ID}-hint-guardrail`, deviation.hint_guardrail);
    updateGuideBandPanel(deviation);
  }

  function updateGuideBandPanel(deviation) {
    const visible = getGuideBandsVisible();
    guideState.status = visible ? deviation.guide_status || "unavailable" : "hidden";
    guideState.mode = GUIDE_MODE;
    guideState.component = visible ? deviation.guide_component || "unavailable" : "hidden";
    guideState.affectedPairIndex = visible ? deviation.guide_affected_pair_index || "unavailable" : "hidden";
    guideState.visibleItems = visible ? deviation.guide_visible_items || "none" : "none";
    guideState.explanation = visible ? deviation.guide_explanation || "No issue-specific visual reference lines are shown." : "Visual reference lines are hidden.";
    setText(`${PANEL_ID}-guide-status`, guideState.status);
    setText(`${PANEL_ID}-guide-mode`, guideState.mode);
    setText(`${PANEL_ID}-guide-component`, guideState.component);
    setText(`${PANEL_ID}-guide-affected-pair-index`, guideState.affectedPairIndex);
    setText(`${PANEL_ID}-guide-visible-items`, guideState.visibleItems);
    setText(`${PANEL_ID}-guide-explanation`, guideState.explanation);
    setText(`${PANEL_ID}-guide-scope`, guideState.scope);
    setText(`${PANEL_ID}-guide-guardrail`, guideState.guardrail);
  }

  function updateHighlightPanel() {
    setText(`${PANEL_ID}-highlight-status`, highlightState.status);
    setText(`${PANEL_ID}-highlight-affected-pair-index`, highlightState.affectedPairIndex);
    setText(`${PANEL_ID}-highlight-row-found`, highlightState.rowFound ? "true" : "false");
    setText(`${PANEL_ID}-highlight-overlay-labels-found`, highlightState.overlayLabelsFound);
    setText(`${PANEL_ID}-diagnosis-affected-pair-index`, currentDiagnosisAffectedPairIndex === null ? "none" : currentDiagnosisAffectedPairIndex + 1);
    setText(`${PANEL_ID}-manual-selected-pair-index`, currentPreviewBasePairs.length ? currentPreviewSelectedPairIndex + 1 : "none");
    setText(`${PANEL_ID}-highlight-mode`, highlightMode());
    setText(`${PANEL_ID}-diagnosis-highlight-status`, highlightState.status);
    setText(`${PANEL_ID}-manual-highlight-status`, currentPreviewBasePairs.length ? "manual_selected_pair_active" : "manual_selected_pair_unavailable");
  }

  function setHighlightState(status, affectedPairIndex, rowFound = false, overlayLabelsFound = 0) {
    highlightState.status = status;
    highlightState.affectedPairIndex = affectedPairIndex;
    highlightState.rowFound = rowFound;
    highlightState.overlayLabelsFound = overlayLabelsFound;
    updateHighlightPanel();
  }

  function highlightMode() {
    const hasManual = currentPreviewBasePairs.length > 0;
    const hasDiagnosis = currentDiagnosisAffectedPairIndex !== null;
    if (hasManual && hasDiagnosis) {
      return currentPreviewOrder[currentPreviewSelectedPairIndex] === currentDiagnosisAffectedPairIndex
        ? "manual_and_diagnosis_same_pair"
        : "dual_state_visible";
    }
    if (hasDiagnosis) return "diagnosis_only";
    if (hasManual) return "manual_only";
    return "none";
  }

  function updateMetaGuardPanel(meta) {
    if (!meta) return;
    setText(`${PANEL_ID}-meta-guard-status`, meta.status);
    setText(`${PANEL_ID}-meta-guard-errors`, meta.errors?.length ? meta.errors.join(",") : "none");
    setText(`${PANEL_ID}-difficulty-choices`, meta.difficulty?.length ? meta.difficulty.join(",") : "none");
    setText(`${PANEL_ID}-model-issue-choices`, meta.model_issue?.length ? meta.model_issue.join(",") : "none");
  }

  function normalizePreviewUrl(rawUrl) {
    if (!rawUrl) return null;
    try {
      const url = new URL(rawUrl, window.location.href);
      if (!url.href.includes("vis_3d.html")) return null;
      return url.toString();
    } catch (e) {
      return null;
    }
  }

  function findExistingPreviewUrl() {
    const selectors = [
      "iframe[src*='vis_3d.html']",
      "a[href*='vis_3d.html']",
      "[src*='vis_3d.html']",
      "[href*='vis_3d.html']",
    ];
    for (const selector of selectors) {
      for (const element of document.querySelectorAll(selector)) {
        if (element.closest(`#${PANEL_ID}`)) continue;
        const raw = element.getAttribute("src") || element.getAttribute("href");
        const url = normalizePreviewUrl(raw);
        if (url && url.includes("data=")) return url;
      }
    }
    return null;
  }

  function findSectionContainer() {
    const headers = Array.from(document.querySelectorAll("h3"));
    const header = headers.find(
      (node) => node.textContent && node.textContent.includes("3D Layout Preview"),
    );
    if (!header) return null;
    const sibling = header.nextElementSibling;
    if (
      sibling &&
      (sibling.classList.contains("lsf-object") ||
        sibling.classList.contains("lsf-richtext") ||
        sibling.querySelector("iframe, a, [src], [href]"))
    ) {
      return sibling;
    }
    return header.parentElement || null;
  }

  function findNativePreviewIframe() {
    const byId = document.getElementById(OFFICIAL_IFRAME_ID);
    if (byId && !byId.closest(`#${PANEL_ID}`)) return byId;
    const frames = Array.from(document.querySelectorAll("iframe[src*='vis_3d.html']")).filter(
      (iframe) => !iframe.closest(`#${PANEL_ID}`),
    );
    return frames[0] || null;
  }

  function getNativePreviewUrl() {
    const image = findMainImage();
    const url = new URL(`${getViewerBaseUrl()}/tools/vis_3d.html`, window.location.href);
    url.searchParams.set("v", String(Date.now()));
    if (image) {
      const width = image.naturalWidth || DEFAULT_WIDTH;
      const height = image.naturalHeight || DEFAULT_HEIGHT;
      url.searchParams.set("w", String(width));
      url.searchParams.set("h", String(height));
    }
    return url.toString();
  }

  function ensureNativePreviewArea() {
    const container = findSectionContainer();
    if (!container) return null;
    Array.from(container.children).forEach((child) => {
      if (child.id !== OFFICIAL_WRAPPER_ID) {
        child.style.display = "none";
      }
    });
    let wrapper = document.getElementById(OFFICIAL_WRAPPER_ID);
    if (!wrapper) {
      wrapper = document.createElement("div");
      wrapper.id = OFFICIAL_WRAPPER_ID;
      container.appendChild(wrapper);
    }
    let iframe = document.getElementById(OFFICIAL_IFRAME_ID);
    if (!iframe) {
      iframe = document.createElement("iframe");
      iframe.id = OFFICIAL_IFRAME_ID;
      iframe.style.cssText = "width: 100%; height: 400px; border: none; background: #000;";
      wrapper.appendChild(iframe);
    }
    const url = getNativePreviewUrl();
    if (!iframe.dataset.src || !iframe.src) {
      iframe.dataset.src = url;
      iframe.src = url;
    }
    let button = document.getElementById(OFFICIAL_BUTTON_ID);
    if (!button) {
      button = document.createElement("button");
      button.id = OFFICIAL_BUTTON_ID;
      button.type = "button";
      button.textContent = "Refresh 3D Preview";
      button.style.cssText =
        "margin-top: 10px; padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;";
      button.addEventListener("click", function () {
        const state = extractKeypointsFromDom();
        state.preview_update_status = updatePreviewIframe(state);
        renderPanel(state);
      });
      wrapper.appendChild(button);
    }
    let toggleLabelsButton = document.getElementById(TOGGLE_LABELS_BUTTON_ID);
    if (!toggleLabelsButton) {
      toggleLabelsButton = document.createElement("button");
      toggleLabelsButton.id = TOGGLE_LABELS_BUTTON_ID;
      toggleLabelsButton.type = "button";
      toggleLabelsButton.style.cssText =
        "margin-top: 10px; margin-left: 10px; padding: 8px 16px; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;";
      applyToggleBtnState(toggleLabelsButton, getLabelsVisible());
      toggleLabelsButton.addEventListener("click", toggleCornerOrderLabels);
      wrapper.appendChild(toggleLabelsButton);
    }
    return iframe;
  }

  function extractPairsFromPreviewUrl(previewUrl) {
    try {
      const url = new URL(previewUrl, window.location.href);
      const rawData = url.searchParams.get("data");
      if (!rawData) return [];
      const parsed = JSON.parse(rawData);
      if (!Array.isArray(parsed)) return [];
      return parsed
        .map((corner) => ({
          x: Number(corner.x),
          y_ceiling: Number(corner.y_ceiling),
          y_floor: Number(corner.y_floor),
        }))
        .filter(
          (corner) =>
            Number.isFinite(corner.x) &&
            Number.isFinite(corner.y_ceiling) &&
            Number.isFinite(corner.y_floor),
        );
    } catch (e) {
      return [];
    }
  }

  function getPreviewUrl(state) {
    return state?.preview_url || `${getViewerBaseUrl()}/tools/vis_3d.html?v=${Date.now()}`;
  }

  function extractOverlayKeypoints(points) {
    const mainImage = findMainImage();
    if (!mainImage) return;
    const imageRect = mainImage.getBoundingClientRect();
    if (!imageRect.width || !imageRect.height) return;
    const candidates = Array.from(
      document.querySelectorAll(
        "[class*='keypoint'], [class*='Keypoint'], [class*='point'], [class*='Point'], [aria-label*='Corner'], [title*='Corner']",
      ),
    );
    for (const element of candidates) {
      if (element.closest(`#${PANEL_ID}`)) continue;
      const rect = element.getBoundingClientRect();
      if (!rect.width || !rect.height) continue;
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      if (
        centerX < imageRect.left ||
        centerX > imageRect.right ||
        centerY < imageRect.top ||
        centerY > imageRect.bottom
      ) {
        continue;
      }
      points.push({
        x: ((centerX - imageRect.left) / imageRect.width) * DEFAULT_WIDTH,
        y: ((centerY - imageRect.top) / imageRect.height) * DEFAULT_HEIGHT,
        source: "dom-keypoint-overlay",
      });
    }
  }

  function extractKeypointsFromDom() {
    const store = getStore();
    const storeStatus = store ? "available" : "unavailable";
    const storeExtraction = extractKeypointsFromStore(store, DEFAULT_WIDTH, DEFAULT_HEIGHT);
    const points = storeExtraction.keypoints;
    const previewUrl = findExistingPreviewUrl();
    const previewPairs = extractPairsFromPreviewUrl(previewUrl);

    for (const circle of document.querySelectorAll("svg circle")) {
      const x = numericAttr(circle, ["cx"]);
      const y = numericAttr(circle, ["cy"]);
      if (x !== null && y !== null) {
        points.push({ x, y, source: "svg-circle" });
      }
    }

    for (const element of document.querySelectorAll("[data-x][data-y], [data-keypoint-x][data-keypoint-y]")) {
      const x = numericAttr(element, ["data-keypoint-x", "data-x"]);
      const y = numericAttr(element, ["data-keypoint-y", "data-y"]);
      if (x !== null && y !== null) {
        points.push({ x, y, source: "data-attribute" });
      }
    }

    extractOverlayKeypoints(points);

    const unique = [];
    const seen = new Set();
    for (const point of points) {
      const key = `${point.source}:${point.x}:${point.y}`;
      if (!seen.has(key)) {
        unique.push(point);
        seen.add(key);
      }
    }

    return {
      keypoint_read_status: unique.length > 0 ? "available" : "unavailable",
      keypoints: unique,
      manhattan_deviation: computeManhattanDeviation(unique, DEFAULT_WIDTH, DEFAULT_HEIGHT),
      store_status: storeStatus,
      result_count: storeExtraction.result_count,
      keypoint_sources: Array.from(new Set(unique.map((point) => point.source))).join(",") || "none",
      page_signature: currentTaskSignature(),
      preview_url_status: previewUrl ? "available" : "unavailable",
      preview_url: previewUrl,
      preview_pairs: previewPairs,
      native_preview_status: findNativePreviewIframe() ? "available" : "unavailable",
      preview_update_status: "not_run",
    };
  }

  function normalizePreviewOrder(order, length) {
    if (!Array.isArray(order) || order.length !== length) return null;
    const seen = new Set();
    const normalized = [];
    for (const raw of order) {
      const index = Number(raw);
      if (!Number.isInteger(index) || index < 0 || index >= length || seen.has(index)) return null;
      seen.add(index);
      normalized.push(index);
    }
    return normalized;
  }

  function orderedPreviewPairs() {
    const order = normalizePreviewOrder(currentPreviewOrder, currentPreviewBasePairs.length);
    return order ? order.map((index) => currentPreviewBasePairs[index]) : currentPreviewBasePairs.slice();
  }

  function currentTaskSignature() {
    const store = getStore();
    const taskId = store?.task?.id || store?.taskStore?.selected?.id || new URLSearchParams(window.location.search).get("task") || "unknown_task";
    const annotationId = store?.annotationStore?.selected?.id || "unknown_annotation";
    const imageUrl = findMainImage()?.src || getImageUrlFromStore() || window.location.href;
    return `${taskId}|${annotationId}|${imageUrl}`;
  }

  function clearPreviewOrderRuntime() {
    currentPreviewBasePairs = [];
    currentPreviewOrder = [];
    currentPreviewSelectedPairIndex = 0;
    currentDiagnosisAffectedPairIndex = null;
    highlightState.status = "not_applied";
    highlightState.affectedPairIndex = "none";
    highlightState.rowFound = false;
    highlightState.overlayLabelsFound = 0;
    const overlay = document.getElementById(OVERLAY_ID);
    if (overlay) overlay.remove();
    updatePreviewOrderPanelUi();
    updateHighlightPanel();
  }

  function clearPreviewOrderOnTaskChange(signature) {
    if (!signature) return;
    if (currentPageSignature === null) {
      currentPageSignature = signature;
      return;
    }
    if (signature !== currentPageSignature) {
      currentPageSignature = signature;
      clearPreviewOrderRuntime();
    }
  }

  function positionOverlay() {
    const image = findMainImage();
    const overlay = document.getElementById(OVERLAY_ID);
    if (!image || !overlay) return null;
    const rect = image.getBoundingClientRect();
    overlay.style.left = `${rect.left}px`;
    overlay.style.top = `${rect.top}px`;
    overlay.style.width = `${rect.width}px`;
    overlay.style.height = `${rect.height}px`;
    return rect;
  }

  function drawGuideLine(overlay, styleText, labelText) {
    const line = document.createElement("div");
    line.className = "hohonet-m13-guide-band";
    line.style.cssText = styleText;
    line.setAttribute("aria-label", labelText);
    overlay.appendChild(line);
  }

  function drawGuideLegend(overlay) {
    const legend = document.createElement("div");
    legend.className = "hohonet-m13-guide-legend";
    legend.style.cssText =
      "position:absolute;left:8px;top:8px;z-index:3;padding:5px 7px;border-radius:6px;background:rgba(17,24,39,0.66);color:#f9fafb;font:11px/1.35 system-ui,sans-serif;box-shadow:0 2px 8px rgba(0,0,0,0.22);pointer-events:none;";
    legend.innerHTML =
      '<div><span style="display:inline-block;width:14px;height:3px;background:rgba(56,189,248,0.72);margin-right:5px;vertical-align:middle;"></span>Ceiling reference</div>' +
      '<div><span style="display:inline-block;width:14px;height:3px;background:rgba(34,197,94,0.64);margin-right:5px;vertical-align:middle;"></span>Floor reference</div>' +
      '<div><span style="display:inline-block;width:3px;height:12px;background:rgba(255,138,0,0.78);margin:0 10px 0 5px;vertical-align:middle;"></span>Affected pair axis</div>' +
      '<div><span style="display:inline-block;width:14px;height:8px;border-left:3px solid rgba(168,85,247,0.86);border-top:2px solid rgba(168,85,247,0.62);border-bottom:2px solid rgba(168,85,247,0.62);margin-right:5px;vertical-align:middle;"></span>Height check</div>';
    overlay.appendChild(legend);
  }

  function pairPointForGuide(pair, kind) {
    const points = Array.isArray(pair?.originalPoints) ? pair.originalPoints : [];
    const point = points.reduce((best, current) => {
      if (!best) return current;
      return kind === "ceiling"
        ? (current.y < best.y ? current : best)
        : (current.y > best.y ? current : best);
    }, null);
    if (!point) return null;
    const pctX = Number.isFinite(point.pctX) ? point.pctX : (point.x / DEFAULT_WIDTH) * 100;
    const pctY = Number.isFinite(point.pctY) ? point.pctY : (point.y / DEFAULT_HEIGHT) * 100;
    return { pctX, pctY };
  }

  function drawPointEmphasis(overlay, rect, point, color, labelText) {
    if (!point) return;
    const marker = document.createElement("div");
    marker.className = "hohonet-m13-guide-point";
    marker.setAttribute("aria-label", labelText);
    marker.style.cssText =
      `position:absolute;left:${(point.pctX / 100) * rect.width}px;top:${(point.pctY / 100) * rect.height}px;` +
      `width:18px;height:18px;border-radius:50%;transform:translate(-50%,-50%);border:3px solid ${color};background:rgba(255,255,255,0.20);box-shadow:0 0 0 3px rgba(17,24,39,0.30);pointer-events:none;`;
    overlay.appendChild(marker);
  }

  function drawHorizontalGuide(overlay, top, color, alpha, labelText) {
    drawGuideLine(
      overlay,
      `position:absolute;left:0;right:0;top:${top - 1}px;height:3px;background:${color.replace("__ALPHA__", alpha)};box-shadow:0 0 0 1px rgba(17,24,39,0.18);pointer-events:none;`,
      labelText,
    );
  }

  function drawAffectedPairAxis(overlay, rect, pair, alpha, labelText) {
    if (!pair || !Number.isFinite(pair.x)) return;
    const left = (pair.x / DEFAULT_WIDTH) * rect.width;
    const top = (pair.y_ceiling / DEFAULT_HEIGHT) * rect.height;
    const bottom = (pair.y_floor / DEFAULT_HEIGHT) * rect.height;
    drawGuideLine(
      overlay,
      `position:absolute;top:${top}px;height:${Math.max(4, bottom - top)}px;left:${left - 1}px;width:3px;background:rgba(255,138,0,${alpha});box-shadow:0 0 0 1px rgba(154,52,18,0.42);pointer-events:none;`,
      labelText,
    );
  }

  function drawHeightBracket(overlay, rect, pair) {
    if (!pair || !Number.isFinite(pair.x)) return;
    const left = (pair.x / DEFAULT_WIDTH) * rect.width;
    const top = (pair.y_ceiling / DEFAULT_HEIGHT) * rect.height;
    const bottom = (pair.y_floor / DEFAULT_HEIGHT) * rect.height;
    drawGuideLine(
      overlay,
      `position:absolute;top:${top}px;height:${Math.max(4, bottom - top)}px;left:${left + 7}px;width:12px;border-left:4px solid rgba(168,85,247,0.86);border-top:3px solid rgba(168,85,247,0.70);border-bottom:3px solid rgba(168,85,247,0.70);background:transparent;pointer-events:none;`,
      "height check bracket",
    );
  }

  function renderGuideBands(overlay, rect, pairs) {
    if (!getGuideBandsVisible()) return;
    const orderedPairs = Array.isArray(pairs) ? pairs : [];
    if (!orderedPairs.length) return;
    const deviation = currentSandboxState?.manhattan_deviation || {};
    const component = deviation.guide_component || deviation.primary_issue_type || "unavailable";
    const affectedIndex = Number(deviation.guide_affected_pair_index || deviation.affected_pair_index) - 1;
    const ceilingMedian = median(orderedPairs.map((pair) => pair.y_ceiling));
    const floorMedian = median(orderedPairs.map((pair) => pair.y_floor));
    const affectedBaseIndex = currentDiagnosisAffectedPairIndex !== null ? currentDiagnosisAffectedPairIndex : affectedIndex;
    const affectedPair = Number.isInteger(affectedBaseIndex)
      ? orderedPairs.find((pair) => Number(pair?.base_pair_index) === affectedBaseIndex)
      : null;
    if (!Number.isFinite(ceilingMedian) || !Number.isFinite(floorMedian) || !affectedPair) return;
    const ceilingTop = (ceilingMedian / DEFAULT_HEIGHT) * rect.height;
    const floorTop = (floorMedian / DEFAULT_HEIGHT) * rect.height;
    drawGuideLegend(overlay);
    if (component === "pair_x_alignment") {
      drawAffectedPairAxis(overlay, rect, affectedPair, "0.78", "affected pair guide");
    } else if (component === "ceiling_alignment") {
      drawHorizontalGuide(overlay, ceilingTop, "rgba(56,189,248,__ALPHA__)", "0.72", "median ceiling band");
      drawPointEmphasis(overlay, rect, pairPointForGuide(affectedPair, "ceiling"), "rgba(56,189,248,0.94)", "affected ceiling point");
    } else if (component === "floor_alignment") {
      drawHorizontalGuide(overlay, floorTop, "rgba(34,197,94,__ALPHA__)", "0.64", "median floor band");
      drawPointEmphasis(overlay, rect, pairPointForGuide(affectedPair, "floor"), "rgba(34,197,94,0.92)", "affected floor point");
    } else if (component === "wall_height_consistency") {
      drawHorizontalGuide(overlay, ceilingTop, "rgba(56,189,248,__ALPHA__)", "0.18", "median ceiling band context");
      drawHorizontalGuide(overlay, floorTop, "rgba(34,197,94,__ALPHA__)", "0.16", "median floor band context");
      drawAffectedPairAxis(overlay, rect, affectedPair, "0.42", "affected pair guide context");
      drawHeightBracket(overlay, rect, affectedPair);
    }
  }

  function renderPreviewOverlayPairs(pairs) {
    const image = findMainImage();
    if (!image) return;
    let overlay = document.getElementById(OVERLAY_ID);
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = OVERLAY_ID;
      overlay.style.cssText = "position: fixed; pointer-events: none; z-index: 2147483646; overflow: hidden;";
      document.body.appendChild(overlay);
    }
    overlay.innerHTML = "";
    const labelsVisible = getLabelsVisible();
    overlay.style.display = labelsVisible || getGuideBandsVisible() ? "block" : "none";
    const rect = positionOverlay();
    if (!rect) return;
    renderGuideBands(overlay, rect, pairs);
    let affectedOverlayCount = 0;
    if (labelsVisible) (Array.isArray(pairs) ? pairs : []).forEach((pair, index) => {
      for (const point of Array.isArray(pair?.originalPoints) ? pair.originalPoints : []) {
        const pctX = Number.isFinite(point.pctX) ? point.pctX : (point.x / DEFAULT_WIDTH) * 100;
        const pctY = Number.isFinite(point.pctY) ? point.pctY : (point.y / DEFAULT_HEIGHT) * 100;
        const badge = document.createElement("div");
        const isAffected = Number(pair?.base_pair_index) === currentDiagnosisAffectedPairIndex;
        const isManualSelected = index === currentPreviewSelectedPairIndex;
        const classes = [];
        if (isManualSelected) classes.push("manual-selected-pair");
        if (isAffected) classes.push("diagnosis-affected-pair");
        if (isManualSelected && isAffected) classes.push("manual-and-diagnosis-pair");
        badge.className = classes.join(" ");
        badge.dataset.basePairIndex = Number.isFinite(Number(pair?.base_pair_index)) ? String(Number(pair.base_pair_index) + 1) : String(index + 1);
        badge.dataset.displayPairIndex = String(index + 1);
        badge.textContent = String(index + 1);
        badge.style.cssText =
          "position:absolute;transform:translate(-50%,-150%);background:rgba(255,255,255,0.56);color:#111827;font-weight:800;padding:2px 6px;border-radius:4px;font-size:12px;border:1px solid rgba(17,24,39,0.55);box-shadow:0 1px 4px rgba(0,0,0,0.22);";
        if (isManualSelected) {
          badge.style.background = "rgba(47,92,255,0.58)";
          badge.style.color = "#fff";
          badge.style.outline = "3px solid rgba(47,92,255,0.78)";
          badge.style.boxShadow = "0 0 0 3px rgba(47,92,255,0.28)";
        }
        if (isAffected) {
          affectedOverlayCount += 1;
          badge.style.background = "rgba(255,138,0,0.62)";
          badge.style.color = "#111827";
          badge.style.border = "2px solid rgba(124,45,18,0.9)";
          badge.style.outline = "4px solid rgba(255,122,0,0.86)";
          badge.style.boxShadow = "0 0 0 4px rgba(255,122,0,0.32)";
        }
        if (isManualSelected && isAffected) {
          badge.style.background = "rgba(168,85,247,0.62)";
          badge.style.color = "#fff";
          badge.style.border = "2px solid rgba(88,28,135,0.92)";
          badge.style.outline = "4px solid rgba(168,85,247,0.84)";
          badge.style.boxShadow = "0 0 0 4px rgba(168,85,247,0.30)";
        }
        badge.style.left = `${(pctX / 100) * rect.width}px`;
        badge.style.top = `${(pctY / 100) * rect.height}px`;
        overlay.appendChild(badge);
      }
    });
    if (currentDiagnosisAffectedPairIndex !== null) {
      setHighlightState(highlightState.status, highlightState.affectedPairIndex, highlightState.rowFound, affectedOverlayCount);
    }
  }

  function sendPreviewOrderToIframe() {
    const iframe = findNativePreviewIframe();
    if (!iframe || !iframe.contentWindow || !currentPreviewBasePairs.length) return "native_preview_unavailable";
    const ordered = orderedPreviewPairs();
    const imageUrl = findMainImage()?.src || getImageUrlFromStore();
    iframe.contentWindow.postMessage(
      {
        type: "update_layout",
        corners: ordered,
        baseCorners: currentPreviewBasePairs,
        width: DEFAULT_WIDTH,
        height: DEFAULT_HEIGHT,
        imageUrl: withCacheBust(rewriteTextureUrlForViewer(imageUrl)),
        preserveOrder: true,
        previewOrderActive: true,
        previewOrder: currentPreviewOrder.slice(),
        previewSignature: "m8-sandbox-local-order",
      },
      "*",
    );
    renderPreviewOverlayPairs(ordered);
    updatePreviewOrderPanelUi();
    return "native_preview_order_update_sent";
  }

  function setPreviewBasePairs(pairs) {
    currentPreviewBasePairs = (Array.isArray(pairs) ? pairs : []).map((pair, index) => {
      const lsCoord = pairLsCoordSummary(pair);
      return {
        ...pair,
        base_pair_index: index,
        display_pair_index: index + 1,
        x_ls: lsCoord.derived ? lsCoord.top.x : (lsCoord.top.x + lsCoord.bottom.x) / 2,
        ceiling_y_ls: lsCoord.top.y,
        floor_y_ls: lsCoord.bottom.y,
      };
    });
    currentPreviewOrder = currentPreviewBasePairs.map((_, index) => index);
    currentPreviewSelectedPairIndex = 0;
    currentDiagnosisAffectedPairIndex = null;
    highlightState.status = "not_applied";
    highlightState.affectedPairIndex = "none";
    highlightState.rowFound = false;
    highlightState.overlayLabelsFound = 0;
    renderPreviewOverlayPairs(orderedPreviewPairs());
    ensurePreviewOrderPanel();
    updatePreviewOrderPanelUi();
  }

  function toggleCornerOrderLabels() {
    const visible = !getLabelsVisible();
    setLabelsVisible(visible);
    applyToggleBtnState(document.getElementById(TOGGLE_LABELS_BUTTON_ID), visible);
    renderPreviewOverlayPairs(orderedPreviewPairs());
  }

  function toggleGuideBands() {
    const visible = !getGuideBandsVisible();
    setGuideBandsVisible(visible);
    applyGuideBtnState(document.getElementById(GUIDE_BANDS_BUTTON_ID), visible);
    renderPreviewOverlayPairs(orderedPreviewPairs());
    updateGuideBandPanel(currentSandboxState?.manhattan_deviation || unavailableDeviation(0, "missing_keypoints"));
  }

  function highlightAffectedPair() {
    const deviation = currentSandboxState?.manhattan_deviation;
    const rawIndex = Number(deviation?.affected_pair_index);
    if (!Number.isInteger(rawIndex) || rawIndex < 1 || rawIndex > currentPreviewBasePairs.length) {
      setHighlightState("unavailable_no_valid_pair", "unavailable");
      return;
    }
    const affectedBaseIndex = rawIndex - 1;
    const displayIndex = currentPreviewOrder.indexOf(affectedBaseIndex);
    if (displayIndex < 0) {
      setHighlightState("unavailable_pair_not_in_order", rawIndex);
      return;
    }
    currentDiagnosisAffectedPairIndex = affectedBaseIndex;
    updatePreviewOrderPanelUi();
    renderPreviewOverlayPairs(orderedPreviewPairs());
    const row = document.querySelector(`#${PREVIEW_PANEL_ID}-pair-rows [data-base-pair-index="${rawIndex}"]`);
    const overlayCount = document.querySelectorAll(`#${OVERLAY_ID} .diagnosis-affected-pair`).length;
    setHighlightState(row || overlayCount ? "diagnosis_highlight_applied" : "unavailable_pair_not_found", rawIndex, Boolean(row), overlayCount);
  }

  function scrollToAffectedPair() {
    if (currentDiagnosisAffectedPairIndex === null) {
      setHighlightState("unavailable_no_diagnosis_highlight", "unavailable");
      return;
    }
    const row = document.querySelector(`#${PREVIEW_PANEL_ID}-pair-rows [data-base-pair-index="${currentDiagnosisAffectedPairIndex + 1}"]`);
    if (!row || typeof row.scrollIntoView !== "function") {
      setHighlightState("unavailable_pair_not_found", currentDiagnosisAffectedPairIndex + 1);
      return;
    }
    row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    setHighlightState("diagnosis_highlight_scrolled", currentDiagnosisAffectedPairIndex + 1, true, highlightState.overlayLabelsFound);
  }

  function swapPreviewPairs(fromIndex, toIndex) {
    if (!currentPreviewOrder.length) return;
    const from = Math.max(0, Math.min(currentPreviewOrder.length - 1, fromIndex));
    const to = Math.max(0, Math.min(currentPreviewOrder.length - 1, toIndex));
    const next = currentPreviewOrder.slice();
    const tmp = next[from];
    next[from] = next[to];
    next[to] = tmp;
    currentPreviewOrder = next;
    currentPreviewSelectedPairIndex = to;
    sendPreviewOrderToIframe();
  }

  function updatePreviewOrderPanelUi() {
    setText(`${PREVIEW_PANEL_ID}-slot`, currentPreviewBasePairs.length ? `${currentPreviewSelectedPairIndex + 1} / ${currentPreviewBasePairs.length}` : "-- / --");
    setText(`${PREVIEW_PANEL_STATUS_ID}`, currentPreviewBasePairs.length ? "sandbox preview-order override active; preview-only, no annotation writeback" : "no preview pairs available");
    setText(
      `${PREVIEW_PANEL_ID}-order`,
      currentPreviewOrder.length ? currentPreviewOrder.map((index) => index + 1).join(" -> ") : "none",
    );
    renderPreviewPairRows();
    const pairInput = document.getElementById(PREVIEW_PANEL_PAIR_INPUT_ID);
    if (pairInput && document.activeElement !== pairInput) pairInput.value = String(currentPreviewSelectedPairIndex + 1);
    const swapInput = document.getElementById(PREVIEW_PANEL_SWAP_INPUT_ID);
    if (swapInput && document.activeElement !== swapInput) swapInput.value = String(Math.min(currentPreviewBasePairs.length, currentPreviewSelectedPairIndex + 2 || 1));
    updateHighlightPanel();
  }

  function renderPreviewPairRows() {
    const container = document.getElementById(`${PREVIEW_PANEL_ID}-pair-rows`);
    if (!container) return;
    container.innerHTML = "";
    const ordered = orderedPreviewPairs();
    if (!ordered.length) {
      container.textContent = "No pairs available";
      return;
    }
    ordered.forEach((pair, displayIndex) => {
      const row = document.createElement("button");
      row.type = "button";
      const isActive = displayIndex === currentPreviewSelectedPairIndex;
      const isAffected = Number(pair?.base_pair_index) === currentDiagnosisAffectedPairIndex;
      row.className = `hp-pair-row${isActive ? " active-pair manual-selected-pair" : ""}${isAffected ? " diagnosis-affected-pair" : ""}${isActive && isAffected ? " manual-and-diagnosis-pair" : ""}`;
      row.dataset.activePair = displayIndex === currentPreviewSelectedPairIndex ? "true" : "false";
      row.dataset.manualSelectedPair = isActive ? "true" : "false";
      row.dataset.diagnosisAffectedPair = isAffected ? "true" : "false";
      row.dataset.basePairIndex = Number.isFinite(Number(pair?.base_pair_index)) ? String(Number(pair.base_pair_index) + 1) : String(displayIndex + 1);
      row.dataset.displayPairIndex = String(displayIndex + 1);
      row.style.cssText =
        "width:100%;display:grid;grid-template-columns:36px 1fr 46px;align-items:center;gap:6px;margin-top:4px;padding:5px 6px;border:1px solid rgba(255,255,255,0.08);border-radius:7px;background:rgba(255,255,255,0.055);color:#f4f7fb;text-align:left;cursor:pointer;font-size:11px;";
      if (isActive) {
        row.style.background = "rgba(47,92,255,0.32)";
        row.style.borderColor = "rgba(111,153,255,0.72)";
      }
      if (isAffected) {
        row.style.outline = "3px solid #ff8a00";
        row.style.boxShadow = "inset 5px 0 0 #ff8a00, 0 0 0 2px rgba(255,138,0,0.22)";
        row.style.borderColor = "#ff8a00";
        row.style.background = "rgba(255,138,0,0.34)";
      }
      if (isActive && isAffected) {
        row.style.outline = "2px solid #a855f7";
        row.style.boxShadow = "inset 5px 0 0 #a855f7, 0 0 0 2px rgba(168,85,247,0.22)";
        row.style.borderColor = "#a855f7";
        row.style.background = "rgba(168,85,247,0.26)";
      }
      const lsCoord = pairLsCoordSummary(pair);
      const prefix = lsCoord.derived ? "derived " : "";
      row.innerHTML = `<strong>Pair ${displayIndex + 1}</strong><span>${prefix}top: x=${formatLsCoord(lsCoord.top.x)}, y=${formatLsCoord(lsCoord.top.y)}<br>${prefix}bottom: x=${formatLsCoord(lsCoord.bottom.x)}, y=${formatLsCoord(lsCoord.bottom.y)}</span><span>${isActive && isAffected ? "selected+affected" : isAffected ? "affected" : isActive ? "selected" : ""}</span>`;
      row.addEventListener("click", () => {
        currentPreviewSelectedPairIndex = displayIndex;
        updatePreviewOrderPanelUi();
        renderPreviewOverlayPairs(orderedPreviewPairs());
      });
      container.appendChild(row);
    });
  }

  function installPreviewOrderPanelDrag(panel, header) {
    if (!panel || !header || header.dataset.dragBound === "1") return;
    header.dataset.dragBound = "1";
    let dragging = false;
    let offsetX = 0;
    let offsetY = 0;
    header.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button")) return;
      const rect = panel.getBoundingClientRect();
      dragging = true;
      offsetX = event.clientX - rect.left;
      offsetY = event.clientY - rect.top;
      header.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
    header.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      panel.style.left = `${Math.max(8, Math.min(window.innerWidth - 120, event.clientX - offsetX))}px`;
      panel.style.top = `${Math.max(8, Math.min(window.innerHeight - 80, event.clientY - offsetY))}px`;
    });
    const stop = (event) => {
      if (!dragging) return;
      dragging = false;
      try {
        window.localStorage.setItem(PREVIEW_PANEL_POSITION_KEY, JSON.stringify({ left: panel.style.left, top: panel.style.top }));
      } catch (e) {}
      if (event && header.hasPointerCapture(event.pointerId)) header.releasePointerCapture(event.pointerId);
    };
    header.addEventListener("pointerup", stop);
    header.addEventListener("pointercancel", stop);
  }

  function ensurePreviewOrderPanel() {
    let panel = document.getElementById(PREVIEW_PANEL_ID);
    if (panel) return panel;
    panel = document.createElement("div");
    panel.id = PREVIEW_PANEL_ID;
    panel.style.cssText =
      "position:fixed;z-index:2147483646;right:370px;bottom:12px;width:282px;color:#f4f7fb;background:rgba(40,44,50,0.86);border:1px solid rgba(255,255,255,0.10);border-radius:10px;box-shadow:0 12px 30px rgba(0,0,0,0.22);font:12px/1.4 system-ui,sans-serif;overflow:hidden;backdrop-filter:blur(14px);";
    try {
      const saved = JSON.parse(window.localStorage.getItem(PREVIEW_PANEL_POSITION_KEY) || "null");
      if (saved?.left && saved?.top) {
        panel.style.left = saved.left;
        panel.style.top = saved.top;
        panel.style.right = "auto";
        panel.style.bottom = "auto";
      }
    } catch (e) {}
    const header = document.createElement("div");
    header.id = PREVIEW_PANEL_HEADER_ID;
    header.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 10px;cursor:move;user-select:none;background:linear-gradient(180deg,rgba(255,255,255,0.07),rgba(255,255,255,0.025));border-bottom:1px solid rgba(255,255,255,0.08);";
    const title = document.createElement("div");
    title.innerHTML = `<div class="hp-title" style="font-size:13px;font-weight:800;">Preview order</div><div id="${PREVIEW_PANEL_ID}-slot" class="hp-slot" style="font-size:11px;color:#d9e2ec;">-- / --</div>`;
    const collapse = document.createElement("button");
    collapse.type = "button";
    collapse.textContent = "Hide";
    collapse.className = "hp-toggle";
    collapse.style.cssText = "border:none;border-radius:7px;padding:4px 7px;background:rgba(255,255,255,0.12);color:white;cursor:pointer;font-size:11px;font-weight:700;";
    collapse.addEventListener("click", () => {
      const body = document.getElementById(`${PREVIEW_PANEL_ID}-body`);
      const collapsed = body.style.display !== "none";
      body.style.display = collapsed ? "none" : "block";
      panel.dataset.collapsed = collapsed ? "1" : "0";
      panel.style.width = collapsed ? "174px" : "282px";
      panel.style.maxHeight = collapsed ? "44px" : "";
      collapse.textContent = collapsed ? "Show" : "Hide";
    });
    header.appendChild(title);
    header.appendChild(collapse);
    const body = document.createElement("div");
    body.id = `${PREVIEW_PANEL_ID}-body`;
    body.style.cssText = "padding:9px 10px 10px;";
    const note = document.createElement("div");
    note.className = "hp-note";
    note.style.cssText = "color:#d6deea;margin-bottom:5px;font-size:11px;line-height:1.38;";
    note.textContent = "Preview-only order controls. No annotation writeback.";
    const status = document.createElement("div");
    status.id = PREVIEW_PANEL_STATUS_ID;
    status.className = "hp-status";
    status.style.cssText = "color:#9fd0ff;margin-bottom:7px;font-size:11px;line-height:1.38;";
    status.textContent = "no preview pairs available";
    body.appendChild(note);
    body.appendChild(status);
    const legend = document.createElement("div");
    legend.className = "hp-legend";
    legend.style.cssText = "display:grid;grid-template-columns:1fr;gap:2px;margin:6px 0 7px;color:#d6deea;font-size:11px;line-height:1.35;";
    legend.innerHTML = '<div><span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:#2f5cff;margin-right:5px;"></span>Blue: manual selected</div><div><span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:#ff8a00;margin-right:5px;"></span>Orange: diagnosis affected</div><div><span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:#a855f7;margin-right:5px;"></span>Purple: both</div>';
    body.appendChild(legend);
    const orderSection = document.createElement("div");
    orderSection.className = "hp-section";
    orderSection.style.cssText = "margin-top:7px;";
    orderSection.innerHTML = `<div class="hp-label" style="margin-bottom:4px;font-size:10px;font-weight:700;letter-spacing:0.04em;color:#9aa8b8;text-transform:uppercase;">Current order</div><div id="${PREVIEW_PANEL_ID}-order" class="hp-row" style="display:flex;flex-wrap:wrap;align-items:center;gap:5px;color:#f4f7fb;">none</div>`;
    body.appendChild(orderSection);
    const pairRowsSection = document.createElement("div");
    pairRowsSection.className = "hp-section";
    pairRowsSection.style.cssText = "margin-top:7px;";
    pairRowsSection.innerHTML = `<div class="hp-label" style="margin-bottom:4px;font-size:10px;font-weight:700;letter-spacing:0.04em;color:#9aa8b8;text-transform:uppercase;">Pair rows</div><div id="${PREVIEW_PANEL_ID}-pair-rows" class="hp-pair-rows" style="max-height:120px;overflow:auto;">No pairs available</div>`;
    body.appendChild(pairRowsSection);
    const pairInput = document.createElement("input");
    pairInput.id = PREVIEW_PANEL_PAIR_INPUT_ID;
    pairInput.type = "number";
    pairInput.min = "1";
    pairInput.step = "1";
    pairInput.style.cssText = "width:54px;padding:4px 6px;border-radius:7px;border:1px solid #415067;background:rgba(11,17,24,0.85);color:white;font-size:12px;";
    pairInput.addEventListener("change", () => {
      const next = Number(pairInput.value) - 1;
      if (Number.isInteger(next) && next >= 0 && next < currentPreviewBasePairs.length) {
        currentPreviewSelectedPairIndex = next;
        updatePreviewOrderPanelUi();
      }
    });
    const prev = document.createElement("button");
    prev.type = "button";
    prev.textContent = "Prev pair";
    prev.style.cssText = "border:none;border-radius:7px;padding:5px 8px;color:white;background:#5e6a7a;cursor:pointer;font-weight:700;font-size:12px;";
    prev.addEventListener("click", () => {
      currentPreviewSelectedPairIndex = Math.max(0, currentPreviewSelectedPairIndex - 1);
      updatePreviewOrderPanelUi();
    });
    const next = document.createElement("button");
    next.type = "button";
    next.textContent = "Next pair";
    next.style.cssText = "border:none;border-radius:7px;padding:5px 8px;color:white;background:#5e6a7a;cursor:pointer;font-weight:700;font-size:12px;";
    next.addEventListener("click", () => {
      currentPreviewSelectedPairIndex = Math.min(currentPreviewBasePairs.length - 1, currentPreviewSelectedPairIndex + 1);
      updatePreviewOrderPanelUi();
    });
    const swapInput = document.createElement("input");
    swapInput.id = PREVIEW_PANEL_SWAP_INPUT_ID;
    swapInput.type = "number";
    swapInput.min = "1";
    swapInput.step = "1";
    swapInput.style.cssText = "width:54px;padding:4px 6px;border-radius:7px;border:1px solid #415067;background:rgba(11,17,24,0.85);color:white;font-size:12px;";
    const swap = document.createElement("button");
    swap.type = "button";
    swap.textContent = "Swap";
    swap.style.cssText = "border:none;border-radius:7px;padding:5px 8px;color:white;background:#5e6a7a;cursor:pointer;font-weight:700;font-size:12px;";
    swap.addEventListener("click", () => {
      const target = Number(swapInput.value) - 1;
      if (Number.isInteger(target)) swapPreviewPairs(currentPreviewSelectedPairIndex, target);
    });
    const reset = document.createElement("button");
    reset.type = "button";
    reset.textContent = "Reset preview order";
    reset.style.cssText = "border:none;border-radius:7px;padding:5px 8px;color:white;background:#5e6a7a;cursor:pointer;font-weight:700;font-size:12px;";
    reset.addEventListener("click", () => {
      currentPreviewOrder = currentPreviewBasePairs.map((_, index) => index);
      currentPreviewSelectedPairIndex = 0;
      sendPreviewOrderToIframe();
    });
    const locateSection = document.createElement("div");
    locateSection.className = "hp-section";
    locateSection.style.cssText = "margin-top:7px;";
    locateSection.innerHTML = `<div class="hp-label" style="margin-bottom:4px;font-size:10px;font-weight:700;letter-spacing:0.04em;color:#9aa8b8;text-transform:uppercase;">Active pair</div>`;
    const locateRow = document.createElement("div");
    locateRow.className = "hp-row";
    locateRow.style.cssText = "display:flex;flex-wrap:wrap;align-items:center;gap:5px;";
    locateRow.appendChild(text("Pair "));
    locateRow.appendChild(pairInput);
    locateRow.appendChild(prev);
    locateRow.appendChild(next);
    locateSection.appendChild(locateRow);
    const swapSection = document.createElement("div");
    swapSection.className = "hp-section";
    swapSection.style.cssText = "margin-top:7px;";
    swapSection.innerHTML = `<div class="hp-label" style="margin-bottom:4px;font-size:10px;font-weight:700;letter-spacing:0.04em;color:#9aa8b8;text-transform:uppercase;">Swap order</div>`;
    const swapRow = document.createElement("div");
    swapRow.className = "hp-row";
    swapRow.style.cssText = "display:flex;flex-wrap:wrap;align-items:center;gap:5px;";
    swapRow.appendChild(text("With "));
    swapRow.appendChild(swapInput);
    swapRow.appendChild(swap);
    swapSection.appendChild(swapRow);
    const resetSection = document.createElement("div");
    resetSection.className = "hp-section";
    resetSection.style.cssText = "margin-top:7px;";
    resetSection.appendChild(reset);
    body.appendChild(locateSection);
    body.appendChild(swapSection);
    body.appendChild(resetSection);
    panel.appendChild(header);
    panel.appendChild(body);
    document.body.appendChild(panel);
    installPreviewOrderPanelDrag(panel, header);
    updatePreviewOrderPanelUi();
    return panel;
  }

  function updatePreviewIframe(state) {
    const iframe = findNativePreviewIframe() || ensureNativePreviewArea();
    if (!iframe) return "native_preview_unavailable";
    const pairs = state.preview_pairs?.length
      ? state.preview_pairs
      : buildPreviewPairs(state.keypoints, DEFAULT_WIDTH);
    if (state.preview_url && state.preview_pairs?.length) {
      setPreviewBasePairs(pairs);
      return "native_preview_already_loaded";
    }
    if (!pairs.length) return "no_preview_pairs";
    setPreviewBasePairs(pairs);
    const orderedPairs = orderedPreviewPairs();
    const imageUrl = findMainImage()?.src || getImageUrlFromStore();
    const textureUrl = withCacheBust(rewriteTextureUrlForViewer(imageUrl));
    iframe.contentWindow?.postMessage(
      {
        type: "update_layout",
        corners: orderedPairs,
        baseCorners: pairs,
        width: DEFAULT_WIDTH,
        height: DEFAULT_HEIGHT,
        imageUrl: textureUrl,
        preserveOrder: true,
        previewOrderActive: true,
        previewOrder: currentPreviewOrder.slice(),
        previewSignature: String(Date.now()),
      },
      "*",
    );
    return "native_preview_update_sent";
  }

  function performRefresh3DPreview() {
    const nextState = extractKeypointsFromDom();
    nextState.preview_update_status = updatePreviewIframe(nextState);
    renderPanel(nextState);
  }

  function resetPreviewOrderFromToolbar() {
    if (!currentPreviewBasePairs.length) return;
    currentPreviewOrder = currentPreviewBasePairs.map((_, index) => index);
    currentPreviewSelectedPairIndex = 0;
    sendPreviewOrderToIframe();
  }

  function toolbarButton(label, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.style.cssText = "border:none;border-radius:7px;padding:5px 8px;background:#334155;color:#f8fafc;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap;";
    button.addEventListener("click", onClick);
    return button;
  }

  function installToolbarDrag(toolbar, header) {
    let dragState = null;
    header.addEventListener("pointerdown", (event) => {
      if (event.target?.tagName === "BUTTON") return;
      const rect = toolbar.getBoundingClientRect();
      dragState = { dx: event.clientX - rect.left, dy: event.clientY - rect.top };
      header.setPointerCapture?.(event.pointerId);
    });
    header.addEventListener("pointermove", (event) => {
      if (!dragState) return;
      toolbar.style.left = `${Math.max(4, event.clientX - dragState.dx)}px`;
      toolbar.style.top = `${Math.max(4, event.clientY - dragState.dy)}px`;
      toolbar.style.right = "auto";
    });
    const stop = (event) => {
      dragState = null;
      try {
        if (event && header.hasPointerCapture(event.pointerId)) header.releasePointerCapture(event.pointerId);
      } catch (e) {}
    };
    header.addEventListener("pointerup", stop);
    header.addEventListener("pointercancel", stop);
  }

  function syncPrimaryToolbar() {
    const cornerButton = document.getElementById(`${TOOLBAR_ID}-corner`);
    if (cornerButton) cornerButton.textContent = getLabelsVisible() ? "Hide corner order" : "Corner order";
    const guideButton = document.getElementById(`${TOOLBAR_ID}-guide`);
    if (guideButton) guideButton.textContent = getGuideBandsVisible() ? "Hide guide lines" : "Guide lines";
  }

  function ensurePrimaryToolbar() {
    let toolbar = document.getElementById(TOOLBAR_ID);
    if (toolbar) {
      syncPrimaryToolbar();
      return toolbar;
    }
    toolbar = document.createElement("div");
    toolbar.id = TOOLBAR_ID;
    toolbar.style.cssText =
      "position:fixed;right:430px;top:96px;z-index:2147483647;width:292px;color:#f8fafc;background:rgba(15,23,42,0.88);border:1px solid rgba(148,163,184,0.35);border-radius:10px;box-shadow:0 10px 24px rgba(0,0,0,0.24);font:12px/1.35 system-ui,sans-serif;overflow:hidden;backdrop-filter:blur(10px);";
    const header = document.createElement("div");
    header.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 9px;cursor:move;background:rgba(255,255,255,0.07);";
    header.appendChild(text("Manhattan tools"));
    const collapse = toolbarButton("Hide", () => {
      const body = document.getElementById(TOOLBAR_BODY_ID);
      const hidden = body.style.display !== "none";
      body.style.display = hidden ? "none" : "flex";
      collapse.textContent = hidden ? "Show" : "Hide";
    });
    header.appendChild(collapse);
    const body = document.createElement("div");
    body.id = TOOLBAR_BODY_ID;
    body.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;padding:8px;";
    body.appendChild(toolbarButton("Refresh 3D", performRefresh3DPreview));
    const cornerButton = toolbarButton("Corner order", () => {
      toggleCornerOrderLabels();
      syncPrimaryToolbar();
    });
    cornerButton.id = `${TOOLBAR_ID}-corner`;
    body.appendChild(cornerButton);
    const guideButton = toolbarButton("Guide lines", () => {
      toggleGuideBands();
      syncPrimaryToolbar();
    });
    guideButton.id = `${TOOLBAR_ID}-guide`;
    body.appendChild(guideButton);
    body.appendChild(toolbarButton("Highlight affected", highlightAffectedPair));
    body.appendChild(toolbarButton("Scroll affected", scrollToAffectedPair));
    body.appendChild(toolbarButton("Reset preview order", resetPreviewOrderFromToolbar));
    toolbar.appendChild(header);
    toolbar.appendChild(body);
    document.body.appendChild(toolbar);
    installToolbarDrag(toolbar, header);
    syncPrimaryToolbar();
    return toolbar;
  }

  function updateDebugDrawerButton() {
    const panel = document.getElementById(PANEL_ID);
    const button = document.getElementById(DEBUG_DRAWER_TOGGLE_ID);
    if (!panel || !button) return;
    button.textContent = panel.dataset.collapsed === "1" ? "Show debug details" : "Hide debug details";
  }

  function toggleDebugDrawer() {
    const panel = document.getElementById(PANEL_ID);
    if (!panel) return;
    panel.dataset.collapsed = panel.dataset.collapsed === "1" ? "0" : "1";
    updateDebugDrawerButton();
  }

  function secondsSinceStart() {
    return Math.max(0, Math.round((Date.now() - START_TIME_MS) / 1000));
  }

  function secondsSinceLastTelemetry(nowMs) {
    return Math.max(0, Math.round((nowMs - lastTelemetryMs) / 1000));
  }

  function activeSecondsSinceLastTelemetry() {
    return Math.max(0, activeSeconds - lastTelemetryActiveSeconds);
  }

  function lastActivityAgeMs(nowMs = Date.now()) {
    return lastActivityTime > 0 ? Math.max(0, nowMs - lastActivityTime) : -1;
  }

  function activeTimerStatus(nowMs = Date.now()) {
    if (!isPageVisible) return "hidden";
    if (!isWindowFocused) return "blurred";
    if (!isLikelyAnnotationPage()) return "non_annotation_page";
    if (lastActivityTime <= 0) return "waiting_for_interaction";
    if (nowMs - lastActivityTime >= IDLE_THRESHOLD_MS) return "idle";
    return "active";
  }

  function isActiveTimeCountingPage() {
    return isPageVisible && isWindowFocused && isLikelyAnnotationPage();
  }

  function updateActivityTimerPanel() {
    const nowMs = Date.now();
    setText(`${PANEL_ID}-active-timer-status`, activeTimerStatus(nowMs));
    setText(`${PANEL_ID}-active-seconds`, activeSeconds);
    setText(`${PANEL_ID}-active-seconds-fragment`, activeSecondsSinceLastTelemetry());
    setText(`${PANEL_ID}-last-activity-age-ms`, lastActivityAgeMs(nowMs));
    setText(`${PANEL_ID}-page-visible-status`, isPageVisible ? "visible" : "hidden");
    setText(`${PANEL_ID}-window-focus-status`, isWindowFocused ? "focused" : "blurred");
    setText(`${PANEL_ID}-last-hidden-duration-ms`, lastHiddenDurationMs);
  }

  function updateTelemetryPanel() {
    setText(`${PANEL_ID}-telemetry-status`, telemetryState.status);
    setText(`${PANEL_ID}-last-telemetry-event`, telemetryState.lastEvent);
    setText(`${PANEL_ID}-last-telemetry-http-status`, telemetryState.lastHttpStatus);
    setText(`${PANEL_ID}-last-telemetry-error`, telemetryState.lastError);
    updateActivityTimerPanel();
  }

  function sandboxTelemetryPayload(eventName, nowMs = Date.now()) {
    const activeSecondsFragment = activeSecondsSinceLastTelemetry();
    const telemetryElapsedSeconds = secondsSinceStart();
    const deviation = computeManhattanDeviation(extractKeypointsFromDom().keypoints, DEFAULT_WIDTH, DEFAULT_HEIGHT);
    return {
      task_id: getTaskId(),
      project_id: getProjectId(),
      project_name: getProjectName(),
      annotator_id: getAnnotatorId(),
      session_id: sessionId,
      page_type: getPageType(),
      active_seconds: activeSeconds,
      active_seconds_fragment: activeSecondsFragment,
      timestamp: nowMs,
      event: eventName,
      telemetry_elapsed_seconds: telemetryElapsedSeconds,
      preview_only_manhattan_deviation_score: deviation.manhattan_deviation_score,
      preview_only_manhattan_deviation_level: deviation.deviation_level,
      preview_only_manhattan_compatibility_status: deviation.compatibility_status,
      preview_only_primary_issue_type: deviation.primary_issue_type,
      preview_only_primary_issue_severity: deviation.primary_issue_severity,
      preview_only_hint_component: deviation.hint_component,
      preview_only_affected_pair_index: deviation.affected_pair_index,
      preview_only_direction_hint_type: deviation.hint_direction_type,
      preview_only_diagnosis_affected_pair_index: currentDiagnosisAffectedPairIndex === null ? "none" : currentDiagnosisAffectedPairIndex + 1,
      preview_only_manual_selected_pair_index: currentPreviewBasePairs.length ? currentPreviewSelectedPairIndex + 1 : "none",
      preview_only_highlight_mode: highlightMode(),
      preview_only_guide_visible: getGuideBandsVisible(),
      preview_only_guide_component: deviation.guide_component,
      preview_only_guide_affected_pair_index: deviation.guide_affected_pair_index,
      preview_order_visible: getLabelsVisible(),
      not_correctness: true,
      no_writeback: true,
      elapsed_ms: nowMs - START_TIME_MS,
      page_url: window.location.href,
      log_context: "manhattan_ls_sandbox",
      tool_stage: "M8",
      script_variant: "timed",
      is_sandbox: true,
      sandbox_project: true,
      exclude_from_primary_active_time: true,
      exclude_from_thesis_evidence: true,
      not_worker_facing: true,
      not_p1_c1_c2_t1_v1_artifact: true,
      manhattan_panel_version: PANEL_VERSION,
    };
  }

  function sendSandboxTelemetry(eventName) {
    const token = getLogToken();
    const nowMs = Date.now();
    const payload = sandboxTelemetryPayload(eventName, nowMs);
    lastTelemetryActiveSeconds = activeSeconds;
    telemetryState.status = "sending";
    telemetryState.lastEvent = eventName;
    telemetryState.lastHttpStatus = "pending";
    telemetryState.lastError = "none";
    updateTelemetryPanel();
    fetch(logTimeUrl(), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-HOHONET-TOKEN": token } : {}),
      },
      body: JSON.stringify(payload),
      keepalive: true,
    })
      .then(function (response) {
        telemetryState.status = response.ok ? "sent" : "http_error";
        telemetryState.lastHttpStatus = String(response.status);
        telemetryState.lastError = response.ok ? "none" : response.statusText || "non_2xx_response";
        lastTelemetryMs = nowMs;
        updateTelemetryPanel();
      })
      .catch(function (error) {
        telemetryState.status = "network_error";
        telemetryState.lastHttpStatus = "network_error";
        telemetryState.lastError = error?.message || "unknown_error";
        lastTelemetryMs = nowMs;
        updateTelemetryPanel();
      // Sandbox telemetry failure must not interrupt annotation or panel display.
      });
  }

  function sendSandboxTelemetryIfActive(eventName) {
    if (activeSecondsSinceLastTelemetry() <= 0) {
      telemetryState.status = "skipped_no_active_seconds";
      telemetryState.lastEvent = `${eventName}_skipped`;
      telemetryState.lastHttpStatus = "not_sent";
      telemetryState.lastError = "none";
      updateTelemetryPanel();
      return false;
    }
    sendSandboxTelemetry(eventName);
    return true;
  }

  function recordUserActivity() {
    if (isActiveTimeCountingPage()) {
      lastActivityTime = Date.now();
      updateActivityTimerPanel();
    }
  }

  function installActiveStateTracking() {
    ["mousemove", "keydown", "click", "scroll", "wheel"].forEach(function (eventName) {
      window.addEventListener(eventName, recordUserActivity, true);
    });
    window.setInterval(function () {
      const nowMs = Date.now();
      if (
        isActiveTimeCountingPage() &&
        lastActivityTime > 0 &&
        nowMs - lastActivityTime < IDLE_THRESHOLD_MS
      ) {
        activeSeconds += 1;
      } else if (!isActiveTimeCountingPage()) {
        lastActivityTime = 0;
      }
      updateActivityTimerPanel();
    }, 1000);
  }

  function installStyles() {
    if (document.getElementById(`${PANEL_ID}-style`)) {
      return;
    }
    const style = document.createElement("style");
    style.id = `${PANEL_ID}-style`;
    style.textContent = `
      #${PANEL_ID} {
        position: fixed;
        right: 12px;
        bottom: 12px;
        z-index: 2147483647;
        width: 340px;
        max-height: 70vh;
        overflow: auto;
        box-sizing: border-box;
        padding: 12px;
        border: 1px solid #6b7280;
        background: #111827;
        color: #f9fafb;
        font: 12px/1.4 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
      }
      #${PANEL_ID} h2,
      #${PANEL_ID} h3 {
        margin: 0 0 8px;
        font-size: 13px;
        letter-spacing: 0;
      }
      #${PANEL_ID} section {
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px solid #374151;
      }
      #${PANEL_ID} ul {
        margin: 0;
        padding-left: 18px;
      }
      .hohonet-m8-row {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        margin: 4px 0;
      }
      .hohonet-m8-key {
        color: #d1d5db;
      }
      .hohonet-m8-value {
        color: #ffffff;
        font-weight: 600;
      }
      #${PANEL_ID}[data-collapsed="1"] {
        width: 190px;
        max-height: 92px;
        overflow: hidden;
      }
      #${PANEL_ID}[data-collapsed="1"] section,
      #${PANEL_ID}[data-collapsed="1"] .hohonet-m8-row {
        display: none;
      }
    `;
    document.head.appendChild(style);
  }

  function renderPanel(state) {
    clearPreviewOrderOnTaskChange(state.page_signature || currentTaskSignature());
    currentSandboxState = state;
    ensurePrimaryToolbar();
    const metaGuard = validateMetaChoices(getStore());
    let panel = document.getElementById(PANEL_ID);
    if (panel) {
      setText(`${PANEL_ID}-read-status`, state.keypoint_read_status);
      setText(`${PANEL_ID}-keypoint-count`, state.keypoints.length);
      setText(`${PANEL_ID}-store-status`, state.store_status);
      setText(`${PANEL_ID}-result-count`, state.result_count);
      setText(`${PANEL_ID}-keypoint-sources`, state.keypoint_sources);
      setText(`${PANEL_ID}-preview-url-status`, state.preview_url_status);
      setText(`${PANEL_ID}-native-preview-status`, state.native_preview_status);
      setText(`${PANEL_ID}-preview-update-status`, state.preview_update_status);
      setText(`${PANEL_ID}-viewer-base-url`, getViewerBaseUrl());
      setText(`${PANEL_ID}-log-time-url`, logTimeUrl());
      updateTelemetryPanel();
      updateActivityTimerPanel();
      updateManhattanDeviationPanel(state.manhattan_deviation);
      updateMetaGuardPanel(metaGuard);
      applyToggleBtnState(document.getElementById(TOGGLE_LABELS_BUTTON_ID), getLabelsVisible());
      applyGuideBtnState(document.getElementById(GUIDE_BANDS_BUTTON_ID), getGuideBandsVisible());
      syncPrimaryToolbar();
      updateDebugDrawerButton();
      return;
    }

    panel = document.createElement("aside");
    panel.id = PANEL_ID;
    panel.dataset.collapsed = "1";
    panel.setAttribute("aria-label", "HOHONET Manhattan sandbox panel timed");
    document.body.appendChild(panel);

    const title = document.createElement("h2");
    title.appendChild(text("Debug drawer"));
    panel.appendChild(title);
    const debugToggle = document.createElement("button");
    debugToggle.id = DEBUG_DRAWER_TOGGLE_ID;
    debugToggle.type = "button";
    debugToggle.textContent = "Show debug details";
    debugToggle.style.cssText = "width:100%;margin:0 0 6px;padding:6px 8px;border:none;border-radius:7px;background:#334155;color:#fff;font-weight:800;cursor:pointer;";
    debugToggle.addEventListener("click", toggleDebugDrawer);
    panel.appendChild(debugToggle);
    panel.appendChild(makeRow("script_variant", "timed"));
    panel.appendChild(makeRow("manhattan_panel_version", PANEL_VERSION));
    panel.appendChild(makeMutableRow("keypoint_read_status", state.keypoint_read_status, `${PANEL_ID}-read-status`));
    panel.appendChild(makeMutableRow("keypoint_count", state.keypoints.length, `${PANEL_ID}-keypoint-count`));
    panel.appendChild(makeMutableRow("store_status", state.store_status, `${PANEL_ID}-store-status`));
    panel.appendChild(makeMutableRow("result_count", state.result_count, `${PANEL_ID}-result-count`));
    panel.appendChild(makeMutableRow("keypoint_sources", state.keypoint_sources, `${PANEL_ID}-keypoint-sources`));
    panel.appendChild(makeMutableRow("preview_url_status", state.preview_url_status, `${PANEL_ID}-preview-url-status`));
    panel.appendChild(makeMutableRow("native_preview_status", state.native_preview_status, `${PANEL_ID}-native-preview-status`));
    panel.appendChild(makeMutableRow("preview_update_status", state.preview_update_status, `${PANEL_ID}-preview-update-status`));
    panel.appendChild(makeRow("log_context", "manhattan_ls_sandbox"));
    panel.appendChild(makeMutableRow("viewer_base_url", getViewerBaseUrl(), `${PANEL_ID}-viewer-base-url`));
    panel.appendChild(makeMutableRow("log_time_url", logTimeUrl(), `${PANEL_ID}-log-time-url`));
    panel.appendChild(makeMutableRow("telemetry_status", telemetryState.status, `${PANEL_ID}-telemetry-status`));
    panel.appendChild(makeMutableRow("last_telemetry_event", telemetryState.lastEvent, `${PANEL_ID}-last-telemetry-event`));
    panel.appendChild(makeMutableRow("last_telemetry_http_status", telemetryState.lastHttpStatus, `${PANEL_ID}-last-telemetry-http-status`));
    panel.appendChild(makeMutableRow("last_telemetry_error", telemetryState.lastError, `${PANEL_ID}-last-telemetry-error`));
    panel.appendChild(makeRow("heartbeat_interval_ms", HEARTBEAT_INTERVAL_MS));
    panel.appendChild(makeMutableRow("active_timer_status", activeTimerStatus(), `${PANEL_ID}-active-timer-status`));
    panel.appendChild(makeMutableRow("active_seconds", activeSeconds, `${PANEL_ID}-active-seconds`));
    panel.appendChild(makeMutableRow("active_seconds_fragment", activeSecondsSinceLastTelemetry(), `${PANEL_ID}-active-seconds-fragment`));
    panel.appendChild(makeMutableRow("last_activity_age_ms", lastActivityAgeMs(), `${PANEL_ID}-last-activity-age-ms`));
    panel.appendChild(makeMutableRow("page_visible_status", isPageVisible ? "visible" : "hidden", `${PANEL_ID}-page-visible-status`));
    panel.appendChild(makeMutableRow("window_focus_status", isWindowFocused ? "focused" : "blurred", `${PANEL_ID}-window-focus-status`));
    panel.appendChild(makeMutableRow("last_hidden_duration_ms", lastHiddenDurationMs, `${PANEL_ID}-last-hidden-duration-ms`));

    const preview = document.createElement("section");
    preview.appendChild(document.createElement("h3")).appendChild(text("3D Preview"));
    preview.appendChild(text("Uses the existing page 3D Layout Preview only; no sandbox iframe is embedded."));
    panel.appendChild(preview);

    const compatibility = document.createElement("section");
    compatibility.appendChild(document.createElement("h3")).appendChild(text("Compatibility"));
    compatibility.appendChild(text("Python parity checker is not embedded; sandbox JS preview compatibility is used for the deviation section below."));
    panel.appendChild(compatibility);

    const residual = document.createElement("section");
    residual.appendChild(document.createElement("h3")).appendChild(text("Residual"));
    residual.appendChild(text("Python residual calculator is not embedded; sandbox JS residuals are shown in the Manhattan deviation section below."));
    panel.appendChild(residual);

    const meta = document.createElement("section");
    meta.appendChild(document.createElement("h3")).appendChild(text("Sandbox meta-label guard"));
    meta.appendChild(makeMutableRow("meta_guard_status", metaGuard.status, `${PANEL_ID}-meta-guard-status`));
    meta.appendChild(makeMutableRow("meta_guard_errors", metaGuard.errors.length ? metaGuard.errors.join(",") : "none", `${PANEL_ID}-meta-guard-errors`));
    meta.appendChild(makeMutableRow("difficulty_choices", metaGuard.difficulty.length ? metaGuard.difficulty.join(",") : "none", `${PANEL_ID}-difficulty-choices`));
    meta.appendChild(makeMutableRow("model_issue_choices", metaGuard.model_issue.length ? metaGuard.model_issue.join(",") : "none", `${PANEL_ID}-model-issue-choices`));
    meta.appendChild(text("Sandbox guard mirrors official mutually-exclusive meta-label rules; it only blocks invalid sandbox submit/update actions and does not write annotations."));
    panel.appendChild(meta);

    const deviation = document.createElement("section");
    deviation.appendChild(document.createElement("h3")).appendChild(text("Manhattan deviation"));
    deviation.appendChild(makeMutableRow("compatibility_status", state.manhattan_deviation.compatibility_status, `${PANEL_ID}-compatibility-status`));
    deviation.appendChild(makeMutableRow("n_keypoints", state.manhattan_deviation.n_keypoints, `${PANEL_ID}-deviation-n-keypoints`));
    deviation.appendChild(makeMutableRow("n_pairs", state.manhattan_deviation.n_pairs, `${PANEL_ID}-deviation-n-pairs`));
    deviation.appendChild(makeMutableRow("vertical_pair_x_residual_px", formatMetric(state.manhattan_deviation.vertical_pair_x_residual), `${PANEL_ID}-vertical-pair-x-residual`));
    deviation.appendChild(makeMutableRow("ceiling_y_range_px", formatMetric(state.manhattan_deviation.ceiling_y_range), `${PANEL_ID}-ceiling-y-range`));
    deviation.appendChild(makeMutableRow("floor_y_range_px", formatMetric(state.manhattan_deviation.floor_y_range), `${PANEL_ID}-floor-y-range`));
    deviation.appendChild(makeMutableRow("wall_height_range_px", formatMetric(state.manhattan_deviation.wall_height_range), `${PANEL_ID}-wall-height-range`));
    deviation.appendChild(makeMutableRow("manhattan_deviation_score", formatMetric(state.manhattan_deviation.manhattan_deviation_score), `${PANEL_ID}-manhattan-deviation-score`));
    deviation.appendChild(makeMutableRow("deviation_level", state.manhattan_deviation.deviation_level, `${PANEL_ID}-deviation-level`));
    deviation.appendChild(makeMutableRow("reason", state.manhattan_deviation.exclusion_reason, `${PANEL_ID}-deviation-reason`));
    deviation.appendChild(text("Preview-only geometry diagnostic. Not correctness. No axis snapping. No corner prediction. No writeback."));
    panel.appendChild(deviation);

    const diagnosis = document.createElement("section");
    diagnosis.appendChild(document.createElement("h3")).appendChild(text("Manhattan diagnosis"));
    diagnosis.appendChild(makeMutableRow("primary_issue_type", state.manhattan_deviation.primary_issue_type, `${PANEL_ID}-primary-issue-type`));
    diagnosis.appendChild(makeMutableRow("primary_issue_severity", state.manhattan_deviation.primary_issue_severity, `${PANEL_ID}-primary-issue-severity`));
    diagnosis.appendChild(makeMutableRow("primary_issue_explanation", state.manhattan_deviation.primary_issue_explanation, `${PANEL_ID}-primary-issue-explanation`));
    diagnosis.appendChild(makeMutableRow("affected_pair_index", state.manhattan_deviation.affected_pair_index, `${PANEL_ID}-affected-pair-index`));
    diagnosis.appendChild(makeMutableRow("affected_wall_index", state.manhattan_deviation.affected_wall_index, `${PANEL_ID}-affected-wall-index`));
    diagnosis.appendChild(makeMutableRow("pair_x_alignment_summary", state.manhattan_deviation.pair_x_alignment_summary, `${PANEL_ID}-pair-x-alignment-summary`));
    diagnosis.appendChild(makeMutableRow("ceiling_alignment_summary", state.manhattan_deviation.ceiling_alignment_summary, `${PANEL_ID}-ceiling-alignment-summary`));
    diagnosis.appendChild(makeMutableRow("floor_alignment_summary", state.manhattan_deviation.floor_alignment_summary, `${PANEL_ID}-floor-alignment-summary`));
    diagnosis.appendChild(makeMutableRow("wall_height_summary", state.manhattan_deviation.wall_height_summary, `${PANEL_ID}-wall-height-summary`));
    diagnosis.appendChild(text("Direction-only preview diagnosis. Not a correction. No target x/y. Not correctness."));
    panel.appendChild(diagnosis);

    const hint = document.createElement("section");
    hint.appendChild(document.createElement("h3")).appendChild(text("Direction-only hint"));
    hint.appendChild(makeMutableRow("hint_status", state.manhattan_deviation.hint_status, `${PANEL_ID}-hint-status`));
    hint.appendChild(makeMutableRow("hint_component", state.manhattan_deviation.hint_component, `${PANEL_ID}-hint-component`));
    hint.appendChild(makeMutableRow("affected_pair_index", state.manhattan_deviation.affected_pair_index, `${PANEL_ID}-hint-affected-pair-index`));
    hint.appendChild(makeMutableRow("direction_hint", state.manhattan_deviation.direction_hint, `${PANEL_ID}-direction-hint`));
    hint.appendChild(makeMutableRow("alternative_anchor_hint", state.manhattan_deviation.alternative_anchor_hint, `${PANEL_ID}-alternative-anchor-hint`));
    hint.appendChild(makeMutableRow("hint_guardrail", state.manhattan_deviation.hint_guardrail, `${PANEL_ID}-hint-guardrail`));
    hint.appendChild(makeMutableRow("highlight_status", highlightState.status, `${PANEL_ID}-highlight-status`));
    hint.appendChild(makeMutableRow("highlight_affected_pair_index", highlightState.affectedPairIndex, `${PANEL_ID}-highlight-affected-pair-index`));
    hint.appendChild(makeMutableRow("diagnosis_affected_pair_index", currentDiagnosisAffectedPairIndex === null ? "none" : currentDiagnosisAffectedPairIndex + 1, `${PANEL_ID}-diagnosis-affected-pair-index`));
    hint.appendChild(makeMutableRow("manual_selected_pair_index", currentPreviewBasePairs.length ? currentPreviewSelectedPairIndex + 1 : "none", `${PANEL_ID}-manual-selected-pair-index`));
    hint.appendChild(makeMutableRow("highlight_mode", highlightMode(), `${PANEL_ID}-highlight-mode`));
    hint.appendChild(makeMutableRow("diagnosis_highlight_status", highlightState.status, `${PANEL_ID}-diagnosis-highlight-status`));
    hint.appendChild(makeMutableRow("manual_highlight_status", currentPreviewBasePairs.length ? "manual_selected_pair_active" : "manual_selected_pair_unavailable", `${PANEL_ID}-manual-highlight-status`));
    hint.appendChild(makeMutableRow("highlight_row_found", highlightState.rowFound ? "true" : "false", `${PANEL_ID}-highlight-row-found`));
    hint.appendChild(makeMutableRow("highlight_overlay_labels_found", highlightState.overlayLabelsFound, `${PANEL_ID}-highlight-overlay-labels-found`));
    hint.appendChild(text("Highlight scope: Preview order pair row and 2D panorama order labels only. No wall or point highlighting inside the 3D preview in this step."));
    const highlightButton = document.createElement("button");
    highlightButton.type = "button";
    highlightButton.textContent = "Highlight affected pair";
    highlightButton.style.cssText = "margin-top:8px;padding:6px 10px;border:1px solid rgba(255,255,255,0.18);border-radius:6px;background:#2f5cff;color:#fff;cursor:pointer;font-size:12px;";
    highlightButton.addEventListener("click", () => highlightAffectedPair());
    hint.appendChild(highlightButton);
    const scrollButton = document.createElement("button");
    scrollButton.type = "button";
    scrollButton.textContent = "Scroll to affected pair";
    scrollButton.style.cssText = "margin-top:8px;margin-left:6px;padding:6px 10px;border:1px solid rgba(255,255,255,0.18);border-radius:6px;background:#64748b;color:#fff;cursor:pointer;font-size:12px;";
    scrollButton.addEventListener("click", () => scrollToAffectedPair());
    hint.appendChild(scrollButton);
    panel.appendChild(hint);

    const guides = document.createElement("section");
    guides.appendChild(document.createElement("h3")).appendChild(text("2D guide bands"));
    guides.appendChild(makeMutableRow("guide_status", getGuideBandsVisible() ? state.manhattan_deviation.guide_status : "hidden", `${PANEL_ID}-guide-status`));
    guides.appendChild(makeMutableRow("guide_mode", GUIDE_MODE, `${PANEL_ID}-guide-mode`));
    guides.appendChild(makeMutableRow("guide_component", getGuideBandsVisible() ? state.manhattan_deviation.guide_component : "hidden", `${PANEL_ID}-guide-component`));
    guides.appendChild(makeMutableRow("guide_affected_pair_index", getGuideBandsVisible() ? state.manhattan_deviation.guide_affected_pair_index : "hidden", `${PANEL_ID}-guide-affected-pair-index`));
    guides.appendChild(makeMutableRow("guide_visible_items", getGuideBandsVisible() ? state.manhattan_deviation.guide_visible_items : "none", `${PANEL_ID}-guide-visible-items`));
    guides.appendChild(makeMutableRow("guide_explanation", getGuideBandsVisible() ? state.manhattan_deviation.guide_explanation : "Visual reference lines are hidden.", `${PANEL_ID}-guide-explanation`));
    guides.appendChild(makeMutableRow("guide_scope", guideState.scope, `${PANEL_ID}-guide-scope`));
    guides.appendChild(makeMutableRow("guide_guardrail", guideState.guardrail, `${PANEL_ID}-guide-guardrail`));
    guides.appendChild(text("Issue-only visual reference lines: Ceiling reference, Floor reference, Affected pair axis, Height check. Guide bands are visual references only. No target x/y, no point movement, no annotation writeback."));
    panel.appendChild(guides);

    const suggestion = document.createElement("section");
    suggestion.appendChild(document.createElement("h3")).appendChild(text("Preview-only suggestion"));
    suggestion.appendChild(text("placeholder only; no automated review prompt is computed"));
    panel.appendChild(suggestion);

    const guards = document.createElement("section");
    guards.appendChild(document.createElement("h3")).appendChild(text("Guardrails"));
    const list = document.createElement("ul");
    for (const guard of GUARDRAILS) {
      const item = document.createElement("li");
      item.appendChild(text(guard));
      list.appendChild(item);
    }
    guards.appendChild(list);
    guards.appendChild(text("Coordinates use Label Studio 0-100 scale."));
    panel.appendChild(guards);
  }

  function refresh() {
    installStyles();
    installSandboxMetaGuard();
    ensureNativePreviewArea();
    const state = extractKeypointsFromDom();
    renderPanel(state);
    window.setTimeout(function () {
      state.preview_update_status = updatePreviewIframe(state);
      renderPanel(state);
    }, 500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refresh, { once: true });
  } else {
    refresh();
  }

  window.setInterval(function () {
    ensureNativePreviewArea();
    clearPreviewOrderOnTaskChange(currentTaskSignature());
  }, 1500);
  window.addEventListener("resize", () => renderPreviewOverlayPairs(orderedPreviewPairs()));
  window.addEventListener("scroll", () => renderPreviewOverlayPairs(orderedPreviewPairs()), true);

  installActiveStateTracking();
  sendSandboxTelemetry("panel_loaded");
  window.setInterval(function () {
    sendSandboxTelemetryIfActive("heartbeat");
  }, HEARTBEAT_INTERVAL_MS);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      pageHiddenTime = Date.now();
      isPageVisible = false;
      sendSandboxTelemetryIfActive("visibility_hidden");
      updateActivityTimerPanel();
    } else {
      if (pageHiddenTime !== null) {
        lastHiddenDurationMs = Date.now() - pageHiddenTime;
        if (lastHiddenDurationMs >= PAGE_HIDDEN_THRESHOLD_MS) {
          lastActivityTime = 0;
        }
      }
      pageHiddenTime = null;
      isPageVisible = true;
      isWindowFocused = document.hasFocus();
      updateActivityTimerPanel();
    }
  });
  window.addEventListener("blur", function () {
    isWindowFocused = false;
    sendSandboxTelemetryIfActive("window_blur");
    lastActivityTime = 0;
    updateActivityTimerPanel();
  });
  window.addEventListener("focus", function () {
    isWindowFocused = document.hasFocus();
    lastActivityTime = 0;
    updateActivityTimerPanel();
  });
  window.addEventListener("pagehide", function () {
    sendSandboxTelemetryIfActive("pagehide");
  });
  window.addEventListener("beforeunload", function () {
    sendSandboxTelemetryIfActive("panel_unloaded");
  });
})();
