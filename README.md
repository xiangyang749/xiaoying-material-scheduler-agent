# 素材审核与发布排期 Agent

小影校招 AI Agent 开发岗位，第 1 题。提供 CLI：读取素材、审核、查询时段、保存排期草稿。
真实模型使用 DeepSeek Function Calling；另有无需联网、无需密钥的 Mock 入口。

**只保存草稿。`ready` 代表草稿具备排期条件，`pending_confirmation` 代表替代时间待用户确认；两者都不是已发布。**

本机验证：28 项自动化测试通过，10 组真实 DeepSeek 场景和 10 组离线场景的业务断言全部通过。

## 快速运行

Python 3.10+，无第三方依赖。在本目录执行：

```powershell
python -m src.main --input examples/normal.input.json
python -m src.main --input examples/conflict.input.json
python -m unittest discover -s tests -v
python -m src.evaluate --mode mock
```

本机已用 Anaconda 的 `guohaiyu` 环境验证。可以先 `conda activate guohaiyu`，再执行上述命令。
依赖声明见 `requirements.txt`。Mock 无须环境变量；`pip install -r requirements.txt` 不会安装外部包。
CLI 默认将草稿持久化到当前目录 `drafts.sqlite`，可用 `--db path.sqlite` 指定独立数据库。
评估命令每个场景使用独立临时数据库，重复提交场景在同一个数据库执行两次。

## DeepSeek 真实运行

在环境变量设置 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_MODEL=deepseek-flash`。
也可以将 `.env.example` 所描述的配置写入私密 `config.local.json`：

```json
{"api_key":"<your-key>","base_url":"https://api.deepseek.com","model":"deepseek-flash"}
```

```powershell
python -m src.main --mode live --config config.local.json --input examples/conflict.input.json
python -m src.evaluate --mode live --config config.local.json
```

配置也可位于仓库外：将 `--config` 指向其绝对路径。环境变量优先于 JSON 中的同名值。
本程序不自动加载 `.env`。私密 JSON、`.env` 和数据库已在 `.gitignore` 排除。
真实模式每个模型请求超时 30 秒，不可用时返回 `model_error`，**不会偷偷退回 Mock**。
评估会产生实际 API 费用，输入均为合成素材；默认不执行任何真实发布动作。

## 评审入口

- [需求与验收点](docs/01-requirements.md)
- [动态决策和工程设计](docs/02-solution.md)
- [预期、实际结果和限制](docs/03-evaluation.md)
- [AI 使用及个人贡献边界](docs/04-ai-usage.md)
- [复盘、用时与改进](docs/05-retrospective.md)
- [自动化测试实际记录](examples/test-results.txt)
- [真实 DeepSeek 评估摘要](examples/live-summary.json)
- [离线 Mock 评估摘要](examples/mock-summary.json)

`examples/live-*.output.json` 包含本次实际模型调用的工具选择、参数、结果、简短决策依据和数据库行数。
`examples/mock-*.output.json` 为确定性测试替身产生的运行记录，只证明业务流程和防护可执行。
两个模式均可通过 `src.evaluate` 重新生成，不手写或伪造 Trace。

## 输入与输出

输入样例见 `examples/*.input.json`。支持一次请求中 1-20 个不重复素材 ID，逐项处理，共享草稿数据库。
每项输出包含审核状态/原因、原要求时间、建议时间、待确认项、保存状态、数据库回执和执行状态。
时间必须包含时区。数据库统一按 UTC 存储，`suggested_at` 按请求的时区展示。
`--max-steps` 默认 10，允许 1-30；每项素材最多调用该次数的模型和工具，无无限重试。

请求 ID 是幂等键的一部分：相同请求 ID 和素材 ID、相同输入仅保存一次；复用 ID 修改输入会被拒绝。
同意替代时间时创建**新请求 ID**，并在 `approved_slots` 明确列出同意的时间，参考 `examples/confirmed.input.json`。
旧的待确认草稿保留为审计资料；它不占用正式时段，不自动升级为确认草稿。

`execution_status=finished` 表示本次决策已结束，业务仍可能是 `blocked`、`needs_information` 或 `save_failed`。
CLI 在业务已结束时退出码为 0；输入错误、模型失败、步数耗尽或无效模型输出时退出码为 2。
必须结合 `status` 和 `draft_save_status` 判断是否保存成功，不能只看退出码。

## 修改占用时段与模拟故障

修改 `data/catalog.json` 的 `occupied` 后重新运行，或者使用 `--fixture` 指向另一份合成目录。

```powershell
python -m src.main --input examples/normal.input.json --db failure-test.sqlite --fail-save
python -m src.main --input examples/normal.input.json --db limit-test.sqlite --max-steps 2
```

`--fail-save` 是显式测试故障注入。已有同一幂等键的草稿会优先返回原回执，故演示保存失败时请使用新数据库。

## 技术取舍与参考

采用 Python 标准库、SQLite 和原生工具调用循环，没有使用 ADK/AgentScope/LangGraph。
运行时版本由 `python --version` 和 `sqlite3.sqlite_version` 查看；本次环境和限制见评估文档。
参考了[官方提交目录示例](https://github.com/lwz1357/agent-campus-submission-example)的交付要求，未复制其业务实现。
DeepSeek 工具协议依据 [Function Calling 官方文档](https://api-docs.deepseek.com/guides/tool_calls)和[Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion)，经 Context7 查询。

## GitHub 提交

提交第 1 题、仓库 URL 和包含所有验证材料的最终 commit SHA。私有仓库需按题目要求配置评审可读权限。
此目录是交付项目；尚未指定 GitHub 目标仓库时，不应把本地实现称为已提交。
