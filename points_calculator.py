"""
加纳中华高球队积分计算模块
根据球队规则计算周例赛和月度大赛积分
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    """赛事类型"""
    WEEKLY = "周例赛"
    MONTHLY = "月度大赛"


class SpecialEventType(Enum):
    """特殊赛事类型"""
    NONE = "普通赛事"
    CAPTAINS_PRIZE = "队长杯"
    YEAR_END = "年终月度大赛"


@dataclass
class PlayerResult:
    """球员比赛结果"""
    name: str
    gross_score: int  # 总杆
    net_score: float  # 净杆
    handicap: float = 0.0  # 差点
    
    def __post_init__(self):
        # 如果没有提供净杆，用总杆减差点估算
        if self.net_score == 0 and self.handicap > 0:
            self.net_score = self.gross_score - self.handicap


@dataclass
class PlayerPoints:
    """球员积分结果"""
    name: str
    gross_score: int
    net_score: float
    gross_rank: int = 0  # 总杆排名
    net_rank: int = 0    # 净杆排名
    base_points: int = 0  # 基础积分
    bonus_points: int = 0  # 奖励积分（总杆冠军）
    total_points: int = 0  # 总积分
    is_gross_champion: bool = False


class PointsCalculator:
    """积分计算器"""
    
    # 周例赛积分表（净杆前3名）
    WEEKLY_POINTS = {
        1: 30,
        2: 20,
        3: 10
    }
    
    # 月度大赛积分表（净杆排名）
    MONTHLY_POINTS = {
        1: 100,
        2: 70,
        3: 60,
        4: 52,
        5: 46,
        6: 41,
        7: 37,
        8: 34,
        9: 31,
        10: 28,
    }
    
    # 第11-15名的积分（线性递减）
    for i in range(11, 16):
        MONTHLY_POINTS[i] = int(26 - (i - 11) * 1.6)
    
    # 第16-25名的积分（线性递减）
    for i in range(16, 26):
        MONTHLY_POINTS[i] = int(17 - (i - 16) * 0.7)
    
    # 第26-50名的积分（线性递减，最低5分）
    for i in range(26, 51):
        MONTHLY_POINTS[i] = max(5, int(9 - (i - 26) * 0.15))
    
    # 总杆冠军额外奖励
    GROSS_CHAMPION_BONUS = 30
    
    def __init__(self, event_type: EventType, special_event: SpecialEventType = SpecialEventType.NONE):
        self.event_type = event_type
        self.special_event = special_event
        self.multiplier = 2 if special_event != SpecialEventType.NONE else 1
    
    def calculate_weekly_points(self, results: List[PlayerResult]) -> List[PlayerPoints]:
        """
        计算周例赛积分
        仅净杆前3名得分
        """
        # 按净杆排序（低到高）
        sorted_by_net = sorted(results, key=lambda x: x.net_score)
        
        # 确定排名（处理并列）
        net_ranks = self._calculate_ranks(sorted_by_net, key=lambda x: x.net_score)
        
        player_points_list = []
        for i, (player, net_rank) in enumerate(zip(sorted_by_net, net_ranks)):
            # 计算积分（处理并列平分）
            points = self._get_weekly_points_with_tie(net_rank, sorted_by_net)
            
            pp = PlayerPoints(
                name=player.name,
                gross_score=player.gross_score,
                net_score=player.net_score,
                net_rank=net_rank,
                base_points=points * self.multiplier,
                total_points=points * self.multiplier
            )
            player_points_list.append(pp)
        
        # 按原始顺序返回
        name_order = {r.name: i for i, r in enumerate(results)}
        player_points_list.sort(key=lambda x: name_order[x.name])
        
        return player_points_list
    
    def calculate_monthly_points(self, results: List[PlayerResult]) -> List[PlayerPoints]:
        """
        计算月度大赛积分
        全员得分，总杆冠军额外+30分
        """
        # 按净杆和总杆排序
        sorted_by_net = sorted(results, key=lambda x: x.net_score)
        sorted_by_gross = sorted(results, key=lambda x: x.gross_score)
        
        # 确定排名
        net_ranks = self._calculate_ranks(sorted_by_net, key=lambda x: x.net_score)
        gross_ranks = self._calculate_ranks(sorted_by_gross, key=lambda x: x.gross_score)
        
        # 创建净杆排名映射
        net_rank_map = {p.name: r for p, r in zip(sorted_by_net, net_ranks)}
        
        # 确定总杆冠军（可能有并列）
        gross_champions = [p.name for p, r in zip(sorted_by_gross, gross_ranks) if r == 1]
        
        player_points_list = []
        for i, player in enumerate(sorted_by_net):
            net_rank = net_ranks[i]
            gross_rank = gross_ranks[sorted_by_gross.index(player)]
            
            # 获取基础积分（按净杆排名）
            base_points = self.MONTHLY_POINTS.get(net_rank, 5)
            
            # 总杆冠军额外奖励
            bonus_points = 0
            is_champion = player.name in gross_champions
            if is_champion:
                bonus_points = self.GROSS_CHAMPION_BONUS
            
            # 特殊赛事加倍
            total_points = (base_points + bonus_points) * self.multiplier
            
            pp = PlayerPoints(
                name=player.name,
                gross_score=player.gross_score,
                net_score=player.net_score,
                gross_rank=gross_rank,
                net_rank=net_rank,
                base_points=base_points * self.multiplier,
                bonus_points=bonus_points * self.multiplier,
                total_points=total_points,
                is_gross_champion=is_champion
            )
            player_points_list.append(pp)
        
        # 按原始顺序返回
        name_order = {r.name: i for i, r in enumerate(results)}
        player_points_list.sort(key=lambda x: name_order[x.name])
        
        return player_points_list
    
    def _calculate_ranks(self, sorted_list: List, key=None) -> List[int]:
        """
        计算排名（处理并列情况）
        返回每个元素的排名（1-based）
        """
        if not sorted_list:
            return []
        
        ranks = []
        current_rank = 1
        
        for i, item in enumerate(sorted_list):
            if i == 0:
                ranks.append(current_rank)
            else:
                prev_value = key(sorted_list[i-1]) if key else sorted_list[i-1]
                curr_value = key(item) if key else item
                
                if curr_value == prev_value:
                    # 并列，使用相同排名
                    ranks.append(current_rank)
                else:
                    # 不并列，排名为位置+1
                    current_rank = i + 1
                    ranks.append(current_rank)
        
        return ranks
    
    def _get_weekly_points_with_tie(self, rank: int, sorted_players: List[PlayerResult]) -> int:
        """
        获取周例赛积分（处理并列平分）
        """
        if rank > 3:
            return 0
        
        # 找出该排名的所有玩家
        same_rank_players = [p for p in sorted_players if 
                            self._get_rank_in_sorted(p, sorted_players) == rank]
        
        # 计算应得积分总和
        points_to_distribute = 0
        positions_covered = 0
        
        for r in range(rank, rank + len(same_rank_players)):
            if r in self.WEEKLY_POINTS:
                points_to_distribute += self.WEEKLY_POINTS[r]
                positions_covered += 1
        
        # 平分积分
        if positions_covered > 0:
            return points_to_distribute // len(same_rank_players)
        
        return 0
    
    def _get_rank_in_sorted(self, player: PlayerResult, sorted_players: List[PlayerResult]) -> int:
        """获取玩家在排序列表中的排名"""
        for i, p in enumerate(sorted_players):
            if p.name == player.name:
                # 找到第一个相同净杆的位置
                for j in range(i, -1, -1):
                    if sorted_players[j].net_score != player.net_score:
                        return j + 2
                return 1
        return 0
    
    def calculate(self, results: List[PlayerResult]) -> List[PlayerPoints]:
        """
        根据赛事类型计算积分
        """
        if self.event_type == EventType.WEEKLY:
            return self.calculate_weekly_points(results)
        else:
            return self.calculate_monthly_points(results)


def calculate_event_points(results_data: List[Dict], 
                          event_type: str, 
                          is_special: bool = False) -> List[Dict]:
    """
    便捷函数：计算赛事积分
    
    Args:
        results_data: 比赛结果列表，每项包含 name, gross_score, net_score, handicap
        event_type: "weekly" 或 "monthly"
        is_special: 是否为特殊赛事（双倍积分）
    
    Returns:
        积分结果列表
    """
    # 转换为 PlayerResult 对象
    player_results = []
    for data in results_data:
        pr = PlayerResult(
            name=data['name'],
            gross_score=int(data['gross_score']),
            net_score=float(data.get('net_score', 0)),
            handicap=float(data.get('handicap', 0))
        )
        player_results.append(pr)
    
    # 确定赛事类型
    evt_type = EventType.WEEKLY if event_type.lower() == 'weekly' else EventType.MONTHLY
    special_type = SpecialEventType.CAPTAINS_PRIZE if is_special else SpecialEventType.NONE
    
    # 计算积分
    calculator = PointsCalculator(evt_type, special_type)
    points_results = calculator.calculate(player_results)
    
    # 转换为字典列表
    return [
        {
            'name': p.name,
            'gross_score': p.gross_score,
            'net_score': p.net_score,
            'gross_rank': p.gross_rank,
            'net_rank': p.net_rank,
            'base_points': p.base_points,
            'bonus_points': p.bonus_points,
            'total_points': p.total_points,
            'is_gross_champion': p.is_gross_champion
        }
        for p in points_results
    ]
