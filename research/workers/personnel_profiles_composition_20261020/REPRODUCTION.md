# 精简包如何复用与复现

本包不是完整外部交付的镜像。选入/省略以CURATION.csv为准；source内原README、字段说明和代码保留原样，所以其中部分默认字体、原图、次级输出路径不在本包内。下面说明实际依赖。

## 最小接入刷新

从仓库根目录运行：

```powershell
D:/anaconda/python.exe research/workers/personnel_profiles_composition_20261020/integrate.py
```

只读取本精简包source表和案例，重建tables/、INTEGRATION.json及CHECKS.json；不需要原外部下载目录，不重跑融合。首次选取原包时可传`--source`指向原包根目录，但本轮已完成，无需重复复制。只需要现有pandas、Python标准库；接入不需要字体、原图下载或HTTP服务器。

## 画像、组合及精选团队的研究重建

原始生成代码按相对结构保留在source/code/；机制代码在source/mechanisms/code/。依赖版本在source/requirements.txt及source/mechanisms/requirements.txt。现有仓库须具备：

- `research/statistics/v2_integrated_analysis_20261019/tables.json.gz`与逐份v2证据；这些是版本绑定的个体分数/时间/资格输入，不代表再次运行原始日志或个体评分。
- `research/difficulty/difficulty_mechanisms_v2_20261020/record_conditions.csv.gz`及既有几何定义。
- 既有融合引擎、INPUT_SNAPSHOT及source/provenance/source_index.csv列出的仓库代码/输入。目录不替代这些依赖，也未随本包复制仓库副本。

源代码与表格的研究身份沿用原包所记研究版本；本轮不另行算哈希，也不把当前仓库状态视为未来永久兼容保证。若重建全搜索，应写独立输出目录，不覆盖归档回执或称新缓存运行是原初计算。

以下命令是可用入口说明；本次未执行全研究或这些团队重放：

```powershell
# 仓库根目录；结果写独立目录，避免覆盖归档。
python research/workers/personnel_profiles_composition_20261020/source/code/profiles/build_profiles.py --repo . --out output/personnel_profiles_rebuild
python research/workers/personnel_profiles_composition_20261020/source/code/replay_claim_teams.py --repo . --claims research/workers/personnel_profiles_composition_20261020/source/claims/claim_teams.json.gz --limit 12 --out output/personnel_claim_replay.json
```

画像原生成器会再次写出逐字审核理由等文件，**其重建目录不能直接视作可公开归档**；发布时仍沿用本包的选取与字段边界。全量prepare/run/analyze的参数、种子和请求复制办法见source/README.txt、source/notes/REPRO_NOTES.txt及source/provenance注册文件。精确请求在source/design，主要结论成对底表与15404个精确团队成员/标量在source/claims。保留请求使搜索可重建，不等于本包包含全部88048队几何。

## 字体、原图与已存展示

原图引用见tables/image_references.csv：六个仓库路径本地可用；未来未物化时按其中Release链接及archive文件名获取。不要下载整个原图全集来重画这几个例子。

本包不复制两份字体。只看现成PNG/PDF/离线卡片无需安装字体；重绘时给原脚本`--font`显式指定现有中文字体，例如Windows的`C:/Windows/Fonts/msyh.ttc`。原报告/机制脚本可接字体路径，但本轮未逐一验收所有重绘命令；报告默认font子目录缺失是有意省略，不能直接照搬完整包的默认命令。

原始渲染器需`--repo`及`--photo`，photo使用tables/image_references.csv的source_path，而非缺省的source/mechanisms/images。图例和原始处理点、参考与JSON几何已经保存，不必为了展示再跑融合。源机制脚本的Linux临时目录默认值可在Windows重画前用MPLCONFIGDIR指向用户自行选择的可写临时目录；本次没有执行这些脚本或遗留服务。

只有source/personnel_cards.html是原有自包含离线页；本次不创建新的研究台。研究台线程读取INTEGRATION.json后，需独立完成实际页面接入与交互验收。
