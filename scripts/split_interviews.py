"""按受访者拆分访谈记录，输出 md / json / csv 三种格式。

数据源：仓库根目录 discovery-report.json（schema v2，70 轮对话，6 个角色 r0~r5）。
输出：docs/interviews/ 下每人一份 .md / .json / .csv，外加合并 all_interviews.csv。

运行：python scripts/split_interviews.py
"""

import csv
import io
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "discovery-report.json")
OUT = os.path.join(ROOT, "docs", "interviews")

# characterId -> (序号, 姓名, 职务, 一句话职责)
PEOPLE = {
    "education-r0": (1, "顾明岚", "产教融合负责人", "业务立项人，决定试点范围与验收口径"),
    "education-r1": (2, "林亦舟", "实习指导教师", "一线操作者，每人带 30 名学生"),
    "education-r2": (3, "唐映秋", "教务管理员", "流程与材料责任人，负责交接与分派核对"),
    "education-r3": (4, "秦芮", "校园信息工程师", "系统与数据条件，负责集成与主数据映射"),
    "education-r4": (5, "傅景", "教学质量负责人", "验收与风险否决，划审核边界"),
    "education-r5": (6, "叶书", "企业实习导师", "企业侧反馈与课程能力映射"),
}

# 每人核心观点（依据其本人的访谈回答与事实编号归纳，不跨人推断）
HIGHLIGHTS = {
    "education-r0": [
        "现状链路是「企业评分 → 教师回访 → 教务汇总 → 专业组评审」，但建议常停在专业组层面，落不到具体课程（f01）",
        "规模缺口明确：每学期 600 名学生实习，反馈完整率 54%，目标 85%（f00）",
        "试点范围收窄为机电专业、覆盖 5 家企业，比较建议可执行性与教师整理工时（f02）",
        "首期先做历史回放验证转换链，成本低且不打断现有人工流程；规则站住后再进并行试点（f05）",
        "预算口径 12 万元，须扣除接口、培训、复核、维护四类成本，既有系统采购不计入节省额（f03）",
        "决策结构：业务立项由其牵头，教学质量负责人有风险否决权，企业导师参与交接结果验收（f04）",
    ],
    "education-r1": [
        "每位教师带 30 人，每月约 10 小时耗在整理微信、Excel、邮件上，这些时间不产出教学判断（f12）",
        "企业常只写「沟通能力不足」，不落到岗位任务，教师无法给出可执行改进建议（f10）",
        "学生换岗或延期后系统仍关联旧导师，反馈发给错误的人，返工量大（f11）",
        "补充说明常留在群聊或个人表，关键原因未作为结构化字段随业务交接（f14）",
        "复核要求：每条辅助结果必须能显示原记录；争议先由教务管理员核对，未确认不得覆盖原记录（f15）",
        "现场用现有终端，不额外配设备；须保留「待补信息」与「最后同步时间」两个状态（f13）",
    ],
    "education-r2": [
        "现行三步流程：确认学生岗位与导师 → 收集任务表现、事实例子、改进建议 → 交专业组确认（f20）",
        "硬约束：教师可写建议，但变更培养方案须教务委员会审批，模型不能决定学生成绩（f22）",
        "规则由业务负责人维护，须保存生效日期与适用范围；争议记录使用版本并由教学质量负责人确认（f24）",
        "分派异常必须写明处理人、截止时间与退回原因，超时交产教融合负责人协调，不允许只改状态（f25）",
        "交接材料须含学生批次、导师身份、岗位任务与企业反馈实例、当前版本、未解决事项，接手人确认后才结束待办（f23）",
    ],
    "education-r3": [
        "学籍、实习、课程平台各用一套 ID，学生与实习批次之间尚无统一映射，是首先要解决的基础问题（f30）",
        "接口侧只开放只读批量导出，成绩写回接口不在本次范围（f32）",
        "历史反馈缺少岗位任务字段，不能把空值当成「没问题」，须先补模板再谈分析（f31）",
        "主数据校验四要素：主编号、事件时间、来源、版本；缺关键字段进人工修复队列，不允许猜值补齐（f33）",
        "试点数据每两周刷新、原文按版本同步；超过一个周期的结果要标注待刷新，历史快照不能伪装成当前状态（f34）",
        "接口失败时继续走原人工流程，保留只读快照与时间戳，恢复后按业务编号去重补齐，不重复建待办（f35）",
    ],
    "education-r4": [
        "验收硬线一：专业组审阅 30 条建议，至少 24 条能对应到课程、任务和改进负责人，对不上课程不签字（f42）",
        "验收硬线二：本轮合成试点评价记录暂留 90 天，到期由教学质量负责人确认删除或归档（f43）",
        "安全红线一：学生个人评价必须限制访问范围，不得向其他企业公开个体记录（f40）",
        "安全红线二：能力推断必须有行为实例支撑，不得用家庭背景、性别等信息解释能力（f41）",
        "兜底四类触发：学生换岗、评价无行为实例、评分口径不一致、依据缺失或关键系统不可用；触发即停自动建议（f44）",
        "转人工须标明停止原因、接手人、人工确认时间；处理过程可重建，但不记口令与非必要个人信息（f45）",
    ],
    "education-r5": [
        "交接冲突根源是口径不一致：企业重设备点检与交接，学校评价偏理论，任务口径须共同校准（f51）",
        "AI 边界：只能整理观察事实与建议，最终评价由导师确认，不自动给学生定性（f52）",
        "各部门完成时间要分别记录，不能用消息发送量代替实际完成量（f53）",
        "下游反馈须关联原业务编号与当时资料版本，由企业导师受理、教务管理员核实，未确认前不承诺赔偿（f54）",
        "反馈节奏：每两周提交一次具体任务例子，长问卷会拖到学期末才填（f50）",
        "闭环：每周复盘误判与未解决问题，由产教融合负责人指定改进负责人，复测达标后才更新规则（f55）",
    ],
}

# 每人「待澄清问题」（源自其回答中明确表示尚未核实/需他人确认的点，不臆造）
OPEN_QUESTIONS = {
    "education-r0": [
        "评审结论的格式要求由谁定（涉及傅景审核边界）",
        "「转换动作」落在教师还是教务（涉及唐映秋交接责任）",
        "无法转换的反馈记为规则缺口，还是允许标注「不适用」后排除",
        "覆盖判定由教师自评还是需复核查验",
    ],
    "education-r1": [
        "反馈模板能否强制挂到岗位任务上",
        "异常换岗由谁触发、教师是否有直接发起权",
        "异常标记位字段是否采用「原记录链接 + 疑点类型 + 提报人」",
        "不同企业现场的终端与网络条件差异",
    ],
    "education-r2": [
        "审批记录与版本记录最终归谁保管",
        "异常换岗由谁发起",
        "整套考核流程各环节是否都有统一办理时限",
        "学生申诉的受理人与答复时限",
    ],
    "education-r3": [
        "各平台具体使用的系统、版本与部署方式（需一次完整盘点）",
        "数据刷新时点由谁触发、各平台导出频率是否对得上",
        "「过期」指批次映射失效还是反馈内容时效",
        "字段清单、口径定义与整体质量分布",
    ],
    "education-r4": [
        "评价记录真实组织的留存期限",
        "异常换岗时评价如何交接",
        "日志谁能看、看到什么粒度（需秦芮说明系统能力）",
        "转人工接手人按场景如何在林亦舟与唐映秋之间分工",
    ],
    "education-r5": [
        "能力映射颗粒度按岗位任务还是按课程模块",
        "验收以谁的口径为准",
        "「可执行」由谁判定",
        "复盘结论如何回传给企业与课程侧",
    ],
}

ROLE_ORDER = sorted(PEOPLE.items(), key=lambda kv: kv[1][0])


def load():
    with io.open(SRC, encoding="utf-8") as f:
        return json.load(f)


def build_fact_index(report):
    """factId -> {id, source, text, character}，并按 character 分组。"""
    facts, by_person = {}, {}
    for req in report.get("requirements", []):
        for e in req.get("evidence", []):
            if not e.get("id"):
                continue
            item = {
                "id": e["id"],
                "source": e.get("source", ""),
                "text": e.get("text", ""),
                "character": e.get("character", ""),
                "requirement": req.get("title", ""),
                "priority": req.get("priority", ""),
            }
            facts[e["id"]] = item
            by_person.setdefault(item["character"], []).append(item)
    return facts, by_person


def split_turns(report):
    """按受访者归集问答对；同一人内重复问答（原文有重复轮次）去重并记录原始轮数。"""
    sessions, order = {}, []
    pending = None
    for turn in report.get("transcript", []):
        cid = turn.get("characterId")
        if cid not in PEOPLE:
            continue
        if cid not in sessions:
            sessions[cid] = {"raw_turns": 0, "pairs": [], "seen": set()}
            order.append(cid)
        sessions[cid]["raw_turns"] += 1
        if turn.get("speaker") == "user":
            pending = (turn.get("text", "").strip(), turn.get("at", ""))
        else:
            q, at = pending if pending else ("（未记录提问）", turn.get("at", ""))
            a = turn.get("text", "").strip()
            key = (q, a)
            if key in sessions[cid]["seen"]:
                pending = None
                continue
            sessions[cid]["seen"].add(key)
            sessions[cid]["pairs"].append({
                "question": q,
                "answer": a,
                "at": at,
                "fact_ids": sorted(set(re.findall(r"education-f\d+", a))),
            })
            pending = None
    return sessions, order


def person_json(report, cid, session, facts):
    seq, name, role, duty = PEOPLE[cid]
    used = []
    for p in session["pairs"]:
        for fid in p["fact_ids"]:
            if fid in facts and facts[fid]["character"] == name and fid not in [u["id"] for u in used]:
                used.append(facts[fid])
    reqs = []
    for req in report.get("requirements", []):
        if any(e.get("character") == name for e in req.get("evidence", [])):
            reqs.append({"title": req.get("title"), "owner": req.get("owner"),
                         "priority": req.get("priority"), "status": req.get("status")})
    return {
        "schema": "interview-report/1.0",
        "project": report.get("title"),
        "interviewee": {"seq": seq, "name": name, "role": role, "duty": duty,
                        "characterId": cid},
        "meta": {"source": "discovery-report.json",
                 "raw_turns": session["raw_turns"],
                 "deduped_turns": len(session["pairs"]),
                 "fact_count": len(used),
                 "interview_date": "2026-10-23"},
        "highlights": HIGHLIGHTS.get(cid, []),
        "turns": [{"round": i + 1, "question": p["question"], "answer": p["answer"],
                   "fact_ids": p["fact_ids"]} for i, p in enumerate(session["pairs"])],
        "facts": used,
        "requirements": reqs,
        "open_questions": OPEN_QUESTIONS.get(cid, []),
    }


def person_md(p):
    it = p["interviewee"]
    m = p["meta"]
    out = [
        f"# 访谈报告 · {it['name']}（{it['role']}）",
        "",
        f"> 项目：{p['project']} · 访谈日期：{m['interview_date']} · "
        f"有效问答 {m['deduped_turns']} 轮（原始 {m['raw_turns']} 轮，重复轮次已合并）· "
        f"关键事实 {m['fact_count']} 条",
        "",
        "## 一、受访者信息",
        "",
        "| 项目 | 内容 |",
        "|------|------|",
        f"| 姓名 | {it['name']} |",
        f"| 职务 | {it['role']} |",
        f"| 在项目中的角色 | {it['duty']} |",
        "| 访谈方式 | 半结构化一对一访谈（结构化问题提纲 + 追问） |",
        f"| 记录编号 | {it['characterId']} |",
        "",
        "## 二、核心观点",
        "",
    ]
    out += [f"{i + 1}. {h}" for i, h in enumerate(p["highlights"])]
    out += ["", "## 三、访谈实录", ""]
    for t in p["turns"]:
        out += [f"### 第 {t['round']} 轮", "", f"**问：** {t['question']}", "", f"**答：** {t['answer']}", ""]
        if t["fact_ids"]:
            out += [f"*引用事实：{'、'.join(t['fact_ids'])}*", ""]
    out += ["## 四、关键事实清单", ""]
    if p["facts"]:
        out += ["| 编号 | 来源 | 事实描述 | 关联需求 |", "|------|------|----------|----------|"]
        for f in p["facts"]:
            out.append(f"| {f['id']} | {f['source']} | {f['text']} | {f['requirement']} |")
    else:
        out.append("（本次访谈未产出独立事实条目）")
    out += ["", "## 五、关联需求", ""]
    if p["requirements"]:
        out += ["| 需求 | 负责人角色 | 优先级 | 状态 |", "|------|-----------|--------|------|"]
        for r in p["requirements"]:
            out.append(f"| {r['title']} | {r['owner']} | {r['priority']} | {r['status']} |")
    else:
        out.append("（无直接关联需求）")
    out += ["", "## 六、待澄清问题", ""]
    out += [f"- {q}" for q in p["open_questions"]] or ["- （无）"]
    out += [
        "",
        "## 七、对设计的影响",
        "",
        _impact(it["name"]),
        "",
        "---",
        "",
        f"*本报告由 `scripts/split_interviews.py` 从 `discovery-report.json` 自动生成，"
        f"数据未作改写；核心观点与待澄清问题为人工归纳，均引用原始事实编号。*",
        "",
    ]
    return "\n".join(out)


def _impact(name):
    return {
        "顾明岚": "确认 MVP 的试点边界与验收口径：范围限定机电专业 5 家企业，"
                  "首期以历史回放验证「评审结论 → 岗位任务 → 课程能力点 → 课程动作」转换链，"
                  "验收标准为 5 家企业反馈均能被覆盖。",
        "林亦舟": "决定 MVP 的输入设计：反馈必须强制关联岗位任务，异常换岗要能改派导师，"
                  "记录须保留「待补/最后同步时间」状态，辅助结果必须可回看原记录。",
        "唐映秋": "决定 MVP 的权限与留痕设计：规则版本、生效日期、适用范围必须可查；"
                  "争议走人工确认，系统不得自动落定评分；分派须含处理人、时限、退回原因。",
        "秦芮": "决定 MVP 的数据接入方式：只做只读批量导出，不做成绩写回；"
                "学生—实习批次需主数据映射，缺字段进人工修复队列，刷新按双周并标注过期。",
        "傅景": "决定 MVP 的验收门槛与安全红线：30 条建议至少 24 条可对应课程/任务/负责人；"
                "个体评价限制访问、能力推断须有行为实例；四类兜底触发即停自动建议。",
        "叶书": "决定 MVP 的输出形态：AI 只整理事实与建议、由导师确认；"
                "反馈按双周收具体任务例子，须关联原业务编号与资料版本，可追溯不承诺结果。",
    }.get(name, "")


def person_csv(p):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    it = p["interviewee"]
    w.writerow(["受访者", "职务", "轮次", "提问", "回答", "引用事实编号", "关联需求"])
    req_titles = "；".join(r["title"] for r in p["requirements"])
    for t in p["turns"]:
        w.writerow([it["name"], it["role"], t["round"], t["question"], t["answer"],
                    "；".join(t["fact_ids"]), req_titles])
    return buf.getvalue()


def main():
    report = load()
    facts, _ = build_fact_index(report)
    sessions, order = split_turns(report)
    os.makedirs(OUT, exist_ok=True)

    made = []
    for cid, (seq, name, role, _duty) in ROLE_ORDER:
        if cid not in sessions:
            print(f"[跳过] {name} 无访谈记录")
            continue
        p = person_json(report, cid, sessions[cid], facts)
        base = f"{seq:02d}_{name}_{role}"
        with io.open(os.path.join(OUT, base + ".json"), "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        with io.open(os.path.join(OUT, base + ".md"), "w", encoding="utf-8") as f:
            f.write(person_md(p))
        with io.open(os.path.join(OUT, base + ".csv"), "w", encoding="utf-8-sig", newline="") as f:
            f.write(person_csv(p))
        made.append((seq, name, role, base, p["meta"]))
        print(f"[完成] {base}: {p['meta']['deduped_turns']} 轮 / {p['meta']['fact_count']} 条事实")

    # 合并 CSV（全员，便于 Excel 透视）
    all_csv = os.path.join(OUT, "all_interviews.csv")
    with io.open(all_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["序号", "受访者", "职务", "轮次", "提问", "回答", "引用事实编号"])
        for seq, name, role, base, meta in made:
            with io.open(os.path.join(OUT, base + ".csv"), encoding="utf-8-sig") as src:
                rows = list(csv.reader(src))
            for row in rows[1:]:
                w.writerow([seq] + row[:5] + [row[5]])

    # 索引
    lines = [
        "# 访谈报告集（6 位受访者）",
        "",
        f"> 数据源：`discovery-report.json` · 生成时间：{report.get('generatedAt', '')[:10]} · "
        f"生成脚本：`scripts/split_interviews.py`",
        "",
        "每位受访者提供三种格式：`.md`（可读报告）、`.json`（结构化数据）、`.csv`（表格，Excel 可直接打开）。",
        "",
        "| # | 受访者 | 职务 | 有效问答 | 关键事实 | 报告文件 |",
        "|---|--------|------|----------|----------|----------|",
    ]
    for seq, name, role, base, meta in made:
        lines.append(f"| {seq} | {name} | {role} | {meta['deduped_turns']} 轮 | "
                     f"{meta['fact_count']} 条 | [md]({base}.md) · [json]({base}.json) · [csv]({base}.csv) |")
    total_turns = sum(m[4]["deduped_turns"] for m in made)
    lines += [
        "",
        f"合计 {len(made)} 位受访者、{total_turns} 轮有效问答。"
        "另提供合并表 [all_interviews.csv](all_interviews.csv)，可按「受访者」列做 Excel 透视。",
        "",
        "## 关于重复轮次",
        "",
        "原始记录 70 轮，其中教务管理员、企业实习导师存在同一问题被重复提问的情况。"
        "拆分时按「提问 + 回答」完全相同去重，保留首次出现，`meta.raw_turns` 保留原始轮数以便追溯。",
        "",
    ]
    with io.open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[汇总] {len(made)} 人，{total_turns} 轮有效问答 -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
