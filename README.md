# 📁 File Transfer Application

A modern, secure file transfer application with auto-delete functionality and support for multiple file uploads.

## ✨ Features

- **Multiple File Upload**: Upload multiple files at once (up to 100MB total)
- **Auto-Delete**: Files automatically delete after 15 minutes
- **Individual & Bulk Download**: Download files individually or all at once as a ZIP
- **File Information**: View file names, types, and sizes
- **Mobile Optimized**: Perfect mobile viewing experience
- **Secure Codes**: 6-digit codes for secure file sharing
- **Real-time Timer**: Shows time remaining before files expire

## 🚀 Deploy to Render

### Method 1: Direct GitHub Deployment

1. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin YOUR_GITHUB_REPO_URL
   git push -u origin main
   ```

2. **Deploy on Render**:
   - Go to [Render Dashboard](https://dashboard.render.com/)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Configure:
     - **Name**: file-transfer-app (or your choice)
     - **Environment**: Python 3
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app`
     - **Instance Type**: Free (or paid for better performance)
   - Click "Create Web Service"

### Method 2: Manual Deployment

1. **Create Render Account**: Sign up at [render.com](https://render.com)

2. **Create New Web Service**:
   - Click "New +" → "Web Service"
   - Choose "Build and deploy from a Git repository"
   - Connect your GitHub account and select repository

3. **Configure Settings**:
   ```
   Name: file-transfer-app
   Region: Choose closest to your users
   Branch: main
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app
   ```

4. **Environment Variables** (Optional):
   - `PORT`: Auto-set by Render
   - Add any custom environment variables if needed

5. **Deploy**: Click "Create Web Service"

## 📦 Local Development

1. **Clone the repository**:
   ```bash
   git clone YOUR_REPO_URL
   cd file-transfer-app
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python app.py
   ```

5. **Access**: Open browser to `http://localhost:5000`

## 📁 Project Structure

```
file-transfer-app/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .gitignore            # Git ignore rules
├── static/
│   └── style.css         # Styling
├── templates/
│   ├── index.html        # Upload page
│   └── download.html     # Download page
└── uploads/              # Temporary file storage (auto-created)
```

## 🔧 Configuration

### File Size Limit
Change in `app.py`:
```python
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB
```

### Auto-Delete Timer
Change in `app.py`:
```python
if (current_time - timestamp) > timedelta(minutes=15):  # Change 15 to desired minutes
```

## 🛠️ Technical Details

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Server**: Gunicorn (production)
- **Auto-cleanup**: Background thread removes old files
- **Storage**: In-memory code storage + file system

## 📱 Mobile Support

Fully responsive design optimized for:
- Mobile phones (320px+)
- Tablets (600px+)
- Desktop (1200px+)

## 🔒 Security Features

- File size validation
- Code expiration (15 minutes)
- Secure file naming
- Input validation

## ⚠️ Important Notes

1. **Persistence**: On Render's free tier, the file system is ephemeral. Files may be deleted on service restart.
2. **Scaling**: For production use, consider:
   - Using object storage (AWS S3, Cloudinary)
   - Database for code storage (PostgreSQL, Redis)
   - Increased instance specs

## 🐛 Troubleshooting

### Files not uploading
- Check total file size < 100MB
- Ensure `uploads/` directory exists

### Auto-delete not working
- Background cleanup thread runs every minute
- Check server logs for errors

### Deployment issues
- Verify `requirements.txt` is correct
- Ensure `gunicorn` is installed
- Check Render logs for errors

## 📄 License

MIT License - feel free to use for any project!

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a pull request.

## 📧 Support

For issues or questions, please open a GitHub issue.
