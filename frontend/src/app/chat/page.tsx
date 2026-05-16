"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, getMe, getToken, API_BASE } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { User, Message } from "@/lib/api";

export default function ChatPage() {
  const router = useRouter();
  const me = getMe();
  const [users, setUsers] = useState<User[]>([]);
  const [activeUser, setActiveUser] = useState<User | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!getToken()) { router.replace("/auth"); return; }
    loadUsers();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadUsers = async () => {
    try {
      const data = await apiFetch("/users");
      setUsers(data);
    } catch {}
  };

  const loadMessages = async (userId: string) => {
    try {
      const data = await apiFetch(`/messages/${userId}`);
      setMessages(data);
    } catch {}
  };

  const selectUser = (user: User) => {
    setActiveUser(user);
    loadMessages(user.id);
  };

  const { send } = useWebSocket(useCallback((event) => {
    if (event.type === "message") {
      const msg = event.payload;
      // Add to messages if it's part of active conversation
      setActiveUser(current => {
        if (current && (msg.sender_id === current.id || msg.receiver_id === current.id)) {
          setMessages(prev => {
            const exists = prev.find(m => m.id === msg.id);
            if (exists) return prev;
            return [...prev, msg];
          });
        }
        return current;
      });
    } else if (event.type === "user_online") {
      setUsers(prev => prev.map(u => u.id === event.user_id ? { ...u, online: true } : u));
      setActiveUser(prev => prev && prev.id === event.user_id ? { ...prev, online: true } : prev);
    } else if (event.type === "user_offline") {
      setUsers(prev => prev.map(u => u.id === event.user_id ? { ...u, online: false } : u));
      setActiveUser(prev => prev && prev.id === event.user_id ? { ...prev, online: false } : prev);
    }
  }, []));

  const sendMessage = () => {
    if (!text.trim() || !activeUser) return;
    send({ type: "message", receiver_id: activeUser.id, content: text.trim() });
    setText("");
  };

  const sendImage = async (file: File) => {
    if (!activeUser) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const token = getToken();
      const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const data = await res.json();
      send({ type: "message", receiver_id: activeUser.id, content: "", image_url: `${API_BASE}${data.url}` });
    } catch {}
    setUploading(false);
  };

  const logout = () => {
    localStorage.clear();
    router.replace("/auth");
  };

  const initials = (name: string) => name.slice(0, 2).toUpperCase();
  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="chat-layout">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <div>
            <div className="sidebar-logo">⬡ nexchat</div>
            <div className="sidebar-me">@{me?.username}</div>
          </div>
          <button className="btn-logout" onClick={logout}>Logout</button>
        </div>
        <div className="sidebar-section-label">People</div>
        <div className="user-list">
          {users.length === 0 && (
            <div style={{ padding: "20px", color: "var(--text3)", fontSize: "13px" }}>
              No other users yet. Share the app!
            </div>
          )}
          {users.map(user => (
            <div key={user.id} className={`user-item ${activeUser?.id === user.id ? "active" : ""}`}
              onClick={() => selectUser(user)}>
              <div className="avatar">
                {initials(user.username)}
                {user.online && <div className="online-dot" />}
              </div>
              <div className="user-info">
                <div className="user-name">{user.username}</div>
                <div className={`user-status ${user.online ? "online" : ""}`}>
                  {user.online ? "● Online" : "Offline"}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Chat Window */}
      <div className="chat-window">
        {!activeUser ? (
          <div className="empty-state">
            <div className="icon">💬</div>
            <p>Select someone to start chatting</p>
          </div>
        ) : (
          <>
            <div className="chat-header">
              <div className="avatar" style={{ width: 40, height: 40 }}>
                {initials(activeUser.username)}
                {activeUser.online && <div className="online-dot" />}
              </div>
              <div className="chat-header-info">
                <div className="chat-header-name">{activeUser.username}</div>
                <div className={`chat-header-status ${activeUser.online ? "online" : ""}`}>
                  {activeUser.online ? "● Online now" : "Offline"}
                </div>
              </div>
            </div>

            <div className="messages-area">
              {messages.length === 0 && (
                <div style={{ margin: "auto", color: "var(--text3)", fontSize: "13px", textAlign: "center" }}>
                  No messages yet. Say hello! 👋
                </div>
              )}
              {messages.map(msg => {
                const isMe = msg.sender_id === me?.user_id;
                return (
                  <div key={msg.id} className={`msg-row ${isMe ? "me" : "them"}`}>
                    {!isMe && (
                      <div className="msg-avatar">{initials(msg.sender_name)}</div>
                    )}
                    <div className="bubble">
                      {msg.msg_type === "image" && msg.image_url ? (
                        <img src={msg.image_url} alt="Shared image" />
                      ) : (
                        msg.content
                      )}
                    </div>
                    <div className="msg-time">{formatTime(msg.created_at)}</div>
                  </div>
                );
              })}
              <div ref={bottomRef} />
            </div>

            <div className="input-bar">
              <input
                type="text"
                placeholder={`Message ${activeUser.username}…`}
                value={text}
                onChange={e => setText(e.target.value)}
                onKeyDown={e => e.key === "Enter" && sendMessage()}
              />
              {uploading && <span className="uploading-badge">Uploading…</span>}
              <button className="btn-icon" title="Send image" onClick={() => fileRef.current?.click()}>
                📷
              </button>
              <input
                ref={fileRef} type="file" accept="image/*" style={{ display: "none" }}
                onChange={e => e.target.files?.[0] && sendImage(e.target.files[0])}
              />
              <button className="btn-send" onClick={sendMessage} disabled={!text.trim()}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M22 2L11 13M22 2L15 22 11 13 2 9l20-7z"/>
                </svg>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
