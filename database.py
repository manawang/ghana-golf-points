"""
数据存储管理模块 - Google Sheets (批量优化版)
解决 429 Quota exceeded 错误
"""

import json
import os
import time
from datetime import datetime
from typing import List, Dict, Optional
import streamlit as st


class Database:
    """Google Sheets 数据库 - 批量操作优化版"""
    
    def __init__(self):
        self.sheet_id = st.secrets.get("SHEET_ID", os.getenv("SHEET_ID"))
        
        if not self.sheet_id:
            raise ValueError("请设置 SHEET_ID 环境变量")
        
        import gspread
        from google.oauth2.service_account import Credentials
        
        creds_dict = st.secrets.get("gcp_service_account", {})
        
        if not creds_dict:
            raise ValueError("请配置 gcp_service_account")
        
        credentials = Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        
        gc = gspread.authorize(credentials)
        self.sheet = gc.open_by_key(self.sheet_id)
        
        self.events_ws = self.sheet.worksheet("events")
        self.rankings_ws = self.sheet.worksheet("rankings")
        self.players_ws = self.sheet.worksheet("players")
    
    # ========== 批量操作工具方法 ==========
    
    def _safe_api_call(self, func, max_retries=3, *args, **kwargs):
        """带重试机制的 API 调用"""
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + 1
                    st.warning(f"API 限流，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    raise
    
    def _get_all_records(self, worksheet) -> List[Dict]:
        """获取所有记录"""
        try:
            return worksheet.get_all_records()
        except Exception as e:
            st.warning(f"读取工作表失败: {e}")
            return []
    
    def _append_rows_batch(self, worksheet, rows_data: List[List]):
        """批量追加多行（一次 API 调用）"""
        if not rows_data:
            return
        return self._safe_api_call(worksheet.append_rows, 3, rows_data)
    
    def _clear_and_write_batch(self, worksheet, rows_data: List[List], header_row: List[str] = None):
        """清空并批量写入（最多 2 次 API 调用）"""
        # 获取当前数据
        all_values = worksheet.get_all_values()
        
        # 清空现有数据（保留表头）
        if len(all_values) > 1:
            self._safe_api_call(worksheet.delete_rows, 3, 2, len(all_values))
        
        # 批量写入新数据
        data_to_write = [header_row] + rows_data if header_row else rows_data
        if data_to_write:
            self._append_rows_batch(worksheet, data_to_write)
    
    # ========== 公共方法 ==========
    
    def get_players(self) -> List[Dict]:
        return self._get_all_records(self.players_ws)
    
    # ========== 保存赛事（批量优化） ==========
    
    def save_event(self, event_data: Dict) -> Dict:
        """保存赛事记录 - 批量写入优化"""
        
        # 1. 获取当前所有赛事，确定新 ID
        events = self._get_all_records(self.events_ws)
        event_id = len(events) + 1
        
        # 2. 准备赛事数据行（results 用 JSON 压缩存储）
        results_json = json.dumps(event_data.get('results', []), ensure_ascii=False)
        
        row_data = [
            event_id,
            event_data.get('date', ''),
            event_data.get('name', ''),
            event_data.get('type', ''),
            str(event_data.get('is_special', False)),
            event_data.get('special_type', ''),
            event_data.get('course', ''),
            results_json
        ]
        
        # 3. 批量追加（1 次 API 调用）
        self._append_rows_batch(self.events_ws, [row_data])
        
        # 4. 批量更新排行榜
        self._update_rankings_batch(event_data)
        
        return {'id': event_id, 'name': event_data.get('name')}
    
    def _update_rankings_batch(self, new_event: Dict):
        """批量更新排行榜 - 内存计算后一次性写入"""
        
        # 读取现有排行榜
        rankings = self._get_all_records(self.rankings_ws)
        rankings_dict = {r['name']: dict(r) for r in rankings}
        
        # 在内存中更新所有数据
        for result in new_event.get('results', []):
            name = result['name']
            points = float(result.get('total_points', 0))
            
            if name in rankings_dict:
                record = rankings_dict[name]
                record['total_points'] = float(record.get('total_points', 0)) + points
                record['events_count'] = int(record.get('events_count', 0)) + 1
                
                # 更新冠军次数
                if new_event.get('type') == 'weekly' and result.get('net_rank') == 1:
                    record['weekly_wins'] = int(record.get('weekly_wins', 0)) + 1
                if new_event.get('type') == 'monthly' and result.get('net_rank') == 1:
                    record['monthly_wins'] = int(record.get('monthly_wins', 0)) + 1
                
                record['updated_at'] = datetime.now().isoformat()
            else:
                # 新球员
                rankings_dict[name] = {
                    'id': len(rankings_dict) + 1,
                    'name': name,
                    'total_points': points,
                    'events_count': 1,
                    'weekly_wins': 1 if (new_event.get('type') == 'weekly' and result.get('net_rank') == 1) else 0,
                    'monthly_wins': 1 if (new_event.get('type') == 'monthly' and result.get('net_rank') == 1) else 0,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
        
        # 按积分排序（确保所有值为数值类型）
        for r in rankings_dict.values():
            r['total_points'] = float(r.get('total_points', 0) or 0)
        
        sorted_rankings = sorted(
            rankings_dict.values(),
            key=lambda x: x['total_points'],
            reverse=True
        )
        
        # 准备批量写入数据
        header = ['id', 'name', 'total_points', 'events_count', 'weekly_wins', 'monthly_wins', 'created_at', 'updated_at']
        rows_data = []
        for i, r in enumerate(sorted_rankings, 1):
            rows_data.append([
                i,
                r['name'],
                r['total_points'],
                r['events_count'],
                r.get('weekly_wins', 0),
                r.get('monthly_wins', 0),
                r.get('created_at', datetime.now().isoformat()),
                r.get('updated_at', datetime.now().isoformat())
            ])
        
        # 批量写入排行榜（2 次 API 调用）
        self._clear_and_write_batch(self.rankings_ws, rows_data, header)
    
    # ========== 读取赛事 ==========
    
    def get_events(self, event_type: Optional[str] = None) -> List[Dict]:
        """获取所有赛事记录"""
        events = self._get_all_records(self.events_ws)
        
        result = []
        for event in events:
            try:
                # 解析 results JSON
                results_str = event.get('results', '[]')
                if isinstance(results_str, str):
                    event['results'] = json.loads(results_str)
                else:
                    event['results'] = []
                
                # 类型过滤
                if event_type is None or event.get('type') == event_type:
                    result.append(event)
            except Exception as e:
                continue
        
        # 按日期倒序
        return sorted(result, key=lambda x: str(x.get('date', '')), reverse=True)
    
    # ========== 删除赛事（批量优化） ==========
    
    def delete_event(self, event_id) -> bool:
        """删除赛事 - 批量操作优化"""
        try:
            # 读取所有事件
            events = self._get_all_records(self.events_ws)
            
            # 找到要删除的行号
            rows_to_delete = []
            for i, event in enumerate(events):
                if str(event.get('id')) == str(event_id):
                    rows_to_delete.append(i + 2)
            
            if not rows_to_delete:
                st.warning(f"未找到赛事 ID: {event_id}")
                return False
            
            # 从后往前删除
            for row_num in sorted(rows_to_delete, reverse=True):
                self._safe_api_call(self.events_ws.delete_rows, 3, row_num)
                time.sleep(0.3)
            
            # 批量重新计算排行榜
            self._recalculate_all_rankings_batch()
            
            return True
            
        except Exception as e:
            st.error(f"删除失败: {e}")
            return False
    
    def _recalculate_all_rankings_batch(self):
        """批量重新计算所有排行榜"""
        
        # 读取所有赛事
        events = self._get_all_records(self.events_ws)
        
        # 在内存中汇总
        player_stats = {}
        
        for event in events:
            try:
                results_str = event.get('results', '[]')
                results = json.loads(results_str) if isinstance(results_str, str) else []
            except:
                continue
            
            for result in results:
                name = result.get('name')
                if not name:
                    continue
                
                points = float(result.get('total_points', 0))
                
                if name not in player_stats:
                    player_stats[name] = {
                        'total_points': 0,
                        'events_count': 0,
                        'weekly_wins': 0,
                        'monthly_wins': 0
                    }
                
                player_stats[name]['total_points'] += points
                player_stats[name]['events_count'] += 1
                
                # 冠军统计
                if result.get('net_rank') == 1 or result.get('net_rank') == '1':
                    if event.get('type') == 'weekly':
                        player_stats[name]['weekly_wins'] += 1
                    elif event.get('type') == 'monthly':
                        player_stats[name]['monthly_wins'] += 1
        
        # 排序并准备数据
        sorted_players = sorted(
            player_stats.items(),
            key=lambda x: x[1]['total_points'],
            reverse=True
        )
        
        header = ['id', 'name', 'total_points', 'events_count', 'weekly_wins', 'monthly_wins', 'created_at', 'updated_at']
        rows_data = []
        
        for i, (name, stats) in enumerate(sorted_players, 1):
            rows_data.append([
                i,
                name,
                stats['total_points'],
                stats['events_count'],
                stats['weekly_wins'],
                stats['monthly_wins'],
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ])
        
        # 批量写入
        self._clear_and_write_batch(self.rankings_ws, rows_data, header)
    
    # ========== 排行榜 ==========
    
    def get_rankings(self) -> List[Dict]:
        """获取排行榜"""
        rankings = self._get_all_records(self.rankings_ws)
        
        # 按积分排序
        rankings.sort(key=lambda x: float(x.get('total_points', 0)), reverse=True)
        
        # 添加排名
        for i, r in enumerate(rankings, 1):
            r['rank'] = i
        
        return rankings
    
    def get_player_stats(self, name: str) -> Optional[Dict]:
        rankings = self.get_rankings()
        for r in rankings:
            if r['name'] == name:
                return r
        return None
    
    def get_player_history(self, name: str) -> List[Dict]:
        events = self.get_events()
        history = []
        for event in events:
            for result in event.get('results', []):
                if result.get('name') == name:
                    history.append({
                        'event_name': event.get('name'),
                        'date': event.get('date'),
                        'total_points': result.get('total_points')
                    })
        return sorted(history, key=lambda x: x.get('date', ''), reverse=True)
    
    def get_statistics(self) -> Dict:
        events = self.get_events()
        rankings = self.get_rankings()
        
        total_points = sum(float(r.get('total_points', 0)) for r in rankings)
        
        return {
            'total_events': len(events),
            'total_players': len(rankings),
            'total_points_issued': int(total_points),
            'weekly_events': len([e for e in events if e.get('type') == 'weekly']),
            'monthly_events': len([e for e in events if e.get('type') == 'monthly']),
            'special_events': len([e for e in events if str(e.get('is_special')).lower() == 'true'])
        }
    
    def export_data(self, export_type: str = 'all') -> Dict:
        data = {}
        if export_type in ['all', 'events']:
            data['events'] = self.get_events()
        if export_type in ['all', 'rankings']:
            data['rankings'] = self.get_rankings()
        if export_type in ['all', 'players']:
            data['players'] = self.get_players()
        return data
