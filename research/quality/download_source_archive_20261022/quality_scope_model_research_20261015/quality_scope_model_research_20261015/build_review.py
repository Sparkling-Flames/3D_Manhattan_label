"""Build a self-contained, static diagnostic gallery from delivered results.
No new answers are collected or made to appear visually adjudicated.
"""
from pathlib import Path
import json,base64,html
import pandas as pd
ROOT=Path(__file__).resolve().parent
ROUTES={'new_corridor_family':'新走廊形底面兼容提示','new_near_stop_family':'新近停止面兼容提示','old_far_stop_family':'原远停止面兼容提示','mixed_stop_unresolved':'两端混合，暂不指定空间','unresolved_family':'空间族未决'}

def build():
    d=pd.read_csv(ROOT/'results/two_image_floor_updates_28.csv');geos={g['record_id']:g for g in json.loads((ROOT/'results/two_image_geometries.json').read_text())}
    esc=html.escape
    pieces=['''<!DOCTYPE html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HOHONET 两图底面诊断（28份存档）</title><style>body{max-width:1080px;margin:auto;padding:28px;font-family:system-ui,sans-serif;line-height:1.7}h1,h2,h3{line-height:1.35}article{border-top:1px solid;padding:24px 0}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{padding:8px;border-bottom:1px solid;text-align:left}code{overflow-wrap:anywhere}summary{cursor:pointer}p{margin:12px 0}.notice{border:2px solid;padding:16px}small{font-size:.9em}</style><h1>两图多空间底面诊断</h1><p class="notice"><strong>28份存档分析几何；不是当前36份的完整收尾。</strong>原图未取得，空间提示来自局部几何。虽然原I、D、Sb、Hm、Hc、3D IoU、WQ均已复算匹配，仍未核验当前对象数组。新增底面顶部未确认，所有新完整WQ／3D IoU为NA。下面F仅为完整WQ的上界，不能当得分使用。</p><p>原GT与新底面并列保留。分组不读取最终Q；没有按最高分挑参考。全部图按每张原图的统一坐标范围绘制，单位为相机高度。</p>''']
    for im,g in d.groupby('image_code'):
        pieces.append(f'<h2>{esc(im)}：{len(g)}份存档manual</h2>')
        for _,r in g.sort_values('record_id').iterrows():
            raw=(ROOT/f'figures/floor_{r.record_id}.png').read_bytes();url='data:image/png;base64,'+base64.b64encode(raw).decode()
            warn='分组对阈值较敏感；不可直接指定正式参考。' if r.routing_threshold_sensitivity_review_required else '提示仍须以当前坐标及原图核验；不授予正式资格。'
            interpretation=('未表达旧底面的侧向分支，但远端延伸仍超出两套参考。' if im.startswith('B6') else ('两个停止墙端点分别落在近／远解释一侧，不能只平均端点或按IoU取大者。' if r.route=='mixed_stop_unresolved' else '停止墙两端在几何上较接近同一候选族；其他墙段的偏差仍单独评价。'))
            pieces.append(f'<article id="{r.record_id}"><h3>{r.record_id} · {r.worker_id} · {esc(ROUTES[r.route])}</h3><p>{esc(interpretation)} {esc(warn)}</p><img src="{url}" alt="{esc(im)} {r.record_id} 底面图"><table><tr><th>项目</th><th>原参考</th><th>新底面</th></tr><tr><td>底面IoU</td><td>{r.old_IoU2D100:.4f}%</td><td>{r.new_IoU2D100:.4f}%</td></tr><tr><td>Sb</td><td>{r.old_Sb_deg:.4f}°</td><td>{r.new_Sb_deg:.4f}°</td></tr><tr><td>完整WQ</td><td>{r.prior_WQ_replayed:.4f}（仅历史重现）</td><td>NA</td></tr><tr><td>F：完整WQ保守上界</td><td>{r.old_floor_diagnostic:.4f}</td><td>{r.new_full_WQ_upper_bound:.4f}</td></tr></table><p>自身D={r.D_deg:.4f}°；公共底面覆盖={100*r.common_floor_recall:.2f}%；候选处于两套底面并集之外的面积比例={100*r.outside_both_area_fraction:.2f}%。这些差异不能全部归因于已确认的范围变化，也不能在缺少照片时自动解释为作答者错误。</p><details><summary>对象、参考与限制</summary><p>object_id：<code>{esc(r.object_id)}</code><br>image_id：<code>{esc(r.image_id)}</code><br>原参考：<code>{esc(r.reference_id)}</code><br>新底面：<code>{esc(r.new_floor_reference_id)}</code></p><p>condition=manual；旧环序确认={r.prior_ring_confirmed}；原留出={r.original_holdout}；人员限制={esc(str(r.personnel_barriers))}；场景限制={esc(str(r.context_barriers))}。</p><p>当前坐标数组核验=false；新完整参考ready=false；新授予正式资格=false。所有原始点与既有评价保留。</p></details></article>')
    pieces.append('<h2>下一步所需材料</h2><p>恢复已存在的当前36份作答对象和旧账本、两张原图；核对新闭合段顶界。B6重点x≈805.91及其到x≈836.91的新闭合段；Uw重点跨ERP接缝的x≈68.69与973.40。无需重新画底面。完整说明见REPORT_ZH.md。</p></html>')
    (ROOT/'REVIEW.html').write_text('\n'.join(pieces),encoding='utf-8')
if __name__=='__main__':build();print('Built REVIEW.html with 28 embedded figures')
