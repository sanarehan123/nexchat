export const API_BASE = "https://nexchat-production-4082.up.railway.app";
export const WS_BASE = "wss://nexchat-production-4082.up.railway.app";

export interface User {
  id: string;
  username: string;
  online: boolean;
}

export interface Message {
  id: string;
  sender_id: string;
  sender_name: string;
  receiver_id: string;
  content: string;
  image_url?: string;
  msg_type: "text" | "image";
  created_at: string;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function getMe(): { user_id: string; username: string } | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("me");
  return raw ? JSON.parse(raw) : null;
}

export async function apiFetch(path: string, options: RequestInit = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error" }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}
