import os
import json
from datetime import datetime
import re

import sys
sys.path.append('../')

from app import app
from database.models import db, WaterQuality

BASE_DIR = '../data/waterquality'

def extract_float(html_str):
    """提取 HTML span 标签中的浮点数值"""
    if html_str == "--":
        return None
    match = re.search(r">([\d\.]+)<", html_str)
    return float(match.group(1)) if match else None

from bs4 import BeautifulSoup

def clean_site_name(raw_html: str) -> str:
    try:
        return BeautifulSoup(raw_html, "html.parser").get_text()
    except:
        return raw_html  # fallback

def parse_monitor_time(raw_time, year="2024"):
    """
    将 '12-30 08:00' 转换为 '2024-12-30 08:00:00' 格式的 datetime 对象
    """
    if raw_time is None:
        return None
    try:
        return datetime.strptime(f"{year}-{raw_time}", "%Y-%m-%d %H:%M")
    except Exception as e:
        print(f"监测时间解析失败: {raw_time} -> {e}")
        return None


def import_water_quality(file_path, year):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    headers = data["thead"]
    rows = data["tbody"]

    for row in rows:
        # 前四个是字符串，后面的是数值/字符串混合
        # print(row)
        record = WaterQuality(
            province=row[0],
            basin=row[1],
            site_name=clean_site_name(row[2]),
            monitor_time=parse_monitor_time(row[3], year),
            water_quality_level=row[4] or None,
            temperature=extract_float(row[5]),
            ph=extract_float(row[6]),
            dissolved_oxygen=extract_float(row[7]),
            conductivity=extract_float(row[8]),
            turbidity=extract_float(row[9]),
            cod_mn=extract_float(row[10]),
            ammonia_nitrogen=extract_float(row[11]),
            total_phosphorus=extract_float(row[12]),
            total_nitrogen=extract_float(row[13]),
            chlorophyll=extract_float(row[14]),
            algae_density=extract_float(row[15]),
            site_status=row[16]
        )
        db.session.add(record)
    
    db.session.commit()
    print(f"成功导入 {len(rows)} 条水质监测数据：{os.path.basename(file_path)}")

def import_all_water_quality():
    count = 0
    for month_dir in os.listdir(BASE_DIR):
        year = month_dir[:4]
        full_month_path = os.path.join(BASE_DIR, month_dir)
        if not os.path.isdir(full_month_path):
            continue

        for file_name in os.listdir(full_month_path):
            if file_name.endswith('.json'):
                full_path = os.path.join(full_month_path, file_name)
                import_water_quality(full_path, year)
                count+=1
    db.session.commit()
    print(f"成功导入 {count} 个json文件")

if __name__ == "__main__":
    with app.app_context():
        import_all_water_quality()
