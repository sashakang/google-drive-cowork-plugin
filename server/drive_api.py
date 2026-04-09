"""Google Drive API operations (shared across all services)."""

from .config import validate_folder, validate_sharing_domain
from .errors import ConfigError
from .workspace_client import WorkspaceClient


class DriveClient(WorkspaceClient):
    def __init__(self):
        super().__init__("drive", "v3")

    def move_to_folder(self, file_id: str, folder_id: str) -> dict:
        if not validate_folder(folder_id):
            raise ConfigError(f"Folder {folder_id} not in allowlist.")

        file = self._execute(
            self.service.files().get(fileId=file_id, fields="parents")
        )
        previous_parents = ",".join(file.get("parents", []))

        self._execute(
            self.service.files().update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields="id, parents",
            )
        )

        return {"status": "ok", "file_id": file_id, "new_folder": folder_id}

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
            result = self._execute(
                self.service.permissions().create(
                    fileId=file_id,
                    body=permission,
                    sendNotificationEmail=send_notification,
                    fields="id",
                )
            )
            results.append({"email": email, "permission_id": result["id"]})
        return {"status": "ok", "shared_with": results}
