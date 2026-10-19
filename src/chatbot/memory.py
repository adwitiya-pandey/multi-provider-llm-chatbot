"""Sliding-window multi-turn conversation memory with turn and token limits."""

from dataclasses import dataclass

from chatbot.models import StructuredReply, UserTurnInput


@dataclass(frozen=True)
class MemoryTurn:
    """A single preserved conversational turn in memory."""

    turn_id: str
    user_text: str
    reply: StructuredReply
    estimated_tokens: int


def estimate_tokens(text: str) -> int:
    """Conservatively estimates tokens as max(1, len(text) // 4)."""
    return max(1, len(text) // 4)


class ConversationMemory:
    """Maintains a bounded sliding window of conversation turns."""

    def __init__(self, max_turns: int = 10, max_estimated_tokens: int = 6000) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        if max_estimated_tokens < 100:
            raise ValueError("max_estimated_tokens must be at least 100")

        self.max_turns = max_turns
        self.max_estimated_tokens = max_estimated_tokens
        self._turns: list[MemoryTurn] = []

    @property
    def turn_count(self) -> int:
        """Returns the number of turns currently stored in memory."""
        return len(self._turns)

    @property
    def estimated_tokens(self) -> int:
        """Returns total estimated tokens across all stored turns."""
        return sum(turn.estimated_tokens for turn in self._turns)

    @property
    def turns(self) -> list[MemoryTurn]:
        """Returns a copy of the stored turns."""
        return list(self._turns)

    def add_turn(
        self,
        user_input: UserTurnInput,
        reply: StructuredReply,
        turn_id: str | None = None,
    ) -> None:
        """Adds a completed turn and evicts oldest turns if limits are exceeded."""
        tid = turn_id or f"TURN-{self.turn_count + 1:04d}"
        reply_json = reply.model_dump_json()
        turn_tokens = estimate_tokens(user_input.text) + estimate_tokens(reply_json)

        new_turn = MemoryTurn(
            turn_id=tid,
            user_text=user_input.text,
            reply=reply,
            estimated_tokens=turn_tokens,
        )
        self._turns.append(new_turn)
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        """Evicts oldest turns until both turn count and token bounds are satisfied."""
        while len(self._turns) > self.max_turns:
            self._turns.pop(0)

        while self.estimated_tokens > self.max_estimated_tokens and self._turns:
            self._turns.pop(0)

    def to_provider_messages(self) -> list[dict[str, str]]:
        """Formats conversation history into a list of role/content dictionaries."""
        messages: list[dict[str, str]] = []
        for turn in self._turns:
            messages.append({"role": "user", "content": turn.user_text})
            messages.append({"role": "assistant", "content": turn.reply.model_dump_json()})
        return messages

    def clear(self) -> None:
        """Resets conversation memory to empty state."""
        self._turns.clear()
