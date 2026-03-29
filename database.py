"""
数据存储管理模块
使用 JSON 文件存储球员信息、赛事记录和积分排名
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class Database:
    """简易 JSON 数据库"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 数据文件路径
        self.players_file = self.data_dir / "players.json"
        self.events_file = self.data_dir / "events.json"
        self.rankings_file = self.data_dir / "rankings.json"
        
        # 初始化数据
        self._init_data()
    
    def _init_data(self):
        """初始化数据文件"""
        for file_path in [self.players_file, self.events_file, self.rankings_file]:
            if not file_path.exists():
                self._save_json(file_path, [])
    
    def _load_json(self, file_path: Path) -> List[Dict]:
        """加载 JSON 文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _save_json(self, file_path: Path, data: List[Dict]):
        """保存 JSON 文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # ========== 球员管理 ==========
    
    def get_players(self) -> List[Dict]:
        """获取所有球员"""
        return self._load_json(self.players_file)
    
    def add_player(self, name: str, handicap: float = 0.0, **kwargs) -> Dict:
        """添加球员"""
        players = self.get_players()
        
        # 检查是否已存在
        for player in players:
            if player['name'] == name:
                return player
        
        # 创建新球员
        new_player = {
            'id': len(players) + 1,
            'name': name,
            'handicap': handicap,
            'created_at': datetime.now().isoformat(),
            **kwargs
        }
        
        players.append(new_player)
        self._save_json(self.players_file, players)
        
        return new_player
    
    def get_player_by_name(self, name: str) -> Optional[Dict]:
        """根据姓名查找球员"""
        players = self.get_players()
        for player in players:
            if player['name'] == name:
                return player
        return None
    
    # ========== 赛事管理 ==========
    
    def save_event(self, event_data: Dict) -> Dict:
        """
        保存赛事记录
        
        event_data 格式:
        {
            'date': '2024-03-30',
            'name': '3月月例赛',
            'type': 'monthly',  # 或 'weekly'
            'is_special': False,
            'special_type': '',  # 'captains_prize' 或 'year_end'
            'course': '球场名称',
            'results': [
                {
                    'name': '球员姓名',
                    'gross_score': 85,
                    'net_score': 72.5,
                    'total_points': 100
                }
            ]
        }
        """
        events = self._load_json(self.events_file)
        
        # 生成赛事 ID
        event_id = len(events) + 1
        
        # 添加元数据
        event_record = {
            'id': event_id,
            'created_at': datetime.now().isoformat(),
            **event_data
        }
        
        events.append(event_record)
        self._save_json(self.events_file, events)
        
        # 更新积分排名
        self._update_rankings(event_record)
        
        return event_record
    
    def get_events(self, event_type: Optional[str] = None) -> List[Dict]:
        """获取所有赛事记录"""
        events = self._load_json(self.events_file)
        
        if event_type:
            events = [e for e in events if e.get('type') == event_type]
        
        return sorted(events, key=lambda x: x.get('date', ''), reverse=True)
    
    def get_event_by_id(self, event_id: int) -> Optional[Dict]:
        """根据 ID 获取赛事"""
        events = self._load_json(self.events_file)
        for event in events:
            if event.get('id') == event_id:
                return event
        return None
    
    def delete_event(self, event_id: int) -> bool:
        """删除赛事记录"""
        events = self._load_json(self.events_file)
        original_len = len(events)
        events = [e for e in events if e.get('id') != event_id]
        
        if len(events) < original_len:
            self._save_json(self.events_file, events)
            self._recalculate_all_rankings()
            return True
        return False
    
    # ========== 积分排名 ==========
    
    def _update_rankings(self, event: Dict):
        """根据赛事更新积分排名"""
        rankings = self._load_json(self.rankings_file)
        
        # 转换为字典便于更新
        rankings_dict = {r['name']: r for r in rankings}
        
        for result in event.get('results', []):
            name = result['name']
            points = result.get('total_points', 0)
            
            if name in rankings_dict:
                # 更新现有记录
                rankings_dict[name]['total_points'] += points
                rankings_dict[name]['events_count'] += 1
                rankings_dict[name]['updated_at'] = datetime.now().isoformat()
            else:
                # 创建新记录
                rankings_dict[name] = {
                    'name': name,
                    'total_points': points,
                    'events_count': 1,
                    'weekly_wins': 0,
                    'monthly_wins': 0,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
            
            # 统计冠军次数
            if event.get('type') == 'weekly' and result.get('net_rank') == 1:
                rankings_dict[name]['weekly_wins'] += 1
            if event.get('type') == 'monthly' and result.get('net_rank') == 1:
                rankings_dict[name]['monthly_wins'] += 1
        
        # 转换回列表并排序
        rankings = list(rankings_dict.values())
        rankings.sort(key=lambda x: x['total_points'], reverse=True)
        
        # 更新排名
        for i, r in enumerate(rankings):
            r['rank'] = i + 1
        
        self._save_json(self.rankings_file, rankings)
    
    def _recalculate_all_rankings(self):
        """重新计算所有排名（删除赛事后使用）"""
        events = self._load_json(self.events_file)
        
        # 清空排名
        self._save_json(self.rankings_file, [])
        
        # 重新计算
        for event in events:
            self._update_rankings(event)
    
    def get_rankings(self) -> List[Dict]:
        """获取当前积分排名"""
        return self._load_json(self.rankings_file)
    
    def get_player_stats(self, name: str) -> Optional[Dict]:
        """获取球员统计信息"""
        rankings = self.get_rankings()
        for r in rankings:
            if r['name'] == name:
                return r
        return None
    
    def get_player_history(self, name: str) -> List[Dict]:
        """获取球员参赛历史"""
        events = self._load_json(self.events_file)
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
        events = self._load_json(self.events_file)
        rankings = self._load_json(self.rankings_file)
        
        total_events = len(events)
        total_players = len(rankings)
        
        # 计算总积分发放
        total_points_issued = sum(r['total_points'] for r in rankings)
        
        # 计算各类赛事数量
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
        """
        导出数据
        
        export_type: 'all', 'events', 'rankings', 'players'
        """
        data = {}
        
        if export_type in ['all', 'events']:
            data['events'] = self._load_json(self.events_file)
        
        if export_type in ['all', 'rankings']:
            data['rankings'] = self._load_json(self.rankings_file)
        
        if export_type in ['all', 'players']:
            data['players'] = self._load_json(self.players_file)
        
        return data


# 全局数据库实例
db = Database()
