"""Google Docs integration: create documents using instructor's OAuth tokens."""

import asyncio

import structlog
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession

from docere.services.google_calendar import GoogleCalendarService

logger = structlog.get_logger()


class GoogleDocsService:
    """Create Google Docs via Docs API."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cal_service = GoogleCalendarService(db)

    async def create_document(
        self,
        instructor_id: str,
        title: str,
        content: str,
    ) -> dict:
        """Create a Google Doc with the given title and content.

        Returns {"document_id": str, "url": str}.
        """
        creds = await self._cal_service._get_credentials(instructor_id)
        if not creds:
            raise ValueError("Google not connected. Please connect your Google account first.")

        def _create():
            docs_service = build("docs", "v1", credentials=creds, static_discovery=False)
            doc = docs_service.documents().create(body={"title": title}).execute()
            doc_id = doc["documentId"]

            if content:
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={
                        "requests": [
                            {
                                "insertText": {
                                    "location": {"index": 1},
                                    "text": content,
                                }
                            }
                        ]
                    },
                ).execute()

            return {
                "document_id": doc_id,
                "url": f"https://docs.google.com/document/d/{doc_id}/edit",
            }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _create)

        logger.info(
            "Google Doc created",
            instructor_id=instructor_id,
            doc_id=result["document_id"],
        )
        return result
