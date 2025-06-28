import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("Agg")  # 使用非交互式后端
from io import BytesIO
import os
import re
import json
import pandas as pd

import matplotlib.dates as mdates

plt.rcParams["font.sans-serif"] = ["SimHei"]  # 用来正常显示中文标签
plt.rcParams["axes.unicode_minus"] = False  # 用来正常显示负号

valid_metrics = [
    "Weight(g)",
    "Height(cm)",
    "Width(cm)",
    "Length1(cm)",
    "Length2(cm)",
    "Length3(cm)",
]


def get_valid_metrics():
    return valid_metrics


# Load data in app.py and then pass it to this function
def plot_average_by_species(df, metric="Height(cm)"):
    if metric not in valid_metrics:
        raise ValueError(f"无效指标: {metric}")

    # 计算每个物种的平均值和标准差
    grouped = df.groupby("Species").agg({metric: ["mean", "std"]}).reset_index()
    grouped.columns = ["Species", "mean", "std"]

    # 按平均值排序
    grouped = grouped.sort_values(by="mean", ascending=False)

    # 创建自定义配色方案
    custom_colors = [
        "#3498db",
        "#2ecc71",
        "#e74c3c",
        "#f39c12",
        "#9b59b6",
        "#1abc9c",
        "#34495e",
    ]

    # 设置图表风格
    plt.style.use("ggplot")

    # 创建图表
    fig, ax = plt.subplots(figsize=(12, 7))

    # 绘制主要条形图
    bars = ax.bar(
        grouped["Species"],
        grouped["mean"],
        yerr=grouped["std"],
        capsize=5,
        color=custom_colors[: len(grouped)],
        edgecolor="white",
        linewidth=1.5,
        alpha=0.8,
    )

    # 添加数据标签
    for bar, value, std in zip(bars, grouped["mean"], grouped["std"]):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height + std + 0.1,
            f"{value:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    # 设置标题和标签
    ax.set_title(f"各鱼类品种的平均{metric}比较", fontsize=15, pad=20)
    ax.set_xlabel("鱼类品种", fontsize=12, labelpad=10)
    ax.set_ylabel(metric, fontsize=12, labelpad=10)

    # 添加网格线（只在Y轴）
    ax.yaxis.grid(True, linestyle="--", alpha=0.7)
    ax.set_axisbelow(True)  # 网格线置于图形元素之下

    # X轴标签旋转
    plt.xticks(rotation=30, ha="right", fontsize=10)
    plt.yticks(fontsize=10)

    # 添加平均值线
    overall_mean = df[metric].mean()
    ax.axhline(y=overall_mean, color="#e74c3c", linestyle="--", linewidth=1.5)
    ax.text(
        len(grouped) - 1,
        overall_mean * 1.02,
        f"总体平均值: {overall_mean:.2f}",
        color="#e74c3c",
        fontsize=9,
        ha="right",
    )

    # 设置背景颜色和边框
    fig.patch.set_facecolor("#f9f9f9")
    ax.set_facecolor("#f9f9f9")

    # 为每个条形添加值标注
    for i, bar in enumerate(bars):
        species_count = len(df[df["Species"] == grouped["Species"].iloc[i]])
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            0.1,
            f"n={species_count}",
            ha="center",
            va="bottom",
            color="dimgrey",
            fontsize=8,
        )

    # 添加脚注
    plt.figtext(
        0.02, 0.02, f"数据样本总数: {len(df)} | 指标: {metric}", fontsize=8, color="grey"
    )

    # 添加图例标识数据含义
    from matplotlib.lines import Line2D

    custom_lines = [
        Line2D([0], [0], color="#e74c3c", lw=1.5, linestyle="--"),
        Line2D([0], [0], color="black", lw=1.5),
    ]
    ax.legend(
        custom_lines,
        ["总体平均值", "标准差范围"],
        loc="upper right",
        frameon=True,
        framealpha=0.7,
    )

    # 调整布局
    # plt.tight_layout()

    # 保存图表
    img_io = BytesIO()
    plt.savefig(img_io, format="png", dpi=120, bbox_inches="tight")
    # plt.show()
    plt.close()
    img_io.seek(0)
    return img_io


def generate_water_quality_plot(dates, values, metric, position, start_date, end_date):
    """生成水质指标趋势图，风格与物种平均图一致"""
    # 设置图表风格
    plt.style.use("ggplot")

    # 创建图表
    fig, ax = plt.subplots(figsize=(12, 7))

    # 设置背景颜色
    fig.patch.set_facecolor("#f9f9f9")
    ax.set_facecolor("#f9f9f9")

    # 绘制折线图 - 使用自定义颜色
    line = ax.plot(
        dates,
        values,
        marker="o",
        linestyle="-",
        color="#3498db",  # 使用与物种图相同的蓝色
        markersize=6,
        linewidth=1.5,
        alpha=0.8,
    )

    # 设置标题和标签 - 保持一致的字体大小和间距
    ax.set_title(
        f"{position} - {metric}趋势\n"
        f"({start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')})",
        fontsize=15,
        pad=20,
    )
    ax.set_xlabel("日期", fontsize=12, labelpad=10)
    ax.set_ylabel(metric, fontsize=12, labelpad=10)

    # 添加网格线（只在Y轴）
    ax.yaxis.grid(True, linestyle="--", alpha=0.7)
    ax.set_axisbelow(True)  # 网格线置于图形元素之下

    # 智能日期格式化
    num_days = (max(dates) - min(dates)).days + 1 if dates else 0

    # 根据时间跨度设置日期格式
    if num_days <= 1:
        # 单日内显示小时
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    elif num_days <= 7:
        # 7天内显示天+小时
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        ax.xaxis.set_major_locator(mdates.DayLocator())
    elif num_days <= 30:
        # 30天内显示天
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, num_days // 7)))
    else:
        # 超过30天按周显示
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))

    # X轴标签旋转 - 与物种图一致的角度
    plt.xticks(rotation=30, ha="right", fontsize=10)
    plt.yticks(fontsize=10)

    # 创建两个新列表存储过滤后的数据
    filtered_dates = []
    filtered_values = []

    for date, value in zip(dates, values):
        # 如果 value 不是 str 类型，则添加到新列表中
        if not isinstance(value, str):
            filtered_dates.append(date)
            filtered_values.append(value)
    dates = filtered_dates
    values = filtered_values

    # 添加数据点标签
    for i, (date, value) in enumerate(zip(dates, values)):
        ax.text(
            date,
            value + (max(values) - min(values)) * 0.02,  # 在点上方向偏移
            f"{value:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#3498db",
        )

    # 添加总体平均值线
    overall_mean = sum(values) / len(values) if values else 0
    ax.axhline(y=overall_mean, color="#e74c3c", linestyle="--", linewidth=1.5)
    ax.text(
        dates[-1] if dates else start_date,
        overall_mean * 1.02,
        f"平均值: {overall_mean:.2f}",
        color="#e74c3c",
        fontsize=9,
        ha="right",
    )

    # 添加脚注
    plt.figtext(
        0.02,
        0.02,
        f"数据时间范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')} | 指标: {metric}",
        fontsize=8,
        color="grey",
    )

    # 添加图例标识数据含义
    from matplotlib.lines import Line2D

    custom_lines = [
        Line2D([0], [0], color="#3498db", lw=1.5, marker="o"),
        Line2D([0], [0], color="#e74c3c", lw=1.5, linestyle="--"),
    ]
    ax.legend(
        custom_lines,
        ["实测值", "平均值"],
        loc="upper right",
        frameon=True,
        framealpha=0.7,
    )

    # 设置中文字体支持
    plt.rcParams["font.sans-serif"] = [
        "SimHei",
        "Microsoft YaHei",
        "WenQuanYi Micro Hei",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    # 调整布局
    plt.tight_layout()

    # 保存到BytesIO
    buf = BytesIO()
    plt.savefig(
        buf,
        format="png",
        dpi=120,
        bbox_inches="tight",  # 使用相同的bbox_inches设置
        facecolor="#f9f9f9",
    )
    plt.close()
    return buf
