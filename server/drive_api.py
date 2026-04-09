"""Google Drive API operations."""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import get_credentials
from .config import validate_folder, validate_sharing_domain
from .docs_api import RETRY_CONFIG
from .errors import ConfigError, handle_http_error

from tenacity import retry


class DriveClient:
    def __init__(self):
        creds = get_credentials()
        self.service = build("drive", "v3", credentials=creds)

    @retry(**RETRY_CONFIG)
    def move_to_folder(self, file_id: str, folder_id: str) -> dict:
        if not validate_folder(folder_id):
            raise ConfigError(f"Folder {folder_id} not in allowlist.")

        try:
            file = self.service.files().get(
                fileId=file_id, fields="parents"
            ).execute()
            previous_parents = ",".join(file.get("parents", []))

            self.service.files().update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields="id, parents",
            ).execute()
        except HttpError as e:
            if e.resp.status in (429, 500, 502, 503):
                raise  # Retry
            handle_http_error(e)

        return {"status": "ok", "file_id": file_id, "new_folder": folder_id}

    @retry(**RETRY_CONFIG)
    def share(
        self,
        file_id: str,
        emails: list[str],
        role: str = "reader",
        send_notification: bool = True,
    ) -> dict:
        results = []
        for email in emails:
            if not validate_sharing_domain(email):
                raise ConfigError(
                    f"Domain of {email} not in allowed sharing domains."
                )
            permission = {"type": "user", "role": role, "emailAddress": email}
            try:
                result = self.service.permissions().create(
                    fileId=file_id,
                    body=permission,
                    sendNotificationEmail=send_notification,
                    fields="id",
                ).execute()
            except HttpError as e:
                if e.resp.status in (429, 500, 502, 503):
                    raise  # Retry
                handle_http_error(e)
            results.append({"email": email, "permission_id": result["id"]})
        return {"status": "ok", "shared_with": results}
