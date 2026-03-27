import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

RIDE_HISTORY_FILE = Path('ride_history.json')


class StateManager:
    """Manages in-memory state and persists ride history."""

    def __init__(self) -> None:
        self.active_ride: str | None = None
        self.last_preview: dict | None = None
        self.last_options: list | None = None

    def save_ride(self, ride_data: dict) -> None:
        """Append a completed ride booking to ride_history.json.

        Args:
            ride_data: The confirmed ride response dict.
        """
        history = self.get_ride_history()
        history.append(ride_data)
        RIDE_HISTORY_FILE.write_text(json.dumps(history, indent=2))
        logger.info('Saved ride to history: %s', ride_data.get('ride_id'))

    def get_ride_history(self) -> list:
        """Read all rides from ride_history.json.

        Returns:
            List of ride dicts, empty list if file doesn't exist.
        """
        if not RIDE_HISTORY_FILE.exists():
            return []
        try:
            return json.loads(RIDE_HISTORY_FILE.read_text())
        except json.JSONDecodeError:
            logger.error('ride_history.json is corrupted, returning empty list')
            return []

    def clear(self) -> None:
        """Reset all in-memory state (does not affect ride_history.json)."""
        self.active_ride = None
        self.last_preview = None
        self.last_options = None
        logger.debug('State cleared')


state = StateManager()
