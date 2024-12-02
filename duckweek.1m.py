#!/usr/bin/env python3
# <xbar.title>Duck Week</xbar.title>
# <xbar.version>v1.0</xbar.version>
# <xbar.author>Mark Eklund</xbar.author>
# <xbar.author.github>bonafideduck</xbar.author.github>
# <xbar.desc>A simple screen-time that displays non-idle time for day and week.</xbar.desc>
# <xbar.image>http://www.hosted-somewhere/pluginimage</xbar.image>
# <xbar.dependencies>python</xbar.dependencies>
# <xbar.abouturl>http://url-to-about.com/</xbar.abouturl>
# <xbar.droptypes>None</xbar.droptypes>

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import subprocess

config_path = Path.home() / ".config" / "xbar-duckweek" / "config.json"

# Ensure the config directory exists
config_path.parent.mkdir(parents=True, exist_ok=True)

# Create the config file if it doesn't exist
if not config_path.exists():
    with config_path.open("w") as f:
        json.dump({}, f)

# Get timestamp of the config file
now = datetime.now()
timestamp = datetime.fromtimestamp(config_path.stat().st_mtime)
timestamp_delta = (now - timestamp).total_seconds()

# Read the contents of the file
with config_path.open("r") as f:
    config = json.load(f)

# Initialize config structure if empty
if not config:
    config = {
        "days": [{"day": now.strftime("%Y-%m-%d"), "seconds": 0}],
        "activeTS": None,
        "idleThreshold": 600,
        "showDuck": True,
        "showWeek": True,
        "showToday": True,
    }


# Helper function to get the last Sunday
def last_sunday():
    today = datetime.today()
    start = today - timedelta(days=(today.weekday() + 1) % 7)
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


# Extract idleThreshold from config or set to default (600 seconds) if not present
idle_threshold = config.setdefault("idleThreshold", 600)

# Remove all days before last Sunday
last_sunday_date = last_sunday().date()
config["days"] = [
    day
    for day in config["days"]
    if datetime.strptime(day["day"], "%Y-%m-%d").date() >= last_sunday_date
]

# Check the idle time using `ioreg`
ioreg_cmd = ["ioreg", "-n", "IOHIDSystem", "-d", "4", "-r", "-k", "HIDIdleTime"]
idle_cmd_output = subprocess.run(ioreg_cmd, stdout=subprocess.PIPE).stdout.decode()


# Extract the HIDIdleTime and convert it to seconds
idle_time_ns = int(
    idle_cmd_output.split("HIDIdleTime")[1].split("=")[1].split("\n")[0].strip()
)
idle_time = idle_time_ns / 1_000_000_000  # Convert nanoseconds to seconds

# Get the last active timestamp
active_ts = config.get("activeTS")
if active_ts:
    active_ts = datetime.strptime(active_ts, "%Y-%m-%d %H:%M:%S")
was_active = active_ts is not None

unsaved_time = 0
new_day = active_ts is not None and active_ts.date() != now.date()
write = False
touch = False


def update_day_seconds(config, active_ts, active_delta):
    found = None
    active_ts_date = active_ts.strftime("%Y-%m-%d")

    for day in config["days"]:
        if day["day"] == active_ts_date:
            found = day
            break

    if not found:
        found = {"day": active_ts_date, "seconds": 0}
        config["days"].append(found)

    found["seconds"] += active_delta


if was_active:
    active_delta = (now - active_ts).total_seconds()

    # This is no longer active
    if idle_time > idle_threshold or timestamp_delta > idle_threshold:
        active_delta -= max(idle_time, timestamp_delta)
        active_delta = max(0, active_delta)
        update_day_seconds(config, active_ts, active_delta)
        config["activeTS"] = None
        write = True
    else:
        # Pause showing updates until the user is active again
        unsaved_time = active_delta - idle_time
        touch = True

elif idle_time < idle_threshold:
    config["activeTS"] = now.strftime("%Y-%m-%d %H:%M:%S")
    write = True

if new_day and unsaved_time > 0:
    update_day_seconds(config, active_ts, unsaved_time)
    unsaved_time = 0
    config["activeTS"] = now.strftime("%Y-%m-%d %H:%M:%S")
    write = True

if write:
    with config_path.open("w") as f:
        json.dump(config, f, indent=2)

if touch and not write:
    os.utime(config_path, None)

# Calculate total hours for today and this week
today_str = now.strftime("%Y-%m-%d")
today_seconds = unsaved_time + sum(
    day["seconds"] for day in config["days"] if day["day"] == today_str
)
week_seconds = unsaved_time + sum(day["seconds"] for day in config["days"])


def sec_to_hh_mm(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{int(hours)}:{int(minutes):02d}"


# Print the output
output = ""
output += "🦆 " if config["showDuck"] else ""
output += sec_to_hh_mm(today_seconds) if config["showToday"] else ""
output += " / " if config["showWeek"] and config["showToday"] else ""
output += sec_to_hh_mm(week_seconds) if config["showWeek"] else ""
print(output)
