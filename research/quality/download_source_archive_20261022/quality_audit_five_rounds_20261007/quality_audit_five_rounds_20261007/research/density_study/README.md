# 密度不变性研究：三轮条件测量压力测试

这不是自动修复、融合、更换GT、重新裁决人员资格或删点工具。只读原包，输出研究副本；原ID以expression_id保留，各派生保持不独立、不投票状态。

## 运行

需要Python 3、numpy、scipy、shapely、pandas。原来源包的src/和vendor/完整保留于--source指定目录。扩大输入包由--expanded指定。默认输出在脚本所在目录。

    python round_a.py --source /path/to/quality_deep_20261007 --expanded /path/to/expanded_input --out /path/to/density_results
    python round_b.py --source /path/to/quality_deep_20261007 --expanded /path/to/expanded_input --out /path/to/density_results
    python verify_invariance.py --source /path/to/quality_deep_20261007 --expanded /path/to/expanded_input --out /path/to/density_results
    python verify_intrinsic.py --source /path/to/quality_deep_20261007 --expanded /path/to/expanded_input --out /path/to/density_results
    python round_c.py --source /path/to/quality_deep_20261007 --expanded /path/to/expanded_input --out /path/to/density_results

round_c.py完成后，可再运行summarize.py生成共同成功/图/建筑汇总，以及retry_solver_failures.py复试原求解失败；同样支持三个路径参数。verify_delivery.py提供轻量交付验收。

本次环境的第三方依赖放在额外PYTHONPATH中；普通已安装依赖的Python不需要该环境路径。单线程BLAS可用OPENBLAS_NUM_THREADS=1稳定复算资源使用。默认目录假设研究文件夹与unpacked/处于同一总包目录，也可显式指定路径。脚本不会读取图片；本研究只对已保存的坐标和资格/场景元数据进行计算，不声称新增了原图人工审核。

## 三轮问题

- A：同三维边界精确细分，固定轴后原等节点拟合测量是否改变？见ROUND_A_ZH.md
- B：连续边界目标和无几何作用参数的规范化能否消除密度效应？见ROUND_B_ZH.md
- C：扩大真实面板上，表示稳定性与参考准确性是否是不同收益？见ROUND_C_ZH.md

输入原件在原路径只读。源码、输入SHA和环境证据见provenance.json；匿名选样见每轮inputs.json。几何单位均为相机高度h或角度，不是实测米。重复派生和多个GT版本不当作独立样本；GT版本分别报告。模型适用性未知不改写为适用。
