# 🟢 CRITICAL: Must be the FIRST lines of the file
import eventlet
eventlet.monkey_patch()

import os
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, make_response, flash
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
        try:
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
                
                # Remove from memory AND Notify users
                for code in expired_rooms:
                    # 🟢 FIX: Notify clients that room is destroyed
                    socketio.emit('room_destroyed', {}, to=code)
                    if code in room_store:
                        del room_store[code]
                        print(f"🧹 Cleanup: Auto-deleted expired room {code}")

            # Delete files from disk (Outside lock to allow other operations)
            for filename in expired_files:
                try:
                    file_path = Path(UPLOAD_FOLDER) / filename
                    if file_path.exists():
                        file_path.unlink()
                except Exception as e:
                    print(f"Error deleting file {filename}: {e}")
                    
        except Exception as e:
            print(f"Error in cleanup loop: {e}")

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
#  MAIN ROUTES
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
    
    # 🟢 FIX: Prevent Browser Caching so timer doesn't reset on reload
    resp = make_response(render_template("room.html",
                         code=code,
                         files=files,
                         history=history,
                         current_user=user,
                         remaining_seconds=max(0, remaining_seconds)))
    
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# ────────────────────────────────────────────────
#  FILE UPLOAD/DOWNLOAD ROUTES
# ────────────────────────────────────────────────

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
#  🆕 NEW: ABOUT & CONTACT ROUTES
# ────────────────────────────────────────────────

@app.route("/about")
def about():
    """About page - Information about the platform and creator"""
    return render_template("about.html")

@app.route("/contact")
def contact():
    """Contact page with form"""
    return render_template("contactus.html")

@app.route("/contact/submit", methods=["POST"])
def contact_submit():
    """Handle contact form submission"""
    # Get form data
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()
    room_code = request.form.get("room_code", "").strip()
    
    # Basic validation
    if not first_name or not email or not subject or not message:
        flash("Please fill in all required fields.", "error")
        return redirect(url_for('contact'))
    
    # Here you would typically:
    # 1. Send an email notification (using smtplib, SendGrid, etc.)
    # 2. Save to database (optional)
    # 3. Log the contact request
    
    # For now, just log and flash success message
    print("\n" + "="*50)
    print("📬 NEW CONTACT FORM SUBMISSION")
    print("="*50)
    print(f"From: {first_name} {last_name}")
    print(f"Email: {email}")
    print(f"Subject: {subject}")
    print(f"Room Code: {room_code if room_code else 'N/A'}")
    print(f"Message: {message}")
    print("="*50 + "\n")
    
    # 🟢 TODO: Implement actual email sending here
    # Example with SendGrid (uncomment and configure):
    # if os.environ.get('SENDGRID_API_KEY'):
    #     send_email_notification(first_name, email, subject, message, room_code)
    
    # Flash success message to user
    flash(f"Thank you {first_name}! Your message has been sent. We'll respond within 24 hours.", "success")
    
    return redirect(url_for('contact'))

# Optional: Email sending function (commented out - implement as needed)
"""
def send_email_notification(name, email, subject, message, room_code):
    '''Send email notification using SendGrid'''
    import sendgrid
    from sendgrid.helpers.mail import Mail
    
    sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))
    
    mail = Mail(
        from_email='noreply@fileportal.onrender.com',
        to_emails='parimalhodar.dev@gmail.com',
        subject=f'Contact Form: {subject}',
        html_content=f'''
        <h2>New Contact Form Submission</h2>
        <p><strong>Name:</strong> {name}</p>
        <p><strong>Email:</strong> {email}</p>
        <p><strong>Subject:</strong> {subject}</p>
        <p><strong>Room Code:</strong> {room_code or 'N/A'}</p>
        <p><strong>Message:</strong></p>
        <p>{message}</p>
        '''
    )
    sg.send(mail)
"""

# ────────────────────────────────────────────────
#  🆕 NEW: SITEMAP.XML ROUTE (For SEO)
# ────────────────────────────────────────────────

@app.route("/sitemap.xml")
def sitemap():
    """Generate sitemap.xml for search engines"""
    # Get current date for lastmod
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Define all your static pages
    pages = [
        {"loc": url_for('index', _external=True), "priority": "1.0"},
        {"loc": url_for('about', _external=True), "priority": "0.8"},
        {"loc": url_for('contact', _external=True), "priority": "0.8"},
    ]
    
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for page in pages:
        sitemap_xml += '  <url>\n'
        sitemap_xml += f'    <loc>{page["loc"]}</loc>\n'
        sitemap_xml += f'    <lastmod>{current_date}</lastmod>\n'
        sitemap_xml += '    <changefreq>daily</changefreq>\n'
        sitemap_xml += f'    <priority>{page["priority"]}</priority>\n'
        sitemap_xml += '  </url>\n'
    
    sitemap_xml += '</urlset>'
    
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response

# ────────────────────────────────────────────────
#  🆕 NEW: ROBOTS.TXT ROUTE (For SEO)
# ────────────────────────────────────────────────

@app.route("/robots.txt")
def robots():
    """Generate robots.txt for search engines"""
    robots_txt = """User-agent: *
Allow: /
Disallow: /room/
Disallow: /destroy/
Disallow: /upload/

Sitemap: """ + url_for('sitemap', _external=True)
    
    response = make_response(robots_txt)
    response.headers["Content-Type"] = "text/plain"
    return response

# ────────────────────────────────────────────────
#  ERROR HANDLERS
# ────────────────────────────────────────────────

@app.errorhandler(404)
def page_not_found(e):
    """Custom 404 page"""
    return render_template("index.html", error="Page not found. Please check the URL."), 404

@app.errorhandler(413)
def too_large(e):
    """File too large error handler"""
    return render_template("index.html", error="File too large. Maximum size is 100MB."), 413

@app.errorhandler(500)
def internal_server_error(e):
    """Custom 500 page"""
    print(f"Server Error: {e}")
    return render_template("index.html", error="Internal server error. Please try again."), 500

# 🟢 NEW: Google Search Console Verification
@app.route('/googlef56d84775932f480.html')
def google_verification():
    """Serve Google verification file"""
    return send_from_directory('static', 'googlef56d84775932f480.html')

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
    print("🚀 FILE TRANSFER ROOM - SERVER STARTING")
    print("="*60)
    print(f"📁 Upload folder: {UPLOAD_FOLDER}")
    print(f"⏱️  Room duration: {ROOM_DURATION_MINS} minutes")
    print(f"📊 Max file size: 100MB")
    print(f"🔗 Local URL: http://127.0.0.1:{port}")
    print(f"🌍 Public URL: http://0.0.0.0:{port}")
    print("="*60)
    print("📄 New Pages Added:")
    print("   • /about - About page")
    print("   • /contact - Contact page")
    print("   • /sitemap.xml - SEO sitemap")
    print("   • /robots.txt - Robots directives")
    print("="*60 + "\n")

    socketio.run(app, host="0.0.0.0", port=port, debug=True)