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

from plot_utils import plot_average_by_species
from waterQualityUtils import draw_metrics

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
    admin = User.query.filter_by(username=username, role='admin').first()
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


@app.route("/datacenter/", methods=["GET"])
def datacenter():
    return render_template("datacenter.html")


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
        return jsonify({"success": True, "redirect": url_for("homepage", name=username)})
    else:
        return jsonify({"success": False, "message": "用户名或密码错误"})

def login_as_admin(adminname, password):
    user = User.query.filter_by(username=adminname, role='admin').first()
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
        return jsonify({"success": True, "redirect": url_for("homepage", name=session['username'])})


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
        username = username,
        email = email,
        password = User.generate_password_hash(password, method='pbkdf2:sha256'),  # 使用模型方法加密密码->because it's too long so we use pbkdf2:sha256
        role = 'user',
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
        page = int(request.args.get("page", 1))        # 当前页码，默认1
        per_page = int(request.args.get("per_page", 10))  # 每页条数，默认10

        query = User.query.order_by(User.created_at.desc())
        query = User.query.filter_by(role='user')  # 只查询普通用户
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        users = [
            {
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for user in pagination.items
        ]

        return jsonify({
            "users": users,
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": page
        })
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
            password=generate_password_hash(data["password"], method='pbkdf2:sha256'),  # 使用模型方法加密密码
            role='user',  # 默认角色为用户
            created_at=datetime.now()  # 设置创建时间
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
        deleted_user = User.query.filter_by(username=username,role='user').first()
        if deleted_user is None:
            return jsonify({"success": False, "error": f'未找到用户名 "{username}"'}), 404
        # 找到后
        db.session.delete(deleted_user)
        db.session.commit()
        return jsonify(
            {"success": True, "message": f'用户 "{username}" 已成功删除'}
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin", methods=["GET"])
def get_admin():
    try:
        page = int(request.args.get("page", 1))        # 当前页码，默认1
        per_page = int(request.args.get("per_page", 10))  # 每页条数，默认10

        query = User.query.order_by(User.created_at.desc())
        query = User.query.filter_by(role='admin')  # 只查询普通用户
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        users = [
            {
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for user in pagination.items
        ]

        return jsonify({
            "users": users,
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": page
        })
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
            password=generate_password_hash(data["password"], method='pbkdf2:sha256'),  # 使用模型方法加密密码
            role='admin',
            created_at=datetime.now()  # 设置创建时间
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
        deleted_user = User.query.filter_by(username=username, role='admin').first()
        if deleted_user.username == 'admin':
            return jsonify({"success": False, "error": '无法删除默认管理员 "admin"'}), 403
        if deleted_user is None:
            return jsonify({"success": False, "error": f'未找到管理员名 "{username}"'}), 404
        # 找到后
        db.session.delete(deleted_user)
        db.session.commit()
        return jsonify(
            {"success": True, "message": f'管理员 "{username}" 已成功删除'}
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Reset admin password
@app.route('/api/users/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    username = data.get('username')

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    # 例如默认重置为 123456
    new_password = '123456'
    user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
    user.created_at = datetime.now()  # 更新创建时间
    db.session.commit()
    return jsonify({'success': True, 'message': f'用户 {username} 的密码已重置为 {new_password}'})


@app.route("/user_list")
def user_list():
    return render_template("用户列表.html")


@app.route("/admin_list")
def admin_list():
    return render_template("管理员列表.html")


@app.route("/computer_list")
def computer_list():
    return render_template("机器列表.html")

@app.route("/api/sensors", methods=['GET'])
def get_sensors():
    try:
        page = int(request.args.get("page", 1))        # 当前页码，默认1
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
                "update_time": sensor.update_time.strftime("%Y-%m-%d %H:%M:%S")
            }
            for sensor in pagination.items
        ]

        return jsonify({
            "sensors": sensors,
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": page
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sensors", methods=['POST'])
def add_sensors():
    data = request.get_json()
    # 验证必填字段
    required_fields = ["id", "name", "capacity", "status", "farm", "test", "count", "price", "update_time"]
    for field in required_fields:
        if field not in data:
            return jsonify({"success": False, "message": f"Missing field: {field}"})
    try:
        # 检查是否被创建了
        if Sensor.query.filter_by(id=data["id"]).first():
            return jsonify({"success": False, "message": "id已被使用"})
        
        new_sensor = Sensor(
            id = data["id"],
            name = data["name"],
            capacity = data["capacity"],
            status = data["status"],
            farm = data["farm"],
            test = data["test"],
            count = data["count"],
            price = data["price"],
            update_time = data["update_time"]
        )
        db.session.add(new_sensor)
        db.session.commit()
        return jsonify({"success": True, "message": "Sensor added successfully"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/sensors", methods=['DELETE'])
def delete_sensors():
    sensorid = request.get_json()
    try:
        deleted_sensor = Sensor.query.filter_by(id=sensorid).first()
        if deleted_sensor is None:
            return jsonify({"success": False, "error": f'未找到传感器id "{sensorid}"'}), 404
        # 找到后
        db.session.delete(deleted_sensor)
        db.session.commit()
        return jsonify(
            {"success": True, "message": f'传感器id "{sensorid}" 已成功删除'}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/sensor_list")
def sensor_list():
    page = request.args.get("page", default=1, type=int)
    per_page = 10

    pagination = Sensor.query.order_by(Sensor.id.desc()).paginate(page=page, per_page=per_page)
    sensors = pagination.items
    total = pagination.total
    pages = pagination.pages

    return render_template("传感器列表.html", sensors=sensors, page=page, total=total, pages=pages)



@app.route("/warning")
def warning():
    return render_template("预警设置.html")


@app.route("/api/charts/growth")
def plot():
    try:
        metric = request.args.get('metric', 'Height(cm)').strip()

        # 将metric传递给绘图函数
        img_io = plot_average_by_species(metric)
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
            "to_year": request.args.get("to_year", "2020").strip(),
            "to_month": request.args.get("to_month", "05").strip(),
            "to_day": request.args.get("to_day", "31").strip(),
            "position": request.args.get("position", "鼓楼外大街").strip(),
            "metrics": re.sub(r"<[^>]+>|\?.*", "", request.args.get("metrics", "水温")),
            "data_root_dir": "data",
        }

        # 获取图像 BytesIO
        result = draw_metrics(**params)

        if isinstance(result, str):
            app.logger.error(f"图表生成失败: {result}")
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": result,
                        "suggestions": ["检查指标名称是否正确", "确认日期范围内存在数据", "验证监测点名称是否有效"],
                    }
                ),
                400,
            )

        result.seek(0)
        img_base64 = base64.b64encode(result.read()).decode("utf-8")

        return jsonify(
            {"status": "success", "image": f"data:image/png;base64,{img_base64}"}
        )

    except Exception as e:
        app.logger.error(f"系统错误: {str(e)}")
        return jsonify({"status": "error", "message": f"内部服务器错误: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)
