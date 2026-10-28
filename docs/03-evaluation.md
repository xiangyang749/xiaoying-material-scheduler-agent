# 03 效果验证与已知限制

## 环境与方法

2026-10-28 在 Windows、Anaconda `guohaiyu`、Python 3.11.11 上执行。
真实模型为 `deepseek-flash`，官方接口；业务工具使用合成元数据和本地 SQLite，不连接真实发布平台。
最终本机结果：28 项自动化测试全部通过；离线 10/10 场景、真实 DeepSeek 10/10 场景通过各自业务断言。
本轮真实场景测得耗时合计 62.837 秒，其中重复提交场景包括两次 Agent 执行。
`python -m src.evaluate --mode mock` 和 `python -m src.evaluate --mode live --config <私密配置路径>` 会逐场景实际运行，独立断言输出状态、数据库行数和时段边界。
真实路径存在随机性，一次通过不代表大样本稳定性。每次重跑会覆盖相应模式下的最新记录，提交前应检查结果。
GitHub Actions 工作流已提供 Windows/Linux、Python 3.10/3.11 测试矩阵，但远程 CI 尚未运行；不把本机通过等同于所有矩阵已通过。

## 预期与证据

- 正常：`ready`，20:00，一份草稿。实际结果见 [live-normal](../examples/live-normal.output.json)。
- 信息不足：M02 缺 rights，`needs_information`，零草稿。见 [live-missing](../examples/live-missing.output.json)。
- 规则风险：禁止用语，`blocked`，零草稿。见 [live-risk](../examples/live-risk.output.json)。
- 时间冲突：18:00 已占，建议 19:00，`pending_confirmation`。见 [live-conflict](../examples/live-conflict.output.json)。
- 重复提交：同一输入连续运行两次，相同草稿 ID、第二次 `duplicate=true`，数据库一行。见 [live-duplicate](../examples/live-duplicate.output.json)。
- 保存失败：显式注入 `save_failed`，零草稿，`draft_save_status=failed`。见 [live-save-failure](../examples/live-save-failure.output.json)。
- 修改占用：18:00、19:00 均占用，建议 20:00，仍待确认。见 [live-changed-conflict](../examples/live-changed-conflict.output.json)。
- 用户确认：输入明确同意 19:00，`ready`。见 [live-confirmed](../examples/live-confirmed.output.json)。
- 无可用时间：`no_available_slots`，提示提供新时间窗口，零草稿。见 [live-no-slots](../examples/live-no-slots.output.json)。
- 步数耗尽：上限设为 2，`incomplete` / `step_limit`，零草稿。见 [live-step-limit](../examples/live-step-limit.output.json)。

每个实际输出包含 `checks` 布尔断言和 `database_row_count`，无需依赖截图判断是否通过。
汇总结果见 [live-summary](../examples/live-summary.json) 与 [mock-summary](../examples/mock-summary.json)，自动化测试实际记录见 [test-results](../examples/test-results.txt)。
`elapsed_seconds` 是本次端到端测量时长，包含模型网络等待；不将单次时长推断为性能承诺。

## 失败与修正

第一轮测试出现 Windows `WinError 32`：测试辅助 `count()` 使用 SQLite 上下文管理器后未关闭连接。
修正为 `contextlib.closing` 显式关闭连接，重跑测试通过。业务存储层本身已显式关闭连接。
另补充了模型过早 `finish` 的防护，只有有审核结论、保存回执或确无空档时允许结束；补充时区等价输入测试。

## 局限

1. 合成元数据规则不是视频内容审核模型，没有 OCR、视觉或音频识别；风险规则不证明实际内容审核准确率。
2. 有限真实测试没有覆盖所有模型输出、攻击或网络异常，不能声称生产鲁棒性或 100% 模型成功率。
3. 无发布接口、无登录鉴权；确认数据由 CLI 输入提供，生产服务需要绑定用户身份。
4. 只比较时点冲突。每日发文限额、视频时长区间、跨账号资源和节假日规则不在范围内。
5. 无确认草稿的原地升级，确认需要新请求。待确认草稿不保留独占时段，确认时仍可能冲突。
6. 本地目录是运行期间的资料快照；并发外部排期变更尚未接入同一事务，只能对本地正式草稿保证唯一性。
7. 仅支持非推理模式公开工具消息，不持久化 reasoning_content，不承诺兼容所有 API 供应商。
8. 每素材有步骤上限；批量最多 20 项，按顺序执行，没有总请求秒级 SLA 或中断后恢复能力。
