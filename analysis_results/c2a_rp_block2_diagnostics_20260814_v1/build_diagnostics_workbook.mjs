import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "file:///C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const dir = path.dirname(new URL(import.meta.url).pathname.replace(/^\/(?:[A-Za-z]:)/, (m) => m.slice(1)));
const output = path.join(dir, "C2A_RP_Block2_Detailed_Diagnostics.xlsx");
const summary = JSON.parse(await fs.readFile(path.join(dir, "diagnostic_summary.json"), "utf8"));
const sources = [
  ["Formal_Model", "formal_model_diagnostics.csv"],
  ["Stage", "stage_summary.csv"],
  ["Workers", "worker_diagnostics.csv"],
  ["Pair_Summary", "block_pair_summary.csv"],
  ["Pairs", "block_pair_diagnostics.csv"],
  ["Tasks", "task_diagnostics.csv"],
  ["Buildings", "building_diagnostics.csv"],
  ["Meta_Rows", "block2_meta_rows.csv"],
  ["Meta_Relations", "block2_meta_relation_summary.csv"],
  ["Meta_Agreement", "block2_meta_agreement_summary.csv"],
  ["Active_Time", "block2_active_time_summary.csv"],
  ["Scope", "block2_scope_summary.csv"],
  ["Sensitivity", "risk_sensitivity_summary.csv"],
  ["LOO_Building", "leave_one_building_out.csv"],
  ["LOO_Task", "leave_one_task_out.csv"],
  ["Ref_Crosswalk", "reference_registry_crosswalk.csv"],
  ["Checks", "checks.csv"],
  ["Sources", "source_manifest.csv"],
  ["Evidence", "source_evidence_snapshot.csv"],
];

const workbook = Workbook.create();
const cover = workbook.worksheets.add("Summary");
for (const [sheetName, fileName] of sources) {
  const imported = await Workbook.fromCSV(await fs.readFile(path.join(dir, fileName), "utf8"), { sheetName });
  const values = imported.worksheets.getItem(sheetName).getUsedRange().values;
  const target = workbook.worksheets.add(sheetName);
  target.getRangeByIndexes(0, 0, values.length, values[0].length).values = values;
}

const colName = (index) => {
  let value = index + 1;
  let result = "";
  while (value) {
    value--;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
};

for (const [index, [sheetName]] of sources.entries()) {
  const sheet = workbook.worksheets.getItem(sheetName);
  const used = sheet.getUsedRange();
  const values = used.values;
  const rows = values.length;
  const cols = values[0].length;
  const headers = values[0].map((v) => String(v ?? ""));
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(1);
  used.format.font = { name: "Aptos", size: 10, color: "#1F2937" };
  used.format.verticalAlignment = "center";
  const header = sheet.getRangeByIndexes(0, 0, 1, cols);
  header.format = {
    fill: "#1F4E78",
    font: { name: "Aptos Display", size: 10, bold: true, color: "#FFFFFF" },
    wrapText: true,
    rowHeight: 30,
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: "#D8E2EC" },
  };
  if (rows > 1) {
    const body = sheet.getRangeByIndexes(1, 0, rows - 1, cols);
    body.format.borders = { preset: "all", style: "thin", color: "#E5E7EB" };
    const table = sheet.tables.add(`A1:${colName(cols - 1)}${rows}`, true, `T${index + 1}_${sheetName.replace(/[^A-Za-z0-9]/g, "")}`);
    table.style = "TableStyleMedium2";
    table.showBandedRows = true;
    table.showFilterButton = true;
  }
  headers.forEach((name, column) => {
    const cells = sheet.getRangeByIndexes(0, column, rows, 1);
    const samples = values.slice(0, Math.min(rows, 100)).map((row) => String(row[column] ?? ""));
    const width = Math.max(9, Math.min(36, Math.max(name.length, ...samples.map((v) => v.length)) + 2));
    cells.format.columnWidth = width;
    if (/sha256|path|warning|reason|base_task_id|annotation_id/i.test(name)) cells.format.wrapText = true;
    if (/seconds/i.test(name)) cells.format.numberFormat = "0.0";
    else if (/tolerance/i.test(name)) cells.format.numberFormat = "0.000E+00";
    else if (/rate|quality|risk|slope|delta|mean|median|variance|q025|q975|q25|q75|sd|agreement|half_width/i.test(name)) cells.format.numberFormat = "0.0000";
    else if (/^(n|rows|workers|tasks|buildings|count|parameters|rank|yes_n)$|_n$|_rows$|_total$|_eligible$/i.test(name)) cells.format.numberFormat = "0";
  });
}

cover.showGridLines = false;
cover.getRange("A1:Q1").format = { fill: "#17365D", rowHeight: 34 };
cover.getRange("A1").values = [["C2-A-RP Block 2 Detailed Diagnostics"]];
cover.getRange("A1").format = { font: { name: "Aptos Display", size: 18, bold: true, color: "#FFFFFF" }, verticalAlignment: "center" };
cover.getRange("A2:Q2").format = { fill: "#FFF2CC", rowHeight: 28 };
cover.getRange("A2").values = [["DIAGNOSTIC ONLY — formal frozen result reproduced, not replaced; no Block 3 generated."]];
cover.getRange("A2").format = { font: { name: "Aptos", size: 10, bold: true, color: "#7F6000" }, verticalAlignment: "center" };

cover.getRange("A4:B4").values = [["Frozen fact", "Value"]];
cover.getRange("A5:A18").values = [
  ["Formal model status"],
  ["Boundary components"],
  ["Formal worker CI available"],
  ["Next block generated"],
  ["Cumulative rows"],
  ["Cumulative eligible rows"],
  ["Workers"],
  ["Eligible tasks"],
  ["Eligible buildings"],
  ["Block 2 submissions"],
  ["Block 2 eligible evidence"],
  ["Block 2 not evaluable"],
  ["Active-time exact matches"],
  ["Active-time median (s)"],
];
cover.getRange("B5:B18").formulas = [
  ["=Formal_Model!A2"],
  ["=Formal_Model!D2"],
  ["=Formal_Model!B2"],
  ["=\"False\""],
  ["=Stage!C2"],
  ["=Stage!D2"],
  ["=Stage!F2"],
  ["=Stage!H2"],
  ["=Stage!J2"],
  ["=Stage!C6"],
  ["=Stage!D6"],
  ["=Stage!E6"],
  ["=Active_Time!D2"],
  ["=Active_Time!F2"],
];
cover.getRange("A20:B20").values = [["Cross-version fact", "Value"]];
cover.getRange("A21:A24").values = [
  ["Eligible rows whose current registry status is not public-GT-as-is"],
  ["Affected tasks"],
  ["Bootstrap seed"],
  ["Bootstrap replicates"],
];
cover.getRange("B21:B24").values = [
  [summary.reference_crosswalk.eligible_rows_current_registry_not_public_gt_as_is],
  [summary.reference_crosswalk.tasks_current_registry_not_public_gt_as_is],
  [summary.bootstrap.seed],
  [summary.bootstrap.replicates],
];
cover.getRange("A26:C26").values = [["Stage", "Ordinary quality mean", "Stress quality mean"]];
cover.getRange("A27:A29").values = [["C2-B"], ["Block 1"], ["Block 2"]];
cover.getRange("B27:C29").formulas = [
  ["=Stage!T10", "=Stage!T11"],
  ["=Stage!T4", "=Stage!T5"],
  ["=Stage!T7", "=Stage!T8"],
];
cover.getRange("B17:B17").format.numberFormat = "0";
cover.getRange("B18:B18").format.numberFormat = "0.0";
cover.getRange("B27:C29").format.numberFormat = "0.0000";

for (const range of ["A4:B4", "A20:B20", "A26:C26"]) {
  cover.getRange(range).format = {
    fill: "#4472C4",
    font: { name: "Aptos", size: 10, bold: true, color: "#FFFFFF" },
    borders: { preset: "all", style: "thin", color: "#D8E2EC" },
  };
}
for (const range of ["A5:B18", "A21:B24", "A27:C29"]) {
  cover.getRange(range).format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
}
cover.getRange("A5:A18").format = { fill: "#D9EAF7", font: { bold: true, color: "#17365D" } };
cover.getRange("A21:A24").format = { fill: "#E2F0D9", font: { bold: true, color: "#385723" }, wrapText: true };
cover.getRange("A27:A29").format = { fill: "#F2F2F2", font: { bold: true } };
cover.getRange("A1:A29").format.columnWidth = 38;
cover.getRange("B1:B29").format.columnWidth = 24;
cover.getRange("C1:C29").format.columnWidth = 24;
cover.getRange("A1:Q29").format.font = { name: "Aptos", size: 10, color: "#1F2937" };
cover.getRange("A1").format.font = { name: "Aptos Display", size: 18, bold: true, color: "#FFFFFF" };
cover.getRange("A2").format.font = { name: "Aptos", size: 10, bold: true, color: "#7F6000" };
cover.freezePanes.freezeRows(2);

const chart = cover.charts.add("bar", cover.getRange("A26:C29"));
chart.title = "Eligible quality by stage and stratum";
chart.hasLegend = true;
chart.yAxis = { numberFormatCode: "0.00" };
chart.setPosition("E4", "Q23");

const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(output);

const previewDir = path.join(os.tmpdir(), "c2a_rp_block2_workbook_preview_20260814");
await fs.mkdir(previewDir, { recursive: true });
for (const sheet of ["Summary", ...sources.map(([name]) => name)]) {
  const preview = await workbook.render({ sheetName: sheet, autoCrop: "all", scale: 0.8, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheet}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(output));
const exportedPreview = await reopened.render({ sheetName: "Summary", autoCrop: "all", scale: 0.8, format: "png" });
await fs.writeFile(path.join(previewDir, "Summary_exported.png"), new Uint8Array(await exportedPreview.arrayBuffer()));
const errors = await reopened.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 1000 },
  summary: "formula error scan",
});
const sha256 = crypto.createHash("sha256").update(await fs.readFile(output)).digest("hex");
await fs.writeFile(
  path.join(dir, "workbook_validation.json"),
  JSON.stringify({ workbook: path.basename(output), sha256, sheets: 1 + sources.length, previews: previewDir, formula_error_scan: errors.ndjson }, null, 2) + "\n",
);
await fs.rm(`${output}.inspect.ndjson`, { force: true });
console.log(JSON.stringify({ status: "ok", output, sha256, sheets: 1 + sources.length, previewDir }));
