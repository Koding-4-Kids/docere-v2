"""Google Sheets integration: create, list, and read spreadsheets."""

import asyncio
import re

import structlog
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession

from docere.services.google_calendar import GoogleCalendarService

logger = structlog.get_logger()

# Regex to extract spreadsheet ID from a Google Sheets URL
_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


class GoogleSheetsService:
    """Create, list, and read Google Sheets via Sheets + Drive APIs."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cal_service = GoogleCalendarService(db)

    async def create_spreadsheet(
        self,
        instructor_id: str,
        title: str,
        headers: list[str],
        rows: list[list[str]],
        sheet_name: str = "Sheet1",
    ) -> dict:
        """Create a Google Sheet with headers and data rows.

        Returns {"spreadsheet_id": str, "url": str}.
        """
        creds = await self._cal_service._get_credentials(instructor_id)
        if not creds:
            raise ValueError("Google not connected. Please connect your Google account first.")

        def _create():
            sheets_service = build("sheets", "v4", credentials=creds, static_discovery=False)

            spreadsheet = (
                sheets_service.spreadsheets()
                .create(
                    body={
                        "properties": {"title": title},
                        "sheets": [{"properties": {"title": sheet_name}}],
                    }
                )
                .execute()
            )

            spreadsheet_id = spreadsheet["spreadsheetId"]

            # Write data: headers + rows
            all_rows = [headers] + rows
            if all_rows:
                sheets_service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"{sheet_name}!A1",
                    valueInputOption="RAW",
                    body={"values": all_rows},
                ).execute()

            return {
                "spreadsheet_id": spreadsheet_id,
                "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
            }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _create)

        logger.info(
            "Google Sheet created",
            instructor_id=instructor_id,
            sheet_id=result["spreadsheet_id"],
        )
        return result

    async def list_spreadsheets(self, instructor_id: str) -> list[dict]:
        """List spreadsheets created by Docere (drive.file scope).

        Returns [{"id": str, "title": str, "url": str, "modified_time": str}].
        """
        creds = await self._cal_service._get_credentials(instructor_id)
        if not creds:
            raise ValueError("Google not connected. Please connect your Google account first.")

        def _list():
            drive_service = build("drive", "v3", credentials=creds, static_discovery=False)
            results = (
                drive_service.files()
                .list(
                    q="mimeType='application/vnd.google-apps.spreadsheet'",
                    fields="files(id,name,modifiedTime)",
                    orderBy="modifiedTime desc",
                    pageSize=50,
                )
                .execute()
            )
            files = results.get("files", [])
            return [
                {
                    "id": f["id"],
                    "title": f["name"],
                    "url": f"https://docs.google.com/spreadsheets/d/{f['id']}/edit",
                    "modified_time": f.get("modifiedTime", ""),
                }
                for f in files
            ]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _list)

    async def read_spreadsheet(
        self,
        instructor_id: str,
        spreadsheet_id: str,
        range_name: str = "Sheet1",
    ) -> dict:
        """Read data from a Google Sheet.

        Returns {"title": str, "headers": list[str], "rows": list[list[str]]}.
        """
        creds = await self._cal_service._get_credentials(instructor_id)
        if not creds:
            raise ValueError("Google not connected. Please connect your Google account first.")

        def _read():
            sheets_service = build("sheets", "v4", credentials=creds, static_discovery=False)

            # Get spreadsheet title
            meta = (
                sheets_service.spreadsheets()
                .get(
                    spreadsheetId=spreadsheet_id,
                    fields="properties.title",
                )
                .execute()
            )
            title = meta.get("properties", {}).get("title", "Untitled")

            # Read all values
            result = (
                sheets_service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                )
                .execute()
            )
            values = result.get("values", [])

            if not values:
                return {"title": title, "headers": [], "rows": []}

            return {
                "title": title,
                "headers": values[0],
                "rows": values[1:],
            }

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _read)

    async def read_from_url(self, instructor_id: str, url: str) -> dict:
        """Read a spreadsheet given its Google Sheets URL.

        Extracts the spreadsheet ID from the URL and delegates to read_spreadsheet.
        """
        match = _SHEET_ID_RE.search(url)
        if not match:
            raise ValueError("Invalid Google Sheets URL")
        spreadsheet_id = match.group(1)
        return await self.read_spreadsheet(instructor_id, spreadsheet_id)
