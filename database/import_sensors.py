# import_sensors.py

import json
from datetime import datetime

import sys
sys.path.append('..')  # Add parent directory to path for imports

from app import app
from database.models import db, Sensor

def import_sensors(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        sensors = json.load(f)
        for s in sensors:
            sensor = Sensor(
                id=s['id'],
                name=s['name'],
                capacity=s.get('capacity', 0),
                status=s.get('status', '正常'),
                farm=s.get('farm', ''),
                test=s.get('test', ''),
                count=s.get('count', 0),
                price=s.get('price', 0.0),
                update_time=s.get('update_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            db.session.add(sensor)
        db.session.commit()
        print("sensor succeed to import")

if __name__ == "__main__":
    with app.app_context():
        import_sensors("../data/sensors.json")
        print("Sensors imported successfully.")