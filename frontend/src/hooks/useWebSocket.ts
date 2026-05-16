"use client";
import { useEffect, useRef, useCallback } from "react";
import { WS_BASE, getToken, getMe } from "@/lib/api";
import type { Message } from "@/lib/api";

type WSEvent =
  | { type: "message"; payload: Message }
  | { type: "user_online"; user_id: string }
  | { type: "user_offline"; user_id: string };

export function useWebSocket(onEvent: (e: WSEvent) => void) {
  const ws = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) return;

    const socket = new WebSocket(`${WS_BASE}/ws/${token}`);
    ws.current = socket;

    socket.onmessage = (e) => {
      const data = JSON.parse(e.data);
      const me = getMe();

      if (data.type === "message") {
        // Push notification when message is from someone else
        if (data.sender_id !== me?.user_id && "Notification" in window && Notification.permission === "granted") {
          new Notification(`New message from ${data.sender_name}`, {
            body: data.msg_type === "image" ? "📷 Image" : data.content,
            icon: "/favicon.ico",
          });
        }
        onEventRef.current({ type: "message", payload: data });
      } else if (data.type === "user_online") {
        onEventRef.current({ type: "user_online", user_id: data.user_id });
      } else if (data.type === "user_offline") {
        onEventRef.current({ type: "user_offline", user_id: data.user_id });
      }
    };

    socket.onclose = () => {
      setTimeout(connect, 3000); // auto-reconnect
    };
  }, []);

  useEffect(() => {
    connect();
    // Request notification permission
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
    return () => ws.current?.close();
  }, [connect]);

  const send = useCallback((data: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
    }
  }, []);

  return { send };
}
