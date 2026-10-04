# 人员复算审核便携子包

先读《审核结论_ZH.md》，最终机器结论在audit/audit_final_results.json。

包含作者必要代码、inputs、tests和完整结果（含两图NPZ），以及本审核所用的最小文件级旧B输入。无下载helper或传输元数据，无重复replay结果副本。完整结果保留是为了对每个真实六人集合进行直接比较。

## 复算

使用兼容Python环境。依赖版本见author_bundle/requirements.txt。首次可在自己创建的虚拟环境安装这些正规科学计算依赖；脚本不会自行安装、更换或降级依赖。

从任意目录运行：

```bash
bash /path/to/personnel_repro_audit_20261004/reproduce.sh /absolute/path/to/NEW_output
```

所有新输出写NEW_output，不覆盖本包。脚本运行作者35tests、11-stage pipeline、独立输入/隔离/公式/全六人核验以及固定GEOS回归例，再保留并消歧首轮诊断。最终摘要有一项特定GEOS路径限制，不能将其误判成作者结果错误。

打包的旧GEOS证据来自单独NumPy1.26.4+Shapely2.0.4环境；默认复算不会修改你当前环境，仅读取这份已冻结对照证据。若要亲自重跑旧环境，请单独安装兼容依赖后运行：

```bash
/path/to/old-env/python audit/resolve_overlay.py --bundle author_bundle --out /path/to/NEW_old_overlay
```

然后finalize_audit.py的--old-evidence可传NEW_old_overlay/overlay_resolution.json。不同GEOS版本可能不再复现该数值缺陷；finalize脚本的固定断言会因此提醒环境差异，不表示作者失败。

checksum_manifest.json是本审核子包的校验清单；作者自有清单在author_bundle/MANIFEST.sha256.json。原始作者交付声明与审核断言区分保留。
