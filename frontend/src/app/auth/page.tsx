"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

export default function AuthPage() {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const submit = async () => {
    if (!username.trim() || !password.trim()) {
      setError("Please fill in all fields.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch(`/auth/${tab}`, {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
      });
      localStorage.setItem("token", data.token);
      localStorage.setItem("me", JSON.stringify({ user_id: data.user_id, username: data.username }));
      router.push("/chat");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">⬡ nexchat</div>
        <div className="auth-subtitle">Real-time messaging, no strings attached.</div>
        <div className="auth-tabs">
          <button className={`auth-tab ${tab === "login" ? "active" : ""}`} onClick={() => setTab("login")}>Sign In</button>
          <button className={`auth-tab ${tab === "register" ? "active" : ""}`} onClick={() => setTab("register")}>Create Account</button>
        </div>
        <div className="field">
          <label>Username</label>
          <input
            type="text" value={username} placeholder="your_username"
            onChange={e => setUsername(e.target.value)}
            onKeyDown={e => e.key === "Enter" && submit()}
          />
        </div>
        <div className="field">
          <label>Password</label>
          <input
            type="password" value={password} placeholder="••••••••"
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && submit()}
          />
        </div>
        <button className="btn-primary" onClick={submit} disabled={loading}>
          {loading ? "Please wait…" : tab === "login" ? "Sign In" : "Create Account"}
        </button>
        {error && <div className="error-msg">{error}</div>}
      </div>
    </div>
  );
}
