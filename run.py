#!/usr/bin/env python3
"""Main application for VoIP.ms Voicemail Home Assistant addon."""

import asyncio
import json
import logging
import os
import signal
import sys
import time

from voipms_client import VoipMsClient, VoipMsError
from mqtt_publisher import MqttPublisher
from audio_server import AudioServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_LOGGER = logging.getLogger("voipms_voicemail")


def load_config() -> dict:
    """Load configuration from Home Assistant addon options.

    Returns:
        Configuration dictionary
    """
    config_path = "/data/options.json"

    if not os.path.exists(config_path):
        _LOGGER.warning(
            "Config file not found at %s, using environment variables",
            config_path
        )
        return {
            "voipms_username": os.environ.get("VOIPMS_USERNAME", ""),
            "voipms_api_password": os.environ.get("VOIPMS_API_PASSWORD", ""),
            "mailboxes": os.environ.get("MAILBOXES", "").split(","),
            "poll_interval": int(os.environ.get("POLL_INTERVAL", "60")),
            "mqtt_host": os.environ.get("MQTT_HOST", "core-mosquitto"),
            "mqtt_port": int(os.environ.get("MQTT_PORT", "1883")),
            "mqtt_username": os.environ.get("MQTT_USERNAME", ""),
            "mqtt_password": os.environ.get("MQTT_PASSWORD", ""),
            "audio_port": int(os.environ.get("AUDIO_PORT", "8099")),
        }

    with open(config_path) as f:
        return json.load(f)


class VoicemailMonitor:
    """Main voicemail monitoring application."""

    def __init__(self, config: dict):
        """Initialize the monitor.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self._running = False
        self._discovered_mailboxes: set[str] = set()

        # Initialize VoIP.ms client
        self.voipms = VoipMsClient(
            username=config["voipms_username"],
            api_password=config["voipms_api_password"],
        )

        # Initialize MQTT publisher
        self.mqtt = MqttPublisher(
            host=config["mqtt_host"],
            port=config["mqtt_port"],
            username=config.get("mqtt_username") or None,
            password=config.get("mqtt_password") or None,
            on_connect_callback=self._on_mqtt_connect,
        )

        # Initialize audio server
        self.audio_server = AudioServer(
            voipms_client=self.voipms,
            port=config.get("audio_port", 8099),
        )

        # Get supervisor hostname for audio URL
        self._hostname = os.environ.get("HOSTNAME", "localhost")
        self._audio_port = config.get("audio_port", 8099)

    def _on_mqtt_connect(self):
        """Handle MQTT connection - republish discovery."""
        for mailbox in self._discovered_mailboxes:
            self.mqtt.publish_discovery(mailbox)

    def _get_audio_base_url(self) -> str:
        """Get the base URL for audio streaming.

        Returns:
            Base URL for audio endpoints
        """
        # In Home Assistant, use the addon hostname
        # Supervisord provides SUPERVISOR_TOKEN when running as addon
        if os.environ.get("SUPERVISOR_TOKEN"):
            # Running as Home Assistant addon
            slug = "voipms_voicemail"
            return f"http://{slug}:{self._audio_port}"

        # Fallback for local testing
        return f"http://localhost:{self._audio_port}"

    async def _poll_voicemails(self):
        """Poll VoIP.ms for voicemail updates."""
        try:
            # Get configured mailboxes or discover all
            configured_mailboxes = self.config.get("mailboxes", [])
            configured_mailboxes = [m for m in configured_mailboxes if m]

            if configured_mailboxes:
                mailboxes = [{"mailbox": m} for m in configured_mailboxes]
            else:
                # Discover all mailboxes
                _LOGGER.debug("Discovering mailboxes...")
                mailboxes = await asyncio.get_event_loop().run_in_executor(
                    None, self.voipms.get_voicemails
                )

            audio_base_url = self._get_audio_base_url()

            for mailbox_info in mailboxes:
                mailbox = mailbox_info.get("mailbox")
                if not mailbox:
                    continue

                mailbox_name = mailbox_info.get("name")

                # Publish discovery if new mailbox
                if mailbox not in self._discovered_mailboxes:
                    self._discovered_mailboxes.add(mailbox)
                    self.mqtt.publish_discovery(mailbox, mailbox_name)

                # Get messages
                messages = await asyncio.get_event_loop().run_in_executor(
                    None, self.voipms.get_voicemail_messages, mailbox
                )

                # Count new messages (not listened)
                new_count = sum(
                    1 for m in messages
                    if m.get("listened") == "no"
                )
                total_count = len(messages)

                # Publish state
                self.mqtt.publish_state(
                    mailbox=mailbox,
                    new_count=new_count,
                    total_count=total_count,
                    messages=messages,
                    audio_base_url=audio_base_url,
                )

        except VoipMsError as err:
            _LOGGER.error("Failed to poll voicemails: %s", err)

    async def run(self):
        """Run the main application loop."""
        _LOGGER.info("Starting VoIP.ms Voicemail Monitor")

        # Test VoIP.ms connection
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self.voipms.test_connection
            )
            _LOGGER.info("VoIP.ms API connection successful")
        except VoipMsError as err:
            _LOGGER.error("Failed to connect to VoIP.ms API: %s", err)
            sys.exit(1)

        # Connect to MQTT
        if not self.mqtt.connect():
            _LOGGER.error("Failed to connect to MQTT broker")
            sys.exit(1)

        # Wait for MQTT connection
        for _ in range(30):
            if self.mqtt.is_connected():
                break
            await asyncio.sleep(0.5)
        else:
            _LOGGER.error("MQTT connection timeout")
            sys.exit(1)

        # Start audio server
        await self.audio_server.start()

        # Main polling loop
        self._running = True
        poll_interval = self.config.get("poll_interval", 60)

        _LOGGER.info(
            "Starting polling loop (interval: %d seconds)",
            poll_interval
        )

        while self._running:
            await self._poll_voicemails()
            await asyncio.sleep(poll_interval)

        # Cleanup
        await self.audio_server.stop()
        self.mqtt.disconnect()
        _LOGGER.info("VoIP.ms Voicemail Monitor stopped")

    def stop(self):
        """Stop the application."""
        _LOGGER.info("Stopping...")
        self._running = False


def main():
    """Main entry point."""
    config = load_config()

    # Validate required config
    if not config.get("voipms_username"):
        _LOGGER.error("voipms_username is required")
        sys.exit(1)
    if not config.get("voipms_api_password"):
        _LOGGER.error("voipms_api_password is required")
        sys.exit(1)

    monitor = VoicemailMonitor(config)

    # Set up signal handlers
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler():
        monitor.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        loop.run_until_complete(monitor.run())
    except KeyboardInterrupt:
        _LOGGER.info("Interrupted")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
