import os
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, make_response
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import zipfile
import io

# ────────────────────────────────────────────────
#  APP & SOCKET.IO CONFIGURATION
# ────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "your-secret-key-here-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB max

# Initialize Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

UPLOAD_FOLDER = "uploads"
ROOM_DURATION_MINS = 15

Path(UPLOAD_FOLDER).mkdir(exist_ok=True)

# ────────────────────────────────────────────────
#  IN-MEMORY STORAGE
# ────────────────────────────────────────────────

room_store = {}

# ────────────────────────────────────────────────
#  UTILITY FUNCTIONS
# ────────────────────────────────────────────────

def generate_code():
    """Generate a unique 6-digit code for the room."""
    while True:
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        if code not in room_store:
            return code

def get_human_size(bytes_size):
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"

def get_or_create_user():
    """Get user ID from cookie or create a new one."""
    user_id = request.cookies.get('user_id')
    if not user_id:
        user_id = f"user_{int(time.time())}_{random.randint(1000, 9999)}"
    return user_id

def add_history(code, user, action):
    """Add an action to room history."""
    if code in room_store:
        room_store[code]["history"].append({
            "user": user,
            "action": action,
            "time": datetime.now().strftime("%H:%M:%S")
        })

def cleanup_expired_rooms():
    """Background task to delete expired rooms and their files."""
    while True:
        time.sleep(60)  # Run every minute
        now = datetime.now()
        expired = []
        
        for code, data in list(room_store.items()):
            if (now - data["timestamp"]) > timedelta(minutes=ROOM_DURATION_MINS):
                expired.append(code)
                for file_info in data["files"]:
                    file_path = Path(UPLOAD_FOLDER) / file_info["stored_name"]
                    if file_path.exists():
                        file_path.unlink()
                
        for code in expired:
            del room_store[code]

# ────────────────────────────────────────────────
#  SOCKET.IO EVENTS (Real-time updates)
# ────────────────────────────────────────────────

@socketio.on('join')
def handle_join(data):
    """Handle user joining a room."""
    code = data.get('code')
    if code and code in room_store:
        join_room(code)
        print(f"User joined room: {code}")

@socketio.on('leave')
def handle_leave(data):
    """Handle user leaving a room."""
    code = data.get('code')
    if code:
        leave_room(code)
        print(f"User left room: {code}")

# ────────────────────────────────────────────────
#  ROUTES
# ────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/create", methods=["POST"])
def create_room():
    code = generate_code()
    print(f"✓ Creating room with code: {code}")
    
    room_store[code] = {
        "timestamp": datetime.now(),
        "files": [],
        "history": []
    }
    user = get_or_create_user()
    add_history(code, user, "created room")
    
    print(f"✓ Room {code} created successfully")
    print(f"✓ Redirecting to /room/{code}")
    
    response = make_response(redirect(url_for('room_page', code=code)))
    response.set_cookie('user_id', user, max_age=60*60*24)
    return response

@app.route("/join", methods=["POST"])
def join_existing_room():
    code = request.form.get("code", "").strip()
    
    print(f"Attempting to join room: {code}")
    print(f"Available rooms: {list(room_store.keys())}")
    
    if code not in room_store:
        return render_template("index.html", error="Invalid or expired code")
    
    user = get_or_create_user()
    add_history(code, user, "joined room")
    
    response = make_response(redirect(url_for('room_page', code=code)))
    response.set_cookie('user_id', user, max_age=60*60*24)
    return response

@app.route("/room/<code>")
def room_page(code):
    print(f"→ Accessing room page for: {code}")
    print(f"→ Room exists: {code in room_store}")
    
    if code not in room_store:
        print(f"✗ Room {code} not found!")
        return render_template("index.html", error="Room not found or expired")
    
    user = get_or_create_user()
    room_data = room_store[code]
    
    now = datetime.now()
    elapsed = now - room_data["timestamp"]
    remaining = timedelta(minutes=ROOM_DURATION_MINS) - elapsed
    remaining_seconds = int(remaining.total_seconds())
    
    print(f"✓ Rendering room {code} successfully")
    
    return render_template("room.html",
                         code=code,
                         files=room_data["files"],
                         history=room_data["history"],
                         current_user=user,
                         remaining_seconds=max(0, remaining_seconds))

@app.route("/upload/<code>", methods=["POST"])
def upload_file(code):
    if code not in room_store:
        return redirect(url_for('index'))

    user = get_or_create_user()
    files = request.files.getlist("file")
    uploaded_files = []
    
    for file in files:
        if file and file.filename:
            orig_name = file.filename
            stored_name = f"{code}_{int(time.time())}_{secure_filename(orig_name)}"
            path = Path(UPLOAD_FOLDER) / stored_name
            file.save(path)
            
            file_data = {
                "original_name": orig_name,
                "stored_name": stored_name,
                "size": get_human_size(path.stat().st_size),
                "type": orig_name.split('.')[-1].upper() if '.' in orig_name else "FILE",
                "sender": user,
                "index": len(room_store[code]["files"])
            }
            
            room_store[code]["files"].append(file_data)
            uploaded_files.append(file_data)
            add_history(code, user, f"sent file: {orig_name}")
    
    # Emit real-time update to all users in the room
    if uploaded_files:
        print(f"📤 Broadcasting {len(uploaded_files)} new file(s) to room {code}")
        socketio.emit('new_files', {
            'files': uploaded_files,
            'sender': user
        }, to=code)
            
    return redirect(url_for('room_page', code=code))

@app.route("/download/<code>/<int:index>")
def download_file(code, index):
    if code in room_store and index < len(room_store[code]["files"]):
        user = get_or_create_user()
        file_info = room_store[code]["files"][index]
        
        add_history(code, user, f"downloaded: {file_info['original_name']}")
        
        socketio.emit('file_downloaded', {
            'filename': file_info['original_name'],
            'user': user
        }, to=code)
        
        return send_from_directory(UPLOAD_FOLDER, 
                                   file_info["stored_name"], 
                                   as_attachment=True, 
                                   download_name=file_info["original_name"])
    return "File not found", 404

@app.route("/download_all/<code>")
def download_all(code):
    if code not in room_store:
        return "Room not found", 404
    
    user = get_or_create_user()
    files = room_store[code]["files"]
    
    if not files:
        return "No files to download", 404
    
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_info in files:
            file_path = Path(UPLOAD_FOLDER) / file_info["stored_name"]
            if file_path.exists():
                zf.write(file_path, file_info["original_name"])
    
    memory_file.seek(0)
    add_history(code, user, "downloaded all files")
    
    return (memory_file.getvalue(), 200, {
        'Content-Type': 'application/zip',
        'Content-Disposition': f'attachment; filename=files_{code}.zip'
    })

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
    Path("static").mkdir(exist_ok=True)
    Path("templates").mkdir(exist_ok=True)
    Path(UPLOAD_FOLDER).mkdir(exist_ok=True)
    
    print("\n" + "=" * 60)
    print("  FILE TRANSFER APP - Real-Time Edition")
    print("=" * 60)
    print(f"📁 Templates: {Path('templates').absolute()}")
    print(f"🎨 Static: {Path('static').absolute()}")
    print(f"📤 Uploads: {Path('uploads').absolute()}")
    print("=" * 60)
    print("🚀 Server starting...")
    print("=" * 60 + "\n")
    
    cleanup_thread = threading.Thread(target=cleanup_expired_rooms, daemon=True)
    cleanup_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)