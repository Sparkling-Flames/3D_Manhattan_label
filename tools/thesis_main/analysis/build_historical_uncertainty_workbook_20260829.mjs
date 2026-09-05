import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "file:///C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

function arg(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

function colName(index) {
  let value = index + 1;
  let result = "";
  while (value) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

const inputDir = path.resolve(arg("--input-dir", "analysis_results/historical_uncertainty_recompute_20260829_v1"));
const output = path.resolve(arg("--output", path.join(inputDir, "历史标注不确定性复算工作簿.xlsx")));
const previewDir = path.join(os.tmpdir(), "historical_uncertainty_workbook_preview_20260829");
const sources = [
  ["图像reference合同", "image_reference_contract.csv"],
  ["标注资格", "annotation_eligibility.csv"],
  ["无reference曲线", "reference_free_curves.csv"],
  ["结构有效支持", "structural_valid_support_by_task_k.csv"],
  ["整体分歧_任务", "disagreement_task_distribution.csv"],
  ["整体分歧_汇总", "disagreement_distribution_summary.csv"],
  ["整体分歧_ECDF", "disagreement_task_ecdf.csv"],
  ["分布关联_描述", "disagreement_recovery_associations.csv"],
  ["全体结构状态", "full_roster_structure_tasks.csv"],
  ["少数结构_任务", "minority_mode_replay_task_k.csv"],
  ["少数结构_汇总", "minority_mode_replay_summary.csv"],
  ["结构阈值敏感性", "structure_threshold_sensitivity.csv"],
  ["平台检验_汇总", "plateau_check_summary.csv"],
  ["聚合质量_任务", "aggregate_quality_task_k.csv"],
  ["聚合质量_汇总", "aggregate_quality_curves.csv"],
  ["边际变化_任务", "marginal_quality_gain_task_k.csv"],
  ["边际变化_汇总", "marginal_quality_gain.csv"],
  ["个体质量_任务", "individual_quality_by_task.csv"],
  ["个体质量_汇总", "individual_quality_summary.csv"],
  ["语言项目敏感性", "language_project_sensitivity.csv"],
];

const workbook = Workbook.create();
const summary = workbook.worksheets.add("汇总");
const data = new Map();

function typedCell(header, value) {
  const text = String(value ?? "").trim();
  if (text === "True" || text === "False") return text === "True";
  const identifierOrLabel = /(?:_id|_sha256|_path)$|status|reason|note|regime|stage|subset|condition|language|split|source|basis|identity|method|interpretation|weighting|metric|k_type|answer_set_version|scope_subtype/i.test(header);
  return !identifierOrLabel && /^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$/.test(text) ? Number(text) : value;
}

for (const [sheetName, fileName] of sources) {
  const imported = await Workbook.fromCSV(await fs.readFile(path.join(inputDir, fileName), "utf8"), { sheetName });
  const values = imported.worksheets.getItem(sheetName).getUsedRange().values;
  if (values.length < 2) throw new Error(`${fileName} has no data rows`);
  values[0][0] = String(values[0][0]).replace(/^\uFEFF/, "");
  for (let row = 1; row < values.length; row += 1) {
    for (let column = 0; column < values[0].length; column += 1) {
      values[row][column] = typedCell(String(values[0][column]), values[row][column]);
    }
  }
  data.set(fileName, values);
  const sheet = workbook.worksheets.add(sheetName);
  sheet.getRangeByIndexes(0, 0, values.length, values[0].length).values = values;
}

function records(fileName) {
  const [header, ...rows] = data.get(fileName);
  return rows.map((row) => Object.fromEntries(header.map((name, index) => [String(name), row[index]])));
}

for (const [index, [sheetName]] of sources.entries()) {
  const sheet = workbook.worksheets.getItem(sheetName);
  const values = sheet.getUsedRange().values;
  const headers = values[0].map((value) => String(value ?? ""));
  const rows = values.length;
  const cols = headers.length;
  const used = sheet.getRangeByIndexes(0, 0, rows, cols);
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(1);
  used.format.font = { name: "Microsoft YaHei", size: 9, color: "#1F2937" };
  used.format.verticalAlignment = "center";
  sheet.getRangeByIndexes(0, 0, 1, cols).format = {
    fill: "#1F4E78",
    font: { name: "Microsoft YaHei", size: 9, bold: true, color: "#FFFFFF" },
    wrapText: true,
    rowHeight: 34,
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: "#D8E2EC" },
  };
  const body = sheet.getRangeByIndexes(1, 0, rows - 1, cols);
  body.format.borders = { preset: "all", style: "thin", color: "#E5E7EB" };
  headers.forEach((name, column) => {
    const cells = sheet.getRangeByIndexes(0, column, rows, 1);
    const samples = values.slice(0, Math.min(rows, 80)).map((row) => String(row[column] ?? ""));
    cells.format.columnWidth = Math.max(9, Math.min(34, Math.max(name.length, ...samples.map((value) => value.length)) + 2));
    if (/path|reason|note|interpretation|basis|identity|sha256/i.test(name)) cells.format.wrapText = true;
    if (/rate|quality|gain|error|estimate|probability|median|mean|iou|ci95|disagreement/i.test(name)) {
      cells.format.numberFormat = "0.0000";
    } else if (/^k$|^k_|count|rows|support|replicates|workers|tasks|buildings/i.test(name)) {
      cells.format.numberFormat = "0";
    }
  });
}

const contract = records("image_reference_contract.csv");
const annotations = records("annotation_eligibility.csv");
const quality = records("aggregate_quality_curves.csv");
const referenceFree = records("reference_free_curves.csv");
const disagreementTasks = records("disagreement_task_distribution.csv");
const minoritySummary = records("minority_mode_replay_summary.csv");
const thresholdSensitivity = records("structure_threshold_sensitivity.csv");
const plateauChecks = records("plateau_check_summary.csv");
const language = records("language_project_sensitivity.csv");
const pooledLanguage = language.find((row) => row.analysis_stratum === "pooled");
const countTrue = (rows, field, stage) => rows.filter((row) => (!stage || row.stage === stage) && String(row[field]).toLowerCase() === "true").length;
const plateauRecovery = plateauChecks.find((row) => row.metric === "reference_free_recovery_gain_12_to_15");
const plateauResolved = plateauChecks.find((row) => row.metric === "resolved_pair_quality_gain_12_to_13");
const pooledMinority20 = minoritySummary.find((row) => row.analysis_stratum === "pooled_42" && Number(row.k) === 20);
const fullMulti95 = thresholdSensitivity.find((row) => row.analysis_stratum === "pooled_42" && Number(row.threshold) === 0.95);

summary.showGridLines = false;
summary.getRange("A1:Q1").format = { fill: "#17365D", rowHeight: 38 };
summary.getRange("A1").values = [["历史标注不确定性复算：42图 / 1,055条标注"]];
summary.getRange("A1").format = { font: { name: "Microsoft YaHei", size: 18, bold: true, color: "#FFFFFF" }, verticalAlignment: "center" };
summary.getRange("A2:Q2").format = { fill: "#D9EAF7", rowHeight: 30 };
summary.getRange("A2").values = [["中英文合并为主；阶段仅保留为reference与流程敏感性。所有历史高密度图均来自HoHoNet test split。"]];
summary.getRange("A2").format = { font: { name: "Microsoft YaHei", size: 10, bold: true, color: "#17365D" }, verticalAlignment: "center" };

summary.getRange("A4:B4").values = [["核验项", "数值"]];
summary.getRange("A5:A13").values = [
  ["历史图像数"], ["reference-ready图像数"], ["规范标注总数"], ["reference质量eligible标注"],
  ["共同质量曲线最大k"], ["冻结严格有效：P1"], ["当前规范化有效：P1"], ["冻结/当前有效：C1"], ["官方split=test图像数"],
];
summary.getRange("B5:B13").values = [[contract.length], [countTrue(contract, "geometry_reference_ready")], [annotations.length],
  [countTrue(annotations, "gt_primary_analysis_eligible")], [13], [countTrue(annotations, "strict_geometry_valid", "P1")],
  [countTrue(annotations, "current_canonical_geometry_valid", "P1")], [countTrue(annotations, "strict_geometry_valid", "C1")],
  [contract.filter((row) => row.official_split === "test").length]];

summary.getRange("A15:D15").values = [["如何解读", "结论", "边界", "证据位置"]];
summary.getRange("A16:D22").values = [
  ["20人的点", "无reference曲线中的k=20是历史标注无放回重采样，不是外推。", "它不是41图共同reference质量点；质量曲线只到k=13。", "无reference曲线 / 聚合质量_汇总"],
  ["中英文", "不作为主分层；仅保留项目/语言敏感性。", `41图合并差=${Number(pooledLanguage.english_minus_chinese_task_mean_quality).toFixed(4)}，且P1/C1方向相反，不能解释为语言因果。`, "语言项目敏感性"],
  ["12到15人", `无reference恢复率增益=${Number(plateauRecovery.estimate).toFixed(4)}；95%簇bootstrap区间[${Number(plateauRecovery.ci95_lower_building_bootstrap).toFixed(4)}, ${Number(plateauRecovery.ci95_upper_building_bootstrap).toFixed(4)}]。`, `reference质量共同支持只到13；12→13两端可交付质量变化=${Number(plateauResolved.estimate).toFixed(4)}。未预设SESOI，不能确认12–15质量平台。`, "平台检验_汇总"],
  ["整体分歧分布", "按42个任务等权画分布；mask、boundary、wall、角点数分歧、无效提交分别保留。", "避免把所有pair直接混合后让标注人数较多的图获得更大权重。", "整体分歧_任务 / 整体分歧_ECDF"],
  ["少数结构", `阈值0.95下全体多模态=${Number(fullMulti95.supported_multimodal_count)}图；k=20确定性第二排序模式纯恢复=${Number(pooledMinority20.same_second_mode_recovery_rate).toFixed(3)}。`, "抽样可见、同一模式恢复、完整分区恢复和generic多模态已分开；3/21图有排序并列，另报排除敏感性。", "少数结构_汇总 / 全体结构状态"],
  ["reference", "C1 12图是主分析；P1与41图合并只作敏感性。", "两阶段reference的独立性合同不等价。", "图像reference合同"],
  ["不计算内容", "不使用GT oracle best-of-k，也不报告有害错误率。", "harm阈值与实际结果尚未冻结。", "README_ZH.md / QA_SUMMARY.json"],
];

for (const range of ["A4:B4", "A15:D15"]) {
  summary.getRange(range).format = { fill: "#4472C4", font: { name: "Microsoft YaHei", size: 10, bold: true, color: "#FFFFFF" }, borders: { preset: "all", style: "thin", color: "#D8E2EC" } };
}
summary.getRange("A5:B13").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
summary.getRange("A5:A13").format = { fill: "#D9EAF7", font: { bold: true, color: "#17365D" } };
summary.getRange("A16:D22").format = { wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: "#D9E2F3" } };
summary.getRange("A16:D22").format.rowHeight = 48;
summary.getRange("A16:A22").format = { fill: "#E2F0D9", font: { bold: true, color: "#385723" } };
summary.getRange("A1:Q140").format.font = { name: "Microsoft YaHei", size: 10, color: "#1F2937" };
summary.getRange("A1").format.font = { name: "Microsoft YaHei", size: 18, bold: true, color: "#FFFFFF" };
summary.getRange("A2").format.font = { name: "Microsoft YaHei", size: 10, bold: true, color: "#17365D" };
summary.getRange("A:A").format.columnWidth = 24;
summary.getRange("B:B").format.columnWidth = 30;
summary.getRange("C:C").format.columnWidth = 42;
summary.getRange("D:D").format.columnWidth = 25;
summary.freezePanes.freezeRows(2);

const kRef = [3, 5, 8, 10, 12, 15, 20];
const refMetric = (metric, k) => Number(referenceFree.find((row) => row.analysis_stratum === "pooled_42" && row.metric === metric && Number(row.k) === k).estimate);
summary.getRange("A50:C50").values = [["k", "不一致度恢复≤0.03", "角点数多样性检出"]];
summary.getRange("A51:C57").values = kRef.map((k) => [k, refMetric("disagreement_recovery_abs_error_le_0_03", k), refMetric("cardinality_diversity_detection", k)]);

const kQuality = Array.from({ length: 11 }, (_, index) => index + 3);
const qualityValue = (stratum, field, k) => Number(quality.find((row) => row.analysis_stratum === stratum && Number(row.k_valid) === k)[field]);
summary.getRange("A60:D60").values = [["k", "C1主分析", "P1敏感性", "41图合并敏感性"]];
summary.getRange("A61:D71").values = kQuality.map((k) => [k, qualityValue("C1_primary_12", "resolved_only_quality", k), qualityValue("P1_sensitivity_29", "resolved_only_quality", k), qualityValue("pooled_image_equal_41", "resolved_only_quality", k)]);
summary.getRange("F60:I60").values = [["k", "C1主分析", "P1敏感性", "41图合并敏感性"]];
summary.getRange("F61:I71").values = kQuality.map((k) => [k, qualityValue("C1_primary_12", "resolved_rate", k), qualityValue("P1_sensitivity_29", "resolved_rate", k), qualityValue("pooled_image_equal_41", "resolved_rate", k)]);
for (const range of ["A50:C50", "A60:D60", "F60:I60"]) {
  summary.getRange(range).format = { fill: "#5B9BD5", font: { bold: true, color: "#FFFFFF" }, borders: { preset: "all", style: "thin", color: "#D8E2EC" } };
}
summary.getRange("B51:C57").format.numberFormat = "0.0%";
summary.getRange("B61:D71").format.numberFormat = "0.000";
summary.getRange("G61:I71").format.numberFormat = "0.0%";

const recoveryChart = summary.charts.add("line", summary.getRange("A50:C57"));
recoveryChart.title = "无reference：历史有限roster恢复率";
recoveryChart.hasLegend = true;
recoveryChart.yAxis = { numberFormatCode: "0%" };
recoveryChart.setPosition("F4", "P18");
const qualityChart = summary.charts.add("line", summary.getRange("A60:D71"));
qualityChart.title = "GT-blind聚合的resolved-only质量";
qualityChart.hasLegend = true;
qualityChart.yAxis = { numberFormatCode: "0.00" };
qualityChart.setPosition("F20", "P34");
const deliveryChart = summary.charts.add("line", summary.getRange("F60:I71"));
deliveryChart.title = "GT-blind聚合的自主交付率";
deliveryChart.hasLegend = true;
deliveryChart.yAxis = { numberFormatCode: "0%" };
deliveryChart.setPosition("F36", "P50");

const pooledMinority = minoritySummary
  .filter((row) => row.analysis_stratum === "pooled_42")
  .sort((left, right) => Number(left.k) - Number(right.k));
summary.getRange("A75:F75").values = [["k", "支持性可见(精确)", "同一第二模式纯恢复", "可见后条件恢复", "完整分区恢复", "generic多模态"]];
summary.getRange("A76:F80").values = pooledMinority.map((row) => [
  Number(row.k),
  Number(row.exact_support_visible_probability),
  Number(row.same_second_mode_recovery_rate),
  Number(row.same_second_mode_recovery_given_support_visible),
  Number(row.full_partition_restriction_recovery_rate),
  Number(row.generic_multimodality_status_rate),
]);
summary.getRange("A75:F75").format = { fill: "#8064A2", font: { bold: true, color: "#FFFFFF" }, borders: { preset: "all", style: "thin", color: "#D8E2EC" } };
summary.getRange("B76:F80").format.numberFormat = "0.0%";
const minorityChart = summary.charts.add("line", summary.getRange("A75:F80"));
minorityChart.title = "少数结构：抽样限制与同一模式恢复必须分开";
minorityChart.hasLegend = true;
minorityChart.yAxis = { numberFormatCode: "0%" };
minorityChart.setPosition("F52", "P66");

const sortedMetric = (field) => disagreementTasks.map((row) => Number(row[field])).sort((left, right) => left - right);
const sortedMask = sortedMetric("full_mask_distance");
const sortedBoundary = sortedMetric("boundary_distance_mean");
const sortedWall = sortedMetric("wall_distance_mean");
summary.getRange("A84:D84").values = [["任务等权排序", "mask均值", "boundary均值", "wall均值"]];
summary.getRange("A85:D126").values = sortedMask.map((value, index) => [index + 1, value, sortedBoundary[index], sortedWall[index]]);
summary.getRange("A84:D84").format = { fill: "#70AD47", font: { bold: true, color: "#FFFFFF" }, borders: { preset: "all", style: "thin", color: "#D8E2EC" } };
summary.getRange("B85:D126").format.numberFormat = "0.000";
const distributionChart = summary.charts.add("line", summary.getRange("A84:D126"));
distributionChart.title = "42图任务等权分歧分布（各通道独立排序）";
distributionChart.hasLegend = true;
distributionChart.yAxis = { numberFormatCode: "0.000" };
distributionChart.setPosition("F68", "P82");

const pooledThreshold = thresholdSensitivity
  .filter((row) => row.analysis_stratum === "pooled_42")
  .sort((left, right) => Number(left.threshold) - Number(right.threshold));
summary.getRange("A130:E130").values = [["阈值", "单峰", "主导+异议", "受支持多模态", "不可评估"]];
summary.getRange("A131:E135").values = pooledThreshold.map((row) => [
  Number(row.threshold), Number(row.unimodal_count), Number(row.dominant_with_dissent_count),
  Number(row.supported_multimodal_count), Number(row.not_evaluable_count),
]);
summary.getRange("A130:E130").format = { fill: "#ED7D31", font: { bold: true, color: "#FFFFFF" }, borders: { preset: "all", style: "thin", color: "#D8E2EC" } };
const thresholdChart = summary.charts.add("line", summary.getRange("A130:E135"));
thresholdChart.title = "结构状态对相似度阈值的敏感性（42图）";
thresholdChart.hasLegend = true;
thresholdChart.setPosition("F84", "P98");

await fs.mkdir(path.dirname(output), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(output);
for (const [index, sheet] of workbook.worksheets.items.entries()) {
  const range = sheet.name === "汇总" ? "A1:Q140" : `A1:${colName(Math.min(sheet.getUsedRange().values[0].length - 1, 11))}${Math.min(sheet.getUsedRange().values.length, 16)}`;
  const preview = await workbook.render({ sheetName: sheet.name, range, scale: 0.75, format: "png" });
  await fs.writeFile(path.join(previewDir, `${String(index).padStart(2, "0")}_${sheet.name}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(output));
const exportedPreview = await reopened.render({ sheetName: "汇总", range: "A1:Q140", scale: 0.75, format: "png" });
await fs.writeFile(path.join(previewDir, "00_汇总_导出后.png"), new Uint8Array(await exportedPreview.arrayBuffer()));
const errors = await reopened.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 1000 }, summary: "formula error scan" });
const sha256 = crypto.createHash("sha256").update(await fs.readFile(output)).digest("hex");
await fs.writeFile(path.join(inputDir, "WORKBOOK_VALIDATION.json"), JSON.stringify({ status: "pass", workbook: path.basename(output), sha256, sheets: workbook.worksheets.items.length, previews: previewDir, formula_error_scan: errors.ndjson }, null, 2) + "\n", "utf8");
await fs.rm(`${output}.inspect.ndjson`, { force: true });
console.log(JSON.stringify({ status: "ok", output, sha256, sheets: workbook.worksheets.items.length, previewDir }));
