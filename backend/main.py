from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import sqlite3, hashlib, jwt, uuid, os, shutil, json, asyncio, random
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"

app = FastAPI(title="ChatApp API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

security = HTTPBearer()

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("chat.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            content TEXT,
            image_url TEXT,
            type TEXT DEFAULT 'text',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (receiver_id) REFERENCES users(id)
        );
    """)
    db.commit()
    db.close()

init_db()

# ── Auth Helpers ──────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(user_id: str, username: str) -> str:
    payload = {"sub": user_id, "username": username, "exp": datetime.utcnow() + timedelta(days=7)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return decode_token(credentials.credentials)

# ── Models ────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

# ── WebSocket Manager ─────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}  # user_id -> websocket

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active[user_id] = ws

    def disconnect(self, user_id: str):
        self.active.pop(user_id, None)

    async def send_to(self, user_id: str, data: dict):
        ws = self.active.get(user_id)
        if ws:
            try:
                await ws.send_json(data)
            except:
                self.disconnect(user_id)

    def online_users(self):
        return list(self.active.keys())

manager = ConnectionManager()

# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/auth/register")
def register(req: RegisterRequest):
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username=?", (req.username,)).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    user_id = str(uuid.uuid4())
    db.execute("INSERT INTO users (id, username, password) VALUES (?,?,?)",
               (user_id, req.username, hash_password(req.password)))
    db.commit()
    db.close()
    token = create_token(user_id, req.username)
    return {"token": token, "user_id": user_id, "username": req.username}

@app.post("/auth/login")
def login(req: LoginRequest):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=? AND password=?",
                      (req.username, hash_password(req.password))).fetchone()
    db.close()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user["id"], user["username"])
    return {"token": token, "user_id": user["id"], "username": user["username"]}

@app.get("/users")
def get_users(current_user=Depends(get_current_user)):
    db = get_db()
    users = db.execute("SELECT id, username, created_at FROM users WHERE id != ?", (current_user["sub"],)).fetchall()
    db.close()
    online = manager.online_users()
    return [{"id": u["id"], "username": u["username"], "online": u["id"] in online} for u in users]

@app.get("/messages/{other_user_id}")
def get_messages(other_user_id: str, current_user=Depends(get_current_user)):
    db = get_db()
    me = current_user["sub"]
    msgs = db.execute("""
        SELECT m.*, u.username as sender_name FROM messages m
        JOIN users u ON u.id = m.sender_id
        WHERE (m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?)
        ORDER BY m.created_at ASC
    """, (me, other_user_id, other_user_id, me)).fetchall()
    db.close()
    return [dict(m) for m in msgs]

@app.post("/upload")
async def upload_image(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only images allowed")
    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    path = f"uploads/{filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"url": f"/uploads/{filename}"}

@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        payload = decode_token(token)
        user_id = payload["sub"]
        username = payload["username"]
    except:
        await websocket.close(code=1008)
        return

    await manager.connect(user_id, websocket)
    
    # Notify others this user is online
    for uid in manager.online_users():
        if uid != user_id:
            await manager.send_to(uid, {"type": "user_online", "user_id": user_id})

    db = get_db()
    try:
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "message":
                msg_id = str(uuid.uuid4())
                now = datetime.utcnow().isoformat()
                receiver_id = data["receiver_id"]
                content = data.get("content", "")
                image_url = data.get("image_url")
                msg_type = "image" if image_url else "text"

                db.execute(
                    "INSERT INTO messages (id, sender_id, receiver_id, content, image_url, type, created_at) VALUES (?,?,?,?,?,?,?)",
                    (msg_id, user_id, receiver_id, content, image_url, msg_type, now)
                )
                db.commit()

                msg_payload = {
                    "type": "message",
                    "id": msg_id,
                    "sender_id": user_id,
                    "sender_name": username,
                    "receiver_id": receiver_id,
                    "content": content,
                    "image_url": image_url,
                    "msg_type": msg_type,
                    "created_at": now,
                }
                # Send to receiver and back to sender (for confirmation)
                await manager.send_to(receiver_id, msg_payload)
                await manager.send_to(user_id, msg_payload)

                # Auto-reply if receiver is NOT online
                if receiver_id not in manager.active:
                    await asyncio.sleep(1)
                    replies = [
                        "Hi! 👋 How are you?",
                        "Hey there! What's up?",
                        "Hello! Nice to hear from you 😊",
                        "Hi! I'll get back to you soon!",
                        "Hey! Thanks for the message 👍",
                        "Oh hi! Good to see you here!",
                        "Hello! How can I help you?",
                        "Hey, what's going on? 😄",
                    ]
                    # pick a reply based on what was sent
                    msg_lower = content.lower()
                    if any(w in msg_lower for w in ["hi", "hello", "hey", "sup"]):
                        auto_reply = random.choice(["Hey! 👋", "Hi there! 😊", "Hello! How are you?", "Hey, what's up?"])
                    elif any(w in msg_lower for w in ["how are you", "how r u", "how are u"]):
                        auto_reply = random.choice(["I'm doing great, thanks! 😄", "Pretty good! How about you?", "All good here! 👍"])
                    elif any(w in msg_lower for w in ["bye", "goodbye", "cya", "see you"]):
                        auto_reply = random.choice(["Bye! 👋 Take care!", "See you later! 😊", "Goodbye! Have a great day!"])
                    elif any(w in msg_lower for w in ["thanks", "thank you", "thx"]):
                        auto_reply = random.choice(["You're welcome! 😊", "No problem at all!", "Happy to help! 👍"])
                    elif "?" in content:
                        auto_reply = random.choice(["Good question! Let me think... 🤔", "Hmm, not sure about that!", "That's interesting! 😄"])
                    else:
                        auto_reply = random.choice(replies)

                    # get receiver info
                    rec = db.execute("SELECT id, username FROM users WHERE id=?", (receiver_id,)).fetchone()
                    if rec:
                        auto_id = str(uuid.uuid4())
                        auto_now = datetime.utcnow().isoformat()
                        db.execute(
                            "INSERT INTO messages (id, sender_id, receiver_id, content, image_url, type, created_at) VALUES (?,?,?,?,?,?,?)",
                            (auto_id, receiver_id, user_id, auto_reply, None, "text", auto_now)
                        )
                        db.commit()
                        auto_payload = {
                            "type": "message",
                            "id": auto_id,
                            "sender_id": receiver_id,
                            "sender_name": rec["username"],
                            "receiver_id": user_id,
                            "content": auto_reply,
                            "image_url": None,
                            "msg_type": "text",
                            "created_at": auto_now,
                        }
                        await manager.send_to(user_id, auto_payload)

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        db.close()
        for uid in manager.online_users():
            await manager.send_to(uid, {"type": "user_offline", "user_id": user_id})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
