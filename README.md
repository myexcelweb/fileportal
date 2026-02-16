# 📁 Real-Time File Transfer Application

A modern, secure file transfer application with **real-time updates**, auto-delete functionality, and support for multiple file uploads. Files appear instantly on all connected devices without page refresh!

## ✨ Features

### 🚀 Real-Time Updates (NEW!)
- **Instant File Visibility**: When someone uploads a file, all users in the room see it immediately without refreshing
- **Live Notifications**: Get notified when files are uploaded or downloaded
- **Real-Time Activity**: See file transfers happening live

### 📤 File Transfer
- **Multiple File Upload**: Upload multiple files at once (up to 100MB total)
- **Auto-Delete**: Files automatically delete after 15 minutes
- **Individual & Bulk Download**: Download files individually or all at once as a ZIP
- **File Information**: View file names, types, and sizes

### 🔐 Security & Privacy
- **Secure Codes**: 6-digit codes for secure file sharing
- **Room Isolation**: Each room is completely separate
- **Auto-Expiration**: Rooms and files auto-delete after 15 minutes

## 🔧 How Real-Time Updates Work

The app uses **Socket.IO** (WebSockets) to enable real-time communication:

1. **User A** uploads a file → Server receives it
2. **Server** saves file and broadcasts to all users in the room
3. **User B, C, D...** instantly see the new file appear on their screen
4. **No refresh needed** - everything happens automatically!

## 🚀 Quick Start

### Local Development

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application**:
   ```bash
   python app.py
   ```

3. **Access**: Open `http://localhost:5000`

### Test Real-Time Features

1. Open the app in **two different browser windows** (or devices)
2. Create a room in Window 1
3. Join the same room in Window 2 using the code
4. Upload a file in Window 1
5. **Watch it appear instantly in Window 2!** ✨

## 🌐 Deploy to Render

### Important Start Command

For WebSocket support, use this start command:
```bash
gunicorn --worker-class eventlet -w 1 app:app
```

**Note**: `-w 1` (single worker) is required for Socket.IO with in-memory storage.

### Full Deployment Steps

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Real-time file transfer app"
   git push origin main
   ```

2. **Deploy on Render**:
   - Go to [Render Dashboard](https://dashboard.render.com/)
   - New Web Service → Connect your repo
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn --worker-class eventlet -w 1 app:app`
   - Deploy!

## 📦 Dependencies

```
Flask==3.0.0
gunicorn==21.2.0
flask-socketio==5.3.6
python-socketio==5.11.0
eventlet==0.35.2
```

## 🎯 Use Cases

- **Quick File Sharing**: Share files with colleagues without email
- **Temporary Transfers**: Send files that auto-delete for privacy
- **Collaborative Work**: Multiple people can upload/download files simultaneously
- **Mobile-to-Desktop**: Easy file transfer between your devices

## 🔒 Security Notes

1. **Room Codes**: 6-digit codes provide basic security
2. **Auto-Expiration**: Files and rooms delete after 15 minutes
3. **WebSocket Security**: Uses secure WebSocket (WSS) in production

## 🐛 Troubleshooting

### Real-Time Updates Not Working
- Ensure Socket.IO client library is loaded
- Verify Gunicorn uses eventlet worker: `--worker-class eventlet`
- Check firewall isn't blocking WebSocket connections

### Files Not Uploading
- Check total file size < 100MB
- Ensure `uploads/` directory exists

## 📄 License

MIT License - feel free to use for any project!
