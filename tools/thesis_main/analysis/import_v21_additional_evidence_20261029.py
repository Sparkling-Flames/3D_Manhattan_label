"""独立归档 v2.1 阶段03/05十包；保留来源版本，不执行研究代码。"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import csv
import difflib
import io
import json
from pathlib import Path
import re
import stat
import zipfile


ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / 'research/workers/personnel_v21_reselection_20261029'
DESTINATION = ARCHIVE / 'additional_delivery'
STAGES = ('03A', '03B_core', '03B_01', '03B_02', '03B_03', '03B_04',
          '03B_05', '03C', '05A', '05B')
CHUNK = 1024 * 1024
MAP_FIELDS = ('stage', 'source_zip', 'member_path', 'archive_relative_path', 'bytes',
              'existing_primary_relation')
COMPARE_FIELDS = ('member_path', 'left_path', 'right_path', 'comparison',
                  'left_bytes', 'right_bytes', 'first_different_byte')


def safe_destination(root: Path, member: str) -> Path:
    parts = member.split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {
        f'{prefix}{i}' for prefix in ('COM', 'LPT') for i in range(1, 10)}
    if (any(c in member for c in '\\:<>"|?*') or any(
            p in ('', '.', '..') or p.endswith((' ', '.')) or '\x00' in p
            or p.split('.')[0].upper() in reserved for p in parts)):
        raise ValueError(f'unsafe_package_path: {member}')
    target = root.joinpath(*parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'package_path_escapes_destination: {member}')
    return target


def streams_equal(left, right) -> tuple[bool, int | None]:
    offset = 0
    first = None
    while True:
        a, b = left.read(CHUNK), right.read(CHUNK)
        if first is None and a != b:
            first = offset + next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                                  min(len(a), len(b)))
        if not a and not b:
            return first is None, first
        offset += max(len(a), len(b))


def csv_bytes(rows: list[dict], fields: tuple[str, ...]) -> bytes:
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


def import_packages(packages: dict[str, Path], destination: Path,
                    existing_archive: Path | None = None, progress=None) -> dict:
    entries = []
    source_counts = []
    with ExitStack() as stack:
        for stage, package in packages.items():
            if not re.fullmatch(r'[A-Za-z0-9_]+', stage):
                raise ValueError(f'unsafe_stage: {stage}')
            archive = stack.enter_context(zipfile.ZipFile(package))
            infos = archive.infolist()
            seen = set()
            for info in infos:
                member = info.filename.rstrip('/') if info.is_dir() else info.filename
                target = safe_destination(destination, f'packages/{stage}/{member}')
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise ValueError(f'package_symlink: {info.filename}')
                key = member.casefold()
                if key in seen:
                    raise ValueError(f'duplicate_package_path: {info.filename}')
                seen.add(key)
                if info.is_dir():
                    continue
                if target.exists():
                    if not target.is_file():
                        raise ValueError(f'existing_content_differs: {target}')
                    with archive.open(info) as src, target.open('rb') as dst:
                        same, _ = streams_equal(src, dst)
                    if not same:
                        raise ValueError(f'existing_content_differs: {target}')
                entries.append((stage, package, archive, info, target))
            source_counts.append({'stage': stage, 'path': str(package),
                                  'entries': len(infos),
                                  'files': sum(not i.is_dir() for i in infos),
                                  'zip_bytes': package.stat().st_size,
                                  'expanded_bytes': sum(i.file_size for i in infos)})

        completed_stage = None
        for stage, _, archive, info, target in entries:
            if stage != completed_stage and completed_stage is not None and progress:
                progress(completed_stage)
            completed_stage = stage
            if target.exists():
                continue  # Already read to EOF and compared during preflight.
            target.parent.mkdir(parents=True, exist_ok=True)
            created = False
            try:
                with target.open('xb') as dst:
                    created = True
                    with archive.open(info) as src:
                        while block := src.read(CHUNK):
                            dst.write(block)
            except Exception:
                # Only remove this call's incomplete new file, never an existing file.
                if created:
                    target.unlink()
                raise
        if completed_stage is not None and progress:
            progress(completed_stage)

    comparisons = []
    mapping = []
    first_sources = {}
    differences = []
    for stage, package, _, info, target in entries:
        primary_relation = 'absent'
        candidates = []
        if existing_archive is not None:
            primary = safe_destination(existing_archive, info.filename)
            if primary.exists():
                if not primary.is_file():
                    raise ValueError(f'existing_primary_not_file: {primary}')
                candidates.append(('existing_primary', primary))
        key = info.filename.casefold()
        if key in first_sources:
            candidates.append(('earlier_new_package', first_sources[key]))
        else:
            first_sources[key] = target
        for kind, other in candidates:
            with other.open('rb') as left, target.open('rb') as right:
                same, first = streams_equal(left, right)
            relation = 'identical' if same else 'different'
            if kind == 'existing_primary':
                primary_relation = relation
            comparisons.append(dict(zip(COMPARE_FIELDS, (
                info.filename, str(other), str(target), relation,
                other.stat().st_size, info.file_size, '' if first is None else first))))
            if not same:
                differences.append(f'## {stage}: `{info.filename}`\n\n'
                                   f'- 保留左侧：`{other}`\n- 新来源：`{target}`\n'
                                   f'- 首个不同字节：{first}；双方内容分别保存。\n')
                if target.suffix == '.py':
                    diff = list(difflib.unified_diff(
                        other.read_text(encoding='utf-8-sig').splitlines(),
                        target.read_text(encoding='utf-8-sig').splitlines(),
                        fromfile='existing', tofile=stage, n=2))
                    differences.append('```diff\n' + '\n'.join(diff[:100]) + '\n```\n'
                                       + ('差异超过100行，仅展示前100行。\n' if len(diff) > 100 else ''))
        mapping.append(dict(zip(MAP_FIELDS, (
            stage, package.name, info.filename, target.relative_to(destination).as_posix(),
            info.file_size, primary_relation))))

    receipt = {
        'data_release': 'v2.1', 'source_packages': source_counts,
        'source_file_entries': len(entries), 'preserved_file_versions': len(entries),
        'distinct_member_paths': len(first_sources),
        'expanded_bytes': sum(i.file_size for _, _, _, i, _ in entries),
        'all_zip_files_read_to_eof_crc_checked': True,
        'overlapping_path_comparisons': len(comparisons),
        'identical_comparisons': sum(r['comparison'] == 'identical' for r in comparisons),
        'different_comparisons': sum(r['comparison'] == 'different' for r in comparisons),
        'primary_archive_overwritten': False, 'source_zip_changed': False,
        'source_content_transformed': False, 'sha_calculated': False,
        'new_fusion_runs': 0, 'new_strategy_runs': 0, 'new_same_room_abc_runs': 0,
        'execution_code_policy': 'Existing 07A-priority code and prior object-ID repairs remain unchanged. '
                                 'All additional code is archived source, not an execution override.',
        'validation_boundary': 'All ZIP entries fully read with ZIP CRC and exact bytes preserved; '
                               'this import does not validate research formulas or CSV semantics.',
        'path_map': 'PATH_MAP.csv', 'path_comparisons': 'PATH_COMPARISONS.csv',
        'difference_notes': 'CONFLICTS.md',
    }
    reports = {
        'IMPORT_RECEIPT.json': (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'),
        'PATH_MAP.csv': csv_bytes(mapping, MAP_FIELDS),
        'PATH_COMPARISONS.csv': csv_bytes(comparisons, COMPARE_FIELDS),
        'CONFLICTS.md': ('# 同名文件差异\n\n逐字节比较，不计算额外哈希。'
                         '新包按来源目录分别保存，差异不触发覆盖。\n\n'
                         + ('\n'.join(differences) if differences else '未发现内容不同的重名文件。\n')).encode('utf-8'),
        'README.md': ('# v2.1 新增十包来源归档\n\n'
                      '阶段03A、03B核心及01—05、03C、05A、05B按包分别存入 `packages/<stage>/`，'
                      '其下保持包内原相对路径。读取方式见 `PATH_MAP.csv`。\n\n'
                      '既有五包、07A优先代码及对象ID修复不变；新包代码只是来源，未执行或替换。'
                      '源ZIP与所有大文件均保留，无上传、哈希、新策略、新同房ABC或新融合。\n\n'
                      f'完整读取{len(entries)}个文件条目并通过ZIP CRC；'
                      f'{len(comparisons)}次同名比较中，'
                      f'{receipt["different_comparisons"]}次字节不同，详见 `CONFLICTS.md`。'
                      '这项检查验证归档读取与字节保存，不替代统计复核。\n').encode('utf-8'),
    }
    for name, content in reports.items():
        path = destination / name
        if path.exists() and path.read_bytes() != content:
            raise ValueError(f'existing_report_differs: {path}')
    for name, content in reports.items():
        path = destination / name
        if not path.exists():
            path.write_bytes(content)
    return receipt


def discover_packages(downloads: Path) -> dict[str, Path]:
    packages = {}
    for stage in STAGES:
        part, _, suffix = stage.partition('_')
        token = '核心与端点' if suffix == 'core' else suffix
        matches = [p for p in downloads.glob(f'HOHONET_v21_阶段{part}_*20261029.zip')
                   if not token or f'_{token}_' in p.name]
        if len(matches) != 1:
            raise ValueError(f'expected_one_package: {stage}: {matches}')
        packages[stage] = matches[0]
    return packages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--downloads', type=Path, default=Path.home() / 'Downloads')
    args = parser.parse_args()
    receipt = import_packages(discover_packages(args.downloads), DESTINATION, ARCHIVE,
                              progress=lambda stage: print(f'ARCHIVED {stage}', flush=True))
    print(json.dumps({'files': receipt['source_file_entries'],
                      'different_comparisons': receipt['different_comparisons'],
                      'receipt': str(DESTINATION / 'IMPORT_RECEIPT.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
