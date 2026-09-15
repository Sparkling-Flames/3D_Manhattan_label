# 复算

在包含repo/的完整包中进入repo目录，Python 3.13；先在独立环境安装requirements-image-links.txt。

```bash
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
M=tools.thesis_main.analysis.image_portrait
python -m $M.image_links_followup_prepare
python -m $M.image_links_followup_predict --workers 3
python -m $M.image_links_followup_associations
python -m $M.image_links_followup_people
python -m $M.image_links_followup_oos_feedback
python -m $M.image_links_followup_transfer
python -m $M.image_links_followup_synthesis
python -m $M.image_links_followup_figures
python -m $M.image_links_followup_report
python -m pytest tests/test_image_links_followup.py -q
```

这些命令读取真实数据与已验证的冻结模型数值；不下载原图或权重。重新拟合预测时，仅删除本版本prediction/candidates和prediction/inner再运行predict；其余旧结果保持。

旧逐通道z-score未复现；用户已审核目标未提供；这些不是通过包内测试得到的结论。
