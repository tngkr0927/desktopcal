"""Google API OAuth 2.0 authentication module.

Handles credential loading, token refresh, and initial OAuth consent flow.
Expects `credentials.json` in the project root (downloaded from Google Cloud Console)
and persists the user token as `token.json`.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

# If modifying these scopes, delete token.json and re-authenticate.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = BASE_DIR / os.getenv("CREDENTIALS_FILE", "credentials.json")
TOKEN_PATH = BASE_DIR / os.getenv("TOKEN_FILE", "token.json")


def get_credentials() -> Credentials:
    """Return valid Google OAuth2 credentials.

    On first run the browser-based consent flow is triggered.
    Subsequent runs reuse / refresh the persisted token.
    """
    creds: Credentials | None = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_PATH}. "
                    "Download it from the Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json())

    return creds
