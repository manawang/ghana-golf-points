"""
数据存储管理模块
使用 Google Sheets 作为云数据库（通过 Streamlit Secrets 配置）
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import streamlit as st


class Database:
    """Google Sheets 数据库"""
    
    def __init__(self):
        # 从 Streamlit secrets 读取配置
        try:
            self.sheet_id = st.secrets.get("SHEET_ID", os.getenv("SHEET_ID"))
        except:
            self.sheet_id = os.getenv("SHEET_ID")
        
        if not self.sheet_id:
            raise ValueError("请设置 SHEET_ID 环境变量")
        
        # 使用 gspread 连接 Google Sheets
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            # 从 secrets 获取 credentials
            creds_dict = st.secrets.get("gcp_service_account", {})
            
            if not creds_dict:
                raise ValueError("请配置 gcp_service_account")
            
            credentials = Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            gc = gspread.authorize(credentials)
            self.sheet = gc.open_by_key(self.sheet_id)
            
            # 获取工作表
            self.events_ws = self.sheet.worksheet("events")
            self.rankings_ws = self.sheet.worksheet("rankings")
            self.players_ws = self.sheet.worksheet("players")
            
        except Exception as e:
            st.error(f"连接 Google Sheets 失败: {e}")
            raise e
    
    def _get_all_records(self, worksheet) -> List[Dict]:
        """获取工作表所有记录"""
        try:
            return worksheet.get_all_records()
        except:
            return []
    
    def _append_row(self, worksheet, row_data: List):
        """添加一行数据"""
        worksheet.append_row(row_data)
    
    def _update_cell(self, worksheet, row: int, col: int, value):
        """更新单元格"""
        worksheet.update_cell(row, col, value)
    
    # ========== 球员管理 ==========
    
    def get_players(self) -> List[Dict]:
        """获取所有球员"""
        return self._get_all_records(self.players_ws)
    
    def add_player(self, name: str, handicap: float = 0.0, **kwargs) -> Dict:
        """添加球员"""
        players = self.get_players()
        
        # 检查是否已存在
        for player in players:
            if player['name'] == name:
                return player
        
        # 创建新球员
        new_id = len(players) + 1
        new_player = [
            new_id,
            name,
            handicap,
            datetime.now().isoformat()
        ]
        
        self._append_row(self.players_ws, new_player)
        
        return {'id': new_id, 'name': name, 'handicap': handicap}
    
    def get_player_by_name(self, name: str) -> Optional[Dict]:
        """根据姓名查找球员"""
        players = self.get_players()
        for player in players:
            if player['name'] == name:
                return player
        return None
    
    # ========== 赛事管理 ==========
    
    def save_event(self, event_data: Dict) -> Dict:
        """保存赛事记录"""
        events = self._get_all_records(self.events_ws)
        
        # 生成赛事 ID
        event_id = len(events) + 1
        
        # 添加行数据
        row_data = [
            event_id,
            event_data.get('date', ''),
            event_data.get('name', ''),
            event_data.get('type', ''),
            event_data.get('is_special', False),
            event_data.get('special_type', ''),
            event_data.get('course', ''),
            json.dumps(event_data.get('results', []), ensure_ascii=False)
        ]
        
        self._append_row(self.events_ws, row_data)
        
        # 构建返回对象
        saved_event = {
            'id': event_id,
            'date': event_data.get('date'),
            'name': event_data.get('name'),
            'type': event_data.get('type'),
            'is_special': event_data.get('is_special'),
            'special_type': event_data.get('special_type'),
            'course': event_data.get('course'),
            'results': event_data.get('results', [])
        }
        
        # 更新积分排名
        self._update_rankings(saved_event)
        
        return saved_event
    
    def get_events(self, event_type: Optional[str] = None) -> List[Dict]:
        """获取所有赛事记录"""
        events = self._get_all_records(self.events_ws)
        
        # 解析 results JSON
        for event in events:
            try:
                event['results'] = json.loads(event.get('results', '[]'))
            except:
                event['results'] = []
        
        if event_type:
            events = [e for e in events if e.get('type') == event_type]
        
        # 按日期排序（降序）
        return sorted(events, key=lambda x: x.get('date', ''), reverse=True)
    
    def get_event_by_id(self, event_id: int) -> Optional[Dict]:
        """根据 ID 获取赛事"""
        events = self.get_events()
        for event in events:
            if event.get('id') == event_id:
                return event
        return None
    
    def delete_event(self, event_id: int) -> bool:
        """删除赛事记录"""
        try:
            events = self._get_all_records(self.events_ws)
            for i, event in enumerate(events):
                if event.get('id') == event_id:
                    # 删除行（i+2 因为第1行是表头）
                    self.events_ws.delete_rows(i + 2)
                    self._recalculate_all_rankings()
                    return True
            return False
        except Exception as e:
            print(f"删除赛事失败: {e}")
            return False
    
    # ========== 积分排名 ==========
    
    def _update_rankings(self, event: Dict):
        """根据赛事更新积分排名"""
        rankings = self._get_all_records(self.rankings_ws)
        
        # 转换为字典便于查找
        rankings_dict = {r['name']: (i, r) for i, r in enumerate(rankings)}
        
        for result in event.get('results', []):
            name = result['name']
            points = result.get('total_points', 0)
            
            if name in rankings_dict:
                # 更新现有记录
                idx, record = rankings_dict[name]
                new_total = record['total_points'] + points
                new_count = record['events_count'] + 1
                
                # 更新单元格
                row_num = idx + 2  # +2 因为第1行是表头
                self._update_cell(self.rankings_ws, row_num, 3, new_total)  # total_points
                self._update_cell(self.rankings_ws, row_num, 4, new_count)  # events_count
                
                # 统计冠军次数
                if event.get('type') == 'weekly' and result.get('net_rank') == 1:
                    new_weekly = record.get('weekly_wins', 0) + 1
                    self._update_cell(self.rankings_ws, row_num, 5, new_weekly)
                if event.get('type') == 'monthly' and result.get('net_rank') == 1:
                    new_monthly = record.get('monthly_wins', 0) + 1
                    self._update_cell(self.rankings_ws, row_num, 6, new_monthly)
                
                # 更新 updated_at
                self._update_cell(self.rankings_ws, row_num, 8, datetime.now().isoformat())
            else:
                # 创建新记录
                new_id = len(rankings) + 1
                new_record = [
                    new_id,
                    name,
                    points,
                    1,  # events_count
                    1 if (event.get('type') == 'weekly' and result.get('net_rank') == 1) else 0,
                    1 if (event.get('type') == 'monthly' and result.get('net_rank') == 1) else 0,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ]
                self._append_row(self.rankings_ws, new_record)
    
    def _recalculate_all_rankings(self):
        """重新计算所有排名（删除赛事后使用）"""
        try:
            # 清空排名表（保留表头）
            all_data = self.rankings_ws.get_all_values()
            if len(all_data) > 1:
                self.rankings_ws.delete_rows(2, len(all_data))
            
            # 重新计算
            events = self.get_events()
            for event in events:
                self._update_rankings(event)
        except Exception as e:
            print(f"重新计算排名失败: {e}")
    
    def get_rankings(self) -> List[Dict]:
        """获取当前积分排名"""
        rankings = self._get_all_records(self.rankings_ws)
        
        # 按积分排序
        rankings.sort(key=lambda x: x.get('total_points', 0), reverse=True)
        
        # 添加排名序号
        for i, r in enumerate(rankings, 1):
            r['rank'] = i
        
        return rankings
    
    def get_player_stats(self, name: str) -> Optional[Dict]:
        """获取球员统计信息"""
        rankings = self.get_rankings()
        for r in rankings:
            if r['name'] == name:
                return r
        return None
    
    def get_player_history(self, name: str) -> List[Dict]:
        """获取球员参赛历史"""
        events = self.get_events()
        history = []
        
        for event in events:
            for result in event.get('results', []):
                if result['name'] == name:
                    history.append({
                        'event_id': event.get('id'),
                        'event_name': event.get('name'),
                        'date': event.get('date'),
                        'type': event.get('type'),
                        'gross_score': result.get('gross_score'),
                        'net_score': result.get('net_score'),
                        'net_rank': result.get('net_rank'),
                        'total_points': result.get('total_points')
                    })
        
        return sorted(history, key=lambda x: x.get('date', ''), reverse=True)
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        events = self.get_events()
        rankings = self.get_rankings()
        
        total_events = len(events)
        total_players = len(rankings)
        total_points_issued = sum(r['total_points'] for r in rankings)
        weekly_count = len([e for e in events if e.get('type') == 'weekly'])
        monthly_count = len([e for e in events if e.get('type') == 'monthly'])
        special_count = len([e for e in events if e.get('is_special')])
        
        return {
            'total_events': total_events,
            'total_players': total_players,
            'total_points_issued': total_points_issued,
            'weekly_events': weekly_count,
            'monthly_events': monthly_count,
            'special_events': special_count
        }
    
    def export_data(self, export_type: str = 'all') -> Dict:
        """导出数据"""
        data = {}
        
        if export_type in ['all', 'events']:
            data['events'] = self.get_events()
        
        if export_type in ['all', 'rankings']:
            data['rankings'] = self.get_rankings()
        
        if export_type in ['all', 'players']:
            data['players'] = self.get_players()
        
        return data
