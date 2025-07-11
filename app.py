import os
import locale
import json
import random
import subprocess
import uuid
import requests
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify
from pdf2image import convert_from_path
from PIL import Image
import time
from urllib.parse import urlparse
from typing import Optional, Dict
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Always log to console
    ]
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# Base directory and folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
STATIC_IMAGE_FOLDER = os.path.join(STATIC_FOLDER, 'images')
SCREENSAVER_FOLDER = os.path.join(STATIC_FOLDER, 'screensaver')

# Create necessary folders
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_IMAGE_FOLDER, exist_ok=True)
os.makedirs(SCREENSAVER_FOLDER, exist_ok=True)
os.makedirs(os.path.join(STATIC_FOLDER, 'js'), exist_ok=True)

# Files for persistent settings and dynamic state
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
UPDATE_FILE = os.path.join(BASE_DIR, 'last_updates.json')
DASHBOARD_MODE_FILE = os.path.join(BASE_DIR, 'dashboard_mode.json')

# Allowed file extensions for security
ALLOWED_PDF_EXTENSIONS = {'pdf'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'avif'}

# --- Helper Functions ---
def allowed_file(filename, allowed_extensions):
    """Check if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_system_stats():
    """Get current system statistics for the Controls tab."""
    stats = {
        "boot_time": "Unknown",
        "cpu_load": "0",
        "cpu_temp": "0",
        "memory_usage": "0",
        "disk_free_pct": "0"
    }
    try:
        stats["boot_time"] = subprocess.check_output("uptime -s", shell=True).decode().strip()
        stats["cpu_load"] = subprocess.check_output("top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'", shell=True).decode().strip()
        stats["cpu_temp"] = subprocess.check_output("vcgencmd measure_temp | egrep -o '[0-9]*\\.[0-9]*'", shell=True).decode().strip()
        stats["memory_usage"] = subprocess.check_output("free | grep Mem | awk '{print $3/$2 * 100.0}'", shell=True).decode().strip()
        disk_used_pct = subprocess.check_output("df -h / | awk 'NR==2 {print $5}'", shell=True).decode().strip().replace('%', '')
        stats["disk_free_pct"] = str(100 - int(disk_used_pct))
    except Exception as e:
        logger.error(f"Could not retrieve all system stats: {e}")
    return stats

# --- Configuration Management ---
def load_config():
    """Load the main configuration from config.json."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading config file: {e}")
    # Default configuration
    return {
        "dashboard_duration": 10,
        "screensaver_config": [],
        "enable_mqtt": False,
        "mqtt_broker": "homeassistant.local",
        "mqtt_port": 1883,
        "mqtt_user": "",
        "mqtt_pass": "",
        "weekplans": [
            {"key": "plan1", "name": "Weekplan 1", "icon": "1"},
            {"key": "plan2", "name": "Weekplan 2", "icon": "2"}
        ]
    }

def save_config(config_data):
    """Save the configuration to config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
    except IOError as e:
        logger.error(f"Error saving config file: {e}")

# Load initial configuration
config = load_config()

# --- Dynamic State (Last Updates) ---
def load_last_updates() -> Dict[str, Optional[datetime]]:
    """Load the last update timestamps for weekplans."""
    if os.path.exists(UPDATE_FILE):
        try:
            with open(UPDATE_FILE, 'r') as f:
                data = json.load(f)
            for key, value in data.items():
                try:
                    data[key] = datetime.fromisoformat(value) if value else None
                except (ValueError, TypeError):
                    data[key] = None
            return data
        except (json.JSONDecodeError, IOError):
            pass
    return {plan['key']: None for plan in config.get("weekplans", [])}

def save_last_updates(updates_data):
    """Save the last update timestamps."""
    data_to_save = {key: dt.isoformat() if dt else "" for key, dt in updates_data.items()}
    with open(UPDATE_FILE, 'w') as f:
        json.dump(data_to_save, f, indent=2)

last_updates = load_last_updates()

# --- Dashboard Mode State ---
def set_forced_dashboard_until(dt: Optional[datetime]):
    """Set the forced dashboard mode until a specific time."""
    data = {"until": dt.isoformat() if dt else ""}
    with open(DASHBOARD_MODE_FILE, 'w') as f:
        json.dump(data, f)

def get_forced_dashboard_until() -> Optional[datetime]:
    """Get the time until which the dashboard is forced."""
    if not os.path.exists(DASHBOARD_MODE_FILE):
        return None
    try:
        with open(DASHBOARD_MODE_FILE, 'r') as f:
            data = json.load(f)
        until = data.get("until")
        return datetime.fromisoformat(until) if until else None
    except (json.JSONDecodeError, ValueError, IOError):
        return None

app = Flask(__name__)

# --- MQTT Setup (optional) ---
mqtt_client = None
if config.get("enable_mqtt"):
    try:
        import paho.mqtt.client as mqtt
        logger.info("MQTT is enabled.")
    except ImportError:
        logger.warning("paho-mqtt library not found. MQTT is disabled.")
        config["enable_mqtt"] = False

# Mock MQTT stats for demonstration if MQTT is disabled
mqtt_stats = {
    "pi/browser/current_url": "http://example.com",
    "pi/brightness/state": "0.75"
}

# --- Routes ---
@app.route('/')
def root():
    """Renders the main dashboard page."""
    now = datetime.now()
    try:
        locale.setlocale(locale.LC_TIME, "en_GB.UTF-8")
    except locale.Error:
        locale.setlocale(locale.LC_TIME, "")

    date_str = now.strftime("%A %-d %B").capitalize()
    time_str = now.strftime("%H:%M:%S")
    
    plan_updates = []
    for plan in config.get("weekplans", []):
        dt = last_updates.get(plan['key'])
        update_str = dt.strftime("%-d %B %Y, at %H:%M") if dt else "—"
        ts = int(dt.timestamp()) if dt else 0
        img_url = url_for('static', filename=f'images/{plan["key"]}-ukeplan.png') + f'?v={ts}'
        plan_updates.append({
            'key': plan['key'],
            'name': plan['name'],
            'icon': plan['icon'],
            'img_url': img_url,
            'last_update': update_str
        })
        
    active_screensaver_images = [item["filename"] for item in config.get("screensaver_config", []) if item.get("active", True)]
    screensaver_image_url = ""
    if active_screensaver_images:
        chosen_image = random.choice(active_screensaver_images)
        screensaver_image_url = url_for('static', filename=f'screensaver/{chosen_image}')
        
    return render_template(
        "dashboard.html",
        date_str=date_str,
        time_str=time_str,
        weekplans=plan_updates,
        screensaver_image_url=screensaver_image_url
    )

@app.route("/mode")
def mode():
    """API endpoint to check if the dashboard should be displayed."""
    until = get_forced_dashboard_until()
    mode_active = until is not None and datetime.now() < until
    return jsonify({"dashboard": mode_active})

@app.route("/screensaver_image")
def screensaver_image():
    """API endpoint to get a random screensaver image URL."""
    active_images = [item["filename"] for item in config.get("screensaver_config", []) if item.get("active", True)]
    if not active_images:
        return jsonify({"image_url": ""})
    
    chosen = random.choice(active_images)
    image_url = url_for('static', filename=f'screensaver/{chosen}')
    return jsonify({"image_url": image_url})

@app.route("/admin", methods=["GET", "POST"])
def admin():
    """Renders the admin panel and handles all admin actions."""
    global config, last_updates, mqtt_stats

    if request.args.get('refresh_status') == 'true':
        return jsonify(system_stats=get_system_stats())

    current_tab = request.args.get('tab', 'ukeplan')

    if request.method == 'POST':
        action = request.form.get('action')
        current_tab = request.form.get('current_tab', 'ukeplan') 

        if action == 'upload_pdf':
            file = request.files.get('pdf_file')
            target = request.form.get('target', 'plan1')
            if file and file.filename and allowed_file(file.filename, ALLOWED_PDF_EXTENSIONS):
                filename = secure_filename(f"{target}.pdf")
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                try:
                    images = convert_from_path(filepath, first_page=1, last_page=1)
                    if images:
                        image_path = os.path.join(STATIC_IMAGE_FOLDER, f"{target}-ukeplan.png")
                        images[0].save(image_path, 'PNG')
                        last_updates[target] = datetime.now()
                        save_last_updates(last_updates)
                except Exception as e:
                    logger.error(f"Error converting PDF: {e}")
            
        elif action == 'upload_screensaver_file':
            file = request.files.get('screensaver_file')
            if file and file.filename and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                filename = secure_filename(file.filename)
                if not any(d.get('filename') == filename for d in config["screensaver_config"]):
                    file.save(os.path.join(SCREENSAVER_FOLDER, filename))
                    config["screensaver_config"].append({"filename": filename, "active": True})
                    save_config(config)
            
        elif action == 'upload_screensaver_url':
            url = request.form.get('screensaver_url')
            if url:
                try:
                    parsed_url = urlparse(url)
                    if not all([parsed_url.scheme, parsed_url.netloc]):
                        raise ValueError("Invalid URL provided")
                    response = requests.get(url, stream=True, timeout=10)
                    response.raise_for_status()
                    content_type = response.headers.get('content-type', '').split(';')[0]
                    if not content_type.startswith('image/'):
                         raise ValueError(f"Invalid content type: {content_type}")
                    filename = secure_filename(os.path.basename(parsed_url.path) or f"downloaded_{uuid.uuid4().hex[:8]}.jpg")
                    if not allowed_file(filename, ALLOWED_IMAGE_EXTENSIONS):
                        ext = content_type.split('/')[-1]
                        valid_ext = ext if ext in ['jpeg', 'jpg', 'png', 'gif', 'webp'] else 'jpg'
                        filename = f"{os.path.splitext(filename)[0]}.{valid_ext}"
                    if not any(d.get('filename') == filename for d in config["screensaver_config"]):
                        filepath = os.path.join(SCREENSAVER_FOLDER, filename)
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        config["screensaver_config"].append({"filename": filename, "active": True})
                        save_config(config)
                except (requests.RequestException, ValueError) as e:
                    logger.error(f"Error downloading from URL {url}: {e}")
            
        elif action == 'delete_screensaver':
            filename = request.form.get('filename')
            if filename:
                safe_filename = secure_filename(filename)
                filepath = os.path.join(SCREENSAVER_FOLDER, safe_filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                config["screensaver_config"] = [item for item in config["screensaver_config"] if item['filename'] != safe_filename]
                save_config(config)
            
        elif action == 'update_screensaver_activation':
            active_images = request.form.getlist('active_images')
            for item in config["screensaver_config"]:
                item['active'] = item['filename'] in active_images
            save_config(config)
            
        elif action == 'show_week_plan':
            duration = config.get("dashboard_duration", 10)
            set_forced_dashboard_until(datetime.now() + timedelta(seconds=duration))
            
        elif action == 'set_duration':
            config['dashboard_duration'] = int(request.form.get('dashboard_duration', 10))
            save_config(config)

        elif action == 'set_weekplan_details':
            for plan in config.get('weekplans', []):
                plan['name'] = request.form.get(f"name_{plan['key']}", plan['name'])
                plan['icon'] = request.form.get(f"icon_{plan['key']}", plan['icon'])
            save_config(config)
        
        elif action == 'set_mqtt_config':
            config['enable_mqtt'] = 'enable_mqtt' in request.form
            config['mqtt_broker'] = request.form.get('mqtt_broker', 'homeassistant.local')
            config['mqtt_port'] = int(request.form.get('mqtt_port', 1883))
            config['mqtt_user'] = request.form.get('mqtt_user', '')
            config['mqtt_pass'] = request.form.get('mqtt_pass', '')
            save_config(config)
            
        elif action == 'set_brightness':
            brightness_pct = request.form.get('brightness', '75')
            brightness_val = float(brightness_pct) / 100.0
            logger.info(f"COMMAND: Set Brightness to {brightness_val}")
            mqtt_stats['pi/brightness/state'] = str(brightness_val)
        
        elif action == 'browser_url':
            url = request.form.get('url')
            if url:
                logger.info(f"COMMAND: Change URL to {url}")
                mqtt_stats['pi/browser/current_url'] = url

        elif action in ['display_on', 'display_off', 'system_restart']:
            logger.info(f"Received command: {action}")
            if action == 'system_restart':
                 logger.warning("System restart command received but not executed.")

        return redirect(url_for('admin', tab=current_tab))

    system_stats = get_system_stats()
    mqtt_connected = config.get('enable_mqtt') and mqtt_client is not None and mqtt_client.is_connected()

    return render_template(
        'admin.html',
        config=config,
        last_updates=last_updates,
        system_stats=system_stats,
        mqtt_stats=mqtt_stats,
        mqtt_connected=mqtt_connected,
        current_tab=current_tab
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
