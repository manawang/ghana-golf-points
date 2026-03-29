"""
加纳中华高球队积分系统 - Streamlit 主应用
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import json

# 导入自定义模块
from points_calculator import calculate_event_points, EventType, SpecialEventType
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

db = get_database()

# ========== 页面样式 ==========
st.markdown("""
<style>
    .stDataFrame {
        font-size: 14px;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ========== 侧边栏 ==========
with st.sidebar:
    st.image("https://img.icons8.com/emoji/96/golf.png", width=80)
    st.title("加纳中华高球队")
    st.caption("Ghana Chinese Golf Association")
    st.divider()

    # 导航
    page = st.radio(
        "📋 功能菜单",
        ["🏠 首页", "📤 导入比赛结果", "📊 计算积分", "🏆 积分榜", "📈 统计报表", "📋 赛事记录", "⚙️ 数据管理"]
    )

# ========== 首页 ==========
if page == "🏠 首页":
    st.title("⛳ 加纳中华高球队积分系统")
    st.caption("Ghana Chinese Golf Association Points System")

    # 统计卡片
    stats = db.get_statistics()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏌️ 参赛球员", stats['total_players'])
    with col2:
        st.metric("📅 已办赛事", stats['total_events'])
    with col3:
        st.metric("🎯 总积分发放", stats['total_points_issued'])
    with col4:
        st.metric("⭐ 特殊赛事", stats['special_events'])

    st.divider()

    # 快速开始
    st.subheader("🚀 快速开始")

    col1, col2 = st.columns(2)
    with col1:
        st.info("""
        **第一步：导入比赛结果**
        - 从 GolfLive 导出 CSV/Excel 文件
        - 在"📤 导入比赛结果"页面上传
        - 系统自动识别球员姓名和成绩
        """)

    with col2:
        st.success("""
        **第二步：计算并保存积分**
        - 选择赛事类型（周例赛/月度大赛）
        - 系统自动计算积分
        - 保存到数据库，更新积分榜
        """)

    # 积分规则速览
    st.divider()
    st.subheader("📋 积分规则速览")

    tab1, tab2 = st.tabs(["周例赛", "月度大赛"])

    with tab1:
        st.markdown("""
        | 净杆排名 | 积分 |
        |---------|------|
        | 🥇 第1名 | 30分 |
        | 🥈 第2名 | 20分 |
        | 🥉 第3名 | 10分 |
        | 其他 | 0分 |

        **特点**：仅奖励前三名，突出顶尖竞争
        """)

    with tab2:
        st.markdown("""
        | 净杆排名 | 积分 | 备注 |
        |---------|------|------|
        | 🥇 第1名 | 100分 | 净杆最佳 |
        | 🥈 第2名 | 70分 | - |
        | 🥉 第3名 | 60分 | - |
        | 第4-10名 | 52→28分 | 依次递减 |
        | 第11-25名 | 26→10分 | 鼓励参与 |
        | 第26-50名 | 9→5分 | 最低参与分 |

        **总杆冠军**：额外 +30分（确保全场最高）
        """)

    # 特殊赛事
    st.divider()
    st.subheader("⭐ 特殊赛事（积分×2）")
    st.markdown("""
    - **队长杯**（Captain's Prize）
    - **年终月度大赛**（Year-end Monthly Major）
    """)

# ========== 导入比赛结果 ==========
elif page == "📤 导入比赛结果":
    st.title("📤 导入 GolfLive 比赛结果")

    uploaded_file = st.file_uploader(
        "上传比赛结果文件",
        type=['csv', 'xlsx', 'xls'],
        help="支持 GolfLive 导出的 CSV 或 Excel 文件"
    )

    if uploaded_file is not None:
        try:
            # 处理文件
            with st.spinner("正在解析文件..."):
                results = process_golflive_file(uploaded_file)

                if not results:
                    st.warning("⚠️ 未能从文件中提取到有效数据，请检查文件格式")
                else:
                    st.success(f"✅ 成功导入 {len(results)} 条球员记录")

                    # 数据验证
                    validation = validate_data(results)

                    if validation['warnings']:
                        with st.expander("⚠️ 数据警告"):
                            for warning in validation['warnings'][:10]:
                                st.warning(warning)

                    # 显示统计
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("有效记录", validation['valid_records'])
                    with col2:
                        st.metric("缺少净杆", validation['missing_net_score'])
                    with col3:
                        st.metric("缺少差点", validation['missing_handicap'])

                    # 数据预览
                    st.subheader("📋 数据预览")
                    preview_df = preview_data(results, max_rows=20)
                    st.dataframe(preview_df, width='stretch')

                    # 保存到 session state
                    st.session_state['imported_data'] = results
                    st.session_state['filename'] = uploaded_file.name

                    st.info("💡 数据已导入！请切换到「📊 计算积分」页面进行下一步操作")

        except Exception as e:
            st.error(f"❌ 导入失败: {str(e)}")
            st.markdown("""
            **可能的解决方案：**
            1. 检查文件编码，建议保存为 UTF-8 格式的 CSV
            2. 确保文件包含「姓名」和「总杆」列
            3. 尝试将 Excel 另存为 CSV 格式后再导入
            """)

# ========== 计算积分 ==========
elif page == "📊 计算积分":
    st.title("📊 计算赛事积分")

    # 检查是否有导入的数据
    if 'imported_data' not in st.session_state:
        st.warning("⚠️ 请先导入比赛结果（📤 导入比赛结果页面）")
        st.stop()

    results = st.session_state['imported_data']

    # 赛事信息设置
    st.subheader("📝 赛事信息")

    col1, col2 = st.columns(2)
    with col1:
        event_date = st.date_input("📅 比赛日期", datetime.now())
        event_name = st.text_input("🏷️ 赛事名称",
                                    value=f"{event_date.month}月月例赛" if datetime.now().day > 15 else "周例赛")

    with col2:
        event_type = st.selectbox(
            "🏆 赛事类型",
            options=[("monthly", "月度大赛"), ("weekly", "周例赛")],
            format_func=lambda x: x[1]
        )
        is_special = st.checkbox("⭐ 特殊赛事（积分×2）",
                                  help="队长杯或年终月度大赛")

        special_type = ("", "")  # 默认空值
        if is_special:
            special_type = st.selectbox(
                "特殊赛事类型",
                options=[("captains_prize", "队长杯 (Captain's Prize)"),
                         ("year_end", "年终月度大赛 (Year-end)")],
                format_func=lambda x: x[1]
            )

    event_course = st.text_input("⛳ 比赛球场（可选）")

    st.divider()

    # 计算积分
    if st.button("🚀 开始计算积分", type="primary", use_container_width=True):
        with st.spinner("正在计算积分..."):
            # 计算积分
            points_results = calculate_event_points(
                results,
                event_type[0],
                is_special
            )

            # 按积分排序
            points_results.sort(key=lambda x: x['total_points'], reverse=True)

            # 显示结果
            st.subheader("📊 积分计算结果")

            # 高亮显示
            def highlight_champions(row):
                if row.get('总杆冠军') == '✓':
                    return ['background-color: gold; color: black'] * len(row)
                elif row.get('净杆排名') == 1:
                    return ['background-color: #d4edda'] * len(row)
                return [''] * len(row)

            # 创建 DataFrame - 修复列名问题
            display_df = pd.DataFrame([
                {
                    '净杆排名': r.get('net_rank', '-'),
                    '姓名': r['name'],
                    '总杆': r.get('gross', r.get('gross_score', '-')),
                    '净杆': r.get('net', r.get('net_score', '-')),
                    '基础分': r.get('base_points', 0),
                    '奖励分': r.get('bonus_points', 0),
                    '总积分': r.get('total_points', 0),
                    '总杆冠军': '✓' if r.get('is_gross_champion', False) else ''
                }
                for r in points_results
            ])

            # 应用样式 - 使用新的 width 参数替代 use_container_width
            styled_df = display_df.style.apply(highlight_champions, axis=1)
            st.dataframe(styled_df, width='stretch')

            # 保存到 session state 供后续使用
            st.session_state['points_results'] = points_results
            st.session_state['event_data'] = {
                'date': event_date.isoformat(),
                'name': event_name,
                'type': event_type[0],
                'is_special': is_special,
                'special_type': special_type[0] if is_special else '',
                'course': event_course,
                'results': points_results
            }

            # 冠军展示
            champions = [r for r in points_results if r.get('is_gross_champion', False)]
            if champions:
                st.success(f"🏆 **总杆冠军**: {', '.join([c['name'] for c in champions])} "
                          f"(+30分奖励)")

            # 保存按钮
            st.divider()
            st.subheader("💾 保存到数据库")

            if st.button("✅ 确认并保存赛事结果", use_container_width=True):
                # 保存
                saved_event = db.save_event(st.session_state['event_data'])

                st.success(f"✅ 赛事「{event_name}」已成功保存！")
                st.balloons()

                # 清除导入的数据
                del st.session_state['imported_data']
                if 'points_results' in st.session_state:
                    del st.session_state['points_results']
                if 'event_data' in st.session_state:
                    del st.session_state['event_data']

# ========== 积分榜 ==========
elif page == "🏆 积分榜":
    st.title("🏆 年度积分排行榜")

    rankings = db.get_rankings()

    if not rankings:
        st.info("📭 暂无积分数据，请先添加赛事结果")
    else:
        # 显示前10名
        st.subheader("🥇 TOP 10 排行榜")

        top10 = rankings[:10]

        # 创建显示数据
        display_data = []
        for i, r in enumerate(top10):
            rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(r['rank'], f"{r['rank']}")
            display_data.append({
                '排名': rank_emoji,
                '姓名': r['name'],
                '总积分': r['total_points'],
                '参赛次数': r['events_count'],
                '周赛冠军': r.get('weekly_wins', 0),
                '月赛冠军': r.get('monthly_wins', 0)
            })

        df_rankings = pd.DataFrame(display_data)
        st.dataframe(df_rankings, width='stretch', hide_index=True)

        # 全部排名
        st.divider()
        st.subheader("📋 完整排名")

        # 添加搜索
        search_name = st.text_input("🔍 搜索球员姓名")

        filtered_rankings = rankings
        if search_name:
            filtered_rankings = [r for r in rankings if search_name.lower() in r['name'].lower()]

        all_data = []
        for r in filtered_rankings:
            all_data.append({
                '排名': r['rank'],
                '姓名': r['name'],
                '总积分': r['total_points'],
                '参赛次数': r['events_count'],
                '周赛冠军': r.get('weekly_wins', 0),
                '月赛冠军': r.get('monthly_wins', 0)
            })

        df_all = pd.DataFrame(all_data)
        st.dataframe(df_all, width='stretch', hide_index=True)

        # 导出按钮
        st.divider()
        if st.button("📥 导出积分榜为 CSV"):
            csv = df_all.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="下载 CSV 文件",
                data=csv,
                file_name=f"积分排行榜_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

# ========== 统计报表 ==========
elif page == "📈 统计报表":
    st.title("📈 统计报表")

    stats = db.get_statistics()

    # 概览卡片
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📅 总赛事数", stats['total_events'])
    with col2:
        st.metric("🏌️ 参赛人数", stats['total_players'])
    with col3:
        st.metric("🎯 总积分", stats['total_points_issued'])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("周例赛", stats['weekly_events'])
    with col2:
        st.metric("月度大赛", stats['monthly_events'])
    with col3:
        st.metric("特殊赛事", stats['special_events'])

    st.divider()

    # 球员查询
    st.subheader("🔍 球员参赛记录查询")

    all_players = [r['name'] for r in db.get_rankings()]
    if all_players:
        selected_player = st.selectbox("选择球员", all_players)

        if selected_player:
            history = db.get_player_history(selected_player)
            stats_player = db.get_player_stats(selected_player)

            if stats_player:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("总积分", stats_player['total_points'])
                with col2:
                    st.metric("参赛次数", stats_player['events_count'])
                with col3:
                    st.metric("冠军次数",
                              stats_player.get('weekly_wins', 0) + stats_player.get('monthly_wins', 0))

            if history:
                df_history = pd.DataFrame(history)
                st.dataframe(df_history, width='stretch')
            else:
                st.info("暂无参赛记录")

# ========== 赛事记录 ==========
elif page == "📋 赛事记录":
    st.title("📋 赛事记录")

    events = db.get_events()

    if not events:
        st.info("📭 暂无赛事记录")
    else:
        # 筛选
        col1, col2 = st.columns(2)
        with col1:
            filter_type = st.selectbox(
                "筛选赛事类型",
                options=["全部", "月度大赛", "周例赛"]
            )

        filtered_events = events
        if filter_type == "月度大赛":
            filtered_events = [e for e in events if e.get('type') == 'monthly']
        elif filter_type == "周例赛":
            filtered_events = [e for e in events if e.get('type') == 'weekly']

        # 显示赛事列表
        for event in filtered_events:
            with st.expander(f"📅 {event.get('date', '未知日期')} - {event.get('name', '未命名')}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**类型**: {'月度大赛' if event.get('type') == 'monthly' else '周例赛'}")
                with col2:
                    st.write(f"**参赛人数**: {len(event.get('results', []))}")
                with col3:
                    if event.get('is_special'):
                        st.write("⭐ **特殊赛事**")

                if event.get('course'):
                    st.write(f"**球场**: {event['course']}")

                # 显示前5名
                results = event.get('results', [])
                results.sort(key=lambda x: x.get('total_points', 0), reverse=True)

                if results:
                    st.write("**前五名**:")
                    top5_data = []
                    for r in results[:5]:
                        top5_data.append({
                            '排名': r.get('net_rank', '-'),
                            '姓名': r['name'],
                            '净杆': r.get('net_score', '-'),
                            '积分': r.get('total_points', 0)
                        })
                    st.dataframe(pd.DataFrame(top5_data), hide_index=True)

                # 删除按钮
                if st.button(f"🗑️ 删除此赛事", key=f"del_{event.get('id')}"):
                    if db.delete_event(event.get('id')):
                        st.success("赛事已删除")
                        st.rerun()

# ========== 数据管理 ==========
elif page == "⚙️ 数据管理":
    st.title("⚙️ 数据管理")

    st.warning("⚠️ 此页面用于数据备份和恢复，请谨慎操作")

    st.divider()

    # 导出数据
    st.subheader("📤 导出数据")

    export_type = st.selectbox(
        "选择导出内容",
        options=[("all", "全部数据"), ("events", "赛事记录"),
                 ("rankings", "积分排名"), ("players", "球员信息")]
    )

                if st.button("📥 导出为 JSON"):
        data = db.export_data(export_type[0])
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        st.download_button(
            label="下载 JSON 文件",
            data=json_str.encode('utf-8'),
            file_name=f"golf_data_{export_type[0]}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )

                # 保存按钮
            st.divider()
            st.subheader("💾 保存到数据库")

            if st.button("✅ 确认并保存赛事结果", use_container_width=True):
                try:
                    with st.spinner("正在保存..."):
                        # 准备数据
                        event_data = {
                            'date': event_date.isoformat(),
                            'name': event_name,
                            'type': event_type[0],
                            'is_special': is_special,
                            'special_type': special_type[0] if is_special else '',
                            'course': event_course,
                            'results': points_results
                        }
                        
                        # 保存
                        saved_event = db.save_event(event_data)
                        
                        st.success(f"✅ 赛事「{event_name}」已成功保存！")
                        st.balloons()
                        
                        # 清除导入的数据
                        del st.session_state['imported_data']
                        if 'points_results' in st.session_state:
                            del st.session_state['points_results']
                        if 'event_data' in st.session_state:
                            del st.session_state['event_data']
                except Exception as e:
                    st.error(f"❌ 保存失败: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

    # 关于
    st.subheader("ℹ️ 关于")
    st.markdown("""
    **加纳中华高球队积分系统**

    - 版本: 1.0
    - 基于球队积分规则开发
    - 支持 GolfLive 数据导入
    - 自动计算周例赛和月度大赛积分

    **积分规则摘要：**
    - 周例赛：净杆前3名得分（30/20/10）
    - 月度大赛：全员得分，总杆冠军+30分
    - 特殊赛事：队长杯、年终大赛积分×2
    """)
