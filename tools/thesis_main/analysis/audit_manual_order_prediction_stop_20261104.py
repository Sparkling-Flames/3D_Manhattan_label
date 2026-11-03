"""Read-only code/identity audit of actual prediction, selection and stop inputs.

No statistics, selection decisions, regression fits, fusion or scores are run.
The full archived stopping prefix table is checked, including unchanged pools
outside the 1,534 endpoint scalar rows patched in the historical v2.1 update.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
BASE_COMMIT='ac395e703d1fef573d1ef3e105df0286d62a0468'
OUT=ROOT/'research/fusion/manual_order_impact_20261104/dependencies'
STUDY=ROOT/'research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030'
SCRIPTS=STUDY/'scripts'
UTILITY=STUDY/'stage05_selection_stop'
NODES=UTILITY/'inputs/research/same_room/same_room_multiview_20261020/replay_nodes.csv.gz'
RULE=UTILITY/'inputs/research/same_room/same_room_profile_return_review_20261021/pro/prior_integration/rebuild_stopping.py'


def team_key(pool_id,workers):
    payload=json.dumps(sorted(workers),sort_keys=True,separators=(',',':')).encode()
    return pool_id+'__'+hashlib.sha256(payload).hexdigest()[:20]


def relative(p):return str(p.relative_to(ROOT))
def link(p,label=None):return '['+(label or p.name)+']('+os.path.relpath(p,OUT).replace(os.sep,'/')+')'


def main():
    endpath=OUT.parent/'endpoints/ENDPOINT_SCORES.csv'
    ends=pd.read_csv(endpath)
    wanted=set(ends.team_key)
    assert len(ends)==len(wanted)==57
    tuples={(r.pool_id,tuple(sorted(r.member_workers.split('|')))) for r in ends.itertuples()}
    selfcheck=[]
    for r in ends.itertuples():
        rebuilt=team_key(r.pool_id,r.member_workers.split('|'))
        selfcheck.append(dict(team_key=r.team_key,pool_id=r.pool_id,member_workers=r.member_workers,
            rebuilt_team_key=rebuilt,passed=rebuilt==r.team_key))
    assert all(r['passed'] for r in selfcheck),'Team hash self-check failed'
    pd.DataFrame(selfcheck).to_csv(OUT/'INDIRECT_PREDICTION_STOP_TEAM_KEY_SELF_CHECK.csv',index=False)
    contractpath=UTILITY/'design/STOPPING_CONTRACT.json';contract=json.loads(contractpath.read_text())
    rows=0;legal=0;teamsets=set();pools=set();groups=set();hash_hits=[];tuple_hits=[];patch_rows=0
    cols=['pool_id','member_workers','k','request_id','reference_id','reference_version','group_id']
    for chunk in pd.read_csv(NODES,usecols=cols,chunksize=25000):
        rows+=len(chunk);legal+=int(chunk.k.ne(2).sum())
        patch_rows+=int((chunk.pool_id.isin(contract['affected_pools'])&chunk.k.ne(2)).sum())
        for r in chunk.itertuples():
            ident=(r.pool_id,tuple(sorted(r.member_workers.split('|'))));teamsets.add(ident)
            pools.add(r.pool_id);groups.add(r.group_id)
            key=team_key(*ident)
            record=dict(request_id=r.request_id,pool_id=r.pool_id,team_key=key,k=r.k,
                reference_id=r.reference_id,reference_version=r.reference_version)
            if key in wanted:hash_hits.append(record)
            if ident in tuples:tuple_hits.append(record)
    assert rows==contract['original_nodes']==124924
    assert len(pools)==contract['original_unique_images']==43
    assert len(groups)==contract['original_groups_with_results']==20
    assert not hash_hits and not tuple_hits,'New actual stopping input dependency requires targeted propagation'
    pd.DataFrame(hash_hits,columns=['request_id','pool_id','team_key','k','reference_id','reference_version']).to_csv(
        OUT/'INDIRECT_PREDICTION_STOP_MATCHES.csv',index=False)
    # Read all actual selection outcome rows and all historically patched stop
    # endpoints. A zero on the complete table covers every later relation subset.
    tables={
      'same_room_Q_QT_selected_outcomes':UTILITY/'selection/POLICY_EVENT_RESULTS.csv.gz',
      'historical_stop_reference_patch_endpoints':UTILITY/'endpoints/STOPPING_SCALARS.csv.gz',
      'same_room_finite_panel_team_links':ROOT/'research/data/releases/v2.1/same_room_current_extended_design/PANEL_TEAM_LINKS.csv.gz'}
    counts={}
    for name,path in tables.items():
        header=pd.read_csv(path,nrows=0).columns
        keys=[c for c in header if c=='team_key' or c.endswith('_team_key') or c.startswith('team_key_')]
        assert keys,(name,'no canonical keys')
        n=0;hits=0;unique=set()
        for d in pd.read_csv(path,usecols=keys,chunksize=25000):
            n+=len(d)
            for c in keys:
                hits+=int(d[c].isin(wanted).sum());unique.update(d[c].dropna())
        assert hits==0,(name,hits)
        counts[name]=dict(path=relative(path),rows=n,unique_endpoint_keys=len(unique),columns=keys,matched_references=hits)
    source_names=['same_room_prediction.py','selection_stop_prepare.py','selection_stop_analyze.py','selection_stop_finalize.py','selection_stop_report.py']
    code={n:(SCRIPTS/n).read_text() for n in source_names}
    assert "histories(q,metric)" in code['same_room_prediction.py']
    assert "q[q.condition.eq(c)&q.layer.eq('ordinary')&q.training_allowed&~q.building.eq(b)]" in code['same_room_prediction.py']
    assert "OUT/'selection/POLICY_EVENT_RESULTS.csv.gz'" in code['selection_stop_finalize.py']
    assert "original=pd.read_csv(INP/REPLAY/'replay_nodes.csv.gz'" in code['selection_stop_analyze.py']
    # Explicit code-review rows document source-to-consumer edges. Empty exact
    # team fields mean original-response identities, not a fake zero team join.
    rows_audit=[]
    def add(id,consumer,script,functions,inputs,gate,identity,source_rows,teams,hits,decision,evidence):
        rows_audit.append(dict(id=id,consumer=consumer,consumer_code=relative(script),functions=functions,
            actual_input_paths=inputs,filters_and_features=gate,identity_kind=identity,source_rows=source_rows,
            unique_teams=teams,exact_57_overlap=hits,half_same_room_AC_summary_read=False,
            requires_recalculation=False,decision=decision,evidence=evidence))
    root_source=relative(STUDY/'source')+'/'
    add('PRED_MEAN','同房公共均值与历史校准预测',SCRIPTS/'same_room_prediction.py','legacy_common.load; enrich; histories; legacy_mean.build_rows/fit_one',
        root_source+'research/statistics/v2_evidence_audit_20261019/records.json.gz|'+root_source+'research/data/releases/v2.1/quality_inventory.json|'+root_source+'research/data/releases/v2.1/difficulty_records.json|'+root_source+'research/same_room/relation_adoption_20261016/relations.json|'+root_source+'research/same_room/same_room_multiview_20261020/GROUPS.json',
        'object_id原答；pool_analysis_eligible & quality_usable & !is_oos & target_aligned；ordinary_primary/doorway_quality；直接同房manual/all/ordinary、scope_comparable、无substantive_conflict、共同人员>=4；楼外ordinary训练原答',
        'original_response_object_id',None,None,None,'保持；不重新拟合',
        '原答Q/劳动、参考与关系未被人工融合补丁修改；输入不含半队、同房ABC或AC事件统计。脚本中的source为冻结源映射。')
    add('PRED_PERSON','同房个人预测',SCRIPTS/'same_room_prediction.py','histories; personal.make_base; fixed public_external_halfown rule',
        '同PRED_MEAN的原答输入与原目标/历史面板；legacy personal_similarity/analyze.py',
        '楼外个人绝对Q及peer residual theta；同房公共均值；原固定0.5倍个人源残差；all_methods_supported共同原答支持；原历史预算',
        'original_response_object_id',None,None,None,'保持；不重算预测',
        '0.5为原个人残差系数，不来自本次50%换人效应；当前融合Q未回写quality_inventory。')
    add('SELECTION_HISTORY','Q/QT候选历史与选员特征',SCRIPTS/'selection_stop_prepare.py','history; selection',
        root_source+'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz|'+root_source+'research/data/releases/v2.1/quality_inventory.csv|'+root_source+'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json|'+relative(UTILITY/'inputs/research/workers/personnel_profiles_composition_20261020/tables/history_lobo.csv'),
        '固定原候选；楼外8图/3楼历史支持；按object_id更新原答Q及source_active_time；Q/T用原2分Q容忍与原随机种子，目标融合Q不进入选员',
        'original_response_object_id',None,None,None,'保持；不重选团队',
        '改动的是既有融合端点连接；源视角个人Q、历史Q_peer、relative_time、资格与候选均未变。')
    sel=counts['same_room_Q_QT_selected_outcomes']
    add('SELECTION_OUTCOMES','Q/QT结果、共同支持与关系分层',SCRIPTS/'selection_stop_analyze.py','selection; selection_stop_finalize.relation_layers',
        relative(UTILITY/'design/SELECTION_DESIGN.csv.gz')+'|'+relative(UTILITY/'endpoints/SCALARS.csv.gz')+' -> '+sel['path'],
        '两历史版本、全部候选域/人数/政策；同时扫描team_key和base_team_key；下游ordinary_manual且scope_comparable，主层剔除pending/substantive_conflict',
        'exact_team_key',sel['rows'],sel['unique_endpoint_keys'],sel['matched_references'],'保持；不重聚合',
        '完整71608行原结果与57精确团队零交集，故其关系子层、图片/建筑聚合及共同支持补充亦无变化输入。')
    add('STOP_ALL_PREFIXES','停止源历史曲线与目标几何补收',SCRIPTS/'selection_stop_analyze.py','stopping; original rebuild_stopping.near_peak/geometry_next/online_node_count',
        relative(NODES)+'|'+relative(contractpath)+'|'+counts['historical_stop_reference_patch_endpoints']['path'],
        '全部旧前缀；四参考变化池k!=2按当前端点覆Q/参考；源历史Q距峰值2分最早k>=3；目标只用几何ok、nodes>=4、connection；在线规则k>=5连续三次同节点数；k2原deferred排除',
        'pool_id + sorted(member_workers); verified exact team_key',rows,len(teamsets),0,'保持；不重跑停止',
        '全124924行/60129唯一团队集合/43池，哈希键与不经哈希的(pool,sorted workers)两种交集均0；57/57哈希合同自校验通过。停止确实依赖源融合Q，但完整源曲线没有本批命中。')
    st=counts['historical_stop_reference_patch_endpoints']
    add('STOP_PATCH_ONLY','历史v2.1参考更新端点子集',SCRIPTS/'selection_stop_analyze.py','endpoint_scalars(only_stopping=True)',
        st['path']+'|'+relative(contractpath),'仅四个历史参考变更池；它不是全部停止源前缀集合',
        'exact_team_key',st['rows'],st['unique_endpoint_keys'],st['matched_references'],'保持',
        '1534端点零命中与STOP_ALL_PREFIXES完整证明并列，不能单用1534子集证明全部停止无依赖。')
    fi=counts['same_room_finite_panel_team_links']
    add('FINITE_CONTEXT','同房有限配比与预测边界',SCRIPTS/'same_room_prediction.py','input separation',fi['path'],
        '原有限配比全团队链接仅作边界核查；预测脚本不读取该面板或同房ABC效应',
        'exact_team_key',fi['rows'],fi['unique_endpoint_keys'],fi['matched_references'],'保持；不重算有限配比',
        '92342链接与57零交集；同房ABC质量支持增加不等于原答预测训练样本增加。')
    pd.DataFrame(rows_audit).to_csv(OUT/'INDIRECT_PREDICTION_STOP_AUDIT.csv',index=False,encoding='utf-8-sig')
    paths=[Path(__file__),endpath,NODES,contractpath,RULE,
        ROOT/'research/same_room/same_room_profile_return_review_20261021/pro/room_similarity/code/common.py',
        ROOT/'research/data/releases/v2.1/full_chain_downstream_20261030/README.md',
        *[SCRIPTS/n for n in source_names],*tables.values()]
    manifest=[]
    for p in sorted(set(paths)):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(1<<20),b''):h.update(b)
        manifest.append(dict(path=relative(p),bytes=p.stat().st_size,sha256=h.hexdigest()))
    checks=dict(source_commit=BASE_COMMIT,audit_only=True,team_hash_contract_selfcheck_passed=57,
        returned_unique_team_keys=57,full_stopping_rows=rows,non_k2_stopping_rows=legal,
        full_stopping_unique_team_sets=len(teamsets),full_stopping_pools=len(pools),full_stopping_groups=len(groups),
        source_patch_rows=patch_rows,full_stop_exact_hash_intersection=0,full_stop_direct_tuple_intersection=0,
        shared_pool_ids_with_57=len(pools & set(ends.pool_id)),source_reference_condition='zero team-set intersection before reference filtering; no old/current-reference false match',
        direct_tables=counts,original_response_features_changed=False,half_same_room_AC_summaries_consumed_by_prediction_or_selection_history=False,
        no_new_prediction_fit=True,no_new_selection=True,no_stopping_replay=True,no_statistics_rerun=True,
        files=manifest)
    (OUT/'INDIRECT_PREDICTION_STOP_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    text=f'''# 同房预测、Q/QT选队与停止：真实间接依赖核查

## 结论

本批57组不会经半队、同房ABC或AC的新结果继续改变同房公共/个人预测、Q/QT选员或停止决策。预测与选员历史读取原答质量及劳动，输入未改；停止确实读取源视角融合Q和目标几何，但完整停止源表也与57组零交集。因此这几条链保持原结果，没有为统一版本而重新拟合、重选或重跑停止。

本核查只读代码与原表，不改变已冻结统计。逐消费者路径、筛选和特征见 [INDIRECT_PREDICTION_STOP_AUDIT.csv](INDIRECT_PREDICTION_STOP_AUDIT.csv)，全部来源哈希见 [INDIRECT_PREDICTION_STOP_CHECKS.json](INDIRECT_PREDICTION_STOP_CHECKS.json)。

## 1. 预测读取原答，未读取换人效应

真实预测实现位于`stage02_same_room/prediction`链，代码为 {link(SCRIPTS/'same_room_prediction.py')}。它由 `legacy_common.load` 读取原答审计记录、训练准入、直接同房关系及原历史面板；通过`object_id`接入v2.1 `quality_inventory`和图片难度。原答入口见 {link(ROOT/'research/same_room/same_room_profile_return_review_20261021/pro/room_similarity/code/common.py','common.py: load')}。

正式原答门控为`pool_analysis_eligible & quality_usable & !is_oos & target_aligned`，限`ordinary_primary/doorway_quality`。直接普通Manual关系要求可比、无实质冲突、至少4个共同人员。楼外历史仅取其它建筑、ordinary且training_allowed的原答。公共均值、个人theta、同房源均值和原楼外校准均从这些原答计算；个人模型的0.5倍源残差是原固定系数，不来自50%换人统计。本批固定源记录与参考，只改变选定融合节点的连接，没有把人工辅助Q写回原答quality_inventory，也没有改变历史训练样本。

## 2. Q/QT选择与结果

{link(SCRIPTS/'selection_stop_prepare.py')} 的 `history` 使用原`record_index`与当前原答`quality_inventory`，保留楼外8图/3楼支持、来源分开的时间字段、固定原候选、原2分Q容忍及随机种子。选员特征是楼外个人Q_peer、源视角个人Q和原劳动，不读取半队或AC均值；目标融合结果用于评价，不进入历史特征。

{link(SCRIPTS/'selection_stop_analyze.py')} 将冻结设计与端点标量合并，生成`POLICY_EVENT_RESULTS.csv.gz`。本次完整检查 **{sel['rows']:,}行**，同时扫描 `{', '.join(sel['columns'])}`，与57组引用交集为0。{link(SCRIPTS/'selection_stop_finalize.py')} 的关系主层只是这些行的`ordinary_manual + scope_comparable`子集，并排除pending与substantive_conflict；其它分层、图片/建筑聚合及共同支持同样没有新输入，保持原结果。

## 3. 停止检查覆盖全部前缀

不能仅凭1,534行`STOPPING_SCALARS`零命中判断整个停止链。该表只覆盖历史v2→v2.1四个参考变化池；真正的停止代码还读取全部旧`replay_nodes.csv.gz`并沿用其它池的前缀。

本次完整读取 **{rows:,}行、{len(teamsets):,}个唯一(pool,成员集合)、{len(pools)}池、{len(groups)}个原组**。按原函数重建精确team_key，同时直接按`(pool_id, sorted(member_workers))`做不经哈希的集合交集，两者与57均为 **0**。参考筛选尚未施加就已零交集，所以不是旧/新参考版本筛选造成的伪零。原完整行数、图数与组数均与STOPPING_CONTRACT一致；源表按历史规则会覆盖{patch_rows:,}条参考变化前缀，剩余前缀也已检查。

团队键合同为：

```python
payload = json.dumps(sorted(workers), sort_keys=True, separators=(',', ':')).encode()
team_key = pool_id + '__' + hashlib.sha256(payload).hexdigest()[:20]
```

先对57端点的已保存pool_id及成员重建，**57/57等于原team_key**，再应用于停止源表；自校验明细见[INDIRECT_PREDICTION_STOP_TEAM_KEY_SELF_CHECK.csv](INDIRECT_PREDICTION_STOP_TEAM_KEY_SELF_CHECK.csv)。并行的直接集合比较不依赖该哈希，避免错误命名合同导致伪零。匹配结果表保留空表头，见[INDIRECT_PREDICTION_STOP_MATCHES.csv](INDIRECT_PREDICTION_STOP_MATCHES.csv)。

原规则 {link(RULE,'rebuild_stopping.py')} 用已取得源视角Q曲线找距峰值2分的最早k≥3；目标只按几何ok、至少4节点、连接可用补收。在线规则在k≥5时检测连续三次完整输出节点数一致。k2继续排除，源不足不插值，目标Q不参与选择。源曲线、几何序列、人员顺序和劳动都无本次命中，所以停止决定及冷启动成本不会被其它链的新统计间接改变。

## 4. 保留边界与复现

同房有限配比原PANEL_TEAM_LINKS另核查{fi['rows']:,}行，零命中；这不构成预测的训练集。新增同房ABC六端可评支持不能等同原答预测支持扩展。旧Q/QT同房选队也不是本次半队DSTRUCT与Q-only公平对照，两者的历史特征与评估端点应按实际路径分别保留。

复现本只读核查：`python -m tools.thesis_main.analysis.audit_manual_order_prediction_stop_20261104`。脚本不会导入执行原统计脚本，不拟合预测、不生成团队、不重评分、不重跑停止。源提交为`{BASE_COMMIT}`。预测代码中的`source/`表示原归档的冻结源映射，历史版本说明以该归档的源合同为准；本审计不修改其参考、关系、准入或旧统计身份。
'''
    (OUT/'INDIRECT_PREDICTION_STOP_AUDIT.md').write_text(text,encoding='utf-8')
    print(json.dumps({k:v for k,v in checks.items() if k!='files'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
