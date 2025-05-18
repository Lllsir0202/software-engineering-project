import os
import json
import re
import datetime
from io import BytesIO
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def query(
    year="2020",
    month="05",
    day="08",
    position="鼓楼外大街",
    metrics="水温",
    data_root_dir="data",
):
    """
    查询水质数据的增强版本，提供详细的错误信息

    Args: [原有参数说明保持不变]

    Returns:
        float/str: 成功返回数值，失败返回包含详细信息的错误字符串
    """
    # 构建文件路径
    file_name = f"{year}-{month}-{day}.json"
    month_dir = os.path.join(data_root_dir, f"{year}-{month}")
    file_path = os.path.join(month_dir, file_name)

    # 错误处理：文件检查
    if not os.path.exists(month_dir):
        return f"错误：月份目录不存在 - 路径: {month_dir}，" f"请确认年份({year})和月份({month})是否正确"
    if not os.path.exists(file_path):
        return f"错误：数据文件未找到 - 路径: {file_path}，" f"请确认日期 {year}-{month}-{day} 是否存在数据"

    # 读取文件
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return (
            f"错误：JSON解析失败 - 文件: {file_path}，"
            f"错误位置: 第{e.lineno}行第{e.colno}列，"
            f"错误详情: {e.msg}"
        )
    except Exception as e:
        return f"错误：文件读取失败 - 路径: {file_path}，系统错误: {str(e)}"

    # 数据结构验证
    missing_parts = []
    if "thead" not in data:
        missing_parts.append("thead")
    if "tbody" not in data:
        missing_parts.append("tbody")
    if missing_parts:
        return f"错误：JSON结构异常 - 文件: {file_path}，" f"缺失部分: {', '.join(missing_parts)}"

    # 列索引查找
    thead = data["thead"]
    tbody = data["tbody"]
    try:
        position_col_index = thead.index("断面名称")
    except ValueError:
        available_columns = ", ".join(thead)
        return f"错误：缺少必要列 - 文件: {file_path}，" f"未找到'断面名称'，可用列: {available_columns}"

    # 指标列查找
    metric_col_index = -1
    metrics = re.sub(r'<[^>]+>', '', metrics)
    for i, header_name in enumerate(thead):
        if header_name.startswith(metrics):
            metric_col_index = i
            break
    if metric_col_index == -1:
        available_metrics = [col for col in thead if col != "断面名称"]
        return (
            f"错误：指标不存在 - 文件: {file_path}，"
            f"请求指标: {metrics}，可用指标: {', '.join(available_metrics)}"
        )

    # 数据行处理
    for row_idx, row in enumerate(data["tbody"]):
        # 跳过不符合长度的行
        if len(row) <= max(position_col_index, metric_col_index):
            continue

        # 匹配监测点
        if row[position_col_index] == position:
            value_str = row[metric_col_index]

            # 原始值提取
            match = re.search(r"<span title='原始值：([\d\.-]+)'>", value_str)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    return (
                        f"错误：数据转换失败 - 文件: {file_path}，"
                        f"行号: {row_idx+1}，原始值: {match.group(1)}，"
                        f"指标: {metrics}，位置: {position}"
                    )
            return value_str

    return (
        f"错误：监测点未找到 - 文件: {file_path}，"
        f"请求监测点: {position}，日期: {year}-{month}-{day}，"
        f"可用监测点: {', '.join(set(r[position_col_index] for r in tbody))}"
    )


def draw_metrics(
    from_year="2020",
    from_month="05",
    from_day="08",
    to_year="2020",
    to_month="05",
    to_day="08",
    position="鼓楼外大街",
    metrics="水温",
    data_root_dir="data",
):
    """
    绘制指标趋势图的增强版本，提供详细的错误追踪

    Args: [原有参数说明保持不变]

    Returns:
        BytesIO: 包含图表的图像缓冲区
        str: 发生错误时返回错误描述字符串
    """
    error_log = []

    # 参数校验
    try:
        start_date = datetime.date(int(from_year), int(from_month), int(from_day))
    except ValueError as e:
        error = (
            f"无效的起始日期参数 - 年: {from_year}, 月: {from_month}, 日: {from_day}，"
            f"错误详情: {str(e)}"
        )
        error_log.append(error)
        return "\n".join(error_log)

    try:
        end_date = datetime.date(int(to_year), int(to_month), int(to_day))
    except ValueError as e:
        error = (
            f"无效的结束日期参数 - 年: {to_year}, 月: {to_month}, 日: {to_day}，" f"错误详情: {str(e)}"
        )
        error_log.append(error)
        return "\n".join(error_log)

    if start_date > end_date:
        error = f"日期范围无效 - 开始日期({start_date})不能晚于结束日期({end_date})"
        error_log.append(error)
        return "\n".join(error_log)

    # 数据收集
    dates_to_plot = []
    values_to_plot = []
    current_date = start_date
    date_range = (end_date - start_date).days + 1

    for day_count in range(date_range):
        date_str = current_date.strftime("%Y-%m-%d")
        year_str = str(current_date.year)
        month_str = f"{current_date.month:02d}"
        day_str = f"{current_date.day:02d}"

        result = query(
            year=year_str,
            month=month_str,
            day=day_str,
            position=position,
            metrics=metrics,
            data_root_dir=data_root_dir,
        )

        # 处理查询结果
        if isinstance(result, float):
            dates_to_plot.append(current_date)
            values_to_plot.append(result)
        elif isinstance(result, str):
            if result.startswith("错误："):
                error_log.append(f"[{date_str}] {result}")
                if "非数值原始值" in result:
                    return "\n".join(error_log)
            else:
                error_log.append(f"[{date_str}] 非数值结果 - 指标: {metrics}，返回值: {result}")
                return "\n".join(error_log)
        else:
            error_log.append(f"[{date_str}] 未知数据类型 - 类型: {type(result)}，值: {result}")
            return "\n".join(error_log)

        current_date += datetime.timedelta(days=1)

    # 数据验证
    if not values_to_plot:
        error_log.append(
            f"无有效数据 - 位置: {position}，指标: {metrics}，"
            f"日期范围: {start_date} 至 {end_date}，"
            f"可能原因: {', '.join(set(e.split(']')[-1].strip() for e in error_log))}"
        )
        return "\n".join(error_log)

    # 绘图配置
    try:
        plt.figure(figsize=(12, 6))
        plt.plot(
            dates_to_plot, values_to_plot, marker="o", linestyle="-", label=metrics
        )

        # 标题和标签
        plt.title(
            f"{metrics}趋势 - {position}\n"
            f"({start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')})"
        )
        plt.xlabel("日期", fontsize=12)
        plt.ylabel(f"{metrics}数值", fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)

        # 日期格式
        ax = plt.gca()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, date_range // 7)))
        plt.xticks(rotation=45, ha="right")

        # 中文支持
        try:
            plt.rcParams["font.sans-serif"] = [
                "SimHei",
                "Microsoft YaHei",
                "WenQuanYi Micro Hei",
            ]
            plt.rcParams["axes.unicode_minus"] = False
        except Exception as e:
            error_log.append(f"字体配置警告: {str(e)}")

        # 生成图像
        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close()
        buf.seek(0)
        return buf

    except Exception as e:
        error_log.append(f"绘图过程出错 - 错误类型: {type(e).__name__}，详情: {str(e)}")
        return "\n".join(error_log)
