"""Complete a portable source/input bundle; never fit, fuse, score or upload.

The default action inventories dependencies by initializing the frozen engine
without evaluating a team. Auxiliary actions only arrange existing input files
or restore saved endpoint JSONL to the layout expected by the original measurer.
"""
from __future__ import annotations

import argparse
import ast
import csv
from collections import defaultdict
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile


COMMIT = "519c7447278dd16c3d69f505b807fb5b53792b36"
BASE_REL = Path("research/workers/personnel_v21_reselection_20261029")
DEFAULT_DELIVERY = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while block := f.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def dump(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def csv_write(rows, path):
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


IMPORT_AUDIT = r'''
import sys,os,json,platform,importlib.metadata as md
from pathlib import Path
repo=Path(sys.argv[1]).resolve()
reads=set()
def audit(event,args):
    if event=='open' and args and isinstance(args[0],str):
        p=Path(args[0])
        if p.is_absolute() and p.resolve().is_relative_to(repo):
            reads.add(str(p.resolve()))
sys.addaudithook(audit)
from benchmark_engine import load_engine
native=load_engine(repo)
# Construction reads the fixed record-time source; context entry imports and
# initializes the frozen measurement package. No evaluate/fuse/measure call.
with native.Engine(full_state=False) as engine:
    assert engine.scorecache=={} and callable(engine.engine.measure)
import numpy,pandas,scipy,sklearn,matplotlib,PIL,shapely
files=sorted({str(Path(x.__file__).resolve()) for x in list(sys.modules.values())
    if getattr(x,'__file__',None) and Path(x.__file__).resolve().is_relative_to(repo)})
third_party={}
mapping=md.packages_distributions()
for top in sorted({m.split('.')[0] for m in sys.modules}):
    for name in mapping.get(top,[]):
        try:third_party[name]=md.version(name)
        except md.PackageNotFoundError:pass
result=dict(repository=str(repo),loaded_repository_files=files,
    repository_files_read=sorted(p for p in reads if Path(p).is_file() and '__pycache__' not in Path(p).parts),
    distribution_versions=dict(sorted(third_party.items())),
    python_version=sys.version,python_executable=sys.executable,platform=platform.platform(),
    shapely_version=shapely.__version__,shapely_module=shapely.__file__,geos_version=shapely.geos_version_string,
    native_engine_initialized=True,measurement_module_initialized=True,
    fusion_calls=0,score_calls=0,classification_fits=0,team_requests_executed=0)
print('REPRO_IMPORT_AUDIT_JSON='+json.dumps(result,ensure_ascii=False))
'''


def import_audit(repo, extra_dependencies):
    repo = Path(repo).resolve()
    paths = [str(repo), str(repo / BASE_REL / "experiment")]
    if extra_dependencies and Path(extra_dependencies).exists():
        paths.insert(0, str(Path(extra_dependencies).resolve()))
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join(paths),
               HOHONET_REPO=str(repo), OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    with tempfile.TemporaryDirectory(prefix="hohonet_source_import_") as cwd:
        result = subprocess.run([sys.executable, "-c", IMPORT_AUDIT, str(repo)], cwd=cwd,
            env=env, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError("Frozen-source import/initialization failed:\n" + result.stdout + result.stderr)
    marker = "REPRO_IMPORT_AUDIT_JSON="
    lines = [x[len(marker):] for x in result.stdout.splitlines() if x.startswith(marker)]
    assert len(lines) == 1, result.stdout
    data = json.loads(lines[0])
    data["stderr"] = result.stderr
    return data


README = r'''HOHONET v2.1 人员研究：分层复现说明
===================================

本文件对应补齐后的 stage06_reproduction。初始已上传的
HOHONET_v21_reaudit_stage06_inputs_and_engine.zip 保持原字节，不被覆盖；
它只有最初243项输入/来源，不能替代这份补齐版本。当前完整数量和新增项
以 SOURCE_FILE_MANIFEST.csv、ADDED_SOURCE_FILES.csv、FINALIZATION_RECEIPT.json 为准。

一、冻结版本与研究合同
--------------------
本轮读取仓库 Sparkling-Flames/3D_Manhattan_label 的提交：
519c7447278dd16c3d69f505b807fb5b53792b36。
实际数据使用 v2.1 主池和其他准入空间快照，人员资格、原答顺序、空间范围、
参考版本、分数与失败定义不改。普通Manual为主。标签使用留目标建筑外历史。

源码中仍可见82c6164...、72a44e80...等旧冻结模块元数据或错误提示；它们是
被当前入口继续调用的历史实现身份，不要求把本轮数据退回旧版本。
本轮运行入口 run_supplement_native.py 覆盖执行来源元数据为上述实际提交。
请保持输入源层次结构，不将旧 prepare()/load_pools()入口用于重建本轮数据。

SOURCE_FILE_MANIFEST.csv 给每个输入/源码的原工作区相对路径、导出路径、字节数
和SHA256；COMPLETE_REPRODUCTION_SHA256.csv覆盖该阶段全部文件（自身除外）。
SOURCE_FILE_MANIFEST_INITIAL_243.csv 与 REPRODUCTION_CONTRACT_INITIAL.json
保留最初版本。原本漏掉的两份prior_extracted表、POOL_TARGET_CONDITIONS.csv、
原生引擎实际import的 tools/thesis_main/lib源码以及设计候选格已补齐。

二、复现能力分层，不能混称
------------------------
A. 直接核查已保存研究结果：
   读取主交付 stage01_classification、stage02_comparison、stage02_capacity、
   stage03_completed_abc、stage04_cases、stage05_synthesis 的展开文件。
   本层无重新拟合、融合、评分。逐事件/逐池身份、失败分母与源码SHA均可核对。

B. 用本源包的冻结输入重做本轮新增研究：
   1) 15个新分类 + 原TARGET K2/K3/K4的精确复现，23折；
   2) 复用保存的原答对距离，重分组得到原答几何分离及基线一致性；
   3) 重建固定种子的新ABC登记，或直接使用主交付冻结的EVENTS/REQUESTS；
   4) 用原生算法重放16,818个已登记端点；
   5) 从已保存端点重做6,548个事件的多指标；
   6) 在同一有限面板、背景、成员候选和精确团队上做Q/QT条件分析与128次置换。
   这里的“原答几何复现”复用冻结RAW_PAIR_DISTANCES，不声称从每条原答坐标
   再计算全部原始Hungarian/重叠距离。这里的“历史特征复现”从冻结历史表开始，
   不声称已把所有旧原始日志、范围裁定和历史特征构造上游独立重新生成。

C. 重建全部旧研究或从旧几何重新计算全部合并指标：
   旧45配置的89,660个精确方法事件、全部旧端点/几何、旧有限配比全分布、
   同房研究和256条自然人数曲线，不由本小源包无条件覆盖。
   stage02_capacity/results/ALL_EXECUTED_EVENTS_Q_AND_IDENTITIES.csv.gz
   保留旧89,660事件的身份和Q，能核查已保存的旧证据链；它不是全部旧几何。
   原研究脚本若继续扫描 repo/.../experiment/*_design、*_endpoints 或旧compact
   包，需要上述提交对应的完整旧仓库/已保存原交付。不能把缺文件视为无事件、
   零质量或方法无效。不要通过重跑这批旧研究来填本轮并未要求的范围。

旧完整来源的目录、提交、release README 与原阶段回执已保留；完整路径清单还在
stage02_capacity/results/CAPACITY_AUDIT_RECEIPT.json。
本轮主文的旧+新XYZ等权汇总需要这些旧已保存指标，不能拿只运行本轮新增事件
的均值来替换主文合并均值。

三、环境与目录变量
----------------
实际环境版本记录在 RUNTIME_VERSIONS.json；安装版本参考 REQUIREMENTS_FROZEN.txt。
关键版本：Python 3.12.14、numpy 2.3.5、pandas 2.2.3、scipy 1.17.0、
scikit-learn 1.8.0、Shapely 2.2.0（GEOS 3.14.1）。本轮在Linux x86_64运行。
Shapely原先由工作区runtime_deps提供；该二进制目录没有复制进本包。
请在自己的Python环境安装对应版本。其他系统/BLAS微小浮点差异需比较语义数值，
不能仅以gzip字节不同判定科学结果不同。原生融合/评分不需要GPU或Node；
Node版本只记录实际工具环境，不列为这些数值步骤的必要依赖。

以下是可直接调整绝对根目录后使用的shell命令；本次补齐没有执行这些研究命令。
将RR_DELIVERY改为解包后包含stage06_reproduction的主交付目录。
新输出RR_OUTPUT必须位于独立目录，不要覆盖保存的研究结果。

RR_DELIVERY="/absolute/path/HOHONET_v21_reaudit_20261029"
RR_OUTPUT="/absolute/path/hohonet_reproduction_new_output"
RR_PYTHON="python"
RR_SRC="$RR_DELIVERY/stage06_reproduction/inputs_and_source"
RR_REPO="$RR_SRC/repo"
RR_BASE="$RR_REPO/research/workers/personnel_v21_reselection_20261029"
RR_EXP="$RR_BASE/experiment"
RR_CLASS_CODE="$RR_SRC/audit_classification/code"
RR_CONTROL_CODE="$RR_SRC/audit_comparison/analyze_fixed_panel_q_controls.py"
RR_CODE="$RR_SRC/HOHONET_v21_reaudit_20261029/code"
mkdir -p "$RR_OUTPUT"
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HOHONET_REPO="$RR_REPO"
export PYTHONPATH="$RR_REPO:$RR_EXP${PYTHONPATH:+:$PYTHONPATH}"

# 建议在独立虚拟环境安装。依赖安装会访问所配置的软件包源。
"$RR_PYTHON" -m pip install -r "$RR_DELIVERY/stage06_reproduction/REQUIREMENTS_FROZEN.txt"

四、参数化步骤与精确输入
----------------------
4.1 分类与原答结构诊断：

"$RR_PYTHON" "$RR_CLASS_CODE/refit_v21_structure_audit.py" \
  --source "$RR_SRC/prior_extracted/stage02" \
  --out "$RR_OUTPUT/classification"

必需输入为该source下classification目录的：
HISTORY_FEATURES_ALL_LOBO.csv.gz、RAW_TARGET_RESPONSE_RECORDS.csv.gz、
MAIN45_LABELS_ALL_LOBO.csv.gz。脚本不把团队结果、Q或T用于新标签拟合。
配置在输出CONFIG_BEFORE_NEW_TEAM_RESULTS.json，含5变体+原TARGET复现、K2/3/4。
精确原TARGET复现应检查EXACT_BASELINE_REPRODUCTION与FIT_AND_AUDIT_RECEIPT，
为3×23×62=4,278行支持与类别身份一致。新配置15个，复现别名3个不算新思想。

4.2 同点数原答几何（重用冻结原答对，不重融合）：

"$RR_PYTHON" "$RR_CLASS_CODE/compare_new_raw_geometry.py" \
  --source "$RR_SRC/prior_extracted/stage02" \
  --pairs-source "$RR_SRC/prior_extracted/stage04" \
  --audit "$RR_OUTPUT/classification"

pairs-source/raw_similarity中的RAW_PAIR_DISTANCES.csv.gz为原答对几何；
RAW_CLASS_DISTANCE_BY_POOL.csv.gz用于重现旧方法按类聚合的完整基线核对。
审计输出RAW_GEOMETRY_EXISTING_BASELINE_PARITY.json，缺失模式应一致，误差<1e-9。

4.3 新ABC登记：推荐直接使用保存的冻结设计

RR_DESIGN="$RR_DELIVERY/stage03_completed_abc"

EVENTS_EXACT.csv.gz固定6,548个方法事件；REQUESTS.csv.gz固定16,818个精确物理团队。
FROZEN_CELLS、FROZEN_LABELS、PRE_OUTCOME_DESIGN保存选型前设计和名单。
旧338个已有m7格未重算；新事件不是全部旧研究的替代样本。

如果需要复现“如何生成登记”，以下辅助命令只布置隔离路径，不运行拟合/融合：

"$RR_PYTHON" "$RR_CODE/finalize_reproduction_bundle.py" prepare-design-workspace \
  --source-root "$RR_SRC" \
  --workspace "$RR_OUTPUT/design_workspace" \
  --labels "$RR_OUTPUT/classification/NEW_LABELS_ALL_LOBO.csv.gz"

"$RR_PYTHON" "$RR_OUTPUT/design_workspace/HOHONET_v21_reaudit_20261029/code/build_supplement_design.py"

RR_DESIGN="$RR_OUTPUT/design_workspace/HOHONET_v21_reaudit_20261029/stage03_new_abc"

该步骤使用固定种子202610291031和已冻结的
audit_capacity/results/M7_M8_EXACT_SUPPLEMENT_CANDIDATES.csv，包含旧登记存在性。
它不重新跑89,660旧事件来推断缺口。原脚本按相对目录寻找依赖，因此辅助命令
只创建repo符号链接、标签/候选表副本和原脚本副本，不改科学逻辑。
比较重新登记的事件/团队键、成员、DXYZ、n/m与原冻结设计；不以压缩流时间戳判断。

4.4 原生ABC端点重放（此命令会真正运行融合与评分；补齐阶段没有执行）：

"$RR_PYTHON" "$RR_CODE/run_supplement_native.py" \
  --repo "$RR_REPO" \
  --pools "$RR_REPO/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json" \
          "$RR_REPO/research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json" \
  --requests "$RR_DESIGN/REQUESTS.csv.gz" \
  --output "$RR_OUTPUT/endpoints" \
  --jobs 6 --part-size 100

主入口只输入精确成员与冻结图池，人员类别不进入融合算法。record_index.csv.gz
提供已记录劳动量来源；measurement_engine.zip与working_models.py提供冻结评分。
本次原研究16,818执行端点中8个是旧标量已有的几何重放，真正新增物理证据16,810。
以后从空缓存重放16,818个不会改变这8个端点的历史身份。fusion_seconds等运行时间
和输出分片顺序不是被研究的人员劳动量，不能拿来要求逐字节一致。

4.5 从保存端点重做measure，或先恢复扁平几何的分片布局

若已完成4.4，RR_ENDPOINTS设为新生成的endpoints即可：
RR_ENDPOINTS="$RR_OUTPUT/endpoints"

若不想重融合，使用主交付扁平完整端点恢复原measurer需要的pools/<pool>/part布局：

"$RR_PYTHON" "$RR_CODE/finalize_reproduction_bundle.py" hydrate-endpoints \
  --geometry "$RR_DELIVERY/stage03_completed_abc/ENDPOINT_GEOMETRY.jsonl.gz" \
  --requests "$RR_DELIVERY/stage03_completed_abc/REQUESTS.csv.gz" \
  --out "$RR_OUTPUT/restored_saved_endpoints"
RR_ENDPOINTS="$RR_OUTPUT/restored_saved_endpoints"
RR_DESIGN="$RR_DELIVERY/stage03_completed_abc"

"$RR_PYTHON" "$RR_BASE/analysis/measure_registered_events.py" \
  --events "$RR_DESIGN/EVENTS_EXACT.csv.gz" \
  --endpoints "$RR_ENDPOINTS" \
  --pools "$RR_REPO/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json" \
          "$RR_REPO/research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json" \
  --target-conditions "$RR_BASE/targets/POOL_TARGET_CONDITIONS.csv" \
  --out "$RR_OUTPUT/metrics"

hydrate只重新分文件，保留每条JSON内容、失败、成员与键，不计算融合或分数。
measure要求全6548事件登记、192池完整；不要用--partial把未完成误作最终结果。
measure中的*_cross/gap仍为旧对称定义，*_AC_absolute和*_AC_gap才是同原A口径；
主文汇总还使用固定XYZ内先平均背景，再池/图/楼，不应直接平均全部事件代替。
缺失Q不填零，各项几何/劳动量按自己的合法分母。

4.6 同团队Q/QT条件控制与置换（不重融合、不重新评分）：

"$RR_PYTHON" "$RR_CONTROL_CODE" \
  --repo "$RR_REPO" \
  --history "$RR_SRC/prior_extracted/stage02/classification/HISTORY_FEATURES_ALL_LOBO.csv.gz" \
  --new-labels "$RR_OUTPUT/classification/NEW_LABELS_ALL_LOBO.csv.gz" \
  --out "$RR_OUTPUT/conditional_results" \
  --seed 20261029 --permutations 128

精确有限团队输入在：
repo/research/workers/personnel_v21_reselection_20261029/additional_delivery/packages/03B_core/composition/
  primary_panel_inputs/PANELS_USED.csv
  primary_panel_inputs/PANEL_TEAMS.csv.gz
  primary_panel_inputs/ENDPOINT_SCALARS.csv.gz
  primary_compact_links/TEAM_LINK_INDEX.csv.gz
  primary_compact_links/METHOD_VECTOR_CODES.csv.gz
  primary_compact_links/VECTOR_CODEBOOK.csv
脚本另读repo/.../classification/MAIN45_LABELS_ALL_LOBO.csv.gz与上面history/new-labels。
共同支持为182面板、38图、22楼、162,708个面板—团队关联，Q可评161,580；
这不是162,708个独立图片或预测样本。固定D、候选及精确团队，随机置换保持每Q层
类别容量；输出是有限样本内剩余方差解释，不能报告为预测准确率、因果独立作用或p值。

五、文件验证、已做与未做的验证
----------------------------
本次补齐对所有source/input文件计算SHA256；gzip完整读至EOF、CSV逐行解析、
JSON解析、Python AST检查、内置评分ZIP全成员CRC检查。IMPORT_DEPENDENCY_AUDIT
分别记录原工作区与仅含导出源树的原生引擎/评分模块初始化；没有evaluate、fuse、
measure或分类fit调用，不能把它写成全研究在全新环境已重跑。

已有研究数值验证不由这个打包步骤重做；应查stage01分类复现回执、stage02_capacity
逐事件独立核验、stage03端点/指标回执。保存的机器耗时不是人员劳动量。
在另一台机器运行上述命令后，先核身份/支持/缺失，再比较数值容差；原生数据异常
或范围裁定缺口必须保留，不自动补零、不换参考、不静默跳过失败。
'''


def finalize(args):
    delivery = Path(args.delivery).resolve()
    work = Path(args.workspace).resolve()
    repo = work / "repo"
    stage = delivery / "stage06_reproduction"
    sources = stage / "inputs_and_source"
    stage.mkdir(parents=True, exist_ok=True)
    manifest_path = stage / "SOURCE_FILE_MANIFEST.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as f:
        old = list(csv.DictReader(f))
    initial_manifest = stage / "SOURCE_FILE_MANIFEST_INITIAL_243.csv"
    if not initial_manifest.exists():
        assert len(old) == 243
        shutil.copy2(manifest_path, initial_manifest)
    initial_contract = stage / "REPRODUCTION_CONTRACT_INITIAL.json"
    if not initial_contract.exists():
        shutil.copy2(stage / "REPRODUCTION_CONTRACT.json", initial_contract)
    initial_zip = delivery / "deliverables/HOHONET_v21_reaudit_stage06_inputs_and_engine.zip"
    initial_zip_sha = digest(initial_zip) if initial_zip.exists() else None
    original_audit = import_audit(repo, work / "runtime_deps")
    additions = {
        "prior_extracted/stage02/classification/MAIN45_LABELS_ALL_LOBO.csv.gz": "refit exact original labels and geometry label baseline",
        "prior_extracted/stage04/raw_similarity/RAW_CLASS_DISTANCE_BY_POOL.csv.gz": "raw geometry existing-class baseline parity",
        "repo/research/workers/personnel_v21_reselection_20261029/targets/POOL_TARGET_CONDITIONS.csv": "measure event difficulty/scope/structural metadata",
        "audit_capacity/results/M7_M8_EXACT_SUPPLEMENT_CANDIDATES.csv": "fixed pre-outcome directed-cell universe including old execution support",
        "audit_classification/code/refit_v21_structure_audit.py": "parameterized classification and original-label reproduction entrypoint",
        "audit_classification/code/compare_new_raw_geometry.py": "parameterized raw-geometry regrouping entrypoint",
        "audit_comparison/analyze_fixed_panel_q_controls.py": "parameterized identical-team Q/QT and conditional randomization entrypoint",
        "audit_comparison/summarize_same_composition_residuals.py": "saved same-composition residual summarizer",
        "HOHONET_v21_reaudit_20261029/code/build_supplement_design.py": "exact frozen seeded new-ABC registration entrypoint",
        "HOHONET_v21_reaudit_20261029/code/run_supplement_native.py": "actual current-commit native execution adapter",
        "HOHONET_v21_reaudit_20261029/code/verify_native_parity.py": "preserved original native parity checker, not rerun by finalization",
        "HOHONET_v21_reaudit_20261029/code/finalize_reproduction_bundle.py": "portable source finalizer and layout-only reproduction helpers",
    }
    for path in original_audit["loaded_repository_files"] + original_audit["repository_files_read"]:
        p = Path(path)
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        additions[str(p.relative_to(work))] = "actual native engine/scorer initialization dependency; no team evaluated"
    for rel, reason in additions.items():
        src = work / rel
        if not src.is_file():
            raise FileNotFoundError(src)
        dst = sources / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            assert digest(src) == digest(dst), f"Existing source version differs: {rel}"
        else:
            shutil.copy2(src, dst)
    exported_audit = import_audit(sources / "repo", work / "runtime_deps")
    assert original_audit["distribution_versions"] == exported_audit["distribution_versions"]
    assert len(original_audit["loaded_repository_files"]) == len(exported_audit["loaded_repository_files"])
    original_rel = {str(Path(x).relative_to(repo)) for x in original_audit["loaded_repository_files"]}
    exported_rel = {str(Path(x).relative_to(sources / "repo")) for x in exported_audit["loaded_repository_files"]}
    assert original_rel == exported_rel
    dump(dict(original_workspace=original_audit, exported_source_tree=exported_audit,
        same_repository_import_set=True, no_fusion_or_score_or_fit_executed=True), stage / "IMPORT_DEPENDENCY_AUDIT.json")

    rows = []
    for p in sorted(sources.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(sources))
        original = work / rel
        same = original.is_file() and digest(p) == digest(original)
        assert same, rel
        rows.append(dict(original_workspace_path=rel, export_path=str(p.relative_to(delivery)),
            bytes=p.stat().st_size, sha256=digest(p), original_matches_export=True,
            inclusion_reason=additions.get(rel, "preserved initial source/input bundle")))
    csv_write(rows, manifest_path)
    with initial_manifest.open(encoding="utf-8-sig", newline="") as f:
        initial_keys = {r0["original_workspace_path"] for r0 in csv.DictReader(f)}
    added = [r for r in rows if r["original_workspace_path"] not in initial_keys]
    csv_write(added, stage / "ADDED_SOURCE_FILES.csv")
    node = shutil.which("node")
    runtime = dict(python_version=sys.version, python_executable=sys.executable, platform=platform.platform(),
        architecture=platform.machine(), source_commit=COMMIT,
        distribution_versions=original_audit["distribution_versions"],
        shapely_version=original_audit["shapely_version"], geos_version=original_audit["geos_version"],
        shapely_original_module=original_audit["shapely_module"], runtime_dependency_binaries_bundled=False,
        native_calculation_requires_node=False, node_version=subprocess.run([node, "--version"],capture_output=True,text=True,check=True).stdout.strip() if node else None,
        thread_settings={k: "1" for k in ["OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"]},
        managed_runtime_bundle=os.environ.get("CODEX_PRIMARY_RUNTIME_BUNDLE_VERSION"),
        runtime_capture_scope="Actual import/initialization dependencies plus classification libraries; no new research execution")
    dump(runtime, stage / "RUNTIME_VERSIONS.json")
    requirements = "# Observed import and numerical dependencies; Python 3.12.14; platform versions recorded separately.\n"
    requirements += "\n".join(f"{k}=={v}" for k, v in sorted(runtime["distribution_versions"].items(), key=lambda x:x[0].lower())) + "\n"
    (stage / "REQUIREMENTS_FROZEN.txt").write_text(requirements, encoding="utf-8")
    (stage / "REPRODUCTION_README_ZH.txt").write_text(README, encoding="utf-8")
    checks = []
    for r in rows:
        p = delivery / r["export_path"]
        check = dict(path=r["export_path"], bytes=r["bytes"], sha256=r["sha256"], all_bytes_read=True)
        if p.suffix == ".gz":
            with gzip.open(p, "rb") as f:
                while f.read(1 << 20):
                    pass
            check["gzip_crc_to_EOF"] = True
        if p.name.endswith((".csv", ".csv.gz")):
            opener = gzip.open if p.suffix == ".gz" else open
            with opener(p, "rt", encoding="utf-8-sig", newline="") as f:
                it = csv.reader(f)
                next(it, None)
                check["csv_data_rows"] = sum(1 for _ in it)
        elif p.suffix == ".json":
            json.loads(p.read_text(encoding="utf-8-sig"))
            check["json_valid"] = True
        elif p.suffix == ".py":
            ast.parse(p.read_text(encoding="utf-8-sig"))
            check["python_AST_valid"] = True
        elif p.suffix == ".zip":
            with zipfile.ZipFile(p) as z:
                assert z.testzip() is None
                check["zip_members_crc_valid"] = len(z.infolist())
        checks.append(check)
    csv_write(checks, stage / "SOURCE_READABILITY_INVENTORY.csv")
    assert initial_zip_sha is None or digest(initial_zip) == initial_zip_sha
    receipt = dict(source_commit=COMMIT, initial_source_files=243, completed_source_files=len(rows),
        added_source_files=len(added), source_bytes=sum(r["bytes"] for r in rows), added_bytes=sum(r["bytes"] for r in added),
        all_sources_match_original_SHA256=True, all_sources_read_to_end=True,
        source_gzip_streams_valid=sum(bool(r.get("gzip_crc_to_EOF")) for r in checks),
        source_csv_files_parsed=sum("csv_data_rows" in r for r in checks),
        source_python_files_parsed=sum(bool(r.get("python_AST_valid")) for r in checks),
        actual_native_repository_imports=len(original_rel), exported_native_imports_same=True,
        imported_frozen_measurement_package=True, classification_fits=0, team_fusions=0, score_evaluations=0,
        initial_uploaded_archive_unchanged=True, initial_uploaded_archive_sha256=initial_zip_sha,
        no_archive_created=True, no_upload_performed=True,
        old_complete_research_reproduction_requires_old_saved_deliveries=True,
        validation_limit="Source/readability and engine initialization only; no new-environment full numerical rerun")
    dump(receipt, stage / "FINALIZATION_RECEIPT.json")
    dump(dict(source_commit=COMMIT, files=len(rows), source_files_all_SHA256=True,
        reproduction_scope="New refits, existing raw-pair regrouping, frozen new ABC, saved-endpoint measures, identical finite-team Q/QT controls",
        history_and_raw_pair_upstream_frozen_not_regenerated=True,
        old_89660_complete_study_not_self_contained=True,
        old_data_requirement="Original complete repository/saved delivery at this commit for full old registration/endpoint/geometry reaggregation",
        instructions="REPRODUCTION_README_ZH.txt", runtime="RUNTIME_VERSIONS.json", requirements="REQUIREMENTS_FROZEN.txt",
        source_manifest="SOURCE_FILE_MANIFEST.csv", previous_manifest="SOURCE_FILE_MANIFEST_INITIAL_243.csv",
        initial_uploaded_zip_not_overwritten=True), stage / "REPRODUCTION_CONTRACT.json")
    full = []
    for p in sorted(stage.rglob("*")):
        if p.is_file() and p.name != "COMPLETE_REPRODUCTION_SHA256.csv":
            full.append(dict(path=str(p.relative_to(stage)), bytes=p.stat().st_size, sha256=digest(p)))
    csv_write(full, stage / "COMPLETE_REPRODUCTION_SHA256.csv")
    print(json.dumps(receipt, ensure_ascii=False), flush=True)


def prepare_design(args):
    src = Path(args.source_root).resolve()
    work = Path(args.workspace).resolve()
    if work.exists() and any(work.iterdir()):
        raise FileExistsError("Use an empty dedicated design workspace: " + str(work))
    work.mkdir(parents=True, exist_ok=True)
    labels = Path(args.labels).resolve()
    candidates = src / "audit_capacity/results/M7_M8_EXACT_SUPPLEMENT_CANDIDATES.csv"
    code = src / "HOHONET_v21_reaudit_20261029/code/build_supplement_design.py"
    for p in [labels, candidates, code]:
        if not p.is_file():
            raise FileNotFoundError(p)
    (work / "repo").symlink_to(src / "repo", target_is_directory=True)
    placements = [(labels, "audit_classification/results/NEW_LABELS_ALL_LOBO.csv.gz"),
                  (candidates, "audit_capacity/results/M7_M8_EXACT_SUPPLEMENT_CANDIDATES.csv"),
                  (code, "HOHONET_v21_reaudit_20261029/code/build_supplement_design.py")]
    for p, rel in placements:
        dest = work / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    dump(dict(source_root=str(src), research_executed=False, input_hashes={rel:digest(p) for p,rel in placements},
        next_command=f"{sys.executable} {work}/HOHONET_v21_reaudit_20261029/code/build_supplement_design.py"),
        work / "LAYOUT_ONLY_RECEIPT.json")
    print("Prepared only the isolated source/input layout; no design generation or fusion executed.")


def hydrate(args):
    geometry = Path(args.geometry).resolve()
    requests = Path(args.requests).resolve()
    out = Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("Restore into an empty output directory: " + str(out))
    out.mkdir(parents=True, exist_ok=True)
    with gzip.open(requests, "rt", encoding="utf-8-sig", newline="") as f:
        request_rows = list(csv.DictReader(f))
    req = {r["team_key"]: r for r in request_rows}
    assert len(req) == len(request_rows), "Duplicate frozen request keys"
    by_pool = defaultdict(list)
    seen = set()
    with gzip.open(geometry, "rt", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            key = r["team_key"]
            assert key in req and key not in seen, key
            assert r["pool_id"] == req[key]["pool_id"]
            ws = r["member_workers"]
            if isinstance(ws, str):
                ws = ws.split("|")
            assert sorted(ws) == sorted(req[key]["member_workers"].split("|"))
            assert len(ws) == int(req[key]["n"])
            assert "geometry" in r and "B8L2" in r
            seen.add(key)
            by_pool[r["pool_id"]].append(line)
    assert seen == set(req)
    geometry_sha = digest(geometry)
    for pid, lines in sorted(by_pool.items()):
        folder = out / "pools" / pid
        folder.mkdir(parents=True, exist_ok=True)
        with gzip.open(folder / "part_00001.jsonl.gz", "wt", encoding="utf-8") as f:
            f.writelines(lines)
        dump(dict(pool_id=pid, requested=len(lines), total=len(lines), complete=True,
            restored_saved_geometry=True, new_native=0, source_geometry_sha256=geometry_sha), folder / "CHECKS.json")
    dump(dict(endpoint_rows=len(seen), pools=len(by_pool), all_requests_found=True,
        input_geometry_sha256=geometry_sha, input_requests_sha256=digest(requests),
        data_unchanged=True, new_fusions=0, new_scores=0, restore_only=True), out / "RESTORE_RECEIPT.json")
    print(json.dumps(dict(restored_endpoints=len(seen), pools=len(by_pool), new_fusions=0, new_scores=0)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    a = sub.add_parser("finalize")
    a.add_argument("--delivery", type=Path, default=DEFAULT_DELIVERY)
    a.add_argument("--workspace", type=Path, default=DEFAULT_DELIVERY.parent)
    a.set_defaults(run=finalize)
    a = sub.add_parser("prepare-design-workspace")
    a.add_argument("--source-root", required=True)
    a.add_argument("--workspace", required=True)
    a.add_argument("--labels", required=True)
    a.set_defaults(run=prepare_design)
    a = sub.add_parser("hydrate-endpoints")
    a.add_argument("--geometry", required=True)
    a.add_argument("--requests", required=True)
    a.add_argument("--out", required=True)
    a.set_defaults(run=hydrate)
    args = ap.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
