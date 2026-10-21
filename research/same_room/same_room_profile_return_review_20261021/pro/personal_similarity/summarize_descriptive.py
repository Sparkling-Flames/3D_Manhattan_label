"""Compact interpretable summaries of the newly computed direct-person evidence."""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

def wcorr(a, b, w):
    a, b, w = (np.asarray(a), np.asarray(b), np.asarray(w))
    ok = np.isfinite(a) & np.isfinite(b) & np.isfinite(w)
    a, b, w = (a[ok], b[ok], w[ok])
    w = w / w.sum()
    a = a - np.sum(w * a)
    b = b - np.sum(w * b)
    return np.sum(w * a * b) / np.sqrt(np.sum(w * a * a) * np.sum(w * b * b))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path(__file__).parent)
    args = ap.parse_args()
    out = args.out
    x = _read_csv(out / 'direct_pair_workers.csv.gz')
    p = _read_csv(out / 'direct_pair_similarity.csv')
    labs = _read_csv(args.repo / 'research/workers/personnel_taxonomy_20261021/labels/lobo_labels.csv')
    x = x.merge(labs[['worker_id', 'condition', 'heldout_building', 'label_version', 'primary_coarse_class', 'primary_fine_class', 'primary_fine_name_zh']], left_on=['worker_id', 'condition', 'building'], right_on=['worker_id', 'condition', 'heldout_building'], how='left', validate='many_to_one')
    _write_csv(x, out / 'direct_pair_workers_with_class.csv.gz', index=False, float_format='%.8g')
    rows = []
    transitions = []
    classrows = []
    for (condition, layer, scope), s in x.groupby(['condition', 'layer', 'scope_comparable']):
        s = s[~s.substantive_conflict].copy()
        if s.empty:
            continue
        npair = s.groupby('building').pair_id.transform('nunique')
        nworker = s.groupby('pair_id').worker_id.transform('size')
        w = 1 / (npair * nworker * s.building.nunique())
        pp = p[p.pair_id.isin(s.pair_id) & p.condition.eq(condition) & p.layer.eq(layer)]
        means = pp.groupby('building')[['Q_pearson', 'rank_rho', 'surprise_pearson', 'same_relative_sign', 'same_surprise_sign', 'relative_sign_chance', 'person_abs_gap', 'relative_abs_gap']].mean().mean()
        base = dict(condition=condition, layer=layer, scope_comparable=scope, n_pairs=s.pair_id.nunique(), n_images=len(set(s.image_a) | set(s.image_b)), n_workers=s.worker_id.nunique(), n_person_pairs=len(s), n_buildings=s.building.nunique())
        outrow = dict(**base, **means.to_dict())
        for prefix in ['Q', 'relative', 'common_relative', 'surprise']:
            outrow['symmetric_weighted_corr_' + prefix] = wcorr(np.r_[s[prefix + '_a'], s[prefix + '_b']], np.r_[s[prefix + '_b'], s[prefix + '_a']], np.r_[w, w]) if s[prefix + '_a'].notna().any() else np.nan
        rows.append(outrow)
        a = pd.DataFrame({'source': s.Q_a.to_numpy(), 'target': s.Q_b.to_numpy(), 'weight': w.to_numpy()})
        b = pd.DataFrame({'source': s.Q_b.to_numpy(), 'target': s.Q_a.to_numpy(), 'weight': w.to_numpy()})
        v = pd.concat([a, b])
        bins = [('Q<50', v.source < 50), ('50<=Q<80', v.source.ge(50) & v.source.lt(80)), ('80<=Q<90', v.source.ge(80) & v.source.lt(90)), ('Q>=90', v.source.ge(90))]
        for name, mask in bins:
            z = v[mask]
            den = z.weight.sum()
            transitions.append(dict(**base, source_quality_bin=name, directed_observations=len(z), target_low_observations=int((z.target < 50).sum()), target_low_rate=float(np.sum(z.weight * (z.target < 50)) / den) if den > 0 else np.nan, target_mean=float(np.sum(z.weight * z.target) / den) if den > 0 else np.nan, weight_mass=float(den / 2)))
        if condition == 'manual' and layer == 'ordinary' and scope:
            for cls, c in s.groupby('primary_fine_class'):
                z = c.assign(abs_gap=abs(c.Q_a - c.Q_b), rel_gap=abs(c.relative_a - c.relative_b), same_sign=(c.relative_a >= 0) == (c.relative_b >= 0), same_surprise=np.where(c.surprise_a.notna() & c.surprise_b.notna(), (c.surprise_a >= 0) == (c.surprise_b >= 0), np.nan))
                ss = z.groupby('building')[['abs_gap', 'rel_gap', 'same_sign', 'same_surprise', 'external_theta']].mean().mean()
                classrows.append(dict(primary_fine_class=cls, n_workers=c.worker_id.nunique(), n_buildings=c.building.nunique(), n_person_pairs=len(c), **ss.to_dict()))
    res = pd.DataFrame(rows)
    _write_csv(res, out / 'information_decomposition_summary.csv', index=False)
    _write_csv(pd.DataFrame(transitions), out / 'low_quality_transitions.csv', index=False)
    _write_csv(pd.DataFrame(classrows), out / 'class_repetition_summary.csv', index=False)
    pp = p[(p.condition == 'manual') & (p.layer == 'ordinary') & p.scope_comparable & ~p.substantive_conflict].copy()
    _write_csv(pp.groupby('building').agg(n_pairs=('pair_id', 'size'), rho=('rank_rho', 'mean'), Q_pearson=('Q_pearson', 'mean'), remaining_pearson=('surprise_pearson', 'mean'), same_sign=('same_relative_sign', 'mean'), remaining_same_sign=('same_surprise_sign', 'mean')).reset_index(), out / 'personal_similarity_by_building.csv', index=False)
    font = out.parent / 'NotoSansCJKsc-Regular.otf'
    if _data_exists(font):
        font_manager.fontManager.addfont(str(font))
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(font)).get_name()
    r = res[(res.condition == 'manual') & (res.layer == 'ordinary') & res.scope_comparable].iloc[0]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7), constrained_layout=True)
    vals = [r.symmetric_weighted_corr_Q, r.symmetric_weighted_corr_relative, r.symmetric_weighted_corr_surprise]
    axes[0].bar(['绝对 Q', '减去同图同行水平', '再减去楼外个人水平'], vals, color=['#256b87', '#5b9e9a', '#bc7785'])
    for k, v in enumerate(vals):
        axes[0].text(k, v + 0.015, f'{v:.3f}', ha='center')
    axes[0].set_ylim(0, 0.75)
    axes[0].set_ylabel('对称加权相关')
    axes[0].set_title('同一人的跨视角关联来自哪里？')
    vals2 = [r.same_relative_sign, r.relative_sign_chance, r.same_surprise_sign]
    axes[1].bar(['相对同行好／差同号', '按同行正负比例的基准', '扣除楼外个人水平后同号'], vals2, color=['#256b87', '#bcbcbc', '#bc7785'])
    for k, v in enumerate(vals2):
        axes[1].text(k, v + 0.012, f'{v:.1%}', ha='center')
    axes[1].set_ylim(0, 0.8)
    axes[1].set_ylabel('比例')
    axes[1].set_title('重复的相对表现主要是稳定人员差异')
    for ax in axes:
        ax.tick_params(axis='x', labelsize=9)
        ax.grid(axis='y', alpha=0.18)
        ax.set_axisbelow(True)
    fig.suptitle('普通 Manual：123 个直接图对，64 图，57 人，12 栋建筑', fontsize=13)
    fig.savefig(out / 'personal_information_decomposition_zh.png', dpi=180)
    plt.close(fig)
    print(res.to_string(index=False))
if __name__ == '__main__':
    main()
