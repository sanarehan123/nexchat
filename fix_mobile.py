import re

content = open('frontend/src/app/globals.css').read()
content = re.sub(r'@media \(max-width: 768px\).*', '', content, flags=re.DOTALL).strip()

mobile = """

@media (max-width: 768px) {
  .chat-layout { flex-direction: column; height: 100vh; }
  .sidebar { width: 100%; height: 130px; min-height: 130px; border-right: none; border-bottom: 1px solid var(--border); flex-shrink: 0; }
  .sidebar-header { padding: 10px 14px; }
  .sidebar-logo { font-size: 13px; }
  .sidebar-me { font-size: 11px; }
  .btn-logout { font-size: 11px; padding: 4px 8px; }
  .sidebar-section-label { padding: 6px 14px 4px; font-size: 10px; }
  .user-list { display: flex; flex-direction: row; overflow-x: auto; overflow-y: hidden; padding: 6px 10px; gap: 10px; flex: 1; }
  .user-item { flex-direction: column; align-items: center; min-width: 60px; max-width: 60px; padding: 6px 4px; border-left: none; border-bottom: 2px solid transparent; border-radius: 10px; text-align: center; }
  .user-item.active { border-bottom-color: var(--accent); background: var(--surface2); }
  .avatar { width: 36px; height: 36px; font-size: 12px; border-radius: 10px; }
  .user-name { font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; }
  .user-status { display: none; }
  .user-info { width: 100%; }
  .chat-window { flex: 1; min-height: 0; overflow: hidden; }
  .messages-area { padding: 12px; }
  .input-bar { padding: 10px 12px; }
  .bubble { max-width: 85%; font-size: 13px; }
  .auth-card { width: 95%; padding: 28px 20px; margin: 16px; }
  .chat-header { padding: 10px 14px; }
}
"""

open('frontend/src/app/globals.css', 'w').write(content + mobile)
print('Done!')