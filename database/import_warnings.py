# import_warnings.py

import json
from datetime import datetime

import sys
sys.path.append('..')  # Add parent directory to path for imports

from app import app
from database.models import db, WarningConfig

def import_warnings(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        warnings = json.load(f)
        for w in warnings:
            warning = WarningConfig(
                sensor_id=w['sensor_id'],
                metric=w['metric'],
                min_value=w['min_value'],
                max_value=w['max_value'],
                enabled=w['enabled']
            )
            db.session.add(warning)
        db.session.commit()
        print("warning succeed to import")

if __name__ == "__main__":
    with app.app_context():
        import_warnings("../examples/warnings.json")
        print("Warnings imported successfully.")