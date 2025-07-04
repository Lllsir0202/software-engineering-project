from flask import (
    Flask,
    redirect,
    url_for,
    request,
    render_template,
    jsonify,
    send_file,
    session,
)
from flask_mail import Mail, Message
from flask_cors import CORS
from email_validator import validate_email, EmailNotValidError
import random
import time
import json
import openmeteo_requests
import requests_cache
from retry_requests import retry
import pandas as pd
from datetime import datetime, timedelta
import pytz
import re
import base64
import io
import os
import matplotlib
from model.inference import predict
from werkzeug.utils import secure_filename
from openai import OpenAI

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from plot_utils import plot_average_by_species, generate_water_quality_plot

# Used in database
from database.models import *
from flask_migrate import Migrate

app = Flask(__name__)
# Reoriganize the verification codes dictionary
# verification_codes = {}
from config import Config

app.config.from_object(Config)
CORS(app)

db.init_app(app)
migrate = Migrate(app, db)

mail = Mail(app)


def generate_code():
    return str(random.randint(100000, 999999))


# Used for test
# @app.route("/test-db")
# def test_db():
#     from database.models import User
#     user = User.query.first()
#     return f"第一个用户：{user.username if user else '暂无用户'}"


@app.route("/")
def index():
    return render_template("login.html")


@app.route("/admin")
def admin():
    # Check if the user is logged in as admin
    username = session.get("username")
    admin = User.query.filter_by(username=username, role="admin").first()
    if admin:
        # If the user is an admin, redirect to the admin page
        return redirect(url_for("admin_page"))
    return render_template("admin.html")


@app.route("/admin_page")
def admin_page():
    return render_template("用户列表.html")


@app.route("/homepage/")
def homepage():
    return render_template("homepage.html")


# In homepage it is used to show the information
@app.route("/api/homepage/summary")
def summary():
    try:
        # 总监测点数量
        sensors_count = Sensor.query.count()

        # 今日预警数量初始化
        warning_count = 0

        # 遍历每个预警配置项
        warning_configs = WarningConfig.query.filter_by(enabled=1).all()

        for config in warning_configs:
            latest_data = Sensor.query.filter_by(id=config.sensor_id).first()
            if latest_data:
                # print(f"Checking sensor {latest_data.name} {latest_data.capacity} with config {config.min_value} - {config.max_value}")
                current_value = latest_data.capacity
                if current_value < config.min_value or current_value > config.max_value:
                    warning_count += 1

        # print(f"今日预警数量: {warning_count}")
        # 正常运行率（例如，你可以计算未报警的 / 总设备数）
        normal_percent = 100.0
        normal_num = Sensor.query.filter_by(status="正常").count()
        if sensors_count > 0:
            normal_percent = round(normal_num / sensors_count * 100, 1)
        # print(f"传感器总数: {sensors_count}, 预警数量: {warning_count}, 正常运行率: {normal_percent}%")
        return jsonify(
            {
                "sensors_count": sensors_count,
                "warning_count": warning_count,
                "normal_percent": normal_percent,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)})


# In homepage it is used to get the data to show the chart
@app.route("/api/homepage/status_summary")
def device_status_summary():
    normal_count = Sensor.query.filter_by(status="正常").count()
    warning_count = Sensor.query.filter_by(status="故障").count()
    maintain_count = Sensor.query.filter_by(status="维护中").count()

    return jsonify(
        {
            "labels": ["正常", "故障", "维护中"],
            "data": [normal_count, warning_count, maintain_count],
        }
    )


# In homepage it is used to get the water quality data to show the chart
@app.route("/api/homepage/water_quality_trend")
def water_quality_trend():
    # 模拟从数据库中获取过去7天数据
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    ph_values = [6.8, 7.0, 7.2, 6.9, 7.1, 7.0, 6.8]  # 从数据库取
    do_values = [5.2, 5.5, 5.8, 5.3, 5.6, 5.4, 5.1]  # 从数据库取

    return jsonify({"labels": days, "ph": ph_values, "do": do_values})


# In homepage it is used to get the data of warnings
@app.route("/api/homepage/warnings")
def get_active_warnings():
    active_configs = WarningConfig.query.filter_by(enabled=1).all()
    warning_list = []
    for config in active_configs:
        sensor = Sensor.query.filter_by(id=config.sensor_id).first()
        if not sensor:
            continue

        # 获取传感器当前的监测值
        current_value = sensor.capacity
        # print(f"Checking sensor {sensor.name} with current value {current_value}")
        if current_value is None:
            continue

        # print(f"Checking sensor {sensor.name} with current value {current_value} against config min {config.min_value} and max {config.max_value}")
        if current_value < config.min_value or current_value > config.max_value:
            warning_list.append(
                {
                    "sensor_name": sensor.name,
                    "capacity": current_value,
                    "test": sensor.test,
                    "min_value": config.min_value,
                    "max_value": config.max_value,
                    "status": sensor.status,
                }
            )

    return jsonify({"warnings": warning_list})


@app.route("/datacenter/", methods=["GET"])
def datacenter():
    return render_template("datacenter.html")


@app.route("/data-fish/", methods=["GET"])
def data_fish():
    return render_template("datacenter_fish.html")


@app.route("/data-analysis/", methods=["GET"])
def data_analysis():
    return render_template("datacenter_analysis.html")


@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")


@app.route("/visualization")
def visualization():
    return render_template("visualization.html")


# Used to get user information
def login_as_user(username, password_input):
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password_input):
        return user
    return None


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("login-username")
    password = request.form.get("login-password")

    user = login_as_user(username, password)
    if user:
        # Reach here means login is successful
        session["username"] = username
        # session["email"] = user["email"]
        session["login_time"] = time.time()
        return jsonify(
            {"success": True, "redirect": url_for("homepage", name=username)}
        )
    else:
        return jsonify({"success": False, "message": "用户名或密码错误"})


def login_as_admin(adminname, password):
    user = User.query.filter_by(username=adminname, role="admin").first()
    if user and user.check_password(password):
        return user
    # print(f"Admin login failed for {adminname} with password {password}")
    return None


@app.route("/login_admin", methods=["POST"])
def login_admin():
    adminname = request.form.get("login-adminname")
    password = request.form.get("login-password")

    admin = login_as_admin(adminname, password)
    if admin:
        return jsonify({"success": True, "redirect": url_for("admin_page")})
    else:
        return jsonify({"success": False, "message": "管理员名或密码错误"})


@app.route("/login_by_email", methods=["POST"])
def login_by_email():
    email = request.form.get("email")
    verification_code = request.form.get("verification-code")
    stored_code = session.get("verification_code")
    stored_email = session.get("verification_email")
    expire_time = session.get("verification_expire")
    if time.time() > expire_time:
        return jsonify({"success": False, "message": "验证码已过期"})
    if stored_code != verification_code or stored_email != email:
        return jsonify({"success": False, "message": "验证码错误或邮箱不匹配"})
    if verification_code == stored_code:
        # Find the user by email
        if User.query.filter_by(email=email).first() is None:
            return jsonify({"success": False, "message": "用户数据不存在"})

        user = User.query.filter_by(email=email).first()
        # Store user information in session
        session["username"] = user.username
        session["login_time"] = time.time()
        session.pop("verification_code", None)
        session.pop("verification_email", None)
        session.pop("verification_expire", None)
        return jsonify(
            {"success": True, "redirect": url_for("homepage", name=session["username"])}
        )


@app.route("/add_user", methods=["POST"])
def add_user():
    username = request.form.get("register-username")
    email = request.form.get("email")
    password = request.form.get("register-password")
    confirm_password = request.form.get("register-confirm-password")
    try:
        validate_email(email)
    except EmailNotValidError:
        return jsonify({"success": False, "message": "邮箱格式无效"})
    if password != confirm_password:
        return jsonify({"success": False, "message": "确认密码必须与密码一致"})
    # Check if the username is already taken
    if User.query.filter_by(username=username).first():
        return jsonify({"success": False, "message": "用户名已被注册"})
    # Check if the email is already taken
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "邮箱已被注册"})

    new_user = User(
        username=username,
        email=email,
        password=User.generate_password_hash(
            password, method="pbkdf2:sha256"
        ),  # 使用模型方法加密密码->because it's too long so we use pbkdf2:sha256
        role="user",
    )

    db.session.add(new_user)
    db.session.commit()
    return jsonify({"success": True, "message": "注册成功", "redirect": url_for("index")})


@app.route("/register")
def register():
    return render_template("register.html")


@app.route("/VerificationCode")
def VerificationCode():
    return render_template("VerificationCode.html")


@app.route("/send_code", methods=["POST"])
def send_code():
    email = request.form.get("email")
    try:
        validate_email(email)
    except EmailNotValidError:
        return jsonify({"success": False, "message": "邮箱格式无效"})

    if User.query.filter_by(email=email).first() is None:
        return jsonify({"success": False, "message": "邮箱未被注册"})

    code = generate_code()
    session["verification_code"] = code
    session["verification_email"] = email
    session["verification_expire"] = time.time() + 300  # 5分钟有效
    try:
        msg = Message(
            subject="您的验证码", recipients=[email], body=f"您的验证码是：{code}，5分钟内有效。"
        )
        mail.send(msg)
        return jsonify({"success": True, "message": "验证码已发送"})
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return jsonify({"success": False, "message": "发送失败，请重试"})


# Logout
@app.route("/logout")
def logout():
    session.clear()
    return render_template("login.html")


@app.route("/api/users", methods=["GET"])
def get_users():
    try:
        page = int(request.args.get("page", 1))  # 当前页码，默认1
        per_page = int(request.args.get("per_page", 10))  # 每页条数，默认10

        query = User.query.order_by(User.created_at.desc())
        query = User.query.filter_by(role="user")  # 只查询普通用户
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        users = [
            {
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for user in pagination.items
        ]

        return jsonify(
            {
                "users": users,
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": page,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 新增用户
@app.route("/api/users", methods=["POST"])
def add_users():
    data = request.get_json()
    # 验证必填字段
    required_fields = ["username", "email", "password"]
    for field in required_fields:
        if field not in data:
            return jsonify({"success": False, "message": f"Missing field: {field}"})
    try:
        # 检查是否被创建了
        if User.query.filter_by(username=data["username"]).first():
            return jsonify({"success": False, "message": "用户名已被注册"})
        if User.query.filter_by(email=data["email"]).first():
            return jsonify({"success": False, "message": "邮箱已被注册"})
        new_user = User(
            username=data["username"],
            email=data["email"],
            password=generate_password_hash(
                data["password"], method="pbkdf2:sha256"
            ),  # 使用模型方法加密密码
            role="user",  # 默认角色为用户
            created_at=datetime.now(),  # 设置创建时间
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"success": True, "message": "User added successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/users", methods=["DELETE"])
def delete_user():
    username = request.get_json()
    try:
        deleted_user = User.query.filter_by(username=username, role="user").first()
        if deleted_user is None:
            return jsonify({"success": False, "error": f'未找到用户名 "{username}"'}), 404
        # 找到后
        db.session.delete(deleted_user)
        db.session.commit()
        return jsonify({"success": True, "message": f'用户 "{username}" 已成功删除'})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin", methods=["GET"])
def get_admin():
    try:
        page = int(request.args.get("page", 1))  # 当前页码，默认1
        per_page = int(request.args.get("per_page", 10))  # 每页条数，默认10

        query = User.query.order_by(User.created_at.desc())
        query = User.query.filter_by(role="admin")  # 只查询普通用户
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        users = [
            {
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for user in pagination.items
        ]

        return jsonify(
            {
                "users": users,
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": page,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 新增用户
@app.route("/api/admin", methods=["POST"])
def add_admin():
    data = request.get_json()
    # 验证必填字段
    required_fields = ["username", "email", "password"]
    for field in required_fields:
        if field not in data:
            return jsonify({"success": False, "message": f"Missing field: {field}"})
    try:
        # 检查是否被创建了
        if User.query.filter_by(username=data["username"]).first():
            return jsonify({"success": False, "message": "用户名已被注册"})
        if User.query.filter_by(email=data["email"]).first():
            return jsonify({"success": False, "message": "邮箱已被注册"})
        new_user = User(
            username=data["username"],
            email=data["email"],
            password=generate_password_hash(
                data["password"], method="pbkdf2:sha256"
            ),  # 使用模型方法加密密码
            role="admin",
            created_at=datetime.now(),  # 设置创建时间
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"success": True, "message": "User added successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin", methods=["DELETE"])
def delete_admin():
    username = request.get_json()
    try:
        deleted_user = User.query.filter_by(username=username, role="admin").first()
        if deleted_user.username == "admin":
            return jsonify({"success": False, "error": '无法删除默认管理员 "admin"'}), 403
        if deleted_user is None:
            return jsonify({"success": False, "error": f'未找到管理员名 "{username}"'}), 404
        # 找到后
        db.session.delete(deleted_user)
        db.session.commit()
        return jsonify({"success": True, "message": f'管理员 "{username}" 已成功删除'})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Reset admin password
@app.route("/api/users/reset_password", methods=["POST"])
def reset_password():
    data = request.get_json()
    username = data.get("username")

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"success": False, "message": "用户不存在"}), 404

    # 例如默认重置为 123456
    new_password = "123456"
    user.password = generate_password_hash(new_password, method="pbkdf2:sha256")
    user.created_at = datetime.now()  # 更新创建时间
    db.session.commit()
    return jsonify(
        {"success": True, "message": f"用户 {username} 的密码已重置为 {new_password}"}
    )


@app.route("/user_list")
def user_list():
    return render_template("用户列表.html")


@app.route("/admin_list")
def admin_list():
    return render_template("管理员列表.html")


@app.route("/api/sensors", methods=["GET"])
def get_sensors():
    try:
        page = int(request.args.get("page", 1))  # 当前页码，默认1
        per_page = int(request.args.get("per_page", 10))  # 每页条数，默认10

        query = Sensor.query.order_by(Sensor.id.asc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        sensors = [
            {
                "id": sensor.id,
                "name": sensor.name,
                "capacity": sensor.capacity,
                "status": sensor.status,
                "farm": sensor.farm,
                "test": sensor.test,
                "count": sensor.count,
                "price": sensor.price,
                "update_time": sensor.update_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for sensor in pagination.items
        ]

        return jsonify(
            {
                "sensors": sensors,
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": page,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sensors", methods=["POST"])
def add_sensors():
    data = request.get_json()
    # print(data)
    # 验证必填字段
    required_fields = [
        "id",
        "name",
        "capacity",
        "status",
        "farm",
        "test",
        "count",
        "price",
        "update_time",
    ]
    for field in required_fields:
        if field not in data:
            return jsonify({"success": False, "message": f"Missing field: {field}"})
    try:
        # 检查是否被创建了
        if Sensor.query.filter_by(id=data["id"]).first():
            return jsonify({"success": False, "message": "id已被使用"})

        new_sensor = Sensor(
            id=data["id"],
            name=data["name"],
            capacity=data["capacity"],
            status=data["status"],
            farm=data["farm"],
            test=data["test"],
            count=data["count"],
            price=data["price"],
            update_time=datetime.strptime(data["update_time"], "%Y-%m-%d %H:%M:%S"),
        )
        db.session.add(new_sensor)
        db.session.commit()
        return jsonify({"success": True, "message": "Sensor added successfully"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/sensors", methods=["DELETE"])
def delete_sensors():
    sensorid = request.get_json()
    try:
        deleted_sensor = Sensor.query.filter_by(id=sensorid).first()
        if deleted_sensor is None:
            return jsonify({"success": False, "error": f'未找到传感器id "{sensorid}"'}), 404
        # 找到后
        db.session.delete(deleted_sensor)
        db.session.commit()
        return jsonify({"success": True, "message": f'传感器id "{sensorid}" 已成功删除'})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/sensor_list")
def sensor_list():
    return render_template("传感器列表.html")


@app.route("/warning")
def warning():
    return render_template("预警设置.html")


# Just used to get a specific warning by id
@app.route("/api/warning", methods=["POST"])
def get_warning():
    try:
        id = request.get_json()
        query = WarningConfig.query.filter_by(id=id).first()
        if query is None:
            return jsonify({"error": "未找到指定预警"}), 404
        warning = {
            "id": query.id,
            "sensor_id": query.sensor_id,
            "metric": query.metric,
            "min_value": query.min_value,
            "max_value": query.max_value,
            "enabled": query.enabled,
        }
        return jsonify(warning)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Used to modify a specific warning
@app.route("/api/warning/update", methods=["POST"])
def update_warning():
    try:
        data = request.get_json()
        warning = WarningConfig.query.get(data["id"])
        if not warning:
            return jsonify({"success": False, "error": "预警不存在"})

        # 更新字段
        warning.sensor_id = data["sensor_id"]
        warning.metric = data["metric"]
        warning.min_value = data["min_value"]
        warning.max_value = data["max_value"]
        warning.enabled = data["enabled"]

        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# Used to create a specific warning
@app.route("/api/warning/create", methods=["POST"])
def create_warning():
    try:
        data = request.get_json()
        new_warning = WarningConfig(
            sensor_id=data["sensor_id"],
            metric=data["metric"],
            min_value=data["min_value"],
            max_value=data["max_value"],
            enabled=data["enabled"],
        )
        db.session.add(new_warning)
        db.session.commit()
        return jsonify({"success": True, "id": new_warning.id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/warnings", methods=["GET"])
def get_warnings():
    try:
        page = int(request.args.get("page", 1))  # 当前页码，默认1
        per_page = int(request.args.get("per_page", 10))  # 每页条数，默认10

        query = WarningConfig.query.order_by(WarningConfig.sensor_id.asc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        warnings = [
            {
                "id": warning.id,
                "sensor_id": warning.sensor_id,
                "metric": warning.metric,
                "min_value": warning.min_value,
                "max_value": warning.max_value,
                "enabled": warning.enabled,
            }
            for warning in pagination.items
        ]

        return jsonify(
            {
                "warnings": warnings,
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": page,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/warnings", methods=["DELETE"])
def delete_warnings():
    id = request.get_json()
    try:
        deleted_warning = WarningConfig.query.filter_by(id=id).first()
        if deleted_warning is None:
            return jsonify({"success": False, "error": f'未找到预警 "{id}"'}), 404
        # 找到后
        db.session.delete(deleted_warning)
        db.session.commit()
        return jsonify({"success": True, "message": f"指定预警已成功删除"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/charts/growth")
def plot():
    try:
        metric = request.args.get("metric", "Height(cm)").strip()

        # 例如前端传了 metric=Height(cm)，后端映射成 height
        column_mapping = {
            "Height(cm)": "height",
            "Weight(g)": "weight",
            "Length1(cm)": "length1",
            "Length2(cm)": "length2",
            "Length3(cm)": "length3",
            "Width(cm)": "width",
        }
        actual_column = column_mapping[metric]

        # 使用 ORM 查询 species + 你选的指标字段
        results = db.session.query(
            FishProfile.species, getattr(FishProfile, actual_column)
        ).all()

        # 转成 DataFrame，列名为 ["species", metric]
        df = pd.DataFrame(results, columns=["Species", metric])

        # print(df)
        # 将metric传递给绘图函数
        img_io = plot_average_by_species(df, metric)
        img_io.seek(0)
        img_base64 = base64.b64encode(img_io.read()).decode("utf-8")

        return jsonify(
            {"status": "success", "image": f"data:image/png;base64,{img_base64}"}
        )

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/weather", methods=["GET"])
def get_weather():
    """获取当前天气信息"""
    try:
        # 设置缓存，避免频繁请求API
        cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(session=retry_session)

        # 设置请求参数 - 以北京为例
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 39.9042,
            "longitude": 116.4074,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
            ],
            "hourly": [
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation_probability",
            ],
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "sunrise",
                "sunset",
            ],
            "timezone": "Asia/Shanghai",
            "forecast_days": 1,
        }

        # 发送请求
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]

        # 提取当前天气数据
        current = response.Current()

        # 调试信息
        api_time = current.Time()
        print(f"API返回的原始时间类型: {type(api_time)}, 值: {api_time}")
        # 更安全的时间转换方法
        try:
            # 方法1: 如果返回的是UNIX时间戳
            if isinstance(api_time, (int, float)):
                dt = datetime.fromtimestamp(api_time, tz=pytz.UTC)
            # 方法2: 如果返回的是字符串
            else:
                dt = pd.to_datetime(api_time)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=pytz.UTC)

            # 转换为北京时间
            beijing_dt = dt.astimezone(pytz.timezone("Asia/Shanghai"))
            current_time = beijing_dt.strftime("%Y-%m-%d %H:%M:%S")
            print(f"转换后的北京时间: {current_time}")
        except Exception as time_err:
            print(f"时间转换错误: {time_err}")
            # 使用当前系统时间作为备用
            current_time = datetime.now(pytz.timezone("Asia/Shanghai")).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        weather_code = current.Variables(4).Value()

        # 天气代码转为描述
        weather_descriptions = {
            0: "晴天",
            1: "大部晴朗",
            2: "多云",
            3: "阴天",
            45: "雾",
            48: "沉积雾",
            51: "小毛毛雨",
            53: "中毛毛雨",
            55: "浓毛毛雨",
            56: "冻毛毛雨",
            57: "强冻毛毛雨",
            61: "小雨",
            63: "中雨",
            65: "大雨",
            66: "冻雨",
            67: "强冻雨",
            71: "小雪",
            73: "中雪",
            75: "大雪",
            77: "雪粒",
            80: "小阵雨",
            81: "中阵雨",
            82: "大阵雨",
            85: "小阵雪",
            86: "大阵雪",
            95: "雷暴",
            96: "雷暴伴小冰雹",
            99: "雷暴伴大冰雹",
        }

        weather_description = weather_descriptions.get(weather_code, "未知天气")

        # 构建返回数据
        # 构建返回数据
        weather_data = {
            "timestamp": current_time,
            "temperature": f"{current.Variables(0).Value():.1f}",  # temperature_2m
            "humidity": f"{current.Variables(1).Value():.1f}",  # relative_humidity_2m
            "apparent_temperature": f"{current.Variables(2).Value():.1f}",
            "precipitation": f"{current.Variables(3).Value():.1f}",
            "wind_speed": f"{current.Variables(5).Value():.1f}",
            "weather_code": weather_code,
            "weather_description": weather_description,
            "condition": get_condition_from_code(weather_code),
            "location": "北京市",  # 添加地点信息
            "location_detail": "海淀区",  # 添加详细地点信息
            "latitude": 39.9042,  # 添加纬度
            "longitude": 116.4074,  # 添加经度
        }

        return jsonify(weather_data)

    except Exception as e:
        app.logger.error(f"天气API请求失败: {str(e)}")
        # 提供备用数据以保持前端正常运行
        return jsonify(
            {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "temperature": "23.5",
                "humidity": "65.0",
                "wind_speed": "3.2",
                "weather_description": "晴天",
                "condition": "sunny",
            }
        )


def get_condition_from_code(code):
    """将天气代码转换为前端需要的condition值"""
    if code in [0, 1]:
        return "sunny"
    elif code in [2, 3]:
        return "cloudy"
    elif code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
        return "rain"
    elif code >= 95:
        return "alert"
    else:
        return "sunny"  # 默认值


@app.route("/api/charts/water_quality")
def water_quality_chart():
    try:
        # 获取清洗后的参数
        params = {
            "from_year": request.args.get("from_year", "2020").strip(),
            "from_month": request.args.get("from_month", "05").strip(),
            "from_day": request.args.get("from_day", "08").strip(),
            "to_year": request.args.get("to_year", "2021").strip(),
            "to_month": request.args.get("to_month", "05").strip(),
            "to_day": request.args.get("to_day", "31").strip(),
            "position": request.args.get("position", "七星岗").strip(),
            "metrics": request.args.get("metric", "水温").strip(),
        }
        print(params["metrics"])

        # 指标到数据库字段的映射
        metric_mapping = {
            "水温": "temperature",
            "pH": "ph",
            "溶解氧": "dissolved_oxygen",
            "电导率": "conductivity",
            "浊度": "turbidity",
            "高锰酸盐指数": "cod_mn",
            "氨氮": "ammonia_nitrogen",
            "总磷": "total_phosphorus",
            "总氮": "total_nitrogen",
            "叶绿素": "chlorophyll",
            "藻密度": "algae_density",
        }

        # 验证指标是否有效
        metric = params["metrics"]
        if metric not in metric_mapping:
            available_metrics = ", ".join(metric_mapping.keys())
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"无效的指标: {metric}",
                        "suggestions": [f"可用指标: {available_metrics}"],
                    }
                ),
                400,
            )

        # 构造日期范围 - 修复日期处理
        try:
            # 创建开始日期（包含时间部分）
            start_date = datetime(
                int(params["from_year"]),
                int(params["from_month"]),
                int(params["from_day"]),
                0,
                0,
                0,  # 设置为当天的开始时间
            )

            # 创建结束日期（包含时间部分）
            end_date = datetime(
                int(params["to_year"]),
                int(params["to_month"]),
                int(params["to_day"]),
                23,
                59,
                59,  # 设置为当天的结束时间
            )
        except ValueError as e:
            return jsonify({"status": "error", "message": f"日期格式错误: {str(e)}"}), 400

        if start_date > end_date:
            return jsonify({"status": "error", "message": "开始日期不能晚于结束日期"}), 400

        # 从数据库查询数据
        db_field = metric_mapping[metric]

        # 构建查询 - 使用正确的日期范围
        results = (
            WaterQuality.query.with_entities(
                WaterQuality.monitor_time, getattr(WaterQuality, db_field)
            )
            .filter(
                WaterQuality.site_name == params["position"],
                WaterQuality.monitor_time.between(start_date, end_date),
                getattr(WaterQuality, db_field).is_not(None),  # 过滤掉 db_field 为 null 的记录
            )
            .order_by(WaterQuality.monitor_time.asc())
            .all()
        )

        # 记录查询结果用于调试
        app.logger.info(f"水质数据查询结果: 位置={params['position']}, 指标={metric}")
        app.logger.info(f"日期范围: {start_date} 至 {end_date}")
        app.logger.info(f"找到 {len(results)} 条记录")

        # 检查是否有数据
        if not results:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"在{params['position']}监测点没有找到{start_date.date()}到{end_date.date()}的数据",
                        "suggestions": ["检查日期范围", "确认监测点名称正确"],
                    }
                ),
                404,
            )

        # 准备绘图数据
        dates = [result[0] for result in results]
        values = [result[1] for result in results]

        # 记录找到的日期范围用于调试
        if dates:
            app.logger.info(f"实际数据日期范围: {min(dates)} 至 {max(dates)}")

        # 生成图表
        img_io = generate_water_quality_plot(
            dates, values, metric, params["position"], start_date, end_date
        )
        img_io.seek(0)
        img_base64 = base64.b64encode(img_io.read()).decode("utf-8")

        return jsonify(
            {"status": "success", "image": f"data:image/png;base64,{img_base64}"}
        )

    except Exception as e:
        app.logger.error(f"水质图表生成错误: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": f"服务器错误: {str(e)}"}), 500


# Here is some routes used in datacenter
@app.route("/api/waterquality/list")
def get_waterquality():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    # 接收筛选参数（如有）
    site_name = request.args.get("site_name")
    basin = request.args.get("basin")
    status = request.args.get("status")

    # 查询数据
    query = WaterQuality.query
    if site_name:
        query = query.filter(WaterQuality.site_name.like(f"%{site_name}%"))
    if basin and basin != "全部区域":
        query = query.filter(WaterQuality.basin.like(f"%{basin}%"))
    if status and status != "全部状态":
        query = query.filter(WaterQuality.site_status == status)

    query = query.order_by(WaterQuality.monitor_time.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    records = pagination.items

    def safe(value):
        return value if value is not None else "--"

    data = []
    for r in records:
        data.append({
            "id": r.id,
            "province": safe(r.province),
            "basin": safe(r.basin),
            "site_name": safe(r.site_name),
            "monitor_time": r.monitor_time.strftime("%Y-%m-%d %H:%M") if r.monitor_time else "--",
            "water_quality_level": safe(r.water_quality_level),
            "temperature": safe(r.temperature),
            "ph": safe(r.ph),
            "dissolved_oxygen": safe(r.dissolved_oxygen),
            "conductivity": safe(r.conductivity),
            "turbidity": safe(r.turbidity),
            "cod_mn": safe(r.cod_mn),
            "ammonia_nitrogen": safe(r.ammonia_nitrogen),
            "total_phosphorus": safe(r.total_phosphorus),
            "total_nitrogen": safe(r.total_nitrogen),
            "chlorophyll": safe(r.chlorophyll),
            "algae_density": safe(r.algae_density),
            "site_status": safe(r.site_status)
        })
    # print(data)
    return jsonify({
        "status": "success",
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
        "records": data
    })

# This route is used to get export
@app.route("/api/waterquality/export")
def export_waterquality():
    # 接收筛选参数（如有）
    site_name = request.args.get("site_name")
    basin = request.args.get("basin")
    status = request.args.get("status")

    # 查询数据
    query = WaterQuality.query
    if site_name:
        query = query.filter(WaterQuality.site_name.like(f"%{site_name}%"))
    if basin and basin != "全部区域":    
        query = query.filter(WaterQuality.basin.like(f"%{basin}%"))
    if status and status != "全部状态":
        query = query.filter(WaterQuality.site_status == status)

    records = query.all()

    # 转换为 DataFrame
    df = pd.DataFrame([{
        "省份": r.province or "--",
        "流域": r.basin or "--",
        "监测点名称": r.site_name or "--",
        "监测时间": r.monitor_time.strftime("%Y-%m-%d %H:%M") if r.monitor_time else "--",
        "水质等级": r.water_quality_level or "--",
        "温度(℃)": r.temperature if r.temperature is not None else "--",
        "PH": r.ph if r.ph is not None else "--",
        "溶解氧": r.dissolved_oxygen if r.dissolved_oxygen is not None else "--",
        "电导率": r.conductivity if r.conductivity is not None else "--",
        "浊度": r.turbidity if r.turbidity is not None else "--",
        "高锰酸盐指数": r.cod_mn if r.cod_mn is not None else "--",
        "氨氮": r.ammonia_nitrogen if r.ammonia_nitrogen is not None else "--",
        "总磷": r.total_phosphorus if r.total_phosphorus is not None else "--",
        "总氮": r.total_nitrogen if r.total_nitrogen is not None else "--",
        "叶绿素": r.chlorophyll if r.chlorophyll is not None else "--",
        "藻密度": r.algae_density or "--",
        "站点状态": r.site_status or "--"
    } for r in records])

    # 写入 BytesIO 缓冲区
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="水质数据")
    output.seek(0)

    return send_file(output,
                     as_attachment=True,
                     download_name="水质监测数据.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# This route is used to add water quality data
@app.route("/api/waterquality/add", methods=["POST"])
def add_waterquality():
    data = request.get_json()
    # print(data)
    # 提取数据
    province = data.get("province")
    basin = data.get("basin")
    site_name = data.get("site_name")
    monitor_time = data.get("monitor_time")
    water_quality_level = data.get("water_quality_level")
    temperature = data.get("temperature")
    ph = data.get("ph")
    dissolved_oxygen = data.get("dissolved_oxygen")
    conductivity = data.get("conductivity")
    turbidity = data.get("turbidity")
    cod_mn = data.get("cod_mn")
    ammonia_nitrogen = data.get("ammonia_nitrogen")
    total_phosphorus = data.get("total_phosphorus")
    total_nitrogen = data.get("total_nitrogen")
    chlorophyll = data.get("chlorophyll")
    algae_density = data.get("algae_density")
    site_status = data.get("site_status")

    # 存储数据到数据库
    new_entry = WaterQuality(
        province = province,
        basin=basin,
        site_name=site_name,
        monitor_time=datetime.strptime(monitor_time, "%Y-%m-%d %H:%M") if monitor_time else None,
        water_quality_level=water_quality_level,
        temperature=temperature,
        ph=ph,
        dissolved_oxygen=dissolved_oxygen,
        conductivity=conductivity,
        turbidity=turbidity,
        cod_mn=cod_mn,
        ammonia_nitrogen=ammonia_nitrogen,
        total_phosphorus=total_phosphorus,
        total_nitrogen=total_nitrogen,
        chlorophyll=chlorophyll,
        algae_density=algae_density,
        site_status=site_status
    )

    db.session.add(new_entry)
    db.session.commit()

    return jsonify({"success": True, "message": "Water quality data added successfully"})

# This route is used to delete water quality data
@app.route("/api/waterquality/delete", methods=["DELETE"])
def delete_waterquality():
    data = request.get_json()
    record_id = data.get('id')
    # print(record_id)
    # 查找记录
    record = FishProfile.query.get(record_id)
    if not record:
        return jsonify({"success": False, "error": "Record not found"}), 404

    # 删除记录
    db.session.delete(record)
    db.session.commit()

    return jsonify({"success": True, "message": "Record deleted successfully"})

# Followings are used in fish profile

# 后端 Flask 路由，返回所有唯一品种
@app.route('/api/species')
def get_species():
    species_list = db.session.query(FishProfile.species).distinct().all()
    species_names = [s[0] for s in species_list if s[0]]  # 去除空值
    return jsonify({"status": "success", "species": species_names})

@app.route('/api/fish/list')
def get_fishes():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    # 接收筛选参数（如有）
    species = request.args.get("species")

    print(species)
    # 查询数据
    query = FishProfile.query
    if species:
        query = query.filter(FishProfile.species.like(f"%{species}%"))

    query = query.order_by(FishProfile.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    records = pagination.items

    def safe(value):
        return value if value is not None else "--"

    data = []
    for r in records:
        data.append({
            "id": r.id,
            "species": safe(r.species),
            "height": safe(r.height),
            "weight": safe(r.weight),
            "length1": safe(r.length1),
            "length2": safe(r.length2),
            "length3": safe(r.length3),
            "width": safe(r.width),
        })

    return jsonify({
        "status": "success",
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
        "records": data
    })

@app.route('/api/fish/export')
def export_fished():
    # 接收筛选参数（如有）
    species = request.args.get("species")

    # 查询数据
    query = FishProfile.query
    if species:
        query = query.filter(FishProfile.species.like(f"%{species}%"))

    records = query.all()

    # 转换为 DataFrame
    df = pd.DataFrame([{
        "品种": r.species or "--",
        "高度(cm)": r.height if r.height is not None else "--",
        "重量(g)": r.weight if r.weight is not None else "--",
        "长度1(cm)": r.length1 if r.length1 is not None else "--",
        "长度2(cm)": r.length2 if r.length2 is not None else "--",
        "长度3(cm)": r.length3 if r.length3 is not None else "--",
        "宽度(cm)": r.width if r.width is not None else "--",
    } for r in records])

    # 写入 BytesIO 缓冲区
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="鱼类数据")
    output.seek(0)

    return send_file(output,
                     as_attachment=True,
                     download_name="鱼类数据.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# This route is used to add fish data
@app.route("/api/fish/add", methods=["POST"])
def add_fish():
    data = request.get_json()
    # print(data)
    # 提取数据
    species = data.get("species")
    height = data.get("height")
    weight = data.get("weight")
    length1 = data.get("length1")
    length2 = data.get("length2")
    length3 = data.get("length3")
    width = data.get("width")

    # 存储数据到数据库
    new_entry = FishProfile(
        species=species,
        height=height,
        weight=weight,
        length1=length1,
        length2=length2,
        length3=length3,
        width=width
    )

    db.session.add(new_entry)
    db.session.commit()

    return jsonify({"success": True, "message": "Fish data added successfully"})

@app.route('/api/fish/delete', methods=["DELETE"])
def delete_fish():
    data = request.get_json()
    record_id = data.get('id')
    # print(record_id)
    # 查找记录
    record = FishProfile.query.get(record_id)
    if not record:
        return jsonify({"success": False, "error": "Record not found"}), 404

    # 删除记录
    db.session.delete(record)
    db.session.commit()

    return jsonify({"success": True, "message": "Record deleted successfully"})



# Using picture recognition
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/picture', methods=['GET', 'POST'])
def upload_image():
    if request.method == 'POST':
        if 'image' not in request.files:
            return "没有上传文件", 400

        file = request.files['image']

        if file.filename == '':
            return "文件名为空", 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)

            fish_type, fish_length = predict(save_path)

            return jsonify({
                "success": True,
                "fish_type": fish_type,
                "fish_length": fish_length,
                "filename": filename
            })

    return jsonify({
        "success": False,
        "message": "请上传图片"
    })

client = OpenAI(
    api_key="sk-423a2d8c08b143ad88363249d2681f1c",
    base_url="https://api.deepseek.com/v1"
)
model = "deepseek-chat"

@app.route('/api/chat', methods=['GET', 'POST'])
def chat():
    if 'history' not in session:
        session['history'] = []

    if request.method == 'POST':
        data = request.get_json()
        user_input = data.get('message')

        if user_input.strip().lower() in ['exit', '退出']:
            session.pop('history', None)
            return redirect(url_for('chat'))

        session['history'].append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(
                model=model,
                messages=session['history'],
                stream=False
            )
            ai_reply = response.choices[0].message.content
            session['history'].append({"role": "assistant", "content": ai_reply})

        except Exception as e:
            ai_reply = f"发生错误：{str(e)}"

        return jsonify(
            {
                "status": "success",
                "reply": ai_reply,
                "history": session['history']
            }
        )

    return jsonify(
        {
            "status": "success",
            "history": session['history']
        }
    )



if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
