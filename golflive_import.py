"""
GolfLive 数据导入模块
支持导入 CSV/Excel 格式的比赛结果
"""

import pandas as pd
from typing import List, Dict, Optional
import io


# GolfLive 可能的列名映射
COLUMN_MAPPINGS = {
    'name': ['姓名', 'Name', 'Player', '球员', 'name', 'NAME', '选手'],
    'gross_score': ['总杆', 'Gross', 'Total', 'Score', 'gross', 'GROSS', '总成绩', '杆数'],
    'net_score': ['净杆', 'Net', 'net', 'NET', '净成绩'],
    'handicap': ['差点', 'HCP', 'Handicap', 'handicap', 'HANDICAP', '差點']
}


def detect_columns(df: pd.DataFrame) -> Dict[str, str]:
    """
    自动检测列名映射
    
    返回:
        {标准列名: 实际列名} 的字典
    """
    detected = {}
    df_columns = list(df.columns)
    
    for standard_name, possible_names in COLUMN_MAPPINGS.items():
        for col in df_columns:
            if col in possible_names:
                detected[standard_name] = col
                break
    
    return detected


def import_golflive_data(file_content: bytes, file_type: str = 'csv') -> List[Dict]:
    """
    导入 GolfLive 数据
    
    Args:
        file_content: 文件内容（二进制）
        file_type: 'csv' 或 'excel'
    
    Returns:
        标准化后的球员数据列表
    """
    # 读取数据
    if file_type.lower() in ['csv', 'text/csv']:
        # 尝试不同编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            raise ValueError("无法识别文件编码，请确保文件为 UTF-8 或 GBK 编码的 CSV 文件")
    
    elif file_type.lower() in ['excel', 'xlsx', 'xls', 
                               'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
        df = pd.read_excel(io.BytesIO(file_content))
    
    else:
        raise ValueError(f"不支持的文件类型: {file_type}")
    
    # 清理数据
    df = df.dropna(how='all')  # 删除全空行
    
    # 自动检测列名
    column_map = detect_columns(df)
    
    # 检查必需列
    required_columns = ['name', 'gross_score']
    missing_columns = [col for col in required_columns if col not in column_map]
    
    if missing_columns:
        # 尝试使用第一列作为姓名，查找包含"杆"或数字的列作为成绩
        if 'name' not in column_map and len(df.columns) > 0:
            column_map['name'] = df.columns[0]
        
        # 查找可能的成绩列
        if 'gross_score' not in column_map:
            for col in df.columns:
                if any(keyword in str(col) for keyword in ['杆', 'Score', 'score', 'Gross', 'gross']):
                    column_map['gross_score'] = col
                    break
    
    # 再次检查
    if 'name' not in column_map or 'gross_score' not in column_map:
        raise ValueError(
            f"无法识别必需的列。请确保文件包含以下列之一:\n"
            f"姓名: {COLUMN_MAPPINGS['name']}\n"
            f"总杆: {COLUMN_MAPPINGS['gross_score']}"
        )
    
    # 提取数据
    results = []
    for _, row in df.iterrows():
        try:
            player_data = {
                'name': str(row[column_map['name']]).strip(),
                'gross_score': int(float(row[column_map['gross_score']])),
            }
            
            # 净杆（可选）
            if 'net_score' in column_map:
                net_val = row[column_map['net_score']]
                if pd.notna(net_val):
                    player_data['net_score'] = float(net_val)
            
            # 差点（可选）
            if 'handicap' in column_map:
                hcp_val = row[column_map['handicap']]
                if pd.notna(hcp_val):
                    player_data['handicap'] = float(hcp_val)
            
            results.append(player_data)
        except (ValueError, TypeError):
            # 跳过无效行
            continue
    
    return results


def process_golflive_file(file_obj) -> List[Dict]:
    """
    处理上传的 GolfLive 文件
    
    Args:
        file_obj: Streamlit 上传的文件对象
    
    Returns:
        标准化后的球员数据列表
    """
    content = file_obj.getvalue()
    
    # 检测文件类型
    file_type = file_obj.type
    if not file_type:
        # 从文件名推断
        filename = file_obj.name.lower()
        if filename.endswith('.csv'):
            file_type = 'csv'
        elif filename.endswith(('.xlsx', '.xls')):
            file_type = 'excel'
        else:
            file_type = 'csv'  # 默认
    
    return import_golflive_data(content, file_type)


def validate_data(results: List[Dict]) -> Dict:
    """
    验证导入的数据
    
    返回验证结果统计
    """
    stats = {
        'total_players': len(results),
        'valid_records': 0,
        'missing_net_score': 0,
        'missing_handicap': 0,
        'invalid_scores': 0,
        'warnings': []
    }
    
    for player in results:
        # 检查必需字段
        if not player.get('name'):
            stats['warnings'].append(f"记录缺少姓名: {player}")
            continue
        
        try:
            gross = int(player.get('gross_score', 0))
            if gross < 50 or gross > 200:
                stats['warnings'].append(f"{player['name']} 的总杆成绩 {gross} 看起来不太正常")
                stats['invalid_scores'] += 1
        except (ValueError, TypeError):
            stats['warnings'].append(f"{player['name']} 的总杆成绩无效")
            stats['invalid_scores'] += 1
            continue
        
        stats['valid_records'] += 1
        
        # 检查可选字段
        if 'net_score' not in player:
            stats['missing_net_score'] += 1
        if 'handicap' not in player:
            stats['missing_handicap'] += 1
    
    return stats


def preview_data(results: List[Dict], max_rows: int = 10) -> pd.DataFrame:
    """
    生成数据预览
    """
    if not results:
        return pd.DataFrame()
    
    df = pd.DataFrame(results)
    return df.head(max_rows)
