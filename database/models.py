from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Sensor(db.Model):
    __tablename__ = 'sensors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    capacity = db.Column(db.Integer)
    status = db.Column(db.String(20), default='正常')
    farm = db.Column(db.String(64))
    test = db.Column(db.String(64))
    count = db.Column(db.Integer)
    price = db.Column(db.Float)
    update_time = db.Column(db.DateTime, default=datetime.now())

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.now())

class WarningConfig(db.Model):
    __tablename__ = 'warning_configs'

    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.id'), nullable=False)
    metric = db.Column(db.String(64), nullable=False)
    min_value = db.Column(db.Float)
    max_value = db.Column(db.Float)
    enabled = db.Column(db.Boolean, default=True)

    sensor = db.relationship('Sensor', backref='warning_configs')

class SensorData(db.Model):
    __tablename__ = 'sensor_data'

    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    metric = db.Column(db.String(64), nullable=False)
    value = db.Column(db.Float)

    sensor = db.relationship('Sensor', backref='data_points')

class WaterQuality(db.Model):
    __tablename__ = 'water_quality'

    id = db.Column(db.Integer, primary_key=True)
    province = db.Column(db.String(50), nullable=True)
    basin = db.Column(db.String(100), nullable=True)
    site_name = db.Column(db.String(512), nullable=True)
    monitor_time = db.Column(db.DateTime, nullable=True, index=True)
    water_quality_level = db.Column(db.String(20), nullable=True)

    temperature = db.Column(db.Float, nullable=True)
    ph = db.Column(db.Float, nullable=True)
    dissolved_oxygen = db.Column(db.Float, nullable=True)
    conductivity = db.Column(db.Float, nullable=True)
    turbidity = db.Column(db.Float, nullable=True)
    cod_mn = db.Column(db.Float, nullable=True)
    ammonia_nitrogen = db.Column(db.Float, nullable=True)
    total_phosphorus = db.Column(db.Float, nullable=True)
    total_nitrogen = db.Column(db.Float, nullable=True)
    chlorophyll = db.Column(db.Float, nullable=True)
    algae_density = db.Column(db.String(100), nullable=True)
    site_status = db.Column(db.String(100), nullable=True)

class FishProfile(db.Model):
    __tablename__ = 'fish_profiles'

    id = db.Column(db.Integer, primary_key=True)
    species = db.Column(db.String(50), nullable=False)
    weight = db.Column(db.Float, nullable=True)
    length1 = db.Column(db.Float, nullable=True)
    length2 = db.Column(db.Float, nullable=True)
    length3 = db.Column(db.Float, nullable=True)
    height = db.Column(db.Float, nullable=True)
    width = db.Column(db.Float, nullable=True)
