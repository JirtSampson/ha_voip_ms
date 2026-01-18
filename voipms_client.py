"""VoIP.ms API client for voicemail operations."""

import logging
import requests
from typing import Optional
from urllib.parse import urlencode

_LOGGER = logging.getLogger(__name__)

API_URL = "https://voip.ms/api/v1/rest.php"


class VoipMsError(Exception):
    """Exception for VoIP.ms API errors."""
    pass


class VoipMsClient:
    """Client for interacting with VoIP.ms API."""

    def __init__(self, username: str, api_password: str):
        """Initialize the client.

        Args:
            username: VoIP.ms account email
            api_password: API password from voip.ms portal
        """
        self.username = username
        self.api_password = api_password
        self._session = requests.Session()

    def _make_request(self, method: str, **params) -> dict:
        """Make an API request.

        Args:
            method: API method name
            **params: Additional parameters

        Returns:
            API response as dict

        Raises:
            VoipMsError: If API returns an error
        """
        params.update({
            "api_username": self.username,
            "api_password": self.api_password,
            "method": method,
        })

        try:
            response = self._session.get(API_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as err:
            raise VoipMsError(f"API request failed: {err}") from err
        except ValueError as err:
            raise VoipMsError(f"Invalid JSON response: {err}") from err

        if data.get("status") != "success":
            error_msg = data.get("status", "Unknown error")
            raise VoipMsError(f"API error: {error_msg}")

        return data

    def get_voicemails(self) -> list[dict]:
        """Get list of all voicemail mailboxes.

        Returns:
            List of mailbox dictionaries with 'mailbox' and 'name' keys
        """
        try:
            data = self._make_request("getVoicemails")
            voicemails = data.get("voicemails", [])
            if isinstance(voicemails, dict):
                voicemails = [voicemails]
            return voicemails
        except VoipMsError as err:
            if "no_voicemail" in str(err).lower():
                return []
            raise

    def get_voicemail_messages(
        self,
        mailbox: str,
        folder: Optional[str] = None
    ) -> list[dict]:
        """Get voicemail messages for a mailbox.

        Args:
            mailbox: Mailbox ID
            folder: Optional folder name (INBOX, Old, Urgent, etc.)

        Returns:
            List of message dictionaries
        """
        params = {"mailbox": mailbox}
        if folder:
            params["folder"] = folder

        try:
            data = self._make_request("getVoicemailMessages", **params)
            messages = data.get("messages", [])
            if isinstance(messages, dict):
                messages = [messages]
            return messages
        except VoipMsError as err:
            if "no_messages" in str(err).lower():
                return []
            raise

    def get_voicemail_message_file(
        self,
        mailbox: str,
        folder: str,
        message_num: str
    ) -> bytes:
        """Get voicemail audio file.

        Args:
            mailbox: Mailbox ID
            folder: Folder name (INBOX, Old, etc.)
            message_num: Message number

        Returns:
            Audio file bytes (WAV format)
        """
        params = {
            "api_username": self.username,
            "api_password": self.api_password,
            "method": "getVoicemailMessageFile",
            "mailbox": mailbox,
            "folder": folder,
            "message_num": message_num,
        }

        try:
            response = self._session.get(API_URL, params=params, timeout=60)
            response.raise_for_status()

            # Check if response is JSON (error) or binary (audio)
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type or "text/" in content_type:
                try:
                    data = response.json()
                    if data.get("status") != "success":
                        raise VoipMsError(f"API error: {data.get('status')}")
                except ValueError:
                    pass

            return response.content
        except requests.RequestException as err:
            raise VoipMsError(f"Failed to get audio file: {err}") from err

    def test_connection(self) -> bool:
        """Test API connection.

        Returns:
            True if connection successful

        Raises:
            VoipMsError: If connection fails
        """
        self._make_request("getBalance")
        return True
