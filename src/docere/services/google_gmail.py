"""Gmail integration: send emails using instructor's Google OAuth tokens."""

import asyncio
import base64
from email.mime.text import MIMEText

import structlog
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession

from docere.services.google_calendar import GoogleCalendarService

logger = structlog.get_logger()


class GmailService:
    """Send emails via Gmail API using existing Google OAuth tokens."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cal_service = GoogleCalendarService(db)

    async def send_email(
        self,
        instructor_id: str,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> dict:
        """Send an email via Gmail API.

        Returns {"message_id": str, "thread_id": str} on success.
        Raises ValueError if no credentials or missing gmail scope.
        """
        creds = await self._cal_service._get_credentials(instructor_id)
        if not creds:
            raise ValueError("Google not connected. Please connect your Google account first.")

        message = MIMEText(body, "html")
        message["to"] = ", ".join(to)
        message["subject"] = subject
        if cc:
            message["cc"] = ", ".join(cc)
        if bcc:
            message["bcc"] = ", ".join(bcc)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        def _send():
            service = build("gmail", "v1", credentials=creds, static_discovery=False)
            result = (
                service.users()
                .messages()
                .send(
                    userId="me",
                    body={"raw": raw},
                )
                .execute()
            )
            return result

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _send)

        logger.info(
            "Email sent via Gmail",
            instructor_id=instructor_id,
            to=to,
            message_id=result.get("id"),
        )
        return {
            "message_id": result.get("id", ""),
            "thread_id": result.get("threadId", ""),
        }
