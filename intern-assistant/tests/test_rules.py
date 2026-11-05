# -*- coding: utf-8 -*-
"""业务规则引擎测试：30 天上限、字数阈值、工时区间、审批路由。

阈值取自 core/rules.py，与《实习制度示例.md》条款一一对应。
"""

import os
import sys

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from intern_assistant.core.rules import APPLY_RULES, days_between, validate_payload


class TestDaysBetween:
    def test_same_day_counts_as_one(self):
        assert days_between("2026-11-10", "2026-11-10") == 1

    def test_inclusive_range(self):
        assert days_between("2026-11-10", "2026-11-12") == 3

    def test_invalid_format_returns_none(self):
        assert days_between("11月10日", "2026-11-12") is None

    def test_reversed_range_negative(self):
        assert days_between("2026-11-12", "2026-11-10") < 0


class TestLeave:
    def _payload(self, **kw):
        p = {"start_date": "2026-11-10", "end_date": "2026-11-12", "reason": "感冒发烧需要就医休息"}
        p.update(kw)
        return p

    def test_three_days_valid(self):
        r = validate_payload("leave", self._payload())
        assert r["valid"] is True
        assert r["route"] == "企业导师审批"

    def test_four_days_routes_to_school(self):
        r = validate_payload("leave", self._payload(end_date="2026-11-13"))
        assert r["valid"] is True
        assert "学校实习指导教师" in r["route"]

    def test_over_30_days_rejected(self):
        r = validate_payload("leave", self._payload(end_date="2026-12-20"))
        assert r["valid"] is False
        assert "30" in r["message"]

    def test_end_before_start_rejected(self):
        r = validate_payload("leave", self._payload(end_date="2026-11-09"))
        assert r["valid"] is False
        assert any("结束日期" in m for m in r["missing"])

    def test_short_reason_rejected(self):
        r = validate_payload("leave", self._payload(reason="感冒"))
        assert r["valid"] is False
        assert any("不少于 4 字" in m for m in r["missing"])

    def test_missing_field_rejected(self):
        r = validate_payload("leave", {"start_date": "2026-11-10"})
        assert r["valid"] is False
        assert "结束日期" in r["missing"] and "请假事由" in r["missing"]


class TestWeeklyReport:
    def test_summary_below_30_chars_rejected(self):
        r = validate_payload("weekly_report", {
            "week_number": "3", "work_summary": "本周完成了点检。",
            "next_plan": "继续点检工作并学习新设备"})
        assert r["valid"] is False
        assert any("不少于 30 字" in m for m in r["missing"])

    def test_plan_below_10_chars_rejected(self):
        r = validate_payload("weekly_report", {
            "week_number": "3",
            "work_summary": "本周完成设备点检共二十三台次，并协助导师完成月度保养计划。",
            "next_plan": "继续点检"})
        assert r["valid"] is False
        assert any("不少于 10 字" in m for m in r["missing"])

    def test_valid_report(self):
        r = validate_payload("weekly_report", {
            "week_number": "3",
            "work_summary": "本周完成设备点检共二十三台次，并协助导师完成月度保养计划与备件盘点。",
            "next_plan": "继续点检工作，学习新设备的润滑标准并整理记录"})
        assert r["valid"] is True
        assert r["route"] == "企业导师评阅"


class TestDailyLog:
    def _payload(self, **kw):
        p = {"log_date": "2026-11-10",
             "content": "上午跟随导师巡检二号车间设备并逐台记录运行参数、温度与振动情况，下午参与三号线的月度润滑保养并负责整理保养台账与签字确认。",
             "duration_hours": "6"}
        p.update(kw)
        return p

    def test_content_below_50_chars_rejected(self):
        r = validate_payload("daily_log", self._payload(content="今天巡检了设备。"))
        assert r["valid"] is False
        assert any("不少于 50 字" in m for m in r["missing"])

    def test_hours_over_8_rejected(self):
        r = validate_payload("daily_log", self._payload(duration_hours="9"))
        assert r["valid"] is False
        assert any("工时" in m for m in r["missing"])

    def test_hours_zero_rejected(self):
        r = validate_payload("daily_log", self._payload(duration_hours="0"))
        assert r["valid"] is False

    def test_hours_non_numeric_rejected(self):
        r = validate_payload("daily_log", self._payload(duration_hours="一天"))
        assert r["valid"] is False
        assert any("应为数字" in m for m in r["missing"])

    def test_valid_log(self):
        r = validate_payload("daily_log", self._payload())
        assert r["valid"] is True


class TestTransferAndTypes:
    def test_transfer_requires_four_fields(self):
        r = validate_payload("transfer", {"current_position": "设备点检助理"})
        assert r["valid"] is False
        assert len(r["missing"]) == 3

    def test_unknown_type_rejected(self):
        r = validate_payload("reimburse", {"amount": "100"})
        assert r["valid"] is False
        assert "不支持的申请类型" in r["message"]

    def test_all_types_have_source_document(self):
        for name, rule in APPLY_RULES.items():
            assert rule["source"].startswith("实习制度示例.md"), name
