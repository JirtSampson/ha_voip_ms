"""HTTP server for streaming voicemail audio files."""

import asyncio
import logging
import time
from typing import Optional

from aiohttp import web

from voipms_client import VoipMsClient, VoipMsError

_LOGGER = logging.getLogger(__name__)

# Cache audio for 5 minutes to avoid repeated API calls
CACHE_TTL = 300


class AudioCache:
    """Simple in-memory cache for audio files."""

    def __init__(self, ttl: int = CACHE_TTL):
        """Initialize cache.

        Args:
            ttl: Time-to-live in seconds for cached items
        """
        self._cache: dict[str, tuple[bytes, float]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[bytes]:
        """Get cached audio data.

        Args:
            key: Cache key

        Returns:
            Audio bytes if cached and not expired, None otherwise
        """
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return data
            del self._cache[key]
        return None

    def set(self, key: str, data: bytes):
        """Cache audio data.

        Args:
            key: Cache key
            data: Audio bytes to cache
        """
        self._cache[key] = (data, time.time())
        self._cleanup()

    def _cleanup(self):
        """Remove expired entries."""
        now = time.time()
        expired = [
            k for k, (_, ts) in self._cache.items()
            if now - ts >= self._ttl
        ]
        for key in expired:
            del self._cache[key]


class AudioServer:
    """HTTP server for streaming voicemail audio."""

    def __init__(
        self,
        voipms_client: VoipMsClient,
        port: int = 8099,
        host: str = "0.0.0.0"
    ):
        """Initialize audio server.

        Args:
            voipms_client: VoIP.ms API client
            port: Port to listen on
            host: Host to bind to
        """
        self._client = voipms_client
        self._port = port
        self._host = host
        self._cache = AudioCache()
        self._app = web.Application()
        self._runner: Optional[web.AppRunner] = None
        self._setup_routes()

    def _setup_routes(self):
        """Set up HTTP routes."""
        self._app.router.add_get(
            "/audio/{mailbox}/{folder}/{message_num}",
            self._handle_audio_request
        )
        self._app.router.add_get("/health", self._handle_health)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle health check requests."""
        return web.Response(text="OK")

    async def _handle_audio_request(
        self,
        request: web.Request
    ) -> web.Response:
        """Handle audio streaming requests.

        Args:
            request: HTTP request

        Returns:
            Audio response or error
        """
        mailbox = request.match_info["mailbox"]
        folder = request.match_info["folder"]
        message_num = request.match_info["message_num"]

        cache_key = f"{mailbox}/{folder}/{message_num}"
        _LOGGER.debug("Audio request: %s", cache_key)

        # Check cache first
        audio_data = self._cache.get(cache_key)
        if audio_data:
            _LOGGER.debug("Serving cached audio: %s", cache_key)
            return web.Response(
                body=audio_data,
                content_type="audio/wav",
                headers={
                    "Content-Disposition": (
                        f'inline; filename="voicemail_{mailbox}_{message_num}.wav"'
                    )
                }
            )

        # Fetch from API
        try:
            loop = asyncio.get_event_loop()
            audio_data = await loop.run_in_executor(
                None,
                self._client.get_voicemail_message_file,
                mailbox,
                folder,
                message_num
            )

            if not audio_data:
                return web.Response(
                    status=404,
                    text="Audio file not found"
                )

            # Cache the audio
            self._cache.set(cache_key, audio_data)

            return web.Response(
                body=audio_data,
                content_type="audio/wav",
                headers={
                    "Content-Disposition": (
                        f'inline; filename="voicemail_{mailbox}_{message_num}.wav"'
                    )
                }
            )

        except VoipMsError as err:
            _LOGGER.error("Failed to fetch audio: %s", err)
            return web.Response(
                status=500,
                text=f"Failed to fetch audio: {err}"
            )

    async def start(self):
        """Start the HTTP server."""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        _LOGGER.info("Audio server started on %s:%d", self._host, self._port)

    async def stop(self):
        """Stop the HTTP server."""
        if self._runner:
            await self._runner.cleanup()
            _LOGGER.info("Audio server stopped")

    @property
    def base_url(self) -> str:
        """Get base URL for audio endpoints."""
        return f"http://{self._host}:{self._port}"
