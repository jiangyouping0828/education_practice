# -*- coding: utf-8 -*-
"""业务规则引擎（core.rules）

申请材料的合规判定权在代码，不在模型：模型只负责收集字段，
本模块给出唯一权威的校验结论。条款出处 = 示例制度文档，
制度更新由管理员维护文档后同步调整此处的阈值与路由。

required 元素：(字段名, 中文标签, 最小字数)；min_len=0 表示只要求非空。
"""
from typing import Callable, Optional

# ---- 四类申请的规则定义 ----------------------------------------------------

APPLY_RULES: dict[str, dict] = {
    "leave": {
        "name": "请假申请",
        "required": [
            ("start_date", "开始日期", 0),
            ("end_date", "结束日期", 0),
            ("reason", "请假事由", 4),
        ],
        # 依据《实习制度示例.md·考勤与请假》：1~3 天导师审批，超 3 天报学校教师
        "route": lambda days: ("企业导师审批" if days <= 3
                               else "企业导师审批 → 学校实习指导教师审批"),
        "source": "实习制度示例.md·考勤与请假",
    },
    "transfer": {
        "name": "换岗申请",
        "required": [
            ("current_position", "现岗位", 0),
            ("target_position", "目标岗位", 0),
            ("reason", "换岗原因", 4),
            ("expected_date", "期望生效日期", 0),
        ],
        # 依据《实习制度示例.md·换岗流程》：换岗自备案完成之日起生效
        "route": lambda days: "企业导师同意 → 学校实习指导教师备案",
        "source": "实习制度示例.md·换岗流程",
    },
    "weekly_report": {
        "name": "实习周报",
        # 依据《实习制度示例.md·周报填报规范》：总结≥30字、计划≥10字
        "required": [
            ("week_number", "周次", 0),
            ("work_summary", "本周工作总结", 30),
            ("next_plan", "下周工作计划", 10),
        ],
        "route": lambda days: "企业导师评阅",
        "source": "实习制度示例.md·周报填报规范",
    },
    "daily_log": {
        "name": "实习日志",
        # 依据《实习制度示例.md·实习日志提交标准》：内容≥50字、工时≤8
        "required": [
            ("log_date", "日期", 0),
            ("content", "当日实习内容", 50),
            ("duration_hours", "当日工时", 0),
        ],
        "route": lambda days: "企业导师月度核查签字",
        "source": "实习制度示例.md·实习日志提交标准",
    },
}

# ---- 类型专属硬阈值（超出即拒绝，提示词改不动）----------------------------

LEAVE_MAX_DAYS = 30          # 请假单次上限
WORK_HOURS_RANGE = (0.0, 8.0)  # 实习日志单日工时区间（开闭区间：0 < h <= 8）

SUPPORTED_TYPES = "、".join(f"{k}（{v['name']}）" for k, v in APPLY_RULES.items())


def days_between(d1: str, d2: str) -> Optional[int]:
    """计算两个 YYYY-MM-DD 日期的间隔天数（含首尾，+1）；格式非法返回 None。"""
    import datetime
    try:
        a = datetime.date.fromisoformat(d1)
        b = datetime.date.fromisoformat(d2)
        return (b - a).days + 1
    except (ValueError, TypeError):
        return None


def validate_payload(apply_type: str, payload: dict) -> dict:
    """纯规则校验（模型只负责收集字段，判定权在代码）：返回 valid / missing / warnings。

    校验维度：必填齐备 → 最小字数（防"内容空洞"）→ 类型专属规则（日期/工时上限）。
    """
    rule = APPLY_RULES.get(apply_type)
    if not rule:
        return {"valid": False, "missing": [],
                "message": f"不支持的申请类型：{apply_type}（可选：{SUPPORTED_TYPES}）"}
    missing, warnings = [], []
    for key, label, min_len in rule["required"]:
        val = str(payload.get(key) or "").strip()
        if not val:
            missing.append(label)
        elif min_len and len(val) < min_len:
            missing.append(f"{label}（不少于 {min_len} 字，当前 {len(val)} 字）")
    if apply_type == "leave" and not missing:
        n = days_between(payload["start_date"], payload["end_date"])
        if n is None:
            missing.append("日期格式（应为 YYYY-MM-DD）")
        elif n <= 0:
            missing.append("结束日期（不能早于开始日期）")
        elif n > LEAVE_MAX_DAYS:
            return {"valid": False, "missing": missing,
                    "message": f"请假 {n} 天超出单次上限 {LEAVE_MAX_DAYS} 天"
                               f"（依据：{rule['source']}），超出部分需另行办理"}
    if apply_type == "daily_log" and not missing:
        try:
            hours = float(payload["duration_hours"])
            if not (WORK_HOURS_RANGE[0] < hours <= WORK_HOURS_RANGE[1]):
                missing.append(f"当日工时（须在 {WORK_HOURS_RANGE[0]:g}~{WORK_HOURS_RANGE[1]:g} 之间，"
                               f"当前 {payload['duration_hours']}，依据：{rule['source']}）")
        except (TypeError, ValueError):
            missing.append("当日工时（应为数字）")
    if not missing:
        n = days_between(payload.get("start_date", "2000-01-01"),
                         payload.get("end_date", "2000-01-02")) or 1
        return {"valid": True, "missing": [], "warnings": warnings,
                "route": rule["route"](n), "source": rule["source"]}
    return {"valid": False, "missing": missing,
            "message": "存在不合规项：" + "、".join(missing) + "。请向用户追问或说明，禁止代填。"}
