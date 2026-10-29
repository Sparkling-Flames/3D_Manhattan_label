"""Validate rendered PDF text against immutable REPORT_BLOCKS.

This is a read-only content-completeness check, not a visual layout approval.
It verifies every paragraph, heading, caption, table title and table cell.
Table cells and complete rows must also occur in order within their own table,
bounded by its title and evidence paragraph.  This catches missing repeated
values that a whole-document substring check would incorrectly accept.

No fuzzy comparison, numerical tolerance, character substitution, scientific
calculation, report edit, or rendering is performed.  A second extraction in
actual page-position order resolves PDF content-stream ordering of superscript
glyphs; both extracted texts and the exact affected block IDs are retained.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import csv
import hashlib
import json
import platform
import re
import time
import unicodedata
from pathlib import Path

import fitz


HEADER = 'HOHONETv2.1普通Manual人群模拟'
FOOTER = re.compile(r'\d{4}-\d{2}-\d{2}·\d+')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def norm(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(text))).replace('\u00ad', '').replace('\u200b', '')


def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.writing')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def csv_write(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def page_range(start, length, offsets):
    if start < 0:
        return []
    first = bisect.bisect_right(offsets, start)
    last = bisect.bisect_right(offsets, start + max(0, length - 1))
    return list(range(first, last + 1))


def extract(pdf_path):
    result = {'content_order': [], 'spatial_order': []}
    removed = []
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc):
            retained = []
            removed_this_page = collections.Counter()
            for block in page.get_text('blocks'):
                text = block[4]
                value = norm(text)
                reason = None
                if value == HEADER and block[1] < 60:
                    reason = 'exact_repeating_header'
                elif FOOTER.fullmatch(value) and block[1] > page.rect.height - 60:
                    reason = 'exact_date_and_page_footer'
                if reason:
                    removed.append({'page': page_index + 1, 'reason': reason,
                                    'text': text, 'bbox': list(block[:4])})
                    removed_this_page[reason] += 1
                else:
                    retained.append(text)
            if removed_this_page != {'exact_repeating_header': 1, 'exact_date_and_page_footer': 1}:
                raise ValueError(('unexpected_repeating_header_footer_count', page_index + 1, dict(removed_this_page)))
            result['content_order'].append(''.join(retained))
            # PyMuPDF reconstructs text order from glyph locations.  No string
            # replacements repair exponents or any other scientific content.
            lines = page.get_text('text', sort=True).splitlines()
            lines = [line for line in lines if norm(line) != HEADER and not FOOTER.fullmatch(norm(line))]
            result['spatial_order'].append('\n'.join(lines))
        pages = len(doc)
        metadata = doc.metadata
    streams = {}
    for name, page_texts in result.items():
        normalized_pages = [norm(text) for text in page_texts]
        offsets = []
        total = 0
        for text in normalized_pages:
            offsets.append(total)
            total += len(text)
        streams[name] = {'text': ''.join(normalized_pages), 'offsets': offsets,
                         'pages': page_texts, 'characters': total}
    return streams, removed, pages, metadata


def audit(pdf_path, blocks, output, prefix):
    initial_sha = sha(pdf_path)
    streams, removed, n_pages, metadata = extract(pdf_path)
    primary = streams['content_order']['text']
    spatial = streams['spatial_order']['text']
    checks, table_checks, row_checks, issues, fallback = [], [], [], [], []

    def verify_item(block, kind, text, **fields):
        value = norm(text)
        a, b = primary.find(value), spatial.find(value)
        method = 'content_order' if a >= 0 else 'spatial_order' if b >= 0 else None
        position = a if a >= 0 else b
        rec = {'block_index': block, 'kind': kind, **fields, 'text': str(text),
               'normalized_characters': len(value), 'content_order_match': a >= 0,
               'spatial_order_match': b >= 0, 'passed': method is not None,
               'accepted_extractor': method or '', 'normalized_match_offset': position,
               'pages': '|'.join(map(str, page_range(position, len(value), streams[method]['offsets']))) if method else ''}
        checks.append(rec)
        if method is None:
            issues.append({'kind': 'text_missing_from_both_extractions', 'block_index': block,
                           'item_kind': kind, **fields, 'text': str(text)})
        elif a < 0:
            fallback.append({'block_index': block, 'item_kind': kind, **fields,
                             'text': str(text), 'pages': rec['pages'],
                             'reason': 'Exact normalized text exists in page-position-ordered extraction; content-stream order differs.'})
        return rec

    for i, block in enumerate(blocks):
        kind = block['kind']
        if kind in ('p', 'h'):
            verify_item(i, kind, block['text'])
        elif kind == 'image':
            verify_item(i, 'image_caption', block['caption'])
        elif kind == 'table':
            title = norm(block['title'])
            verify_item(i, 'table_title', block['title'])
            start = primary.find(title)
            end_marker = norm('证据 [' + block['source'] + ']。完整精度与各指标分母保留在对应结果表。')
            end = primary.find(end_marker, start + len(title)) if start >= 0 else -1
            valid_scope = start >= 0 and end >= 0 and primary.count(title) == 1
            scoped = primary[start + len(title):end] if valid_scope else ''
            if not valid_scope:
                issues.append({'kind': 'table_scope_not_unique_or_incomplete', 'block_index': i,
                               'title': block['title'], 'title_occurrences': primary.count(title), 'end_found': end >= 0})
            cursor = 0
            row_cursor = 0
            missing_cells = 0
            missing_rows = 0
            rows = [block['headers']] + block['rows']
            for row_index, row in enumerate(rows):
                row_text = ''.join(norm(cell) for cell in row)
                row_start = scoped.find(row_text, row_cursor) if valid_scope else -1
                row_passed = row_start >= 0
                row_checks.append({'block_index': i, 'title': block['title'], 'row_index': row_index,
                                   'header_row': row_index == 0, 'column_count': len(row),
                                   'exact_contiguous_row_in_own_table_order': row_passed,
                                   'scope_offset': row_start})
                if row_passed:
                    row_cursor = row_start + len(row_text)
                else:
                    missing_rows += 1
                    issues.append({'kind': 'table_row_missing_or_reordered', 'block_index': i,
                                   'row_index': row_index, 'cells': row})
                for col_index, cell in enumerate(row):
                    rec = verify_item(i, 'table_cell', cell, row_index=row_index, column_index=col_index,
                                      title=block['title'])
                    value = norm(cell)
                    found = scoped.find(value, cursor) if valid_scope else -1
                    rec['own_table_ordered_match'] = found >= 0
                    rec['own_table_offset'] = found
                    if found >= 0:
                        cursor = found + len(value)
                    else:
                        rec['passed'] = False
                        missing_cells += 1
                        issues.append({'kind': 'cell_missing_from_own_table_or_reordered', 'block_index': i,
                                       'row_index': row_index, 'column_index': col_index, 'text': str(cell),
                                       'exists_elsewhere_in_document': rec['content_order_match'] or rec['spatial_order_match']})
            table_checks.append({'block_index': i, 'title': block['title'], 'source': block['source'],
                                 'headers': len(block['headers']), 'data_rows': len(block['rows']),
                                 'cells': sum(map(len, rows)), 'valid_unique_scope': valid_scope,
                                 'missing_or_out_of_order_cells': missing_cells,
                                 'missing_or_out_of_order_rows': missing_rows,
                                 'all_cells_and_rows_passed': valid_scope and not missing_cells and not missing_rows,
                                 'pages': '|'.join(map(str, page_range(start, max(0, end - start), streams['content_order']['offsets'])))})
        else:
            issues.append({'kind': 'unknown_report_block_kind', 'block_index': i, 'value': kind})
    final_sha = sha(pdf_path)
    if initial_sha != final_sha:
        issues.append({'kind': 'pdf_changed_during_validation', 'before_sha256': initial_sha, 'after_sha256': final_sha})
    output.mkdir(parents=True, exist_ok=True)
    for name, stream in streams.items():
        (output / f'{prefix}_{name.upper()}_EXTRACTED.txt').write_text(
            '\n\f\n'.join(stream['pages']), encoding='utf-8')
    csv_write(output / f'{prefix}_ITEM_CHECKS.csv', checks)
    csv_write(output / f'{prefix}_TABLE_CHECKS.csv', table_checks)
    csv_write(output / f'{prefix}_ROW_CHECKS.csv', row_checks)
    receipt = {'passed': not issues, 'pdf': str(pdf_path), 'pdf_sha256': initial_sha,
               'pdf_bytes': pdf_path.stat().st_size, 'pdf_pages': n_pages, 'pdf_metadata': metadata,
               'input_unchanged_during_validation': initial_sha == final_sha,
               'report_blocks': len(blocks), 'block_counts': dict(collections.Counter(b['kind'] for b in blocks)),
               'text_item_checks': len(checks), 'global_text_items_missing': sum(not (c['content_order_match'] or c['spatial_order_match']) for c in checks),
               'table_count': len(table_checks), 'table_cells': sum(t['cells'] for t in table_checks),
               'table_rows_including_headers': len(row_checks),
               'table_cells_missing_or_out_of_order_in_own_table': sum(t['missing_or_out_of_order_cells'] for t in table_checks),
               'table_rows_missing_or_out_of_order_in_own_table': sum(t['missing_or_out_of_order_rows'] for t in table_checks),
               'exact_page_position_order_fallbacks': fallback,
               'removed_repeating_header_footer_blocks': removed,
               'normalized_characters': {name: data['characters'] for name, data in streams.items()},
               'issues': issues}
    dump(output / f'{prefix}_DETAIL.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--pdf', type=Path)
    parser.add_argument('--baseline-pdf', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    report = root / 'stage08_report'
    output = args.output or report / 'verification'
    pdf = args.pdf or report / 'render_verified/HOHONET_v21_AC_population_report_ZH.pdf'
    blocks_path = report / 'REPORT_BLOCKS.json'
    initial_blocks_sha = sha(blocks_path)
    blocks = json.loads(blocks_path.read_text(encoding='utf-8-sig'))
    started = time.monotonic()
    result = audit(pdf, blocks, output, 'PDF_FINAL_TEXT')
    result.update(
        schema_version='1.0', validator_sha256=sha(Path(__file__)),
        python_version=platform.python_version(), pymupdf_version=fitz.VersionBind,
        report_blocks_sha256=initial_blocks_sha,
        normalization='Unicode NFKC, removal of whitespace, U+00AD soft hyphen and U+200B zero-width space; no fuzzy text or numeric equivalence.',
        table_validation='Exact global cell match, then exact monotonically ordered cell matches and contiguous row matches inside each unique table title/evidence boundary.',
        extraction='PyMuPDF content-stream text plus page-position-ordered text (sort=True); only exact recognized repeated header/footer removed.',
        scope_limitation='Text completeness only; this does not replace the separate visual review of page layout, clipping, figures and legibility.',
    )
    if args.baseline_pdf:
        baseline = audit(args.baseline_pdf, blocks, output, 'PDF_BEFORE_FIX_TEXT')
        result['before_fix_regression'] = {k: baseline[k] for k in [
            'passed', 'pdf', 'pdf_sha256', 'pdf_pages', 'global_text_items_missing',
            'table_cells_missing_or_out_of_order_in_own_table',
            'table_rows_missing_or_out_of_order_in_own_table', 'issues']}
    result['report_blocks_unchanged_during_validation'] = initial_blocks_sha == sha(blocks_path)
    if not result['report_blocks_unchanged_during_validation']:
        result['passed'] = False
        result['issues'].append({'kind': 'report_blocks_changed_during_validation'})
    result['elapsed_seconds'] = time.monotonic() - started
    dump(output / 'PDF_TEXT_COMPLETENESS_VALIDATION.json', result)
    print(json.dumps({k: result[k] for k in ['passed', 'pdf_pages', 'report_blocks', 'text_item_checks',
        'table_count', 'table_cells', 'table_rows_including_headers', 'global_text_items_missing',
        'table_cells_missing_or_out_of_order_in_own_table', 'elapsed_seconds']}, ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
