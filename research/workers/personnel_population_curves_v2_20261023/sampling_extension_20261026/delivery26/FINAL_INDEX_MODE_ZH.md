# 交付入口的阶段模式与最终模式

`update_delivery_index.py`只根据已有真实保存回执及读回记录整理入口，不上传、不下载、不做研究计算。

## 阶段模式保持兼容

```bash
python delivery26/update_delivery_index.py --base "$STUDY"
```

默认仍输出阶段入口，按现有真实ZIP回执更新已保存数量。即使最终独立文件清单已经存在，也不会自动切换采用状态。CSV原九列保留名称和顺序，末尾增加`artifact_kind`、`role`、`download_verified`；旧程序可继续按原列名读取。

## 填写独立附件清单

将`FINAL_INDIVIDUAL_DELIVERIES.template.json`复制为同目录的`FINAL_INDIVIDUAL_DELIVERIES.json`。模板不填任何身份、大小、hash或成功状态。每份独立附件实际保存且取回检查后，再填写：

- `filename`：实际交付文件的basename；`library_file_id`：工具返回的真实身份。
- `delivered_version`：实际版本号；首次保存可以为0，不能把未知版本猜作0。
- `bytes`、`sha256`：实际取回附件的字节数与SHA256。
- `save_status="succeeded"`与`download_verified=true`：仅在真实保存及取回核验后填写。
- 恰好一项`role="primary_report"`，用于入口顶部的最新综合报告；至少一项`role="key_table"`。其余可用`report`、`table`、`figure`、`code`或`other`。
- `download_url`可保持null，脚本按真实身份构造链接；如填写，必须与身份一致。

最后设置`ready_for_final=true`。若当前保存了多个不同文件名的S10或S11，用`final_packages.S10/S11`指定采用的真实ZIP文件名；各自只有一个时可保持null。清单由根任务填入实际核验结果，脚本不会凭本地预览或报告数字补造身份。

## 显式最终切换

```bash
python delivery26/update_delivery_index.py --base "$STUDY" --final
```

切换前必须全部满足：

1. 选定S10和S11均有成功UPLOAD／SAVE回执与实际`*DOWNLOADED_ZIP_READBACK.json`，全部成员及内部gzip已读至EOF，bytes及SHA有效。
2. 全部已闭合DATA包均有真实保存身份和下载读回，下载ZIP的bytes/SHA与`PACKAGE_COMPLETE.json`一致。
3. DATA的`unique_new_endpoint_records`合计恰为1,356,657。
4. 最终独立附件清单完成，报告、小表的真实身份、版本、bytes、SHA及下载核验字段齐全。

任一项缺失，脚本在写入`CURRENT_VALID_FILES.csv`和`CURRENT_ENTRY_ZH.md`前退出；未填模板不能启用最终模式。`--final`不会执行上传或替用户完成下载核验。

最终入口顶部给出独立综合报告和关键表。最少阅读／汇总接入组合为S10+S11；完整路径复算另加S01、全部DATA以及固定main历史输入。S00/S04标为历史检查点，S05保留完整策略阶段身份，S10为当前采用代码；六小池与两个案例包仍保留独立复算用途。

独立附件的`downloaded_inner_tables_verified`留空，因为它们不是ZIP；其实际取回核验使用统一`download_verified`字段，不冒称每份报告都存在内部gzip。
