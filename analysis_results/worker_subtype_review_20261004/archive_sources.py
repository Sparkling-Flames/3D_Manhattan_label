"""精选归档两份外部返回；保留原字节，避免再次复制完整作者包和复跑副本。"""
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'research/worker_subtype_returns_20261004'
PRO = Path('C:/Users/ASUS/Downloads/worker_subtype_research_20261004_delivery/worker_subtype_research_20261004')
DOT = Path('C:/Users/ASUS/Downloads/full_layout_and_worker_independent_review_20261004/full_layout_and_worker_independent_review_20261004')


def main():
    copied, omitted = [], []
    for origin, source in [('pro', PRO), ('dot', DOT)]:
        for path in sorted(source.rglob('*')):
            if not path.is_file():
                continue
            rel = path.relative_to(source); parts = rel.parts
            reason = None; equivalent = None
            if any(p in {'__pycache__', '.pytest_cache'} for p in parts):
                reason = '运行缓存'
            elif origin == 'pro' and rel.as_posix() == 'REPORT_ZH.html':
                reason = '同报告的内嵌图HTML；保留Markdown及独立图'
            elif origin == 'dot':
                if parts[:2] == ('personnel_repro_audit_20261004', 'author_bundle'):
                    equivalent = PRO/Path(*parts[2:])
                    if equivalent.is_file() and equivalent.read_bytes() == path.read_bytes():
                        reason = '与本归档pro目录逐字节相同的作者包副本'
                    else:
                        equivalent = None  # 不相同的版本仍按原路径保留。
                elif parts[:2] == ('personnel_inference', 'clean_replay'):
                    equivalent = DOT/'personnel_inference/results'/Path(*parts[2:])
                    if equivalent.is_file() and equivalent.read_bytes() == path.read_bytes():
                        reason = '与已保留results逐字节相同的复跑副本'
                    else:
                        equivalent = None
                elif parts[0] == 'oct4-layout-reproduction' and len(parts) > 1 and parts[1] in {'source', 'replay', 'pinned_pilot', 'pinned_schedule'}:
                    reason = '旧完整布局作者包及重复运行树；保留本轮独立核验摘要、脚本和日志，原型另见既有full_layout_pro_review归档'
                elif parts[0] == 'source_docs':
                    reason = '旧仓库文档摘录；版本位置在外部报告保留，当前以本地研究台账为准'
            if reason:
                omitted.append(dict(source=str(path), relative=origin+'/'+rel.as_posix(),
                    reason=reason, identical_to=str(equivalent) if equivalent else None))
                continue
            target = OUT/origin/rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != path.read_bytes():
                raise ValueError('refuse_overwrite_changed_archive:' + str(target))
            shutil.copyfile(path, target)
            assert target.read_bytes() == path.read_bytes()
            copied.append(dict(path=target.relative_to(OUT).as_posix(), bytes=target.stat().st_size,
                source=str(path), identical_to_source=True))
    manifest = dict(schema='selected_external_returns_20261004_v1',
        rule='外部原件按字节保留；声明、代码与结果不自动成为本地已验证结论。复现入口及删重后路径见README。',
        copied=copied, omitted=omitted, copied_bytes=sum(r['bytes'] for r in copied))
    (OUT/'ARCHIVE.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(copied=len(copied), omitted=len(omitted), copied_bytes=manifest['copied_bytes'])))


if __name__ == '__main__':
    main()
