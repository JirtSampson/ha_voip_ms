"""MQTT publisher for Home Assistant discovery and state updates."""

import json
import logging
from typing import Callable, Optional

import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PREFIX = "homeassistant"
STATE_PREFIX = "voipms"


class MqttPublisher:
    """MQTT client for publishing voicemail status to Home Assistant."""

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        on_connect_callback: Optional[Callable] = None,
    ):
        """Initialize MQTT publisher.

        Args:
            host: MQTT broker hostname
            port: MQTT broker port
            username: Optional MQTT username
            password: Optional MQTT password
            on_connect_callback: Optional callback for connection events
        """
        self.host = host
        self.port = port
        self._client = mqtt.Client(client_id="voipms_voicemail")
        self._connected = False
        self._on_connect_callback = on_connect_callback

        if username:
            self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        """Handle connection to MQTT broker."""
        if rc == 0:
            _LOGGER.info("Connected to MQTT broker")
            self._connected = True
            if self._on_connect_callback:
                self._on_connect_callback()
        else:
            _LOGGER.error("Failed to connect to MQTT broker: %s", rc)
            self._connected = False

    def _on_disconnect(self, client, userdata, rc):
        """Handle disconnection from MQTT broker."""
        _LOGGER.warning("Disconnected from MQTT broker: %s", rc)
        self._connected = False

    def connect(self) -> bool:
        """Connect to MQTT broker.

        Returns:
            True if connection initiated successfully
        """
        try:
            self._client.connect(self.host, self.port, keepalive=60)
            self._client.loop_start()
            return True
        except Exception as err:
            _LOGGER.error("Failed to connect to MQTT broker: %s", err)
            return False

    def disconnect(self):
        """Disconnect from MQTT broker."""
        self._client.loop_stop()
        self._client.disconnect()

    def is_connected(self) -> bool:
        """Check if connected to MQTT broker."""
        return self._connected

    def publish_discovery(
        self,
        mailbox: str,
        mailbox_name: Optional[str] = None
    ):
        """Publish Home Assistant MQTT discovery config for a mailbox.

        Args:
            mailbox: Mailbox ID
            mailbox_name: Optional friendly name for the mailbox
        """
        name = mailbox_name or f"Voicemail {mailbox}"
        unique_id = f"voipms_voicemail_{mailbox}"
        state_topic = f"{STATE_PREFIX}/{mailbox}/state"
        json_attr_topic = f"{STATE_PREFIX}/{mailbox}/attributes"

        config = {
            "name": name,
            "unique_id": unique_id,
            "state_topic": state_topic,
            "json_attributes_topic": json_attr_topic,
            "icon": "mdi:voicemail",
            "unit_of_measurement": "messages",
            "device": {
                "identifiers": [f"voipms_{mailbox}"],
                "name": f"VoIP.ms Mailbox {mailbox}",
                "manufacturer": "VoIP.ms",
                "model": "Voicemail",
            },
        }

        discovery_topic = f"{DISCOVERY_PREFIX}/sensor/voipms_{mailbox}/config"

        self._client.publish(
            discovery_topic,
            json.dumps(config),
            retain=True,
            qos=1
        )
        _LOGGER.debug("Published discovery config for mailbox %s", mailbox)

    def publish_state(
        self,
        mailbox: str,
        new_count: int,
        total_count: int,
        messages: list[dict],
        audio_base_url: str
    ):
        """Publish voicemail state for a mailbox.

        Args:
            mailbox: Mailbox ID
            new_count: Number of new (unlistened) messages
            total_count: Total number of messages
            messages: List of message metadata
            audio_base_url: Base URL for audio streaming
        """
        state_topic = f"{STATE_PREFIX}/{mailbox}/state"
        attr_topic = f"{STATE_PREFIX}/{mailbox}/attributes"

        # Enrich messages with audio URLs
        enriched_messages = []
        for msg in messages:
            enriched = dict(msg)
            folder = msg.get("folder", "INBOX")
            msg_num = msg.get("message_num", "")
            if msg_num:
                enriched["audio_url"] = (
                    f"{audio_base_url}/audio/{mailbox}/{folder}/{msg_num}"
                )
            enriched_messages.append(enriched)

        attributes = {
            "total_messages": total_count,
            "new_messages": new_count,
            "messages": enriched_messages,
        }

        self._client.publish(state_topic, str(new_count), retain=True, qos=1)
        self._client.publish(
            attr_topic,
            json.dumps(attributes),
            retain=True,
            qos=1
        )
        _LOGGER.debug(
            "Published state for mailbox %s: %d new, %d total",
            mailbox, new_count, total_count
        )

    def remove_discovery(self, mailbox: str):
        """Remove discovery config for a mailbox.

        Args:
            mailbox: Mailbox ID
        """
        discovery_topic = f"{DISCOVERY_PREFIX}/sensor/voipms_{mailbox}/config"
        self._client.publish(discovery_topic, "", retain=True, qos=1)
        _LOGGER.debug("Removed discovery config for mailbox %s", mailbox)
