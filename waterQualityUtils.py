import json
import os
import re
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def query(year='2020', month='05', day='08', position='鼓楼外大街', metrics='水温', data_root_dir='data'):
    """
    Queries water quality data from JSON files.

    Args:
        year (str): The year of the data.
        month (str): The month of the data (e.g., '05').
        day (str): The day of the data (e.g., '08').
        position (str): The name of the monitoring station (断面名称).
        metrics (str): The name of the metric to query (e.g., '水温', 'pH').
        data_root_dir (str): The root directory where data is stored (e.g., '/data' or 'data' for local).

    Returns:
        The queried value. Float if it has an "原始值", otherwise string.
        Returns an error message string if data is not found or an error occurs.
    """
    file_name = f"{year}-{month}-{day}.json"
    file_path = os.path.join(data_root_dir, f"{year}-{month}", file_name)

    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return f"Error: Could not decode JSON from {file_path}"
    except Exception as e:
        return f"Error reading file {file_path}: {e}"

    if 'thead' not in data or 'tbody' not in data:
        return "Error: JSON structure is invalid (missing 'thead' or 'tbody')."

    thead = data['thead']
    tbody = data['tbody']
    try:
        position_col_index = thead.index("断面名称")
    except ValueError:
        return "Error: '断面名称' column not found in thead."

    metric_col_index = -1
    for i, header_name in enumerate(thead):
        if header_name.startswith(metrics):
            metric_col_index = i
            break

    if metric_col_index == -1:
        return f"Error: Metric '{metrics}' not found in thead."

    for row in tbody:
        if len(row) <= max(position_col_index, metric_col_index):
            continue

        if row[position_col_index] == position:
            value_str = row[metric_col_index]

            match = re.search(r"<span title='原始值：([\d\.-]+)'>", value_str)
            if match:
                try:
                    original_value = float(match.group(1))
                    return original_value
                except ValueError:
                    return f"Error: Could not convert original value '{match.group(1)}' to float for {metrics} at {position}."
            else:
                return value_str

    return f"Error: Position '{position}' not found for the date {year}-{month}-{day}."


def draw_metrics(from_year='2020', from_month='05', from_day='08',
                 to_year='2020', to_month='05', to_day='08',
                 position='鼓楼外大街', metrics='水温', data_root_dir='data'):
    """
    Draws a line graph for a given metric over a date range,
    if the metric consistently provides numerical original values.

    Args:
        from_year (str): Start year.
        from_month (str): Start month.
        from_day (str): Start day.
        to_year (str): End year.
        to_month (str): End month.
        to_day (str): End day.
        position (str): Monitoring station name.
        metrics (str): Metric name.
        data_root_dir (str): Root directory for data.
    """
    try:
        start_date = datetime.date(int(from_year), int(from_month), int(from_day))
        end_date = datetime.date(int(to_year), int(to_month), int(to_day))
    except ValueError as e:
        print(f"Error: Invalid date input - {e}")
        return

    if start_date > end_date:
        print("Error: The 'from_date' cannot be after 'to_date'. Please provide a valid date range.")
        return

    dates_to_plot = []
    values_to_plot = []
    current_date = start_date
    metric_has_consistent_original_values = True

    print(f"Fetching data for {metrics} at {position} from {start_date} to {end_date}...")

    while current_date <= end_date:
        year_str = str(current_date.year)
        month_str = f"{current_date.month:02d}" 
        day_str = f"{current_date.day:02d}"

        value = query(year=year_str, month=month_str, day=day_str,
                      position=position, metrics=metrics, data_root_dir=data_root_dir)

        if isinstance(value, float):
            dates_to_plot.append(current_date)
            values_to_plot.append(value)
        elif isinstance(value, str):
            if value.startswith("Error:"):
                print(f"Warning for {current_date}: {value} (Skipping this data point)")
            else:
                metric_has_consistent_original_values = False
                print(f"Error: Metric '{metrics}' at position '{position}' on {current_date} "
                      f"returned '{value}', which is not a numerical original value. "
                      f"This function requires metrics that consistently provide parseable '原始值'.")
                break
        else:
            print(f"Warning for {current_date}: Received unexpected data type for metric '{metrics}': {type(value)}. Skipping.")


        current_date += datetime.timedelta(days=1)

    if not metric_has_consistent_original_values:
        return

    if not values_to_plot:
        print(f"Error: No valid numerical data found for metric '{metrics}' at "
              f"position '{position}' in the date range {start_date} to {end_date}. Cannot draw plot.")
        return

    plt.figure(figsize=(12, 6))
    plt.plot(dates_to_plot, values_to_plot, marker='o', linestyle='-', label=metrics)

    plt.title(f"{metrics} for {position}\n({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})")
    plt.xlabel("Date")
    plt.ylabel(f"{metrics} Value")
    plt.legend()
    plt.grid(True)

    ax = plt.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45, ha="right") 
    plt.tight_layout()

    try:
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False 
    except Exception as e:
        print(f"Note: Could not set Chinese font. Characters might not display correctly. Error: {e}")

    plt.show()