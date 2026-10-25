# LRP v0.1.0 端到端验收报告

## 测试入口

```text
python -m unittest discover -s tests -p 'test_lrp_*.py'
```

## 结果

- TASK-04：模式选择、拆解确认、阶段出口：通过
- TASK-05：先输出后反馈、最多两个错误、mastery 更新：通过
- TASK-06：依赖门控、间隔、提取、变式、交错、留出任务去重：通过
- TASK-07：真实任务出口、learn/completed、learn_retain/retention：通过
- TASK-08：保持剂量、到期调度、退化补丁和用户确认：通过
- TASK-09：Wiki append-only、提案快照、留出门控和回滚状态：通过
- TASK-10：字段、日期、依赖、阶段/模式互斥校验：通过
- TASK-11A：跨会话核心双模式验收：通过
- TASK-11B：自然语言信号、升级/降级、completed 无保持压力：通过

## GA 证据映射

| 验收项 | 证据 |
|---|---|
| GA-01/04/05/06 | `tests/test_lrp_task04.py`, `test_lrp_task06.py`, `test_lrp_task08.py`, `test_lrp_task09.py` |
| GA-02/03/07 | `tests/test_lrp_state.py`, `test_lrp_task05.py`, SKILL.md word-count check |
| GA-08/09/10/11/13/14 | `tests/test_lrp_task04.py`, `test_lrp_task05.py`, `test_lrp_task11b.py` |
| GA-12/15/16 | `tests/test_lrp_task07.py`, `test_lrp_task08.py`, `test_lrp_task11a.py`, `test_lrp_task11b.py` |

## 验收边界

外部通知投递不属于 v0.1.0 核心验收；核心只提供到期状态、会话内检查和提醒模板。
