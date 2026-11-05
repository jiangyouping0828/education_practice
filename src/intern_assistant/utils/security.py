# -*- coding: utf-8 -*-
"""安全工具（utils.security）：日志脱敏 + 提示词注入特征检测。"""

import re

# ---- 日志最小化：落库前脱敏 --------------------------------------------------


def digest(text: str, limit: int = 200) -> str:
    """截断文本作为日志摘要（日志最小化，避免落明文敏感内容）。"""
    text = (text or "").strip().replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")


def mask_phone(text: str) -> str:
    """手机号脱敏：138****1234。"""
    return re.sub(r"(1[3-9]\d)\d{4}(\d{4})", r"\1****\2", text or "")


def mask_idcard(text: str) -> str:
    """身份证号脱敏（18 位）：保留前 4 后 2。"""
    return re.sub(r"(\d{4})\d{12}(\d{2})[\dXx]?", r"\1**************\2", text or "")


def mask_all(text: str) -> str:
    """组合脱敏：手机号 + 身份证号一次处理（日志管道统一入口）。"""
    return mask_idcard(mask_phone(text))


# ---- 提示词注入检测（纵深防御第一层：先发现，再由系统提示词纪律兜底）--------

INJECTION_PATTERNS: list[tuple[str, str]] = [
    (r"忽略(之前|以上|上面|前面)(的)?(所有)?(指令|提示|规则|要求)", "指令覆盖"),
    (r"(无视|不顾|不要遵守|不遵守)(之前|以上|所有|任何)?(的)?(指令|提示|规则|要求)", "指令覆盖"),
    (r"(你现在是|从现在开始你是|假装你是|扮演).{0,12}(管理员|系统|开发者|AI|模型)", "角色伪装"),
    (r"(系统提示词|system prompt|初始指令).{0,6}(是什么|发我|给我|打印|输出)", "提示词窃取"),
    (r"(跳过|绕过|越过).{0,10}(校验|审批|确认|闸门|步骤|流程)", "流程绕过"),
    (r"(帮我|替我)?(伪造|编造|虚构|造假|代填).{0,8}(病假条|证明|理由|材料|记录|签字)", "材料伪造"),
]


def detect_injection(text: str) -> list[str]:
    """检测用户输入中的提示词注入特征，返回命中的攻击类别列表（无命中为空表）。

    说明：命中不等于拦截——本函数只做"发现并记录"，
    真正的防线是系统提示词纪律 + 工具 Schema + 服务端票据闸门三层。
    命中结果用于 agent_rounds 日志标记，供管理员在后台审计时重点关注。
    """
    t = text or ""
    return [name for pattern, name in INJECTION_PATTERNS if re.search(pattern, t)]
