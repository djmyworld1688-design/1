# -*- coding: utf-8 -*-
import os
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

import streamlit as st
import plotly.graph_objects as go
from crewai import Agent, Task, Crew
from crewai.tools import tool
from duckduckgo_search import DDGS

# ═══════════════════════════════════════════════
# 路径配置（兼容本地和云端）
# ═══════════════════════════════════════════════
IS_CLOUD = not Path.home().joinpath("Desktop").exists()

if IS_CLOUD:
    # 云端：用临时目录
    ARCHIVE_DIR = Path("/tmp/Health_Archive")
else:
    # 本地：用桌面
    ARCHIVE_DIR = Path.home() / "Desktop" / "Health_Archive"

ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════
st.set_page_config(page_title="AI 私人健康系统 v3", layout="wide", page_icon="❤️")

st.markdown("""
<style>
:root {
    --color-primary: #007AFF;
    --color-primary-hover: #0051D5;
    --color-bg-secondary: #F5F5F7;
    --color-border: #E5E5EA;
    --color-shadow: rgba(0,0,0,0.08);
    --radius-lg: 16px;
    --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.main { background-color: #FFFFFF; font-family: var(--font-family); }
[data-testid="stSidebar"] {
    background: linear-gradient(135deg, var(--color-bg-secondary) 0%, #FFFFFF 100%);
    border-right: 1px solid var(--color-border);
}
.stButton > button {
    background-color: var(--color-primary); color: white; border: none;
    border-radius: var(--radius-lg); font-size: 16px; font-weight: 600;
    padding: 14px 24px; width: 100%; min-height: 44px;
    box-shadow: 0 2px 8px var(--color-shadow);
}
.stButton > button:hover { background-color: var(--color-primary-hover); transform: translateY(-1px); }
.disclaimer {
    background: linear-gradient(135deg, #FFF3E0 0%, #FFF9E6 100%);
    border-left: 4px solid #FF9500; padding: 16px; border-radius: 8px;
    margin-bottom: 20px; font-size: 14px; line-height: 1.6;
}
.compare-box {
    background: #F0F8FF; border-left: 4px solid #007AFF;
    padding: 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px;
}
</style>
""", unsafe_allow_html=True)

st.title("❤️ AI 私人健康定制系统 v3")
st.caption("由 AI 多智能体驱动 · 数据持久化 · 可视化图表 · 历史对比")

st.markdown("""
<div class="disclaimer">
<strong style="font-size:15px;color:#FF9500;">&#x26A0;&#xFE0F; 重要免责声明</strong>
<p style="margin:10px 0 6px 0;"><strong>1. 非医疗诊断工具</strong><br/>
本系统由 AI 驱动，不能替代医生诊疗。所有建议仅供参考，不构成医学诊断或用药建议。</p>
<p style="margin:6px 0 6px 0;"><strong>2. 紧急情况</strong><br/>
出现胸痛、呼吸困难、意识丧失等症状，请立即拨打120或就近就医。</p>
<p style="margin:6px 0 6px 0;"><strong>3. 必须咨询医生</strong><br/>
正在服用处方药、患有慢性疾病、怀孕/哺乳期，任何改变前必须咨询医生。</p>
<p style="margin:6px 0 0;font-size:12px;color:#888;">点击开始即表示您已阅读并同意本声明。</p>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
# 历史报告函数
# ═══════════════════════════════════════════════
def get_last_report():
    reports = sorted(ARCHIVE_DIR.glob("*.md"), reverse=True)
    if reports:
        try:
            return reports[0].read_text(encoding="utf-8")
        except Exception:
            return None
    return None

def get_last_report_date():
    reports = sorted(ARCHIVE_DIR.glob("*.md"), reverse=True)
    return reports[0].stem if reports else None

def save_report(content):
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M") + ".md"
    filepath = ARCHIVE_DIR / filename
    try:
        filepath.write_text(content, encoding="utf-8")
        return filepath
    except Exception:
        return None

# ═══════════════════════════════════════════════
# 可视化函数
# ═══════════════════════════════════════════════
def parse_scores(text):
    scores = {"饮食": 7, "运动": 6, "睡眠": 7, "整体": 7}
    for key in scores:
        m = re.search(rf"{key}[^\d]*(\d+)/10", text)
        if m:
            scores[key] = int(m.group(1))
    return scores

def parse_nutrition(text):
    macros = {"蛋白质": 30, "碳水化合物": 45, "脂肪": 25}
    for key in macros:
        m = re.search(rf"{key[:2]}[^\d]*(\d+)[%％]", text)
        if m:
            macros[key] = int(m.group(1))
    return macros

def parse_exercise_plan(text):
    days = {"周一": 0, "周二": 0, "周三": 0, "周四": 0, "周五": 0, "周六": 0, "周日": 0}
    for day in days:
        m = re.search(rf"\|?\s*{day}\s*\|[^|]*\|\s*(\d+)\s*分钟", text)
        if m:
            days[day] = int(m.group(1))
    if all(v == 0 for v in days.values()):
        days = {"周一": 30, "周二": 0, "周三": 45, "周四": 20, "周五": 40, "周六": 60, "周日": 0}
    return days

def draw_radar(scores, title="健康综合评分"):
    cats = list(scores.keys())
    vals = list(scores.values()) + [list(scores.values())[0]]
    cats_c = cats + [cats[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=vals, theta=cats_c, fill='toself',
        fillcolor='rgba(0,122,255,0.2)', line=dict(color='#007AFF', width=2)))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
        showlegend=False,
        title=dict(text=title, font=dict(size=15), x=0.5),
        height=320, margin=dict(l=50, r=50, t=55, b=20),
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def draw_nutrition_pie(macros):
    fig = go.Figure(data=[go.Pie(
        labels=list(macros.keys()), values=list(macros.values()), hole=0.4,
        marker=dict(colors=['#007AFF', '#34C759', '#FF9500']),
        textinfo='label+percent', textfont=dict(size=13)
    )])
    fig.update_layout(
        title=dict(text="每日营养素建议比例", font=dict(size=15), x=0.5),
        height=320, margin=dict(l=20, r=20, t=55, b=20),
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def draw_exercise_bar(days):
    colors = ['#007AFF' if v > 0 else '#E5E5EA' for v in days.values()]
    fig = go.Figure(data=[go.Bar(
        x=list(days.keys()), y=list(days.values()), marker_color=colors,
        text=[f"{v}分钟" if v > 0 else "休息" for v in days.values()],
        textposition='outside', textfont=dict(size=12)
    )])
    fig.update_layout(
        title=dict(text="本周运动计划（分钟）", font=dict(size=15), x=0.5),
        yaxis=dict(range=[0, max(days.values()) * 1.4 + 10]),
        height=320, margin=dict(l=40, r=20, t=55, b=40),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    return fig

def parse_task_output(task):
    try:
        if task.output and task.output.raw:
            return str(task.output.raw)
    except Exception:
        pass
    return ""

def render_content(content, fallback_msg):
    if content.strip():
        st.markdown(content)
    else:
        st.warning(f"⚠️ {fallback_msg}，请重试。")

def build_health_metrics(resting_hr, max_hr, systolic, diastolic,
                         total_chol, ldl, hdl, fasting_glucose, hba1c):
    lines = []
    if resting_hr > 0: lines.append(f"Resting HR: {resting_hr} bpm")
    if max_hr > 0: lines.append(f"Max HR: {max_hr} bpm")
    if systolic > 0 and diastolic > 0: lines.append(f"BP: {systolic}/{diastolic} mmHg")
    if total_chol > 0: lines.append(f"Total Cholesterol: {total_chol} mmol/L")
    if ldl > 0: lines.append(f"LDL: {ldl} mmol/L")
    if hdl > 0: lines.append(f"HDL: {hdl} mmol/L")
    if fasting_glucose > 0: lines.append(f"Fasting Glucose: {fasting_glucose} mmol/L")
    if hba1c > 0: lines.append(f"HbA1c: {hba1c}%")
    if lines:
        return "Health Metrics:\n" + "\n".join(f"  - {l}" for l in lines)
    return "Health Metrics: Not provided (analyze based on basic info)"

# ═══════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════
@tool("medical_search")
def medical_search(query: str) -> str:
    """Search for medical and health information."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if not results:
                return "No results found. Use professional knowledge."
            return "\n".join([r['title'] + ": " + r['body'] for r in results])
    except Exception:
        return "Search unavailable. Use professional knowledge."

# ═══════════════════════════════════════════════
# 侧边栏
# ═══════════════════════════════════════════════
with st.sidebar:
    last_date = get_last_report_date()
    if last_date:
        st.info(f"📂 上次记录：{last_date}")
    else:
        st.caption("📂 暂无历史记录")

    st.header("📋 基本信息")
    age = st.number_input("年龄", min_value=1, max_value=120, value=30)
    gender = st.selectbox("性别", ["男", "女"])
    weight = st.text_input("体重（如：75kg）", value="75kg")
    height = st.text_input("身高（如：175cm）", value="175cm")

    st.header("🏃 生活方式")
    activity = st.selectbox("运动频率", [
        "久坐（几乎不运动）", "轻度（每周1-2次）",
        "中度（每周3-4次）", "高强度（每周5次以上）"
    ])
    sleep_hours = st.slider("每天睡眠时间（小时）", 4, 12, 7)
    stress = st.selectbox("压力水平", ["低", "中", "高"])

    st.header("💊 健康状况")
    meds = st.text_area("正在服用的药物", value="无", height=68)
    conditions = st.text_area("健康问题/病史", value="无", height=68)
    goal = st.text_input("健康目标", value="保持健康，增强体能")

    st.header("🔬 健康检测数据（可选）")
    st.caption("填写越多，AI 分析越精准")

    with st.expander("❤️ 心率数据", expanded=False):
        resting_hr = st.number_input("静息心率（次/分）", min_value=0, max_value=200, value=0, help="0表示未填写")
        max_hr = st.number_input("运动最大心率（次/分）", min_value=0, max_value=250, value=0, help="0表示未填写")

    with st.expander("🩺 血压数据", expanded=False):
        systolic = st.number_input("收缩压（高压，mmHg）", min_value=0, max_value=300, value=0, help="0表示未填写")
        diastolic = st.number_input("舒张压（低压，mmHg）", min_value=0, max_value=200, value=0, help="0表示未填写")

    with st.expander("🧪 胆固醇数据", expanded=False):
        total_chol = st.number_input("总胆固醇（mmol/L）", min_value=0.0, max_value=20.0, value=0.0, step=0.1, help="0表示未填写")
        ldl = st.number_input("LDL 坏胆固醇（mmol/L）", min_value=0.0, max_value=15.0, value=0.0, step=0.1, help="0表示未填写")
        hdl = st.number_input("HDL 好胆固醇（mmol/L）", min_value=0.0, max_value=10.0, value=0.0, step=0.1, help="0表示未填写")

    with st.expander("🩸 血糖数据", expanded=False):
        fasting_glucose = st.number_input("空腹血糖（mmol/L）", min_value=0.0, max_value=30.0, value=0.0, step=0.1, help="0表示未填写")
        hba1c = st.number_input("糖化血红蛋白 HbA1c（%）", min_value=0.0, max_value=20.0, value=0.0, step=0.1, help="0表示未填写")

    st.header("🔑 API 设置")
    api_key = st.text_input(
        "Anthropic API Key", type="password",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        help="直接在此输入 Key"
    )
    start_btn = st.button("🚀 开始生成方案")

# ═══════════════════════════════════════════════
# 主逻辑
# ═══════════════════════════════════════════════
if start_btn:
    if not api_key:
        st.error("请在左侧输入您的 Anthropic API Key。")
        st.stop()

    if not re.search(r'\d', weight) or not re.search(r'\d', height):
        st.error("体重或身高格式有误，请包含数字，例如：75kg、175cm。")
        st.stop()

    os.environ["ANTHROPIC_API_KEY"] = api_key

    last_report = get_last_report()
    last_date = get_last_report_date()

    health_metrics = build_health_metrics(
        resting_hr, max_hr, systolic, diastolic,
        total_chol, ldl, hdl, fasting_glucose, hba1c
    )

    user_info = (
        f"Age: {age}, Gender: {gender}, Height: {height}, Weight: {weight}\n"
        f"Activity: {activity}, Sleep: {sleep_hours}h/day, Stress: {stress}\n"
        f"Medical History: {conditions}\nMedications: {meds}\n"
        f"Health Goal: {goal}\n{health_metrics}"
    )

    history_context = ""
    if last_report:
        history_context = (
            f"\n\nPREVIOUS REPORT ({last_date}):\n"
            + last_report[:2000]
            + "\nCompare and note improvements or regressions."
        )

    MODEL = "anthropic/claude-haiku-4-5-20251001"

    doctor = Agent(role="Doctor",
        goal="Analyze health data, give top 3 warnings. Respond in Chinese.",
        backstory="General practitioner skilled at simple health explanations.",
        tools=[medical_search], llm=MODEL)
    nutritionist = Agent(role="Nutritionist",
        goal="Give 3 key dietary changes. Include protein%/carbs%/fat% ratios. Respond in Chinese.",
        backstory="Registered dietitian focused on critical advice.",
        llm=MODEL)
    fitness_expert = Agent(role="Fitness Expert",
        goal="Give weekly exercise plan with daily minutes in table. Respond in Chinese.",
        backstory="Sports medicine expert for safe exercise plans.",
        llm=MODEL)
    sleep_expert = Agent(role="Sleep Expert",
        goal="Find top sleep issues, give tonight's solutions. Respond in Chinese.",
        backstory="Sleep specialist for fast behavioral interventions.",
        llm=MODEL)
    health_expert = Agent(role="Health Expert",
        goal="Integrate advice, list top 5 priorities, score diet/exercise/sleep/overall out of 10. Respond in Chinese.",
        backstory="Preventive medicine expert turning advice into action.",
        llm=MODEL)

    t_doctor = Task(
        description=(
            "You are a doctor. Respond ONLY in Chinese.\n\n" + user_info + history_context +
            "\n\n## 最需要关注的问题（最多3条）\n**问题1**: [描述] → 立即这样做: [行动]\n\n"
            "## 身体做得好的地方\n- [说明]\n\n## 出现这些症状请立即就医\n- [症状]\n"
            + ("## 与上次相比\n- [对比]\n" if last_report else "")
        ),
        expected_output="Medical analysis in Chinese", agent=doctor)

    t_nutrition = Task(
        description=(
            "You are a nutritionist. Respond ONLY in Chinese.\n\n" + user_info +
            "\n\n## 本周最重要的3个饮食改变\n"
            "**改变1**: 减少[食物] → 改吃[替代] → 原因:[说明]\n"
            "**改变2**: 增加[食物+分量] → 时机:[时间] → 原因:[说明]\n"
            "**改变3**: [建议] → [方法] → [原因]\n\n"
            "## 每日营养素建议比例\n蛋白质: XX%, 碳水化合物: XX%, 脂肪: XX%\n\n"
            "## 明天的饮食安排\n- 早餐: [食物+分量]\n- 午餐: [食物+分量]\n- 晚餐: [食物+分量]\n\n"
            "## 外卖首选/避免\n首选:[菜品]  避免:[菜品]"
        ),
        expected_output="Dietary advice in Chinese with macro %", agent=nutritionist)

    t_fitness = Task(
        description=(
            "You are a fitness expert. Respond ONLY in Chinese.\n\n" + user_info +
            "\n\n## 运动水平\n[新手/初级/中级] - [原因]\n\n## 今天的训练\n"
            "热身5分钟: [动作]\n主训练:\n- [动作]: [组数]x[次数]\n拉伸5分钟: [动作]\n\n"
            "## 本周计划\n| 天 | 安排 | 时长 |\n|----|------|------|\n"
            "| 周一 | [内容] | [X]分钟 |\n| 周二 | [内容] | [X]分钟 |\n"
            "| 周三 | [内容] | [X]分钟 |\n| 周四 | [内容] | [X]分钟 |\n"
            "| 周五 | [内容] | [X]分钟 |\n| 周六 | [内容] | [X]分钟 |\n| 周日 | 休息 | 0分钟 |"
        ),
        expected_output="Exercise plan in Chinese with table", agent=fitness_expert)

    t_sleep = Task(
        description=(
            "You are a sleep expert. Respond ONLY in Chinese.\n\n" + user_info +
            "\n\n## 主要睡眠问题\n[描述] - 影响:[说明]\n\n## 今晚就做这3件事\n"
            "1. [时间] [行动]\n2. 睡前[X]分钟 [行动]\n3. 停止[行为], 改为[替代]\n\n"
            "## 1周后的改变\n- [效果]"
        ),
        expected_output="Sleep advice in Chinese", agent=sleep_expert)

    t_summary = Task(
        description=(
            "You are a health expert. Respond ONLY in Chinese.\n\n" + user_info + history_context +
            "\n\n## 本周最重要的5件事\n"
            "**第1优先（今天）**: [行动] - 效果:[说明]\n**第2优先（明天）**: [行动] - 效果:[说明]\n"
            "**第3优先（本周）**: [行动] - 效果:[说明]\n**第4优先（本周）**: [行动] - 效果:[说明]\n"
            "**第5优先（长期）**: [行动] - 效果:[说明]\n\n"
            "## 健康评分\n| 维度 | 评分 | 改善重点 |\n|------|------|----------|\n"
            "| 饮食 | X/10 | [说明] |\n| 运动 | X/10 | [说明] |\n"
            "| 睡眠 | X/10 | [说明] |\n| 整体 | X/10 | [说明] |\n\n"
            + ("## 与上次相比的进步\n- [对比]\n\n" if last_report else "")
            + "## 给你的一句话\n[朋友口吻]"
        ),
        expected_output="Action list with scores in Chinese", agent=health_expert)

    crew = Crew(
        agents=[doctor, nutritionist, fitness_expert, sleep_expert, health_expert],
        tasks=[t_doctor, t_nutrition, t_fitness, t_sleep, t_summary],
    )

    with st.spinner("👨‍⚕️ AI 专家团队正在为您会诊，约需 2-3 分钟..."):
        try:
            crew.kickoff()
            run_success = True
        except Exception as e:
            st.error(f"会诊过程中出现了问题：{str(e)}")
            st.info("请检查网络连接和 API Key 是否有效，然后重新尝试。")
            run_success = False
        finally:
            os.environ.pop("ANTHROPIC_API_KEY", None)

    if run_success:
        st.success("🎉 您的专属健康方案已生成！")
        st.divider()

        doctor_content    = parse_task_output(t_doctor)
        nutrition_content = parse_task_output(t_nutrition)
        fitness_content   = parse_task_output(t_fitness)
        sleep_content     = parse_task_output(t_sleep)
        summary_content   = parse_task_output(t_summary)

        if summary_content.strip():
            st.subheader("🎯 健康专家综合建议")
            st.markdown(summary_content)
            st.divider()

        st.subheader("📊 数据可视化")
        scores = parse_scores(summary_content)
        macros = parse_nutrition(nutrition_content)
        exercise_days = parse_exercise_plan(fitness_content)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.plotly_chart(draw_radar(scores), use_container_width=True)
        with col2:
            st.plotly_chart(draw_nutrition_pie(macros), use_container_width=True)
        with col3:
            st.plotly_chart(draw_exercise_bar(exercise_days), use_container_width=True)

        if last_report:
            last_scores = parse_scores(last_report)
            st.divider()
            st.subheader(f"📈 与上次记录对比（{last_date}）")
            st.markdown('<div class="compare-box">📂 检测到历史记录，以下展示健康变化趋势。</div>', unsafe_allow_html=True)
            col_l, col_r = st.columns(2)
            with col_l:
                fig_compare = go.Figure()
                cats = list(scores.keys())
                cats_c = cats + [cats[0]]
                fig_compare.add_trace(go.Scatterpolar(
                    r=list(last_scores.values()) + [list(last_scores.values())[0]],
                    theta=cats_c, fill='toself',
                    fillcolor='rgba(255,149,0,0.15)',
                    line=dict(color='#FF9500', width=2, dash='dash'), name='上次'
                ))
                fig_compare.add_trace(go.Scatterpolar(
                    r=list(scores.values()) + [list(scores.values())[0]],
                    theta=cats_c, fill='toself',
                    fillcolor='rgba(0,122,255,0.2)',
                    line=dict(color='#007AFF', width=2), name='本次'
                ))
                fig_compare.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
                    showlegend=True,
                    title=dict(text="健康评分对比", font=dict(size=15), x=0.5),
                    height=350, margin=dict(l=50, r=50, t=55, b=20),
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_compare, use_container_width=True)
            with col_r:
                st.markdown("**评分变化**")
                for dim in scores:
                    cur = scores[dim]
                    lst = last_scores[dim]
                    diff = cur - lst
                    arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
                    color = "green" if diff > 0 else ("red" if diff < 0 else "gray")
                    st.markdown(
                        f"**{dim}**：{lst}/10 → {cur}/10 "
                        f"<span style='color:{color};font-weight:bold;'>{arrow}{abs(diff) if diff else ''}</span>",
                        unsafe_allow_html=True
                    )

        st.divider()
        tab1, tab2, tab3, tab4 = st.tabs(["👨‍⚕️ 医生分析", "🥗 饮食计划", "💪 运动方案", "😴 睡眠建议"])
        with tab1: render_content(doctor_content, "医生分析生成失败")
        with tab2: render_content(nutrition_content, "饮食计划生成失败")
        with tab3: render_content(fitness_content, "运动方案生成失败")
        with tab4: render_content(sleep_content, "睡眠建议生成失败")

        st.divider()
        full_report = (
            "# AI 私人健康方案\n"
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n"
            f"## 健康专家综合建议\n{summary_content}\n\n---\n\n"
            f"## 医生分析\n{doctor_content}\n\n---\n\n"
            f"## 饮食计划\n{nutrition_content}\n\n---\n\n"
            f"## 运动方案\n{fitness_content}\n\n---\n\n"
            f"## 睡眠建议\n{sleep_content}\n\n---\n"
            "*本报告由 AI 生成，仅供参考，不构成医疗建议。*\n"
        )

        saved = save_report(full_report)
        if saved:
            st.success(f"📂 报告已存档：{saved.name}")

        st.download_button(
            label="📥 下载我的健康方案",
            data=full_report.encode("utf-8"),
            file_name=f"health_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown"
        )

        archive_files = sorted(ARCHIVE_DIR.glob("*.md"), reverse=True)
        if archive_files:
            with st.expander(f"📁 本次会话存档（共 {len(archive_files)} 份）"):
                for f in archive_files:
                    st.text(f"• {f.name}")
