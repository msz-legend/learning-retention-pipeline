# 使用示例

## 只学习掌握

1. 用户说：`我想学 Python 数据分析`。
2. Skill 依次确认目标、场景、基础、时间、输出方式，并要求明确选择 `learn`。
3. 用户确认拆解后，按认知 → 联结 → 自动化推进。
4. 真实任务通过后进入 `completed`；不会创建保持队列、`retention_due` 或主动提醒。

## 学习加长期保持

1. 用户在首次会话明确选择 `learn_retain`。
2. 自动化真实任务通过后，Skill 建立至少 3 个留出任务和保留测试基线。
3. 进入 `retention`，按到期日期和技能类型安排最低剂量练习。
4. 保留测试退化时，先生成补丁提案；用户确认且留出任务严格优于基线后才采纳。

## 本地 CLI

```text
python learning-retention-pipeline/scripts/lrp.py init "Python data analysis" --context '{"goal":"complete a real analysis"}'
python learning-retention-pipeline/scripts/lrp.py load python-data-analysis
python learning-retention-pipeline/scripts/validate-state.py path/to/progress-state.json
```

运行状态默认存储在用户数据目录；设置 `LRP_DATA_DIR` 可覆盖。Skill 文档负责自然语言交互，CLI 只负责确定性状态操作。
