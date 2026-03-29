"""
数据存储管理模块 - Google Sheets
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import streamlit as st


class Database:
    """Google Sheets 数据库"""
    
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
    
    def _get_all_records(self, worksheet) -> List[Dict]:
        try:
            return worksheet.get_all_records()
        except:
            return []
    
    def _append_row(self, worksheet, row_data: List):
        worksheet.append_row(row_data)
    
    def _update_cell(self, worksheet, row: int, col: int, value):
        worksheet.update_cell(row, col, value)
    
    def get_players(self) -> List[Dict]:
        return self._get_all_records(self.players_ws)
    
    def save_event(self, event_data: Dict) -> Dict:
        """保存赛事记录"""
        events = self._get_all_records(self.events_ws)
        event_id = len(events) + 1
        
        results_json = json.dumps(event_data.get('results', []), ensure_ascii=False)
        
        row_data = [
            event_id,
            event_data.get('date', ''),
            event_data.get('name', ''),
            event_data.get('type', ''),
            event_data.get('is_special', False),
            event_data.get('special_type', ''),
            event_data.get('course', ''),
            results_json
        ]
        
        self._append_row(self.events_ws, row_data)
        
        # 更新排名
        self._update_rankings(event_data)
        
        return {'id': event_id, 'name': event_data.get('name')}
    
    def get_events(self, event_type: Optional[str] = None) -> List[Dict]:
        events = self._get_all_records(self.events_ws)
        
        for event in events:
            try:
                event['results'] = json.loads(event.get('results', '[]'))
            except:
                event['results'] = []
        
        if event_type:
            events = [e for e in events if e.get('type') == event_type]
        
        return sorted(events, key=lambda x: x.get('date', ''), reverse=True)
    
    def delete_event(self, event_id: int) -> bool:
        try:
            events = self._get_all_records(self.events_ws)
            for i, event in enumerate(events):
                if event.get('id') == event_id:
                    self.events_ws.delete_rows(i + 2)
                    self._recalculate_all_rankings()
                    return True
            return False
        except Exception as e:
            st.error(f"删除失败: {e}")
            return False
    
    def _update_rankings(self, event: Dict):
        """更新积分排名"""
        rankings = self._get_all_records(self.rankings_ws)
        rankings_dict = {r['name']: (i, r) for i, r in enumerate(rankings)}
        
        for result in event.get('results', []):
            name = result['name']
            points = result.get('total_points', 0)
            
            if name in rankings_dict:
                idx, record = rankings_dict[name]
                new_total = record['total_points'] + points
                new_count = record['events_count'] + 1
                
                row_num = idx + 2
                self._update_cell(self.rankings_ws, row_num, 3, new_total)
                self._update_cell(self.rankings_ws, row_num, 4, new_count)
                
                if event.get('type') == 'weekly' and result.get('net_rank') == 1:
                    new_weekly = record.get('weekly_wins', 0) + 1
                    self._update_cell(self.rankings_ws, row_num, 5, new_weekly)
                
                if event.get('type') == 'monthly' and result.get('net_rank') == 1:
                    new_monthly = record.get('monthly_wins', 0) + 1
                    self._update_cell(self.rankings_ws, row_num, 6, new_monthly)
                
                self._update_cell(self.rankings_ws, row_num, 8, datetime.now().isoformat())
            else:
                new_id = len(rankings) + 1
                new_record = [
                    new_id,
                    name,
                    points,
                    1,
                    1 if (event.get('type') == 'weekly' and result.get('net_rank') == 1) else 0,
                    1 if (event.get('type') == 'monthly' and result.get('net_rank') == 1) else 0,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ]
                self._append_row(self.rankings_ws, new_record)
    
    def _recalculate_all_rankings(self):
        all_data = self.rankings_ws.get_all_values()
        if len(all_data) > 1:
            self.rankings_ws.delete_rows(2, len(all_data))
        
        events = self.get_events()
        for event in events:
            self._update_rankings(event)
    
    def get_rankings(self) -> List[Dict]:
        rankings = self._get_all_records(self.rankings_ws)
        rankings.sort(key=lambda x: x.get('total_points', 0), reverse=True)
        
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
                if result['name'] == name:
                    history.append({
                        'event_name': event.get('name'),
                        'date': event.get('date'),
                        'total_points': result.get('total_points')
                    })
        return sorted(history, key=lambda x: x.get('date', ''), reverse=True)
    
    def get_statistics(self) -> Dict:
        events = self.get_events()
        rankings = self.get_rankings()
        
        return {
            'total_events': len(events),
            'total_players': len(rankings),
            'total_points_issued': sum(r['total_points'] for r in rankings),
            'weekly_events': len([e for e in events if e.get('type') == 'weekly']),
            'monthly_events': len([e for e in events if e.get('type') == 'monthly']),
            'special_events': len([e for e in events if e.get('is_special')])
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
