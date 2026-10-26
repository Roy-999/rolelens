from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from ..config import Settings

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_authorized(self) -> bool:
        credentials = self._load_credentials()
        return bool(credentials and credentials.valid)

    def authorization_url(self) -> str:
        flow = self._build_flow()
        url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent select_account",
        )
        return url

    def complete_authorization(self, authorization_response_url: str) -> None:
        flow = self._build_flow()
        flow.fetch_token(authorization_response=authorization_response_url)
        self._save_credentials(flow.credentials)

    def disconnect(self) -> None:
        token_path = Path(self.settings.gmail_token_path)
        if token_path.is_file():
            token_path.unlink()

    def connected_email(self) -> str:
        service = self._service()
        profile = service.users().getProfile(userId="me").execute()
        return str(profile.get("emailAddress") or "")

    def list_messages(self, query: str, max_results: int) -> list[dict[str, Any]]:
        service = self._service()
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        return list(response.get("messages") or [])

    def get_message(self, message_id: str) -> dict[str, Any]:
        service = self._service()
        return (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

    def get_attachment_bytes(self, message_id: str, attachment_id: str) -> bytes:
        service = self._service()
        response = (
            service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        payload = response.get("data") or ""
        return base64.urlsafe_b64decode(payload.encode("utf-8"))

    def mark_as_read(self, message_id: str) -> None:
        service = self._service()
        (
            service.users()
            .messages()
            .modify(userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]})
            .execute()
        )

    def _service(self):
        credentials = self._load_credentials()
        if not credentials:
            raise RuntimeError("Gmail is not authorized. Connect Gmail first.")
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save_credentials(credentials)
        if not credentials.valid:
            raise RuntimeError("Gmail authorization is invalid. Reconnect Gmail.")
        return build("gmail", "v1", credentials=credentials)

    def _load_credentials(self) -> Credentials | None:
        token_path = Path(self.settings.gmail_token_path)
        if not token_path.is_file():
            return None
        credentials = Credentials.from_authorized_user_file(
            str(token_path), GMAIL_SCOPES
        )
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save_credentials(credentials)
        return credentials

    def _save_credentials(self, credentials: Credentials) -> None:
        token_path = Path(self.settings.gmail_token_path)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")

    def _build_flow(self) -> Flow:
        credentials_path = Path(self.settings.gmail_credentials_path)
        if not credentials_path.is_file():
            raise RuntimeError(f"Gmail credentials file not found: {credentials_path}")
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
        return Flow.from_client_secrets_file(
            str(credentials_path),
            scopes=GMAIL_SCOPES,
            redirect_uri=self.settings.gmail_oauth_redirect_uri,
        )
