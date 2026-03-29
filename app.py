"""
加纳中华高球队积分系统 - Streamlit 主应用
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import json

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
    return Database()

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
    st.caption("Ghana Chinese Golf Association")
    page = st.radio("📋 功能菜单", 
        ["🏠 首页", "📤 导入比赛结果", "📊 计算积分", "🏆 积分榜", "📋 赛事记录"])

# ========== 首页 ==========
if page == "🏠 首页":
    st.title("⛳ 加纳中华高球队积分系统")
    stats = db.get_statistics()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏌️ 参赛球员", stats['total_players'])
    col2.metric("📅 已办赛事", stats['total_events'])
    col3.metric("🎯 总积分", stats['total_points_issued'])
    col4.metric("⭐ 特殊赛事", stats['special_events'])

    st.divider()
    st.subheader("🚀 快速开始")
    col1, col2 = st.columns(2)
    with col1:
        st.info("**第一步：导入比赛结果**\n- 上传 GolfLive CSV/Excel 文件")
    with col2:
        st.success("**第二步：计算并保存**\n- 选择赛事类型，自动计算积分")

# ========== 导入比赛结果 ==========
elif page == "📤 导入比赛结果":
    st.title("📤 导入 GolfLive 比赛结果")
    
    uploaded_file = st.file_uploader("上传比赛结果文件", type=['csv', 'xlsx', 'xls'])
    
    if uploaded_file:
        try:
            results = process_golflive_file(uploaded_file)
            st.session_state['imported_data'] = results
            st.success(f"✅ 成功导入 {len(results)} 条球员记录")
            st.info("💡 请切换到「计算积分」页面继续")
        except Exception as e:
            st.error(f"❌ 导入失败: {e}")

# ========== 计算积分 ==========
elif page == "📊 计算积分":
    st.title("📊 计算赛事积分")
    
    if 'imported_data' not in st.session_state:
        st.warning("⚠️ 请先导入比赛结果")
        st.stop()
    
    results = st.session_state['imported_data']
    
    # 赛事信息
    col1, col2 = st.columns(2)
    with col1:
        event_date = st.date_input("📅 比赛日期", datetime.now())
        event_name = st.text_input("🏷️ 赛事名称", 
            value=f"{event_date.month}月月例赛" if datetime.now().day > 15 else "周例赛")
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
                points_results = calculate_event_points(results, event_type[0], is_special)
                points_results.sort(key=lambda x: x['total_points'], reverse=True)
                
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
                st.success("✅ 积分计算完成！")
                
            except Exception as e:
                st.error(f"❌ 计算失败: {e}")
    
    # 保存按钮
    if 'event_data' in st.session_state:
        st.divider()
        st.subheader("💾 保存到数据库")
        
        if st.button("✅ 确认并保存赛事结果", use_container_width=True):
            try:
                with st.spinner("正在保存..."):
                    saved_event = db.save_event(st.session_state['event_data'])
                    st.success(f"✅ 赛事「{saved_event['name']}」已成功保存！")
                    st.balloons()
                    
                    # 清理
                    del st.session_state['imported_data']
                    del st.session_state['points_results']
                    del st.session_state['event_data']
            except Exception as e:
                st.error(f"❌ 保存失败: {e}")

# ========== 积分榜 ==========
elif page == "🏆 积分榜":
    st.title("🏆 年度积分排行榜")
    
    rankings = db.get_rankings()
    
    if not rankings:
        st.info("📭 暂无积分数据")
    else:
        # TOP 10
        st.subheader("🥇 TOP 10")
        top10 = rankings[:10]
        display_data = []
        for i, r in enumerate(top10):
            emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(r['rank'], str(r['rank']))
            display_data.append({
                '排名': emoji,
                '姓名': r['name'],
                '总积分': r['total_points'],
                '参赛次数': r['events_count'],
                '周赛冠军': r.get('weekly_wins', 0),
                '月赛冠军': r.get('monthly_wins', 0)
            })
        st.dataframe(pd.DataFrame(display_data), width='stretch', hide_index=True)
        
        # 全部排名
        st.divider()
        st.subheader("📋 完整排名")
        all_data = [{'排名': r['rank'], '姓名': r['name'], '总积分': r['total_points'], 
                     '参赛次数': r['events_count']} for r in rankings]
        st.dataframe(pd.DataFrame(all_data), width='stretch', hide_index=True)

# ========== 赛事记录 ==========
elif page == "📋 赛事记录":
    st.title("📋 赛事记录")
    
    events = db.get_events()
    
    if not events:
        st.info("📭 暂无赛事记录")
    else:
        for event in events:
            with st.expander(f"📅 {event.get('date')} - {event.get('name')}"):
                st.write(f"类型: {'月度大赛' if event.get('type') == 'monthly' else '周例赛'}")
                st.write(f"参赛人数: {len(event.get('results', []))}")
                
                # 显示前五名
                results = sorted(event.get('results', []), 
                               key=lambda x: x.get('total_points', 0), reverse=True)
                if results:
                    top5 = [{'排名': r.get('net_rank'), '姓名': r['name'], 
                            '积分': r.get('total_points')} for r in results[:5]]
                    st.dataframe(pd.DataFrame(top5), hide_index=True)
                
                # 删除按钮
                if st.button("🗑️ 删除", key=f"del_{event.get('id')}"):
                    if db.delete_event(event.get('id')):
                        st.success("已删除")
                        st.rerun()
