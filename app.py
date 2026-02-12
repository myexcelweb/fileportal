from flask import Flask, render_template, request, send_from_directory, jsonify, url_for
import os
import random
import string
from datetime import datetime, timedelta
import threading
import time
import zipfile
from io import BytesIO

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB limit

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Get base URL for sharing
def get_base_url():
    """Get the base URL for the application"""
    # In production, you should set SERVER_NAME in config
    # For now, we'll try to detect it from the request
    return request.url_root.rstrip('/')

# Enhanced file store: code -> {files: [{filename, original_name, size, type}], timestamp}
file_store = {}

def generate_code():
    return ''.join(random.choices(string.digits, k=6))


def get_file_size(size_bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_file_type(filename):
    """Get file extension/type"""
    return os.path.splitext(filename)[1][1:].upper() or 'FILE'


def cleanup_old_files():
    """Background task to delete files older than 15 minutes"""
    while True:
        try:
            current_time = datetime.now()
            codes_to_delete = []
            
            for code, data in file_store.items():
                timestamp = data.get('timestamp')
                if timestamp and (current_time - timestamp) > timedelta(minutes=15):
                    # Delete all files associated with this code
                    for file_info in data.get('files', []):
                        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file_info['filename'])
                        try:
                            if os.path.exists(filepath):
                                os.remove(filepath)
                                print(f"Deleted: {filepath}")
                        except Exception as e:
                            print(f"Error deleting {filepath}: {e}")
                    codes_to_delete.append(code)
            
            # Remove codes from store
            for code in codes_to_delete:
                del file_store[code]
                print(f"Removed code: {code}")
                
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        time.sleep(60)  # Check every minute


# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            files = request.files.getlist("file")
            
            if not files or all(not f.filename for f in files):
                return render_template("index.html", error="No files selected")
            
            code = generate_code()
            uploaded_files = []
            total_size = 0
            
            for file in files:
                if file and file.filename:
                    original_name = str(file.filename)
                    file_size = 0
                    
                    # Save file and get size
                    filename = f"{code}_{original_name}"
                    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(filepath)
                    file_size = os.path.getsize(filepath)
                    total_size += file_size
                    
                    # Check total size doesn't exceed 100MB
                    if total_size > 100 * 1024 * 1024:
                        # Delete all uploaded files for this code
                        for uf in uploaded_files:
                            try:
                                os.remove(os.path.join(app.config["UPLOAD_FOLDER"], uf['filename']))
                            except:
                                pass
                        return render_template("index.html", error="Total file size exceeds 100MB limit")
                    
                    uploaded_files.append({
                        'filename': filename,
                        'original_name': original_name,
                        'size': get_file_size(file_size),
                        'type': get_file_type(original_name)
                    })
            
            if uploaded_files:
                file_store[code] = {
                    'files': uploaded_files,
                    'timestamp': datetime.now()
                }
                
                # Generate share URL
                base_url = get_base_url()
                share_url = f"{base_url}/d/{code}"
                
                return render_template("index.html", code=code, files=uploaded_files, share_url=share_url)
        except Exception as e:
            print(f"Upload error: {e}")
            return render_template("index.html", error=f"Upload failed: {str(e)}")
    
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def download():
    code = request.form.get("code")
    
    if code and code in file_store:
        data = file_store[code]
        files = data.get('files', [])
        timestamp = data.get('timestamp')
        
        # Calculate time remaining
        time_remaining = None
        if timestamp:
            elapsed = datetime.now() - timestamp
            remaining = timedelta(minutes=15) - elapsed
            if remaining.total_seconds() > 0:
                minutes = int(remaining.total_seconds() // 60)
                seconds = int(remaining.total_seconds() % 60)
                time_remaining = f"{minutes}m {seconds}s"
        
        # Generate share URL
        base_url = get_base_url()
        share_url = f"{base_url}/d/{code}"
        
        return render_template("download.html", code=code, files=files, 
                             time_remaining=time_remaining, share_url=share_url)
    else:
        return render_template("download.html", error="Invalid or expired code")


@app.route("/d/<code>")
def direct_download(code):
    """Direct download page accessed via shareable URL"""
    if code and code in file_store:
        data = file_store[code]
        files = data.get('files', [])
        timestamp = data.get('timestamp')
        
        # Calculate time remaining
        time_remaining = None
        if timestamp:
            elapsed = datetime.now() - timestamp
            remaining = timedelta(minutes=15) - elapsed
            if remaining.total_seconds() > 0:
                minutes = int(remaining.total_seconds() // 60)
                seconds = int(remaining.total_seconds() % 60)
                time_remaining = f"{minutes}m {seconds}s"
        
        # Generate share URL
        base_url = get_base_url()
        share_url = f"{base_url}/d/{code}"
        
        return render_template("download.html", code=code, files=files, 
                             time_remaining=time_remaining, share_url=share_url)
    else:
        return render_template("download.html", error="Invalid or expired code")


@app.route("/get_file/<code>/<int:index>")
def get_file(code, index):
    """Download a single file"""
    if code in file_store:
        files = file_store[code].get('files', [])
        if 0 <= index < len(files):
            filename = files[index]['filename']
            original_name = files[index]['original_name']
            return send_from_directory(
                app.config["UPLOAD_FOLDER"], 
                filename, 
                as_attachment=True,
                download_name=original_name
            )
    return "File not found!", 404


@app.route("/get_all_files/<code>")
def get_all_files(code):
    """Download all files as a ZIP"""
    if code not in file_store:
        return "Files not found!", 404
    
    files = file_store[code].get('files', [])
    
    if len(files) == 1:
        # If only one file, download it directly
        filename = files[0]['filename']
        original_name = files[0]['original_name']
        return send_from_directory(
            app.config["UPLOAD_FOLDER"], 
            filename, 
            as_attachment=True,
            download_name=original_name
        )
    
    # Create ZIP file in memory
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_info in files:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], file_info['filename'])
            if os.path.exists(filepath):
                zf.write(filepath, file_info['original_name'])
    
    memory_file.seek(0)
    
    return send_from_directory(
        directory=app.config["UPLOAD_FOLDER"],
        path='',
        as_attachment=True,
        download_name=f'files_{code}.zip',
        mimetype='application/zip'
    ), 200, {
        'Content-Disposition': f'attachment; filename=files_{code}.zip',
        'Content-Type': 'application/zip',
    }


@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve static files"""
    return send_from_directory('static', filename)


# Render compatible run
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)