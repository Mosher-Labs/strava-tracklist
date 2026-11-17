"""OAuth tokens on the data volume, one JSON file per service, mode 0600."""

import json
import os
import tempfile
from pathlib import Path


class AuthError(RuntimeError):
    pass


class TokenFile:
    def __init__(self, path: Path, service: str):
        self._path = path
        self._service = service

    def exists(self) -> bool:
        return self._path.is_file()

    def load(self) -> dict:
        try:
            return json.loads(self._path.read_text())
        except FileNotFoundError:
            raise AuthError(
                f"Not logged in to {self._service}. Run strava-tracklist-cli auth-{self._service.lower()}."
            ) from None

    def save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix='.token-')
        try:
            with os.fdopen(fd, 'w') as handle:
                json.dump(data, handle)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self._path)
        except BaseException:
            os.unlink(tmp)
            raise
