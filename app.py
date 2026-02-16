# pyright: reportOptionalMemberAccess=false
import os
import random
import string
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, send_file, jsonify, send_from_directory, redirect, url_for, session
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static')

# ────────────────────────────────────────────────
#  CONFIGURATION & SECURITY
# ────────────────────────────────────────────────
# Use Environment Variable for Secret Key on Render, or a default for local dev
app.secret_key = os.environ.get("SECRET_KEY", "fileportal_secure_key_98765")

# Render's free tier works best with /tmp for temporary file storage
UPLOAD_FOLDER = "/tmp/uploads"
ROOM_DURATION_MINS = 30
MAX_TOTAL_SIZE = 100 * 1024 * 1024  # 100 MB total per room limit
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_TOTAL_SIZE

# Ensure upload directory exists
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

# In-memory database for Rooms
# Structure: { "code": {"timestamp": datetime, "host": str, "files": [], "history": []} }
room_store = {}

# User Name Generation Lists
ADJECTIVES = ["Swift", "Brave", "Shiny", "Cool", "Clever", "Happy", "Silver", "Neon", "Fast", "Quiet"]
ANIMALS = ["Tiger", "Panda", "Fox", "Eagle", "Wolf", "Dolphin", "Lion", "Falcon", "Owl", "Shark"]

# ────────────────────────────────────────────────
#  LOGGING
# ────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────
#  HELPER FUNCTIONS
# ────────────────────────────────────────────────

def get_or_create_user():
    """Assigns a unique, persistent username to the visitor's session."""
    if 'username' not in session:
        name = f"{random.choice(ADJECTIVES)}-{random.choice(ANIMALS)}-{random.randint(10, 99)}"
        session['username'] = name
    return session['username']

def generate_room_code(length=6):
    """Generates a unique 6-digit numeric code for the room."""
    while True:
        code = ''.join(random.choices(string.digits, k=length))
        if code not in room_store:
            return code

def get_human_size(size_bytes):
    """Converts bytes to a human-readable string (MB, KB, etc)."""
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"

def add_history(code, user, action):
    """Logs an activity into the room's history list."""
    if code in room_store:
        timestamp = datetime.now().strftime("%I:%M %p")
        room_store[code]['history'].insert(0, {
            "user": user,
            "action": action,
            "time": timestamp
        })

# ────────────────────────────────────────────────
#  BACKGROUND CLEANUP TASK
# ────────────────────────────────────────────────

def cleanup_expired_rooms():
    """Thread that runs every minute to delete rooms older than 30 mins."""
    while True:
        try:
            now = datetime.now()
            expired_codes = []
            
            for code, data in room_store.items():
                if now - data['timestamp'] > timedelta(minutes=ROOM_DURATION_MINS):
                    expired_codes.append(code)
            
            for code in expired_codes:
                # Delete files from disk
                for file_info in room_store[code]['files']:
                    file_path = Path(UPLOAD_FOLDER) / file_info['stored_name']
                    if file_path.exists():
                        file_path.unlink()
                
                # Delete from memory
                del room_store[code]
                logger.info(f"Cleanup: Room {code} and its files deleted.")
                
        except Exception as e:
            logger.error(f"Cleanup Error: {e}")
        
        time.sleep(60)

# Start cleanup thread in the background
threading.Thread(target=cleanup_expired_rooms, daemon=True).start()

# ────────────────────────────────────────────────
#  WEB ROUTES
# ────────────────────────────────────────────────

@app.route("/")
def index():
    user = get_or_create_user()
    error = request.args.get('error')
    return render_template("index.html", error=error, username=user)

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route("/create-room", methods=["POST"])
def create_room():
    user = get_or_create_user()
    code = generate_room_code()
    
    room_store[code] = {
        "timestamp": datetime.now(),
        "host": user,
        "files": [],
        "history": []
    }
    
    add_history(code, user, "created the room (Host)")
    logger.info(f"Room Created: {code} by {user}")
    return redirect(url_for('room_page', code=code))

@app.route("/join", methods=["POST"])
def join_room():
    code = request.form.get("code", "").strip()
    if code in room_store:
        user = get_or_create_user()
        add_history(code, user, "joined the room")
        return redirect(url_for('room_page', code=code))
    return redirect(url_for('index', error="Invalid or Expired Room Code"))

@app.route("/room/<code>")
def room_page(code):
    if code not in room_store:
        return redirect(url_for('index', error="This room has expired or does not exist."))

    user = get_or_create_user()
    room = room_store[code]
    
    base_url = request.url_root.rstrip("/")
    share_url = f"{base_url}/room/{code}"
    
    return render_template("room.html", 
                           code=code, 
                           files=room["files"], 
                           history=room["history"],
                           my_username=user,
                           share_url=share_url)

@app.route("/room/<code>", methods=["POST"])
def upload_file(code):
    if code not in room_store:
        return redirect(url_for('index'))

    user = get_or_create_user()
    files = request.files.getlist("file")
    
    for file in files:
        if file and file.filename:
            orig_name = file.filename
            # Generate a unique filename for disk
            stored_name = f"{code}_{int(time.time())}_{secure_filename(orig_name)}"
            path = Path(UPLOAD_FOLDER) / stored_name
            file.save(path)
            
            file_data = {
                "original_name": orig_name,
                "stored_name": stored_name,
                "size": get_human_size(path.stat().st_size),
                "type": orig_name.split('.')[-1].upper() if '.' in orig_name else "FILE",
                "sender": user
            }
            
            room_store[code]["files"].append(file_data)
            add_history(code, user, f"sent file: {orig_name}")
            
    return redirect(url_for('room_page', code=code))

@app.route("/download/<code>/<int:index>")
def download_file(code, index):
    if code in room_store and index < len(room_store[code]["files"]):
        user = get_or_create_user()
        file_info = room_store[code]["files"][index]
        
        add_history(code, user, f"downloaded: {file_info['original_name']}")
        
        return send_from_directory(UPLOAD_FOLDER, 
                                   file_info["stored_name"], 
                                   as_attachment=True, 
                                   download_name=file_info["original_name"])
    return "File not found", 404

@app.route("/api/timer/<code>")
def api_timer(code):
    if code not in room_store:
        return jsonify({"expired": True})
    
    now = datetime.now()
    room_ts = room_store[code]["timestamp"]
    elapsed = now - room_ts
    remaining = (timedelta(minutes=ROOM_DURATION_MINS) - elapsed).total_seconds()
    
    return jsonify({
        "expired": remaining <= 0,
        "remaining_seconds": int(max(0, remaining))
    })

# ────────────────────────────────────────────────
#  APP START
# ────────────────────────────────────────────────

if __name__ == "__main__":
    # Ensure standard folders exist
    Path("static").mkdir(exist_ok=True)
    Path("templates").mkdir(exist_ok=True)
    
    # Render provides a PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)