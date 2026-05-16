# ⬡ NexChat — Real-Time Chat App

A full-stack real-time chat app built with **Python FastAPI** (backend) and **Next.js + TypeScript** (frontend). No Firebase, no subscriptions, completely free.

## ✅ Features
- 🔐 User Authentication (Register / Login with JWT)
- 💬 One-to-One Real-Time Chat (WebSockets)
- 📷 Image Sharing
- 🔔 Browser Push Notifications
- 🟢 Online/Offline Presence Indicators
- 🔄 Auto-reconnect on disconnect

## 📋 Requirements
- Python 3.8+
- Node.js 18+
- npm

## 🚀 Quick Start

### 1. Setup (run once)
```bash
chmod +x setup.sh start.sh
./setup.sh
```

### 2. Start the app
```bash
./start.sh
```

### 3. Open in browser
Go to **http://localhost:3000**

> Open in **two different browser windows** (or use incognito for the second user) to test real-time chat between two accounts.

## 📁 Project Structure
```
chatapp/
├── backend/
│   ├── main.py          # FastAPI app (API + WebSockets)
│   ├── requirements.txt
│   └── uploads/         # Uploaded images stored here
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── auth/    # Login & Register page
│   │   │   └── chat/    # Main chat page
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts  # WebSocket + notifications
│   │   └── lib/
│   │       └── api.ts   # API helpers & types
│   └── package.json
├── setup.sh
└── start.sh
```

## 🛠️ Tech Stack
| Layer | Technology |
|-------|-----------|
| Backend | Python + FastAPI |
| Real-time | WebSockets (built into FastAPI) |
| Database | SQLite (zero config) |
| Auth | JWT tokens |
| Frontend | Next.js 14 + TypeScript |
| Notifications | Web Push API (browser built-in) |
| Images | Local file storage |

## 🔧 Troubleshooting
- **Port in use?** Kill existing processes: `lsof -ti:8000 | xargs kill` and `lsof -ti:3000 | xargs kill`
- **Notifications not working?** Allow notifications when the browser prompts you
- **CORS errors?** Make sure backend is running on port 8000
