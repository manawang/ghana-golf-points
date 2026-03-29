"""
加纳中华高球队积分系统 - Streamlit 主应用
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import json
import traceback

# 导入自定义模块
from points_calculator import calculate_event_points
from golflive_import import process_golflive_file, validate_data, preview_data
from database import Database

# 页面配置
st.set_page_config(
    page_title="加纳中华高球队积分系统",
    page_icon="⛳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化数据库
@st.cache_resource
def get_database():
    st.write("🔍 [DEBUG] 初始化数据库...")
    try:
        db = Database()
        st.write("✅ [DEBUG] 数据库初始化成功")
        return db
    except Exception as e:
        st.error(f"❌ [DEBUG] 数据库初始化失败: {str(e)}")
        st.code(traceback.format_exc())
        raise e

try:
    db = get_database()
except Exception as e:
    st.error("数据库连接失败，请检查配置")
    st.stop()

# ========== 页面样式 ==========
st.markdown("""
<style>
    .stDataFrame { font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# ========== 侧边栏 ==========
with st.sidebar:
    st.title("加纳中华高球队")
    page = st.radio("📋 功能菜单", 
        ["🏠 首页", "📤 导入比赛结果", "📊 计算积分", "🏆 积分榜", "📋 赛事记录"])

# ========== 计算积分 ==========
if page == "📊 计算积分":
    st.title("📊 计算赛事积分")

    if 'imported_data' not in st.session_state:
        st.warning("⚠️ 请先导入比赛结果")
        st.stop()

    results = st.session_state['imported_data']
    st.write(f"🔍 [DEBUG] 导入数据条数: {len(results)}")

    # 赛事信息
    col1, col2 = st.columns(2)
    with col1:
        event_date = st.date_input("📅 比赛日期", datetime.now())
        event_name = st.text_input("🏷️ 赛事名称", value="测试赛事")
    with col2:
        event_type = st.selectbox("🏆 赛事类型", 
            options=[("monthly", "月度大赛"), ("weekly", "周例赛")],
            format_func=lambda x: x[1])
        is_special = st.checkbox("⭐ 特殊赛事（积分×2）")

    special_type = ""
    if is_special:
        special_type = st.selectbox("特殊赛事类型",
            options=[("captains_prize", "队长杯"), ("year_end", "年终月度大赛")],
            format_func=lambda x: x[1])[0]

    event_course = st.text_input("⛳ 比赛球场（可选）")

    # 计算积分按钮
    if st.button("🚀 开始计算积分", type="primary", use_container_width=True):
        with st.spinner("正在计算积分..."):
            try:
                st.write("🔍 [DEBUG] 开始计算积分...")
                points_results = calculate_event_points(results, event_type[0], is_special)
                st.write(f"✅ [DEBUG] 计算完成，共 {len(points_results)} 条结果")

                # 显示结果
                display_df = pd.DataFrame([
                    {
                        '净杆排名': r.get('net_rank', '-'),
                        '姓名': r['name'],
                        '总杆': r.get('gross', r.get('gross_score', '-')),
                        '净杆': r.get('net', r.get('net_score', '-')),
                        '基础分': r.get('base_points', 0),
                        '奖励分': r.get('bonus_points', 0),
                        '总积分': r.get('total_points', 0),
                    }
                    for r in points_results
                ])
                st.dataframe(display_df, width='stretch')

                # 保存到 session state
                st.session_state['points_results'] = points_results
                st.session_state['event_data'] = {
                    'date': event_date.isoformat(),
                    'name': event_name,
                    'type': event_type[0],
                    'is_special': is_special,
                    'special_type': special_type if is_special else '',
                    'course': event_course,
                    'results': points_results
                }
                st.success("✅ 积分计算完成！请向下滚动点击保存按钮")

            except Exception as e:
                st.error(f"❌ 计算积分出错: {str(e)}")
                st.code(traceback.format_exc())

    # 保存按钮（在计算按钮外面，这样计算后才能看到）
    if 'event_data' in st.session_state:
        st.divider()
        st.subheader("💾 保存到数据库")
        
        st.write(f"🔍 [DEBUG] 待保存赛事: {st.session_state['event_data'].get('name')}")
        st.write(f"🔍 [DEBUG] 结果数: {len(st.session_state['event_data'].get('results', []))}")

        if st.button("✅ 确认并保存赛事结果", use_container_width=True):
            st.write("🔍 [DEBUG] 点击保存按钮...")
            try:
                with st.spinner("正在保存..."):
                    event_data = st.session_state['event_data']
                    
                    st.write("🔍 [DEBUG] 调用 db.save_event...")
                    saved_event = db.save_event(event_data)
                    
                    st.success(f"✅ 赛事「{event_data['name']}」已成功保存！")
                    
                    # 清理
                    del st.session_state['imported_data']
                    del st.session_state['points_results']
                    del st.session_state['event_data']
                    
            except Exception as e:
                st.error(f"❌ 保存失败: {str(e)}")
                st.code(traceback.format_exc())

# ... 其他页面代码保持不变 ...
elif page == "🏠 首页":
    st.title("⛳ 加纳中华高球队积分系统")
    try:
        stats = db.get_statistics()
        col1, col2, col3 = st.columns(3)
        col1.metric("参赛球员", stats['total_players'])
        col2.metric("已办赛事", stats['total_events'])
        col3.metric("总积分", stats['total_points_issued'])
    except Exception as e:
        st.error(f"获取统计失败: {e}")

elif page == "📤 导入比赛结果":
    st.title("📤 导入比赛结果")
    uploaded_file = st.file_uploader("上传文件", type=['csv', 'xlsx'])
    if uploaded_file:
        try:
            results = process_golflive_file(uploaded_file)
            st.session_state['imported_data'] = results
            st.success(f"导入成功: {len(results)} 条记录")
        except Exception as e:
            st.error(f"导入失败: {e}")

elif page == "🏆 积分榜":
    st.title("🏆 积分榜")
    try:
        rankings = db.get_rankings()
        if rankings:
            df = pd.DataFrame(rankings)
            st.dataframe(df, width='stretch')
        else:
            st.info("暂无数据")
    except Exception as e:
        st.error(f"获取排名失败: {e}")

elif page == "📋 赛事记录":
    st.title("📋 赛事记录")
    try:
        events = db.get_events()
        for event in events:
            with st.expander(f"{event.get('date')} - {event.get('name')}"):
                st.write(f"类型: {event.get('type')}")
                st.write(f"参赛人数: {len(event.get('results', []))}")
    except Exception as e:
        st.error(f"获取赛事失败: {e}")
