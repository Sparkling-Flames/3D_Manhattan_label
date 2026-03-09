#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复ls_userscript.js，添加页面可见性检测（归档副本）

此文件为用户提供的修复脚本的归档副本。README 已声明该目录用于存放
已被替代或为历史兼容而保留的脚本。当前仓库的 `tools/ls_userscript.js`
已包含等效或更完善的可见性/计时逻辑，因此未在主脚本中应用此补丁。
"""

import os

script_path = r"d:\Work\HOHONET\tools\ls_userscript.js"

with open(script_path, "r", encoding="utf-8") as f:
    content = f.read()

# 替换1：添加isPageVisible变量和visibilitychange监听
old1 = """  const IDLE_THRESHOLD = 10 * 1000;
  let currentTaskId = null;

  // 监听用户活动
  ["mousemove", "keydown", "click", "scroll", "wheel"].forEach((evt) => {
    window.addEventListener(
      evt,
      () => {
        lastActivityTime = Date.now();
      },
      true
    );
  });"""

new1 = """  const IDLE_THRESHOLD = 10 * 1000;
  let currentTaskId = null;
  let isPageVisible = true;

  // 检测页面可见性（用户切换标签页时暂停计时）
  document.addEventListener("visibilitychange", () => {
    isPageVisible = !document.hidden;
    if (isPageVisible) {
      // 用户切回来时，重置活动时间，避免累积背景时间
      lastActivityTime = Date.now();
    }
  });

  // 监听用户活动
  ["mousemove", "keydown", "click", "scroll", "wheel"].forEach((evt) => {
    window.addEventListener(
      evt,
      () => {
        if (isPageVisible) {
          lastActivityTime = Date.now();
        }
      },
      true
    );
  });"""

content = content.replace(old1, new1)

# 替换2：更新计时器逻辑
old2 = """  // 累积活动时间的计时器
  setInterval(() => {
    if (Date.now() - lastActivityTime < IDLE_THRESHOLD) {
      activeSeconds += 1;
    }"""

new2 = """  // 累积活动时间的计时器（仅在页面可见且有活动时累积）
  setInterval(() => {
    if (isPageVisible && Date.now() - lastActivityTime < IDLE_THRESHOLD) {
      activeSeconds += 1;
    }"""

content = content.replace(old2, new2)

with open(script_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✓ 已成功添加页面可见性检测（归档副本已写入 tools/ls_userscript.js ）")
print("  - 注意：仓库中的主脚本已包含类似/更完善逻辑，本文件作为归档保存")
