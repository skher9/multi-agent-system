"""Live updates to the browser through Pusher Channels.

Workers can't talk to the browser directly: the browser is connected to Pusher,
and our code tells Pusher "send event X on channel Y". Later, every pipeline
stage change is pushed this way, so the progress view updates without polling.
"""

from dataclasses import dataclass
from typing import Any

import pusher


@dataclass(frozen=True)
class PusherCredentials:
    app_id: str
    key: str
    secret: str
    cluster: str


class Realtime:
    def __init__(self, creds: PusherCredentials) -> None:
        self._client = pusher.Pusher(
            app_id=creds.app_id,
            key=creds.key,
            secret=creds.secret,
            cluster=creds.cluster,
            ssl=True,
            timeout=5,
        )

    def send(self, channel: str, event: str, data: dict[str, Any]) -> None:
        self._client.trigger(channel, event, data)

    def ping(self) -> None:
        """Raise if Pusher rejects our credentials. Reads channel info; sends nothing."""
        self._client.channels_info()
