"""
memory.py
---------
Conversation and context memory for the e₹ Bridge AI agent.

Two memory layers:

  Short-term (working memory)
    Conversation history for the current session.
    Kept in-process. Lost when the server restarts.
    Configurable limit: last N message pairs per session.

  Long-term (episodic memory)
    Summary of past sessions and key user preferences.
    In production: PostgreSQL with pgvector for semantic retrieval.
    In PoC: in-process dict, cleared on restart.

The memory manager injects relevant context into each agent
invocation so responses are coherent across a conversation.
"""

from collections import defaultdict
from datetime import datetime, timezone


MAX_SHORT_TERM = 10   # message pairs kept per session
MAX_SESSIONS = 1000   # maximum concurrent sessions in memory


class MemoryManager:

    def __init__(self):
        self._conversations: dict[str, list[dict]] = defaultdict(list)
        self._session_meta: dict[str, dict] = {}

    def add_turn(self, session_id: str, user_msg: str, agent_msg: str) -> None:
        """Record a completed conversation turn."""
        conv = self._conversations[session_id]
        conv.append({
            "role": "user",
            "content": user_msg,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        conv.append({
            "role": "agent",
            "content": agent_msg,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        # Keep only the most recent N pairs
        if len(conv) > MAX_SHORT_TERM * 2:
            self._conversations[session_id] = conv[-(MAX_SHORT_TERM * 2):]
        # Evict oldest sessions if at capacity
        if len(self._conversations) > MAX_SESSIONS:
            oldest = next(iter(self._conversations))
            del self._conversations[oldest]
            self._session_meta.pop(oldest, None)

    def get_history(self, session_id: str) -> list[dict]:
        """Returns the conversation history for a session."""
        return self._conversations.get(session_id, [])

    def get_context_summary(self, session_id: str) -> str:
        """Returns a compact summary of recent conversation context."""
        history = self.get_history(session_id)
        if not history:
            return ""
        recent = history[-6:]  # last 3 turns
        lines = []
        for msg in recent:
            role = "User" if msg["role"] == "user" else "Agent"
            lines.append(f"{role}: {msg['content'][:100]}")
        return "\n".join(lines)

    def clear_session(self, session_id: str) -> None:
        self._conversations.pop(session_id, None)
        self._session_meta.pop(session_id, None)

    @property
    def active_sessions(self) -> int:
        return len(self._conversations)
