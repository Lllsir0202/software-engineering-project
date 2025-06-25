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
    print(f"Admin login failed for {adminname} with password {password}")
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
        try:
            with open("static/user.json", "r", encoding="utf-8") as file:
                users = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return jsonify({"success": False, "message": "用户数据不存在"})
        user = next((u for u in users if u["email"] == email), None)
        if not user:
            return jsonify({"success": False, "message": "邮箱未注册"})
        # Store user information in session
        session["username"] = user["username"]
        session["login_time"] = time.time()
        session.pop("verification_code", None)
        session.pop("verification_email", None)
        session.pop("verification_expire", None)
        return jsonify({"success": True, "redirect": url_for("homepage", name=email)})


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
    data_dict = {"username": username, "email": email, "password": password}
    file_path = "static/user.json"
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            users = json.load(file)  # 读取为列表
    except (FileNotFoundError, json.JSONDecodeError):
        users = []
    if any(user["username"] == username for user in users):
        return jsonify({"success": False, "message": "用户名已被注册"})
    if any(user["email"] == email for user in users):
        return jsonify({"success": False, "message": "邮箱已被注册"})
    users.append(data_dict)
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)
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

    file_path = "static/user.json"
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            users = json.load(file)  # 读取为列表
    except (FileNotFoundError, json.JSONDecodeError):
        users = []
    if all(user["email"] != email for user in users):
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
    USER_FILE = "static/user.json"
    try:
        with open(USER_FILE, "r") as f:
            users = json.load(f)
        return jsonify(users)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 新增用户
@app.route("/api/users", methods=["POST"])
def add_users():
    USER_FILE = "static/user.json"
    data = request.get_json()
    # 验证必填字段
    required_fields = ["username", "email", "password"]
    for field in required_fields:
        if field not in data:
            return jsonify({"success": False, "message": f"Missing field: {field}"})

    try:
        # 读取现有用户
        with open(USER_FILE, "r") as f:
            users = json.load(f)

        # 检查用户名是否已存在
        for user in users:
            if user["username"] == data["username"]:
                return jsonify({"success": False, "message": "Username already exists"})

        # 创建新用户
        new_user = {
            "username": data["username"],
            "email": data["email"],
            "password": data["password"],
        }

        # 添加到用户列表
        users.append(new_user)
        print(new_user)

        # 保存回文件
        with open(USER_FILE, "w", encoding="utf-8") as file:
            json.dump(users, file, ensure_ascii=False, indent=4)

        return jsonify({"success": True, "message": "User added successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/users", methods=["DELETE"])
def delete_user():
    USER_FILE = "static/user.json"
    username = request.get_json()
    try:
        # 读取用户文件
        with open(USER_FILE, "r") as f:
            users = json.load(f)

        # 查找要删除的用户
        user_index = next(
            (i for i, user in enumerate(users) if user["username"] == username), None
        )

        if user_index is not None:
            # 删除用户
            deleted_user = users.pop(user_index)

            # 保存更新后的用户列表
            with open(USER_FILE, "w", encoding="utf-8") as file:
                json.dump(users, file, ensure_ascii=False, indent=4)

            return jsonify(
                {"message": f'用户 "{username}" 已成功删除', "deleted_user": deleted_user}
            )
        else:
            return jsonify({"error": f'未找到用户名 "{username}"'}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin", methods=["GET"])
def get_admin():
    USER_FILE = "static/admin.json"
    try:
        with open(USER_FILE, "r") as f:
            users = json.load(f)
        return jsonify(users)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 新增用户
@app.route("/api/admin", methods=["POST"])
def add_admin():
    USER_FILE = "static/admin.json"
    data = request.get_json()
    # 验证必填字段
    required_fields = ["adminname", "email", "password"]
    for field in required_fields:
        if field not in data:
            return jsonify({"success": False, "message": f"Missing field: {field}"})

    try:
        # 读取现有用户
        with open(USER_FILE, "r") as f:
            users = json.load(f)

        # 检查用户名是否已存在
        for user in users:
            if user["adminname"] == data["adminname"]:
                return jsonify(
                    {"success": False, "message": "Adminname already exists"}
                )

        # 创建新用户
        new_user = {
            "adminname": data["adminname"],
            "email": data["email"],
            "password": data["password"],
        }

        # 添加到用户列表
        users.append(new_user)
        print(new_user)

        # 保存回文件
        with open(USER_FILE, "w", encoding="utf-8") as file:
            json.dump(users, file, ensure_ascii=False, indent=4)

        return jsonify({"success": True, "message": "Admin added successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin", methods=["DELETE"])
def delete_admin():
    USER_FILE = "static/admin.json"
    adminname = request.get_json()
    try:
        # 读取用户文件
        with open(USER_FILE, "r") as f:
            users = json.load(f)

        # 查找要删除的用户
        user_index = next(
            (i for i, user in enumerate(users) if user["adminname"] == adminname), None
        )

        if user_index is not None:
            # 删除用户
            deleted_user = users.pop(user_index)

            # 保存更新后的用户列表
            with open(USER_FILE, "w", encoding="utf-8") as file:
                json.dump(users, file, ensure_ascii=False, indent=4)

            return jsonify(
                {"message": f'管理员 "{adminname}" 已成功删除', "deleted_user": deleted_user}
            )
        else:
            return jsonify({"error": f'未找到管理员名 "{adminname}"'}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/user_list")
def user_list():
    return render_template("用户列表.html")


@app.route("/admin_list")
def admin_list():
    return render_template("管理员列表.html")


@app.route("/computer_list")
def computer_list():
    return render_template("机器列表.html")


@app.route("/sensor_list")
def sensor_list():
    return render_template("传感器列表.html")


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
