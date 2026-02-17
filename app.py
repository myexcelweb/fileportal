# 🟢 CRITICAL: Must be the FIRST lines of the file
import eventlet
eventlet.monkey_patch()

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
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB max upload size

# 🟢 CONFIG: Using 'eventlet' for async mode (Required for Render)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

UPLOAD_FOLDER = "uploads"
ROOM_DURATION_MINS = 15

# Ensure upload directory exists
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)

# ────────────────────────────────────────────────
#  IN-MEMORY STORAGE & LOCKING
# ────────────────────────────────────────────────

room_store = {}
# 🟢 LOCK: Prevents crashes when multiple users access/delete rooms simultaneously
room_lock = threading.Lock()

# ────────────────────────────────────────────────
#  UTILITY FUNCTIONS
# ────────────────────────────────────────────────

def generate_code():
    """Generate a unique 6-digit code for the room."""
    with room_lock:
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
    """Add an action to room history (Thread Safe)."""
    with room_lock:
        if code in room_store:
            room_store[code]["history"].append({
                "user": user,
                "action": action,
                "time": datetime.now().strftime("%H:%M:%S")
            })

def cleanup_expired_rooms():
    """Background task to delete expired rooms and their files."""
    while True:
        eventlet.sleep(60)  # Check every minute
        now = datetime.now()
        expired_files = []
        expired_rooms = []
        
        # Identify expired items safely
        with room_lock:
            for code, data in list(room_store.items()):
                if (now - data["timestamp"]) > timedelta(minutes=ROOM_DURATION_MINS):
                    expired_rooms.append(code)
                    for file_info in data["files"]:
                        expired_files.append(file_info["stored_name"])
            
            # Remove from memory
            for code in expired_rooms:
                del room_store[code]

        # Delete files from disk (Outside lock to allow other operations)
        for filename in expired_files:
            try:
                file_path = Path(UPLOAD_FOLDER) / filename
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                print(f"Error deleting file {filename}: {e}")
                
        if expired_rooms:
            print(f"🧹 Cleanup: Removed {len(expired_rooms)} expired rooms.")

# ────────────────────────────────────────────────
#  SOCKET.IO EVENTS
# ────────────────────────────────────────────────

@socketio.on('join')
def handle_join(data):
    code = data.get('code')
    exists = False
    with room_lock:
        exists = code in room_store

    if code and exists:
        join_room(code)
        print(f"User joined room: {code}")

@socketio.on('leave')
def handle_leave(data):
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
    
    with room_lock:
        room_store[code] = {
            "timestamp": datetime.now(),
            "files": [],
            "history": []
        }
    
    user = get_or_create_user()
    add_history(code, user, "created room")
    
    response = make_response(redirect(url_for('room_page', code=code)))
    response.set_cookie('user_id', user, max_age=60*60*24)
    return response

@app.route("/join", methods=["POST"])
def join_existing_room():
    code = request.form.get("code", "").strip()
    
    with room_lock:
        if code not in room_store:
            return render_template("index.html", error="Invalid or expired code")
    
    user = get_or_create_user()
    add_history(code, user, "joined room")
    
    response = make_response(redirect(url_for('room_page', code=code)))
    response.set_cookie('user_id', user, max_age=60*60*24)
    return response

# Handle Direct Join Links (QR Code)
@app.route("/j/<code>")
def join_via_link(code):
    with room_lock:
        if code not in room_store:
            return render_template("index.html", error="Room expired or invalid")
    
    # Create user and log history
    user = get_or_create_user()
    add_history(code, user, "joined via QR/Link")
    
    # Set cookie and redirect
    response = make_response(redirect(url_for('room_page', code=code)))
    response.set_cookie('user_id', user, max_age=60*60*24)
    return response

@app.route("/room/<code>")
def room_page(code):
    with room_lock:
        if code not in room_store:
            return render_template("index.html", error="Room not found or expired")
        
        room_data = room_store[code]
        files = room_data["files"]
        history = room_data["history"]
        timestamp = room_data["timestamp"]

    user = get_or_create_user()
    
    now = datetime.now()
    elapsed = now - timestamp
    remaining = timedelta(minutes=ROOM_DURATION_MINS) - elapsed
    remaining_seconds = int(remaining.total_seconds())
    
    return render_template("room.html",
                         code=code,
                         files=files,
                         history=history,
                         current_user=user,
                         remaining_seconds=max(0, remaining_seconds))

@app.route("/upload/<code>", methods=["POST"])
def upload_file(code):
    with room_lock:
        if code not in room_store:
            return redirect(url_for('index'))

    user = get_or_create_user()
    files = request.files.getlist("file")
    uploaded_files = []
    
    # Process files
    processed_files_data = []
    for file in files:
        if file and file.filename:
            orig_name = file.filename
            stored_name = f"{code}_{int(time.time())}_{secure_filename(orig_name)}"
            path = Path(UPLOAD_FOLDER) / stored_name
            file.save(path)
            
            processed_files_data.append({
                "original_name": orig_name,
                "stored_name": stored_name,
                "size": get_human_size(path.stat().st_size),
                "type": orig_name.split('.')[-1].upper() if '.' in orig_name else "FILE",
                "sender": user
            })

    # Update store safely
    with room_lock:
        if code in room_store:
            current_count = len(room_store[code]["files"])
            for i, f_data in enumerate(processed_files_data):
                f_data["index"] = current_count + i
                room_store[code]["files"].append(f_data)
                uploaded_files.append(f_data)
    
    if uploaded_files:
        add_history(code, user, f"sent {len(uploaded_files)} file(s)")
        socketio.emit('new_files', {
            'files': uploaded_files,
            'sender': user
        }, to=code)
            
    return redirect(url_for('room_page', code=code))

@app.route("/download/<code>/<int:index>")
def download_file(code, index):
    file_info = None
    
    with room_lock:
        if code in room_store and index < len(room_store[code]["files"]):
            file_info = room_store[code]["files"][index]
    
    if file_info:
        user = get_or_create_user()
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
    files_to_zip = []
    
    with room_lock:
        if code not in room_store:
            return "Room not found", 404
        # Create a shallow copy to use outside the lock
        files_to_zip = list(room_store[code]["files"])
    
    if not files_to_zip:
        return "No files to download", 404
    
    user = get_or_create_user()
    memory_file = io.BytesIO()
    
    try:
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_info in files_to_zip:
                file_path = Path(UPLOAD_FOLDER) / file_info["stored_name"]
                if file_path.exists():
                    zf.write(file_path, file_info["original_name"])
    except Exception as e:
        return f"Error creating zip: {str(e)}", 500
    
    memory_file.seek(0)
    add_history(code, user, "downloaded all files")
    
    return (memory_file.getvalue(), 200, {
        'Content-Type': 'application/zip',
        'Content-Disposition': f'attachment; filename=files_{code}.zip'
    })

# 🟢 NEW ROUTE: Immediate Room Destruction (Exit & Delete)
@app.route("/destroy/<code>", methods=["POST"])
def destroy_room(code):
    files_to_delete = []
    
    # 1. Remove from memory safely
    with room_lock:
        if code in room_store:
            # Get list of files to delete from disk
            for file_info in room_store[code]["files"]:
                files_to_delete.append(file_info["stored_name"])
            
            # Delete room data from memory
            del room_store[code]
            print(f"💥 Room {code} destroyed by user.")
    
    # 2. Delete files from disk
    for filename in files_to_delete:
        try:
            file_path = Path(UPLOAD_FOLDER) / filename
            if file_path.exists():
                file_path.unlink() # Deletes the file
        except Exception as e:
            print(f"Error deleting file {filename}: {e}")

    # 3. Notify everyone in the room to leave
    socketio.emit('room_destroyed', {}, to=code)
    
    # 4. Redirect the user who clicked the button to home
    return redirect(url_for('index'))

# ────────────────────────────────────────────────
#  APP START
# ────────────────────────────────────────────────

if __name__ == "__main__":
    # Create necessary folders
    Path("static").mkdir(exist_ok=True)
    Path("templates").mkdir(exist_ok=True)
    Path(UPLOAD_FOLDER).mkdir(exist_ok=True)
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_expired_rooms, daemon=True)
    cleanup_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    
    print("\n" + "="*60)
    print(f"🚀 Server is running! Open this URL in your browser:")
    print(f"🔗 http://127.0.0.1:{port}")
    print("="*60 + "\n")

    socketio.run(app, host="0.0.0.0", port=port, debug=True)