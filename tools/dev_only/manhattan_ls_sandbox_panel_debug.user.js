// ==UserScript==
// @name         HOHONET Manhattan LS Sandbox Panel Debug
// @namespace    hohonet-dev-only
// @version      m11-dev-only-debug-0.1.0
// @description  dev-only sandbox-only read-only Manhattan panel; debug variant with no active_time upload.
// @match        http://175.178.71.217:8080/*
// @match        https://175.178.71.217:8080/*
// @grant        none
// ==/UserScript==

/*
 * HOHONET Manhattan LS Sandbox Panel Debug
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
 * This script is server-scoped to the current Label Studio host. Localhost
 * testing may be enabled manually during development, but it is not enabled
 * by default in this file.
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
  window[WINDOW_GUARD] = { script_variant: "debug" };

  const PANEL_ID = "hohonet-manhattan-sandbox-panel";
  const PANEL_VERSION = "m11-dev-only-debug-0.1.0";
  const OFFICIAL_IFRAME_ID = "hohonet-iframe";
  const OFFICIAL_WRAPPER_ID = "hohonet-wrapper";
  const OFFICIAL_BUTTON_ID = "hohonet-refresh-btn";
  const TOGGLE_LABELS_BUTTON_ID = "hohonet-m8-toggle-labels-btn";
  const OVERLAY_ID = "hohonet-m8-preview-order-overlay";
  const LABELS_VISIBLE_KEY = "hohonet_m8_preview_labels_visible";
  const PREVIEW_PANEL_ID = "hohonet-m8-preview-order-panel";
  const PREVIEW_PANEL_HEADER_ID = "hohonet-m8-preview-order-panel-header";
  const PREVIEW_PANEL_STATUS_ID = "hohonet-m8-preview-order-status";
  const PREVIEW_PANEL_PAIR_INPUT_ID = "hohonet-m8-preview-order-pair-input";
  const PREVIEW_PANEL_SWAP_INPUT_ID = "hohonet-m8-preview-order-swap-input";
  const PREVIEW_PANEL_POSITION_KEY = "hohonet_m8_preview_order_panel_position";
  const DEFAULT_WIDTH = 1024;
  const DEFAULT_HEIGHT = 512;
  const DUPLICATE_KEYPOINT_THRESHOLD_RATIO = 0.01;
  let currentPreviewBasePairs = [];
  let currentPreviewOrder = [];
  let currentPreviewSelectedPairIndex = 0;
  let currentSandboxState = null;
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
    "no snap coordinates",
    "no adjustment vector",
    "no auto-correction",
    "debug variant: no active_time upload",
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

  function applyToggleBtnState(button, visible) {
    if (!button) return;
    button.textContent = visible ? "Hide corner order" : "Show corner order";
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
    overlay.style.display = getLabelsVisible() ? "block" : "none";
    const rect = positionOverlay();
    if (!rect) return;
    (Array.isArray(pairs) ? pairs : []).forEach((pair, index) => {
      for (const point of Array.isArray(pair?.originalPoints) ? pair.originalPoints : []) {
        const pctX = Number.isFinite(point.pctX) ? point.pctX : (point.x / DEFAULT_WIDTH) * 100;
        const pctY = Number.isFinite(point.pctY) ? point.pctY : (point.y / DEFAULT_HEIGHT) * 100;
        const badge = document.createElement("div");
        badge.textContent = String(index + 1);
        badge.style.cssText =
          "position:absolute;transform:translate(-50%,-150%);background:rgba(255,255,0,0.9);color:#000;font-weight:700;padding:2px 6px;border-radius:4px;font-size:12px;border:1px solid #111;";
        badge.style.left = `${(pctX / 100) * rect.width}px`;
        badge.style.top = `${(pctY / 100) * rect.height}px`;
        overlay.appendChild(badge);
      }
    });
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
    currentPreviewBasePairs = Array.isArray(pairs) ? pairs.slice() : [];
    currentPreviewOrder = currentPreviewBasePairs.map((_, index) => index);
    currentPreviewSelectedPairIndex = 0;
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
      row.className = displayIndex === currentPreviewSelectedPairIndex ? "hp-pair-row active-pair" : "hp-pair-row";
      row.dataset.activePair = displayIndex === currentPreviewSelectedPairIndex ? "true" : "false";
      row.style.cssText =
        "width:100%;display:grid;grid-template-columns:36px 1fr 46px;align-items:center;gap:6px;margin-top:4px;padding:5px 6px;border:1px solid rgba(255,255,255,0.08);border-radius:7px;background:rgba(255,255,255,0.055);color:#f4f7fb;text-align:left;cursor:pointer;font-size:11px;";
      if (displayIndex === currentPreviewSelectedPairIndex) {
        row.style.background = "rgba(47,92,255,0.32)";
        row.style.borderColor = "rgba(111,153,255,0.72)";
      }
      row.innerHTML = `<strong>Pair ${displayIndex + 1}</strong><span>x=${formatMetric(pair.x)} c=${formatMetric(pair.y_ceiling)} f=${formatMetric(pair.y_floor)}</span><span>${displayIndex === currentPreviewSelectedPairIndex ? "active" : ""}</span>`;
      row.addEventListener("click", () => {
        currentPreviewSelectedPairIndex = displayIndex;
        updatePreviewOrderPanelUi();
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
    `;
    document.head.appendChild(style);
  }

  function renderPanel(state) {
    currentSandboxState = state;
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
      updateManhattanDeviationPanel(state.manhattan_deviation);
      updateMetaGuardPanel(metaGuard);
      applyToggleBtnState(document.getElementById(TOGGLE_LABELS_BUTTON_ID), getLabelsVisible());
      return;
    }

    panel = document.createElement("aside");
    panel.id = PANEL_ID;
    panel.setAttribute("aria-label", "HOHONET Manhattan sandbox panel debug");
    document.body.appendChild(panel);

    const title = document.createElement("h2");
    title.appendChild(text("Manhattan Sandbox Panel"));
    panel.appendChild(title);
    panel.appendChild(makeRow("script_variant", "debug"));
    panel.appendChild(makeRow("manhattan_panel_version", PANEL_VERSION));
    panel.appendChild(makeMutableRow("keypoint_read_status", state.keypoint_read_status, `${PANEL_ID}-read-status`));
    panel.appendChild(makeMutableRow("keypoint_count", state.keypoints.length, `${PANEL_ID}-keypoint-count`));
    panel.appendChild(makeMutableRow("store_status", state.store_status, `${PANEL_ID}-store-status`));
    panel.appendChild(makeMutableRow("result_count", state.result_count, `${PANEL_ID}-result-count`));
    panel.appendChild(makeMutableRow("keypoint_sources", state.keypoint_sources, `${PANEL_ID}-keypoint-sources`));
    panel.appendChild(makeMutableRow("preview_url_status", state.preview_url_status, `${PANEL_ID}-preview-url-status`));
    panel.appendChild(makeMutableRow("native_preview_status", state.native_preview_status, `${PANEL_ID}-native-preview-status`));
    panel.appendChild(makeMutableRow("preview_update_status", state.preview_update_status, `${PANEL_ID}-preview-update-status`));
    panel.appendChild(makeMutableRow("viewer_base_url", getViewerBaseUrl(), `${PANEL_ID}-viewer-base-url`));

    const controls = document.createElement("section");
    controls.appendChild(document.createElement("h3")).appendChild(text("Controls"));
    const refreshButton = document.createElement("button");
    refreshButton.type = "button";
    refreshButton.textContent = "Refresh 3D Preview";
    refreshButton.addEventListener("click", function () {
      const nextState = extractKeypointsFromDom();
      nextState.preview_update_status = updatePreviewIframe(nextState);
      renderPanel(nextState);
    });
    controls.appendChild(refreshButton);
    panel.appendChild(controls);

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
    deviation.appendChild(makeMutableRow("vertical_pair_x_residual", formatMetric(state.manhattan_deviation.vertical_pair_x_residual), `${PANEL_ID}-vertical-pair-x-residual`));
    deviation.appendChild(makeMutableRow("ceiling_y_range", formatMetric(state.manhattan_deviation.ceiling_y_range), `${PANEL_ID}-ceiling-y-range`));
    deviation.appendChild(makeMutableRow("floor_y_range", formatMetric(state.manhattan_deviation.floor_y_range), `${PANEL_ID}-floor-y-range`));
    deviation.appendChild(makeMutableRow("wall_height_range", formatMetric(state.manhattan_deviation.wall_height_range), `${PANEL_ID}-wall-height-range`));
    deviation.appendChild(makeMutableRow("manhattan_deviation_score", formatMetric(state.manhattan_deviation.manhattan_deviation_score), `${PANEL_ID}-manhattan-deviation-score`));
    deviation.appendChild(makeMutableRow("deviation_level", state.manhattan_deviation.deviation_level, `${PANEL_ID}-deviation-level`));
    deviation.appendChild(makeMutableRow("reason", state.manhattan_deviation.exclusion_reason, `${PANEL_ID}-deviation-reason`));
    deviation.appendChild(text("Preview-only geometry diagnostic. Not correctness. Not snap. Not next corner prediction. Not writeback."));
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
    diagnosis.appendChild(text("Direction-only preview diagnosis. Not a correction. Not a target coordinate. Not correctness."));
    panel.appendChild(diagnosis);

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
  }, 1500);
  window.addEventListener("resize", () => renderPreviewOverlayPairs(orderedPreviewPairs()));
  window.addEventListener("scroll", () => renderPreviewOverlayPairs(orderedPreviewPairs()), true);
})();
