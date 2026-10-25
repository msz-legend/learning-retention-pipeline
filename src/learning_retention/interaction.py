PHASE_LABELS = {
    "decompose": "技能拆解阶段",
    "cognitive": "认知阶段",
    "associative": "联结阶段",
    "autonomous": "自动化阶段",
    "retention": "保持阶段",
    "completed": "已完成",
}


def parse_signal(text: str) -> str | None:
    signals = {
        "太难了": "too_difficult", "太简单了": "too_easy", "没时间": "no_time",
        "暂停": "pause", "继续": "resume", "我学到哪了": "progress",
        "我想继续保持": "upgrade", "我不想保持了": "downgrade", "我懂了": "claims_understanding",
    }
    return next((signals[phrase] for phrase in sorted(signals, key=len, reverse=True) if phrase in text), None)


def progress_summary(state: dict) -> str:
    phase = PHASE_LABELS.get(state.get("current_phase"), "未知阶段")
    mode = "只学模式" if state.get("learning_mode") == "learn" else "学习加保持模式" if state.get("learning_mode") == "learn_retain" else "尚未选择模式"
    subskills = state.get("subskills", [])
    mastered = sum(1 for item in subskills if item.get("mastery_level", 0) >= 0.8)
    next_action = "先确认学习模式和技能拆解" if state.get("current_phase") == "decompose" else "完成一个无提示练习"
    return f"你现在处于{phase}，是{mode}；已达到自动化阈值的子技能为 {mastered}/{len(subskills)}。下一步建议：{next_action}。"
