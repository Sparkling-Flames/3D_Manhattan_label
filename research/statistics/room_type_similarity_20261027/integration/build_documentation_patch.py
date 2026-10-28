#!/usr/bin/env python3
"""Generate narrowly scoped continuation patch against saved exact b2 originals.

Never edits repository documents. Writes candidate files below this directory.
"""
from pathlib import Path
import difflib,hashlib,json

BASE='b2b0898b90bd631df37f1f2e75e8380800a43cf8'
def main():
    root=Path(__file__).resolve().parent
    mappings=[('CONCLUSIONS_ZH.md','research/statistics/research_closeout_20261022/CONCLUSIONS_ZH.md','CONCLUSIONS_INSERT_ZH.md'),('README.md','research/statistics/room_type_similarity_scoping_20261027/README.md','SCOPING_UPDATE_ZH.md')]
    patches=[];receipt=[]
    for name,rel,insert in mappings:
        raw=(root/'source_original'/name).read_bytes();old=raw.decode('utf8');nl='\r\n' if '\r\n' in old else '\n'
        block=(root/insert).read_text(encoding='utf8').replace('\r\n','\n').rstrip()+'\n\n';block=block.replace('\n',nl)
        if name=='CONCLUSIONS_ZH.md':
            anchor='## 3. 最初预期目前实现了哪些'+nl
            assert old.count(anchor)==1
            new=old.replace(anchor,block+anchor,1)
            new=new.replace('更新：2026-10-26。','更新：2026-10-27。',1)
            t='|选队与人数选择|'
            assert new.count(t)==1
            row='|同用途的不同物理房间|跨楼同难度三图150图均Q差9.042／9.537分，同用途略接近；个人相对Q和转折差不随之更接近。固定161图、已知难度与参考几何，在同候选模型库下加用途使公共均值预测MAE4.567→4.188（未加人员池历史）；个人一般历史11.449，加独立用途收缩11.450，无实用增量。|[本轮用途研究](../room_type_similarity_20261027/README.md)与第2.7节。用途不是物理同房身份或永久人员类型；沿用资格，无新融合。|'+nl
            new=new.replace(t,row+t,1)
        else:
            anchor='## 要回答什么'+nl;assert old.count(anchor)==1
            new=old.replace(anchor,block+anchor,1)
            oldstatus='2026-10-27。状态：已核对既有标签、数据覆盖和描述统计；相关性与预测增量留给下一轮 Pro 实算。可直接使用[后续任务提示词](PRO_TASK_ZH.md)。'
            newstatus='2026-10-27。状态：初步盘点已完成，后续相关性与预测增量现已实际计算；本页保留盘点身份。原[任务提示词](PRO_TASK_ZH.md)为已执行任务依据，最新结果见下节。'
            assert oldstatus in new;new=new.replace(oldstatus,newstatus,1)
            new=new.replace('当前尚未计算相关系数、个人用途偏好或预测收益。上述结果支持继续研究，不预先决定结果必须为正。','本页盘点阶段未计算相关系数、个人用途差异或预测收益；后续实际结果已接入上方完成说明，以下保留当时形成任务的依据。',1)
            new=new.replace('## 下一轮应如何接续','## 盘点时拟定的接续方式（保留设计史，现已实际计算）',1)
            new=new.replace('未新增融合、评分、分类拟合或预测实验。','本页盘点未新增融合、评分、分类拟合或预测实验；后续新增分析另见上方完成入口。',1)
        candidate=root/'candidate'/rel;candidate.parent.mkdir(parents=True,exist_ok=True);candidate.write_bytes(new.encode('utf8'))
        patch=''.join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile='a/'+rel,tofile='b/'+rel))
        patches.append(patch)
        receipt.append({'repository_path':rel,'base_commit':BASE,'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(new.encode()).hexdigest(),'source_newline':'CRLF' if nl=='\r\n' else 'LF','bytes_original':len(raw),'bytes_candidate':len(new.encode())})
    target=root/'ROOM_TYPE_CONTINUATION.patch';target.write_bytes(''.join(patches).encode('utf8'))
    (root/'DOCUMENTATION_PATCH_RECEIPT.json').write_text(json.dumps({'base_commit':BASE,'patch_file':target.name,'patch_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'files':receipt,'repository_documents_modified':False,'new_fusion':0,'scope_attachment_role':'Interpretation background only; no changes to qualification, reference, labeling policy, OOS, or retained votes'},ensure_ascii=False,indent=2)+'\n')
    print(target)
if __name__=='__main__':main()
