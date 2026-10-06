"""复用候选图片审查台样式，为既定8图生成难度补标页。"""
import ast
import json

from .difficulty_consensus_20261006 import OUT, REVIEW
from .lee_tile_stage1_20261002 import ROOT
from .worker_count_composition_20261006 import read_csv


def build():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    images = {r['image_code']: r for r in load_current_bundle()['research']['images']}
    roster = {r['image']: r for r in read_csv(OUT/'difficulty_roster.csv')}
    rows = []
    for code in REVIEW:
        r = images[code]
        label = ROOT / r['references']['gt_original'].split(':', 2)[2]
        photo = label.parent.parent/'img'/f"{r['image_id']}.png"
        assert photo.is_file(), photo
        rows.append(dict(image_code=code, image_id=r['image_id'],
                         manual_n=int(roster[code]['manual_n']),
                         src='../../'+photo.relative_to(ROOT).as_posix()))
    # 只读取旧模板，不导入会重建历史页面的旧脚本。
    source = ROOT/'tools/thesis_main/analysis/build_candidate_review_20260912.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    template = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id=='template' for t in n.targets))
    style = template.split('<style>', 1)[1].split('</style>', 1)[0]
    page = (ROOT/'tools/thesis_main/analysis/difficulty_review_20261006.html').read_text(encoding='utf-8')
    data = dict(schema='difficulty_review_20261006_v1', images=rows)
    page = page.replace('/*__STYLE__*/', style).replace('/*__DATA__*/',
                json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))
    (OUT/'index.html').write_text(page, encoding='utf-8')
    print(OUT/'index.html')


if __name__ == '__main__':
    build()
