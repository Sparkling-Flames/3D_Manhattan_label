# 本地与云端合并独立审核

先读 REVIEW_ZH.md。它回答研究做到了哪里、idea已获得哪些支持、什么尚未证实、当前改动，以及本轮新增实测。

## 内容

- LOCAL_VERIFICATION.txt：本地20项测试、版本与工作树证据边界
- independent_experiment/：新增同坐标块保持敏感性，完整代码、紧凑输入及30域结果；可以独立运行
- reproduction/：原云端25项测试、98工件重放与独立合法性核查证据
- source_crosscheck/：不可变源75行诊断和人工真源核对
- PROVENANCE.json：版本、来源时间与验证范围
- MANIFEST_SHA256.json：本包所有其他文件的SHA-256

## 先复算新增实验

进入 independent_experiment，安装其中 requirements.txt（仅NumPy），运行：

```
python run_sensitivity.py --source portable_source --out NEW_results
```

NEW_results必须不存在。不需要原图、GT、网络或原30MB账本。

## 原交付完整复算

解压已有 point_correspondence_20261006_delivery.zip，设PACKAGE为解压后的point_correspondence_20261006目录。需要该包requirements中的NumPy、SciPy、pytest。

```
bash reproduction/run.sh --source "$PACKAGE" --work NEW_replay
python reproduction/verify_artifacts.py --source "$PACKAGE" --replay NEW_replay/results
python reproduction/verify_raw_geometry.py --source "$PACKAGE" --replay NEW_replay/results
```

## 源75行交叉检查

```
python source_crosscheck/check_full_source_audit.py --source-audit source_crosscheck/source_audit.json --human-review source_crosscheck/human_review.json --delivery "$PACKAGE" --out NEW_source_check.json
```

原始/派生支持计数、组合状态、扰动复制均不等于独立真人样本。可复现数值不等于已验证语义或总体效果。没有修改或发布远程代码、原数据或正式资格。
