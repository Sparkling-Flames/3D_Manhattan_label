import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { SpreadsheetFile, Workbook } = require("@oai/artifact-tool");
const JSZip = require("jszip");

function excelValue(value, qa) {
  if (value === null || value === undefined) return null;
  if (typeof value === "number" || typeof value === "boolean") return value;
  let text = String(value);
  if (text.startsWith("=")) text = `'${text}`;
  if (text.length > 32700) {
    qa.truncatedCells += 1;
    text = `${text.slice(0, 32670)}…[完整值见同名CSV]`;
  }
  return text;
}

function columnLetters(index) {
  let value = index + 1;
  let output = "";
  while (value) {
    value -= 1;
    output = String.fromCharCode(65 + (value % 26)) + output;
    value = Math.floor(value / 26);
  }
  return output;
}

async function buildBatch(payloadPath, outputPath, previewDir) {
  const payload = JSON.parse(await fsp.readFile(payloadPath, "utf8"));
  const workbook = Workbook.create();
  const qa = { previews: [], truncatedCells: 0, tableCount: 0, rowCount: 0 };

  for (const table of payload.tables) {
    const sheetName = table.sheetName;
    const sheet = workbook.worksheets.add(sheetName);
    const fields = table.spec.fields;
    const columns = table.workbookColumns;
    const notes = [
      ["表名", table.name],
      ["总体", table.spec.population],
      ["分析单位", table.spec.analysis_unit],
      ["筛选规则", table.spec.filter_rule],
      ["分组方式", table.spec.grouping],
      ["来源", table.spec.source],
      ["XLSX字段覆盖", `字段总数=${columns.length}；省略字段数=0`],
      ["XLSX行覆盖", `同名CSV总行数=${table.fullRowCount}；XLSX显示行数=${table.rows.length}；省略行数=0`],
    ];
    sheet.getRangeByIndexes(0, 0, notes.length, 2).values = notes;
    const fieldHeaderRow = notes.length + 1;
    sheet.getRangeByIndexes(fieldHeaderRow, 0, 1, 4).values = [["英文列名", "中文含义", "来源或公式", "缺失含义"]];
    const fieldRows = fields.map((field) => [field.field, field.meaning_zh, field.source_or_formula, field.missing_meaning]);
    if (fieldRows.length) sheet.getRangeByIndexes(fieldHeaderRow + 1, 0, fieldRows.length, 4).values = fieldRows;
    const dataHeaderRow = fieldHeaderRow + fieldRows.length + 2;
    const columnCount = Math.max(columns.length, 1);
    sheet.getRangeByIndexes(dataHeaderRow, 0, 1, columnCount).values = [columns.length ? columns : ["empty_table"]];
    const rows = table.rows.map((row) => columns.map((column) => excelValue(row[column], qa)));
    for (let start = 0; start < rows.length; start += 2000) {
      const block = rows.slice(start, start + 2000);
      sheet.getRangeByIndexes(dataHeaderRow + 1 + start, 0, block.length, columnCount).values = block;
    }

    const lastRow = dataHeaderRow + Math.max(rows.length, 1);
    const lastCol = columnLetters(columnCount - 1);
    sheet.getRange(`A1:${lastCol}${lastRow + 1}`).format = {
      fill: "#FFFFFF",
      font: { name: "Microsoft YaHei", size: 10, color: "#000000" },
      verticalAlignment: "top",
    };
    sheet.getRange(`A1:B${notes.length}`).format = { font: { name: "Microsoft YaHei", size: 10 }, wrapText: true };
    sheet.getRange(`A${fieldHeaderRow + 1}:D${fieldHeaderRow + 1}`).format = {
      fill: "#E7E6E6",
      font: { name: "Microsoft YaHei", size: 10, bold: true, color: "#000000" },
      borders: { top: { style: "thin", color: "#A6A6A6" }, bottom: { style: "thin", color: "#A6A6A6" }, left: { style: "thin", color: "#A6A6A6" }, right: { style: "thin", color: "#A6A6A6" } },
    };
    if (fieldRows.length) sheet.getRange(`A${fieldHeaderRow + 2}:D${fieldHeaderRow + fieldRows.length + 1}`).format = { wrapText: true, font: { name: "Microsoft YaHei", size: 10 } };
    sheet.getRange(`A${dataHeaderRow + 1}:${lastCol}${dataHeaderRow + 1}`).format = {
      fill: "#D9D9D9",
      font: { name: "Microsoft YaHei", size: 10, bold: true, color: "#000000" },
      borders: { top: { style: "thin", color: "#808080" }, bottom: { style: "thin", color: "#808080" }, left: { style: "thin", color: "#808080" }, right: { style: "thin", color: "#808080" } },
    };
    if (rows.length) {
      const tableObject = sheet.tables.add(`A${dataHeaderRow + 1}:${lastCol}${dataHeaderRow + rows.length + 1}`, true, table.tableName);
      tableObject.style = "TableStyleLight1";
      tableObject.showBandedRows = false;
      tableObject.showBandedColumns = false;
      tableObject.showFilterButton = true;
      qa.tableCount += 1;
    }
    sheet.freezePanes.freezeRows(dataHeaderRow + 1);
    const sampleRows = rows.slice(0, 80);
    for (let column = 0; column < columnCount; column += 1) {
      const values = [columns[column] || "", ...sampleRows.map((row) => row[column] ?? "")];
      const width = Math.max(11, Math.min(42, Math.max(...values.map((value) => String(value).length)) + 2));
      sheet.getRange(`${columnLetters(column)}:${columnLetters(column)}`).format.columnWidth = width;
    }
    sheet.getRange("A:D").format.wrapText = true;
    sheet.showGridLines = true;

    if (previewDir) {
      await fsp.mkdir(previewDir, { recursive: true });
      const previewLastRow = Math.min(lastRow + 1, dataHeaderRow + 12);
      const previewLastCol = columnLetters(Math.max(3, Math.min(columnCount - 1, 11)));
      const preview = await workbook.render({ sheetName, range: `A1:${previewLastCol}${previewLastRow}`, scale: 0.8, format: "png" });
      const previewPath = path.join(previewDir, `${String(table.globalIndex + 1).padStart(3, "0")}_${sheetName}.png`);
      await fsp.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
      qa.previews.push({ sheetName, previewPath, dataHeaderRow: dataHeaderRow + 1, rowCount: rows.length, columnCount });
    }
    qa.rowCount += rows.length;
  }

  qa.formulaInspection = await workbook.inspect({ kind: "formula", maxChars: 4000, options: { maxResults: 50 } });
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await fsp.mkdir(path.dirname(outputPath), { recursive: true });
  await xlsx.save(outputPath);
  await fsp.writeFile(`${outputPath}.qa.json`, `${JSON.stringify(qa, null, 2)}\n`, "utf8");
}

function xmlElements(xml, name) {
  return xml.match(new RegExp(`<${name}\\b[^>]*\\/>`, "g")) ?? [];
}

function attribute(xml, name) {
  const match = xml.match(new RegExp(`\\b${name}="([^"]*)"`));
  if (!match) throw new Error(`missing XML attribute ${name}`);
  return match[1];
}

function resolveRelationshipPart(sourcePart, target) {
  if (target.startsWith("/")) return target.slice(1);
  return path.posix.normalize(path.posix.join(path.posix.dirname(sourcePart), target));
}

function relationshipPart(sourcePart) {
  return path.posix.join(path.posix.dirname(sourcePart), "_rels", `${path.posix.basename(sourcePart)}.rels`);
}

function insertBefore(xml, closingTag, addition) {
  const index = xml.lastIndexOf(closingTag);
  if (index < 0) throw new Error(`missing closing tag ${closingTag}`);
  return `${xml.slice(0, index)}${addition}${xml.slice(index)}`;
}

async function readZipText(zip, name) {
  const entry = zip.file(name);
  if (!entry) throw new Error(`missing XLSX part ${name}`);
  return entry.async("string");
}

async function assertSamePart(master, source, name) {
  const [left, right] = await Promise.all([master.file(name).async("nodebuffer"), source.file(name).async("nodebuffer")]);
  if (!left.equals(right)) throw new Error(`segmented workbooks disagree on ${name}`);
}

function cellXfsSection(stylesXml) {
  const match = stylesXml.match(/<x:cellXfs\b[^>]*>[\s\S]*?<\/x:cellXfs>/);
  if (!match) throw new Error("missing cellXfs style section");
  return match[0];
}

function cellXfs(stylesXml) {
  return cellXfsSection(stylesXml).match(/<x:xf\b(?:[^>]*\/>|[^>]*>[\s\S]*?<\/x:xf>)/g) ?? [];
}

function fontsSection(stylesXml) {
  const match = stylesXml.match(/<x:fonts\b[^>]*>[\s\S]*?<\/x:fonts>/);
  if (!match) throw new Error("missing fonts style section");
  return match[0];
}

function fonts(stylesXml) {
  return fontsSection(stylesXml).match(/<x:font\b(?:[^>]*\/>|[^>]*>[\s\S]*?<\/x:font>)/g) ?? [];
}

function mergeCellXfs(masterStylesXml, masterXfs, masterFonts, sourceStylesXml) {
  const masterRemainder = masterStylesXml.replace(cellXfsSection(masterStylesXml), "").replace(fontsSection(masterStylesXml), "");
  const sourceRemainder = sourceStylesXml.replace(cellXfsSection(sourceStylesXml), "").replace(fontsSection(sourceStylesXml), "");
  if (masterRemainder !== sourceRemainder) {
    throw new Error("segmented workbooks disagree on non-font/cellXfs styles");
  }
  const fontMap = fonts(sourceStylesXml).map((font) => {
    let index = masterFonts.indexOf(font);
    if (index < 0) {
      masterFonts.push(font);
      index = masterFonts.length - 1;
    }
    return index;
  });
  return cellXfs(sourceStylesXml).map((sourceXf) => {
    const xf = sourceXf.replace(/\bfontId="(\d+)"/, (match, index) => {
      const mapped = fontMap[Number(index)];
      if (mapped === undefined) throw new Error(`cellXf references unknown font ${index}`);
      return `fontId="${mapped}"`;
    });
    let index = masterXfs.indexOf(xf);
    if (index < 0) {
      masterXfs.push(xf);
      index = masterXfs.length - 1;
    }
    return index;
  });
}

function remapSheetStyles(sheetXml, styleMap) {
  const remap = (match, prefix, index, suffix) => {
    const mapped = styleMap[Number(index)];
    if (mapped === undefined) throw new Error(`worksheet references unknown style ${index}`);
    return `${prefix}${mapped}${suffix}`;
  };
  return sheetXml
    .replace(/(<x:c\b[^>]*\bs=")(\d+)(")/g, remap)
    .replace(/(<x:row\b[^>]*\bs=")(\d+)(")/g, remap)
    .replace(/(<x:col\b[^>]*\bstyle=")(\d+)(")/g, remap);
}

async function mergeWorkbooks(partPaths, outputPath, expectedSheets) {
  if (!partPaths.length) throw new Error("no workbook segments to merge");
  const master = await JSZip.loadAsync(await fsp.readFile(partPaths[0]));
  let workbookXml = await readZipText(master, "xl/workbook.xml");
  let workbookRels = await readZipText(master, "xl/_rels/workbook.xml.rels");
  let contentTypes = await readZipText(master, "[Content_Types].xml");
  let sheetCount = xmlElements(workbookXml, "x:sheet").length;
  let tableCount = Object.keys(master.files).filter((name) => /^xl\/tables\/table\d+\.xml$/.test(name)).length;
  const masterShared = await readZipText(master, "xl/sharedStrings.xml");
  if (/<x:si\b/.test(masterShared)) throw new Error("shared string remapping is required but unsupported");
  let masterStylesXml = await readZipText(master, "xl/styles.xml");
  const masterXfs = cellXfs(masterStylesXml);
  const masterFonts = fonts(masterStylesXml);

  for (const partPath of partPaths.slice(1)) {
    const source = await JSZip.loadAsync(await fsp.readFile(partPath));
    await assertSamePart(master, source, "xl/theme/theme1.xml");
    let styleMap;
    try {
      styleMap = mergeCellXfs(masterStylesXml, masterXfs, masterFonts, await readZipText(source, "xl/styles.xml"));
    } catch (error) {
      throw new Error(`${partPath}: ${error.message}`, { cause: error });
    }
    const sourceShared = await readZipText(source, "xl/sharedStrings.xml");
    if (/<x:si\b/.test(sourceShared)) throw new Error("shared string remapping is required but unsupported");

    const sourceWorkbook = await readZipText(source, "xl/workbook.xml");
    const sourceWorkbookRels = await readZipText(source, "xl/_rels/workbook.xml.rels");
    const sourceRelationships = new Map(
      xmlElements(sourceWorkbookRels, "Relationship").map((element) => [attribute(element, "Id"), element]),
    );
    for (const sourceSheetTag of xmlElements(sourceWorkbook, "x:sheet")) {
      const sourceRid = attribute(sourceSheetTag, "r:id");
      const worksheetRelationship = sourceRelationships.get(sourceRid);
      if (!worksheetRelationship || !attribute(worksheetRelationship, "Type").endsWith("/worksheet")) throw new Error(`missing worksheet relationship ${sourceRid}`);
      const sourceSheetPart = resolveRelationshipPart("xl/workbook.xml", attribute(worksheetRelationship, "Target"));
      const sourceSheetRelsPart = relationshipPart(sourceSheetPart);
      const newSheetNumber = ++sheetCount;
      const newSheetPart = `xl/worksheets/sheet${newSheetNumber}.xml`;
      const newRid = `Rv5sheet${String(newSheetNumber).padStart(4, "0")}`;
      const newSheetTag = sourceSheetTag
        .replace(/\bsheetId="[^"]*"/, `sheetId="${newSheetNumber}"`)
        .replace(/\br:id="[^"]*"/, `r:id="${newRid}"`);
      workbookXml = insertBefore(workbookXml, "</x:sheets>", newSheetTag);
      workbookRels = insertBefore(
        workbookRels,
        "</Relationships>",
        `<Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="/${newSheetPart}" Id="${newRid}" />`,
      );
      master.file(newSheetPart, remapSheetStyles(await readZipText(source, sourceSheetPart), styleMap));
      contentTypes = insertBefore(
        contentTypes,
        "</Types>",
        `<Override PartName="/${newSheetPart}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml" />`,
      );

      const sourceSheetRelsEntry = source.file(sourceSheetRelsPart);
      if (sourceSheetRelsEntry) {
        let newSheetRels = await sourceSheetRelsEntry.async("string");
        for (const tableRelationship of xmlElements(newSheetRels, "Relationship").filter((element) => attribute(element, "Type").endsWith("/table"))) {
          const sourceTablePart = resolveRelationshipPart(sourceSheetPart, attribute(tableRelationship, "Target"));
          const newTableNumber = ++tableCount;
          const newTablePart = `xl/tables/table${newTableNumber}.xml`;
          const sourceTableXml = await readZipText(source, sourceTablePart);
          const newTableXml = sourceTableXml.replace(/(<x:table\b[^>]*\bid=")\d+("[^>]*>)/, `$1${newTableNumber}$2`);
          master.file(newTablePart, newTableXml);
          newSheetRels = newSheetRels.replace(tableRelationship, tableRelationship.replace(/\bTarget="[^"]*"/, `Target="/${newTablePart}"`));
          contentTypes = insertBefore(
            contentTypes,
            "</Types>",
            `<Override PartName="/${newTablePart}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml" />`,
          );
        }
        master.file(relationshipPart(newSheetPart), newSheetRels);
      }
    }
  }

  if (sheetCount !== expectedSheets) throw new Error(`merged sheet count ${sheetCount} != ${expectedSheets}`);
  master.file("xl/workbook.xml", workbookXml);
  master.file("xl/_rels/workbook.xml.rels", workbookRels);
  master.file("[Content_Types].xml", contentTypes);
  masterStylesXml = masterStylesXml.replace(fontsSection(masterStylesXml), `<x:fonts count="${masterFonts.length}">${masterFonts.join("")}</x:fonts>`);
  masterStylesXml = masterStylesXml.replace(cellXfsSection(masterStylesXml), `<x:cellXfs count="${masterXfs.length}">${masterXfs.join("")}</x:cellXfs>`);
  master.file("xl/styles.xml", masterStylesXml);
  const output = await master.generateAsync({ type: "nodebuffer", compression: "DEFLATE", compressionOptions: { level: 6 }, streamFiles: true });
  await fsp.writeFile(outputPath, output);
  return { sheetCount, tableCount };
}

async function main(payloadDir, outputPath, previewDir) {
  const manifest = JSON.parse(await fsp.readFile(path.join(payloadDir, "manifest.json"), "utf8"));
  const partsDir = await fsp.mkdtemp(path.join(path.dirname(outputPath), ".v5_xlsx_parts_"));
  const partPaths = [];
  const batchQa = [];
  let complete = false;
  try {
    for (const [index, batch] of manifest.batches.entries()) {
      const partPath = path.join(partsDir, `part_${String(index + 1).padStart(3, "0")}.xlsx`);
      const args = ["--max-old-space-size=8192", fs.realpathSync(process.argv[1]), "--batch", path.join(payloadDir, batch.file), partPath];
      if (previewDir) args.push(previewDir);
      const result = spawnSync(process.execPath, args, { cwd: process.cwd(), env: process.env, stdio: "inherit" });
      if (result.error) throw result.error;
      if (result.status !== 0) throw new Error(`workbook batch ${batch.file} failed with exit ${result.status}`);
      const qa = JSON.parse(await fsp.readFile(`${partPath}.qa.json`, "utf8"));
      if (qa.truncatedCells) throw new Error(`${batch.file} truncated ${qa.truncatedCells} overlong cells`);
      if (!qa.formulaInspection?.ndjson?.includes("No records matched")) throw new Error(`${batch.file} contains formulas or formula inspection failed`);
      batchQa.push(qa);
      partPaths.push(partPath);
    }
    const rowCount = batchQa.reduce((total, item) => total + item.rowCount, 0);
    if (rowCount !== manifest.row_count) throw new Error(`workbook row count ${rowCount} != ${manifest.row_count}`);
    const merged = await mergeWorkbooks(partPaths, outputPath, manifest.table_count);
    if (previewDir) {
      await fsp.mkdir(previewDir, { recursive: true });
      await fsp.writeFile(path.join(previewDir, "qa.json"), `${JSON.stringify({
        previews: batchQa.flatMap((item) => item.previews),
        formulaInspections: batchQa.map((item) => item.formulaInspection),
        rowCount,
        tableCount: manifest.table_count,
        merged,
      }, null, 2)}\n`, "utf8");
    }
    process.stdout.write(`${JSON.stringify({ outputPath, batches: manifest.batches.length, rowCount, tableCount: manifest.table_count, merged })}\n`);
    complete = true;
  } finally {
    if (complete) await fsp.rm(partsDir, { recursive: true, force: true });
    else process.stderr.write(`kept failed workbook segments at ${partsDir}\n`);
  }
}

async function mergeExisting(partsDir, outputPath, expectedSheets, previewDir) {
  const partPaths = (await fsp.readdir(partsDir))
    .filter((name) => /^part_\d+\.xlsx$/.test(name))
    .sort()
    .map((name) => path.join(partsDir, name));
  const batchQa = await Promise.all(partPaths.map((partPath) => fsp.readFile(`${partPath}.qa.json`, "utf8").then(JSON.parse)));
  if (batchQa.some((qa) => qa.truncatedCells)) throw new Error("a retained workbook segment contains truncated cells");
  if (batchQa.some((qa) => !qa.formulaInspection?.ndjson?.includes("No records matched"))) throw new Error("a retained workbook segment contains formulas or failed inspection");
  const rowCount = batchQa.reduce((total, qa) => total + qa.rowCount, 0);
  const merged = await mergeWorkbooks(partPaths, outputPath, expectedSheets);
  if (previewDir) {
    const previewFiles = (await fsp.readdir(previewDir)).filter((name) => name.endsWith(".png")).sort();
    if (previewFiles.length !== expectedSheets) throw new Error(`preview count ${previewFiles.length} != ${expectedSheets}`);
    await fsp.writeFile(path.join(previewDir, "qa.json"), `${JSON.stringify({
      previewFiles,
      formulaInspections: batchQa.map((qa) => qa.formulaInspection),
      rowCount,
      tableCount: expectedSheets,
      merged,
    }, null, 2)}\n`, "utf8");
  }
  await fsp.rm(partsDir, { recursive: true, force: true });
  process.stdout.write(`${JSON.stringify({ outputPath, batches: partPaths.length, rowCount, tableCount: expectedSheets, merged })}\n`);
}

async function writeWorkbookSlice(sourceBytes, outputPath, startIndex, endIndex) {
  const zip = await JSZip.loadAsync(sourceBytes);
  let workbookXml = await readZipText(zip, "xl/workbook.xml");
  let workbookRels = await readZipText(zip, "xl/_rels/workbook.xml.rels");
  let contentTypes = await readZipText(zip, "[Content_Types].xml");
  const allSheets = xmlElements(workbookXml, "x:sheet");
  const selectedSheets = allSheets.slice(startIndex, endIndex);
  const relationshipElements = xmlElements(workbookRels, "Relationship");
  const relationshipById = new Map(relationshipElements.map((element) => [attribute(element, "Id"), element]));
  const selectedWorksheetParts = new Set();
  const selectedWorksheetRelParts = new Set();
  const selectedTableParts = new Set();

  const renumberedSheets = [];
  const selectedWorksheetRelationships = [];
  for (const [index, sheetTag] of selectedSheets.entries()) {
    const relationship = relationshipById.get(attribute(sheetTag, "r:id"));
    if (!relationship) throw new Error(`missing slice worksheet relationship for ${sheetTag}`);
    const worksheetPart = resolveRelationshipPart("xl/workbook.xml", attribute(relationship, "Target"));
    const worksheetRelPart = relationshipPart(worksheetPart);
    selectedWorksheetParts.add(worksheetPart);
    selectedWorksheetRelationships.push(relationship);
    if (zip.file(worksheetRelPart)) {
      selectedWorksheetRelParts.add(worksheetRelPart);
      const sheetRels = await readZipText(zip, worksheetRelPart);
      for (const tableRelationship of xmlElements(sheetRels, "Relationship").filter((element) => attribute(element, "Type").endsWith("/table"))) {
        selectedTableParts.add(resolveRelationshipPart(worksheetPart, attribute(tableRelationship, "Target")));
      }
    }
    renumberedSheets.push(sheetTag.replace(/\bsheetId="[^"]*"/, `sheetId="${index + 1}"`));
  }

  workbookXml = workbookXml.replace(/<x:sheets>[\s\S]*?<\/x:sheets>/, `<x:sheets>${renumberedSheets.join("")}</x:sheets>`);
  const nonWorksheetRelationships = relationshipElements.filter((element) => !attribute(element, "Type").endsWith("/worksheet"));
  workbookRels = workbookRels.replace(
    /<Relationships\b[^>]*>[\s\S]*?<\/Relationships>/,
    `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${nonWorksheetRelationships.concat(selectedWorksheetRelationships).join("")}</Relationships>`,
  );
  const overrides = xmlElements(contentTypes, "Override");
  const retainedOverrides = overrides.filter((element) => {
    const part = attribute(element, "PartName").replace(/^\//, "");
    if (/^xl\/worksheets\/sheet\d+\.xml$/.test(part)) return selectedWorksheetParts.has(part);
    if (/^xl\/tables\/table\d+\.xml$/.test(part)) return selectedTableParts.has(part);
    return true;
  });
  const defaults = xmlElements(contentTypes, "Default");
  contentTypes = `<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">${defaults.concat(retainedOverrides).join("")}</Types>`;

  for (const name of Object.keys(zip.files)) {
    if (/^xl\/worksheets\/sheet\d+\.xml$/.test(name) && !selectedWorksheetParts.has(name)) zip.remove(name);
    if (/^xl\/worksheets\/_rels\/sheet\d+\.xml\.rels$/.test(name) && !selectedWorksheetRelParts.has(name)) zip.remove(name);
    if (/^xl\/tables\/table\d+\.xml$/.test(name) && !selectedTableParts.has(name)) zip.remove(name);
  }
  zip.file("xl/workbook.xml", workbookXml);
  zip.file("xl/_rels/workbook.xml.rels", workbookRels);
  zip.file("[Content_Types].xml", contentTypes);
  const output = await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE", compressionOptions: { level: 6 }, streamFiles: true });
  await fsp.writeFile(outputPath, output);
  return { sheetCount: selectedSheets.length, tableCount: selectedTableParts.size };
}

async function splitExisting(inputPath, firstOutput, secondOutput, splitAfter) {
  const sourceBytes = await fsp.readFile(inputPath);
  const zip = await JSZip.loadAsync(sourceBytes);
  const sheetCount = xmlElements(await readZipText(zip, "xl/workbook.xml"), "x:sheet").length;
  if (!Number.isInteger(splitAfter) || splitAfter < 1 || splitAfter >= sheetCount) throw new Error(`invalid split point ${splitAfter} for ${sheetCount} sheets`);
  const first = await writeWorkbookSlice(sourceBytes, firstOutput, 0, splitAfter);
  const second = await writeWorkbookSlice(sourceBytes, secondOutput, splitAfter, sheetCount);
  process.stdout.write(`${JSON.stringify({ inputPath, splitAfter, firstOutput, first, secondOutput, second })}\n`);
}

const args = process.argv.slice(2);
if (args[0] === "--batch") {
  if (!args[1] || !args[2]) throw new Error("usage: --batch payload.json output.xlsx [preview-dir]");
  await buildBatch(args[1], args[2], args[3]);
} else if (args[0] === "--merge-parts") {
  if (!args[1] || !args[2] || !args[3]) throw new Error("usage: --merge-parts parts-directory output.xlsx expected-sheets [preview-dir]");
  await mergeExisting(args[1], args[2], Number(args[3]), args[4]);
} else if (args[0] === "--split-existing") {
  if (!args[1] || !args[2] || !args[3] || !args[4]) throw new Error("usage: --split-existing input.xlsx first.xlsx second.xlsx split-after-sheet");
  await splitExisting(args[1], args[2], args[3], Number(args[4]));
} else {
  if (!args[0] || !args[1]) throw new Error("usage: payload-directory output.xlsx [preview-dir]");
  await main(args[0], args[1], args[2]);
}
