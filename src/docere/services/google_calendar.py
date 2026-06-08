"""Google Calendar integration: OAuth2, token encryption, Calendar API."""

import asyncio
from datetime import datetime, timezone
from functools import partial

import structlog
from cryptography.fernet import Fernet
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.config import settings
from docere.models.calendar import InstructorCalendarToken

logger = structlog.get_logger()

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def _get_fernet() -> Fernet:
    """Get Fernet cipher for token encryption."""
    if not settings.token_encryption_key:
        raise ValueError(
            "token_encryption_key not configured — generate one with Fernet.generate_key()"
        )
    return Fernet(settings.token_encryption_key.encode())


def _encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


class GoogleCalendarService:
    """Handles Google Calendar OAuth2 and Calendar API operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── OAuth2 ──

    def get_authorization_url(self, state: str | None = None) -> str:
        """Generate Google OAuth2 consent URL."""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.google_redirect_uri],
                }
            },
            scopes=SCOPES,
        )
        flow.redirect_uri = settings.google_redirect_uri
        url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state or "",
        )
        return url

    async def handle_oauth_callback(self, code: str, instructor_id: str) -> InstructorCalendarToken:
        """Exchange auth code for tokens and store encrypted."""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.google_redirect_uri],
                }
            },
            scopes=SCOPES,
        )
        flow.redirect_uri = settings.google_redirect_uri

        # Google often returns extra scopes (openid, userinfo) — allow it
        import os

        os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

        # fetch_token is a blocking HTTP call — run in thread
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(flow.fetch_token, code=code))

        creds = flow.credentials
        encrypted_access = _encrypt(creds.token)
        encrypted_refresh = _encrypt(creds.refresh_token or "")
        granted_scopes = ",".join(creds.scopes or [])

        # Upsert: replace existing token for this instructor
        result = await self.db.execute(
            select(InstructorCalendarToken).where(
                InstructorCalendarToken.instructor_id == instructor_id
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.encrypted_access_token = encrypted_access
            existing.encrypted_refresh_token = encrypted_refresh
            existing.token_expiry = (
                creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else None
            )
            existing.scopes = granted_scopes
            existing.is_active = True
            existing.updated_at = datetime.now(timezone.utc)
            token_record = existing
        else:
            token_record = InstructorCalendarToken(
                instructor_id=instructor_id,
                encrypted_access_token=encrypted_access,
                encrypted_refresh_token=encrypted_refresh,
                token_expiry=creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else None,
                scopes=granted_scopes,
            )
            self.db.add(token_record)

        await self.db.commit()
        await self.db.refresh(token_record)

        logger.info("Google Calendar tokens stored", instructor_id=instructor_id)
        return token_record

    async def _get_credentials(self, instructor_id: str) -> Credentials | None:
        """Load and refresh Google credentials for an instructor."""
        result = await self.db.execute(
            select(InstructorCalendarToken).where(
                InstructorCalendarToken.instructor_id == instructor_id,
                InstructorCalendarToken.is_active == True,  # noqa: E712
            )
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            return None

        access_token = _decrypt(token_record.encrypted_access_token)
        refresh_token = _decrypt(token_record.encrypted_refresh_token)

        # Use only the scopes the user actually granted (not the full SCOPES list)
        # to avoid invalid_scope errors on token refresh
        granted = token_record.scopes.split(",") if token_record.scopes else []
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=granted or SCOPES,
        )

        # Refresh if expired (blocking HTTP call — run in thread)
        if creds.expired and creds.refresh_token:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, creds.refresh, Request())
            except Exception as e:
                error_msg = str(e).lower()
                if "invalid_grant" in error_msg or "revoked" in error_msg:
                    logger.warning(
                        "Google token expired or revoked — deactivating",
                        instructor_id=instructor_id,
                    )
                    token_record.is_active = False
                    token_record.updated_at = datetime.now(timezone.utc)
                    await self.db.commit()
                    return None
                raise

            token_record.encrypted_access_token = _encrypt(creds.token)
            if creds.refresh_token:
                token_record.encrypted_refresh_token = _encrypt(creds.refresh_token)
            token_record.token_expiry = (
                creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else None
            )
            token_record.updated_at = datetime.now(timezone.utc)
            await self.db.commit()

        return creds

    # ── Calendar API ──

    async def get_free_busy(
        self,
        instructor_id: str,
        time_min: datetime,
        time_max: datetime,
        calendar_id: str = "primary",
    ) -> list[dict[str, str]]:
        """Query Google Calendar free/busy for a time range.

        Returns list of {"start": iso, "end": iso} busy periods.
        """
        creds = await self._get_credentials(instructor_id)
        if not creds:
            return []

        service = build("calendar", "v3", credentials=creds)
        body = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items": [{"id": calendar_id}],
        }

        result = service.freebusy().query(body=body).execute()
        busy = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])

        return [{"start": b["start"], "end": b["end"]} for b in busy]

    async def create_event(
        self,
        instructor_id: str,
        summary: str,
        description: str,
        start: datetime,
        end: datetime,
        attendee_email: str | None = None,
        calendar_id: str = "primary",
    ) -> str | None:
        """Create a Google Calendar event. Returns the event ID."""
        creds = await self._get_credentials(instructor_id)
        if not creds:
            logger.warning("No calendar credentials for instructor", instructor_id=instructor_id)
            return None

        service = build("calendar", "v3", credentials=creds)
        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        }
        if attendee_email:
            event["attendees"] = [{"email": attendee_email}]

        created = (
            service.events()
            .insert(
                calendarId=calendar_id,
                body=event,
                sendUpdates="all" if attendee_email else "none",
            )
            .execute()
        )

        event_id = created.get("id")
        logger.info("Calendar event created", event_id=event_id, instructor_id=instructor_id)
        return event_id

    async def cancel_event(
        self,
        instructor_id: str,
        event_id: str,
        calendar_id: str = "primary",
    ) -> bool:
        """Cancel a Google Calendar event."""
        creds = await self._get_credentials(instructor_id)
        if not creds:
            return False

        service = build("calendar", "v3", credentials=creds)
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
            sendUpdates="all",
        ).execute()

        logger.info("Calendar event cancelled", event_id=event_id)
        return True

    async def has_calendar_connected(self, instructor_id: str) -> bool:
        """Check if instructor has active calendar tokens."""
        result = await self.db.execute(
            select(InstructorCalendarToken.id).where(
                InstructorCalendarToken.instructor_id == instructor_id,
                InstructorCalendarToken.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none() is not None
