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
                if receiver_id not in manager.active and content.strip():
                    await asyncio.sleep(1)
                    rec = db.execute("SELECT id, username FROM users WHERE id=?", (receiver_id,)).fetchone()
                    if rec:
                        m = content.lower().strip()

                        if any(w in m for w in ["hi", "hello", "hey", "hiya", "sup", "wassup", "howdy"]):
                            auto_reply = random.choice(["Hey! 👋 So good to hear from you!", "Hi there! 😊 How's your day going?", "Hello! Great to see you! 🌟", "Hey hey! What's up? 😄"])
                        elif any(w in m for w in ["how are you", "how r u", "how are u", "hows it going", "how's it going", "u ok", "you ok"]):
                            auto_reply = random.choice(["I'm doing really well, thanks for asking! 😊 How about you?", "Pretty great! Just been keeping busy 😄 What about you?", "All good here! 💙 How are you doing?"])
                        elif any(w in m for w in ["bye", "goodbye", "cya", "see you", "see ya", "later", "gotta go", "ttyl"]):
                            auto_reply = random.choice(["Bye! 👋 Take care of yourself!", "See you later! 😊 It was great chatting!", "Goodbye! Have an amazing day! 🌟", "Catch you later! 💙"])
                        elif any(w in m for w in ["thanks", "thank you", "thx", "ty", "appreciate"]):
                            auto_reply = random.choice(["You're so welcome! 😊", "Anytime! That's what friends are for 💙", "Of course! Happy to help! 🌟", "No problem at all! 😄"])
                        elif any(w in m for w in ["sorry", "my bad", "apolog", "forgive"]):
                            auto_reply = random.choice(["No worries at all! 😊", "It's totally fine, don't worry about it! 💙", "All good! We're cool 😄"])
                        elif any(w in m for w in ["sad", "upset", "depressed", "unhappy", "crying", "cry", "miss"]):
                            auto_reply = random.choice(["Aww, I'm sorry to hear that 💙 I'm here for you!", "That's tough. You're stronger than you think! 💪", "Sending you a big hug! 🤗 Things will get better!"])
                        elif any(w in m for w in ["happy", "great", "awesome", "amazing", "wonderful", "excited", "fantastic"]):
                            auto_reply = random.choice(["That's amazing!! I'm so happy for you! 🎉", "Yay!! That's so great to hear! 😄🌟", "Love that energy!! Keep it up! 💪✨"])
                        elif any(w in m for w in ["help", "advice", "what should", "what do you think", "opinion"]):
                            auto_reply = random.choice(["I'd love to help! Tell me more about it 😊", "Of course! What's going on? I'm all ears 💙", "Sure thing! Give me the details and we'll figure it out together 🌟"])
                        elif any(w in m for w in ["work", "job", "office", "boss", "meeting", "deadline"]):
                            auto_reply = random.choice(["Work stuff can be tough sometimes! Hope it's going okay 😊", "Hang in there! You've totally got this 💪", "Ugh, work stress is real! Take it one step at a time 💙"])
                        elif any(w in m for w in ["food", "eat", "hungry", "lunch", "dinner", "breakfast", "cook"]):
                            auto_reply = random.choice(["Ooh, food talk! 😄 What are you having?", "Yum! That sounds delicious 🍕 I love food chats!", "Oh nooo now I'm hungry too 😂 What's the plan?"])
                        elif any(w in m for w in ["sleep", "tired", "exhausted", "sleepy", "nap", "rest"]):
                            auto_reply = random.choice(["Get some rest! You deserve it 😴💙", "Take care of yourself! Sleep is so important 🌙", "Aww, hope you feel refreshed soon! 💤"])
                        elif any(w in m for w in ["love", "like", "crush", "relationship", "date", "boyfriend", "girlfriend"]):
                            auto_reply = random.choice(["Ooh tell me more! 👀😄", "That's so sweet! 💕 How are things going?", "Aww! 😊 That sounds really nice!"])
                        elif any(w in m for w in ["funny", "lol", "haha", "lmao", "hilarious", "joke"]):
                            auto_reply = random.choice(["Haha I love that! 😂", "LOL!! You're so funny 😄", "Hahaha that made my day! 😂💙"])
                        elif any(w in m for w in ["hot", "heat", "garam", "garmi", "sweating", "sweat", "humid", "weather", "karachi", "temperature", "ac", "fan", "load shedding", "loadshedding"]):
                            auto_reply = random.choice([
                                "Bro this Karachi heat is NO JOKE 🥵 I'm literally melting!",
                                "Don't even get me started on this weather 😩 It's like living inside an oven!",
                                "Karachi in May is just... suffering 😭🔥 Stay hydrated please!",
                                "The heat + load shedding combo is absolutely brutal 😤 How are you surviving?",
                                "I swear the AC is running 24/7 and it's still not enough 😂🥵",
                                "This heat is unreal yaar 🔥 40+ degrees and no mercy!",
                                "Karachi weather right now: step outside for 2 minutes, become a puddle 😭",
                                "Bro same!! I haven't gone outside without sweating through my clothes 😩🌡️",
                                "The humidity makes it 10x worse 😤 At least give us a breeze Karachi!",
                                "Real talk, this is the hottest it has felt in years 🥵 Stay inside if you can!",
                            ])
                        elif "?" in content:
                            auto_reply = random.choice(["Hmm, that's a really good question! 🤔", "Ooh interesting! Let me think about that 😄", "Great question! What do you think? 😊", "I'm not sure but I'd love to figure it out with you! 💙"])
                        elif any(w in m for w in ["ok", "okay", "alright", "sure", "fine", "got it", "i see"]):
                            auto_reply = random.choice(["Sounds good! 😊", "Perfect! 👍", "Great! Let me know if you need anything 💙", "Cool cool! 😄"])
                        else:
                            auto_reply = random.choice([
                                "That's really interesting! Tell me more 😊",
                                "I totally get what you mean! 💙",
                                "Oh wow, really? That's so cool! 😄",
                                "You always have the best things to say! 🌟",
                                "Haha yeah I feel you! 😄",
                                "Aww I'm always here for you! 💙",
                                "That's so true! Couldn't agree more 😊",
                                "No way!! That's wild 😂",
                                "Ugh I know right! 😄",
                                "You're the best, you know that? 🌟",
                            ])

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
