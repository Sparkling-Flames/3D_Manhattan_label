import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


function arg(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) throw new Error(`missing ${name}`);
  return process.argv[index + 1];
}


function parseCsvLine(line) {
  const cells = [];
  let value = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"' && quoted && line[index + 1] === '"') {
      value += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      cells.push(value);
      value = "";
    } else {
      value += char;
    }
  }
  cells.push(value);
  return cells;
}


function safeSheetName(name, code, used) {
  const base = name.replace(/[][\\/*?:]/g, "_").trim() || code;
  let candidate = base.slice(0, 31);
  if (used.has(candidate)) candidate = `${base.slice(0, 25)}_${code}`.slice(0, 31);
  if (used.has(candidate)) throw new Error(`duplicate sheet name: ${candidate}`);
  used.add(candidate);
  return candidate;
}


const input = path.resolve(arg("--input"));
const output = path.resolve(arg("--output"));
const previewDir = path.resolve(arg("--preview-dir"));
const lines = (await fs.readFile(input, "utf8")).replace(/^\uFEFF/, "").trim().split(/\r?\n/);
const headers = parseCsvLine(lines.shift());
if (headers.join(",") !== "public_worker_code,worker_name,task_code") throw new Error("unexpected Chinese release schema");
const rows = lines.map((line) => Object.fromEntries(headers.map((header, index) => [header, parseCsvLine(line)[index]])));
const byWorker = new Map();
for (const row of rows) {
  if (!/^W\d{3}$/.test(row.public_worker_code) || !/^任务4-\d{3}$/.test(row.task_code) || !row.worker_name) {
    throw new Error(`invalid worker-facing row: ${JSON.stringify(row)}`);
  }
  const key = `${row.public_worker_code}\t${row.worker_name}`;
  if (!byWorker.has(key)) byWorker.set(key, []);
  byWorker.get(key).push(row.task_code);
}
if (!byWorker.size || [...byWorker.values()].some((tasks) => !tasks.length || new Set(tasks).size !== tasks.length)) {
  throw new Error("worker sheets require non-empty unique task codes");
}

const workbook = Workbook.create();
const note = workbook.worksheets.add("说明");
note.getRange("A1:A5").values = [["说明"], ["每个人使用自己姓名对应的 sheet。"], ["当前 C2-B 入口为任务4；英文字母对应关系为 D=4。"], ["请按 task_code 找任务，例如 任务4-001；“-”后是该项目 planned import 的内部顺序。"], ["外部 assignment manifest 是唯一分发真源，本工作簿只是工人可读显示表。"]];
note.getRange("A1:A5").format.wrapText = true;
note.getRange("A1").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
note.getRange("A1:A5").format.columnWidthPx = 720;
note.tables.add("A1:A5", true, "InstructionsTable");

const used = new Set(["说明"]);
const sorted = [...byWorker.entries()].sort(([left], [right]) => Number(left.slice(1, 4)) - Number(right.slice(1, 4)));
for (const [key, tasks] of sorted) {
  const [code, name] = key.split("\t");
  const sheet = workbook.worksheets.add(safeSheetName(name, code, used));
  sheet.getRange(`A1:B${tasks.length + 1}`).values = [["order", "task_code"], ...tasks.map((task, index) => [index + 1, task])];
  sheet.getRange("A1:B1").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
  sheet.getRange(`A1:B${tasks.length + 1}`).format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
  sheet.getRange(`A1:A${tasks.length + 1}`).format.columnWidthPx = 72;
  sheet.getRange(`B1:B${tasks.length + 1}`).format.columnWidthPx = 160;
  sheet.freezePanes.freezeRows(1);
  sheet.tables.add(`A1:B${tasks.length + 1}`, true, `Tasks_${code}`);
}

await fs.mkdir(path.dirname(output), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(output);
for (const [index, sheet] of workbook.worksheets.items.entries()) {
  const preview = await workbook.render({ sheetName: sheet.name, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, `${String(index).padStart(2, "0")}_${sheet.name.replace(/[^\p{L}\p{N}_.-]+/gu, "_")}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const inspection = await workbook.inspect({ kind: "workbook,sheet,table", maxChars: 20000, tableMaxRows: 12, tableMaxCols: 4 });
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "formula error scan" });
await fs.rm(`${output}.inspect.ndjson`, { force: true });
console.log(JSON.stringify({ output, workerSheets: byWorker.size, sheets: workbook.worksheets.items.length, rows: rows.length }));
console.log(inspection.ndjson);
console.log(errors.ndjson);
