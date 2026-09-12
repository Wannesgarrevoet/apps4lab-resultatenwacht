"""Client voor de Apps 4 LAB ouderportaal-API.

De webapp op portaal.apps4lab.be praat met een JSON-API op apps4lab.be/api.
Elke call heeft twee dingen nodig:
  Authorization: Bearer <access_token>   (15 minuten geldig)
  X-School-Id:   <school id>             (bv. lab_sn)
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://apps4lab.be/api"
DEFAULT_SCHOOL_ID = "lab_sn"

# Let op: de API gebruikt twee schoolcodes. De header X-School-Id draagt de lange
# vorm ("lab_sn"), de loginbody het korte schoolId ("sn").


class PortaalError(RuntimeError):
    """Fout bij het praten met het portaal."""


class LoginError(PortaalError):
    """Inloggen is niet gelukt."""


class PortaalClient:
    def __init__(
        self,
        email: str,
        password: str,
        school_id: str = DEFAULT_SCHOOL_ID,
        api_base: str = DEFAULT_API_BASE,
        timeout: int = 30,
        school_code: str | None = None,
    ) -> None:
        self.email = email
        self.password = password
        self.school_id = school_id
        self.school_code = school_code or school_id.removeprefix("lab_")
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout

        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.leerlingen: list[dict[str, Any]] = []

        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-School-Id": self.school_id,
                "Accept": "application/json",
                "User-Agent": "resultatenwacht/1.0",
            }
        )

    # ------------------------------------------------------------------ login

    def login(self) -> None:
        """Haalt een access token op met e-mailadres en wachtwoord."""
        payload = {"email": self.email, "password": self.password, "schoolId": self.school_code}
        response = self.session.post(
            f"{self.api_base}/auth/login", json=payload, timeout=self.timeout
        )

        if response.status_code == 401:
            raise LoginError("Inloggen geweigerd (401). Controleer e-mailadres en wachtwoord.")
        if response.status_code != 200:
            raise LoginError(
                f"Inloggen mislukt: HTTP {response.status_code} {response.text[:200]}"
            )

        self._store_login(response.json())
        log.info("Ingelogd als %s (%d kind(eren))", self.email, len(self.leerlingen))

    def _store_login(self, body: dict[str, Any]) -> None:
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        self.access_token = _first(data, "access_token", "accessToken", "token")
        self.refresh_token = _first(data, "refresh_token", "refreshToken")

        if not self.access_token:
            raise LoginError("Login gelukt maar er kwam geen access token terug.")

        self.session.headers["Authorization"] = f"Bearer {self.access_token}"

        gebruiker = data.get("user") if isinstance(data.get("user"), dict) else data
        leerlingen = _first(gebruiker, "leerlingen", "kinderen") or []
        if isinstance(leerlingen, list):
            # De foto's zijn base64-blobs van tientallen kB; die hebben we niet nodig.
            self.leerlingen = [
                {k: v for k, v in kind.items() if k != "foto"}
                for kind in leerlingen
                if isinstance(kind, dict)
            ]

    # -------------------------------------------------------------- API-calls

    def get(self, path: str, retry_on_expiry: bool = True) -> Any:
        """GET op de API; logt automatisch opnieuw in als het token verlopen is."""
        if not self.access_token:
            self.login()

        url = f"{self.api_base}/{path.lstrip('/')}"
        response = self.session.get(url, timeout=self.timeout)

        if response.status_code == 401 and retry_on_expiry:
            log.debug("Token verlopen op %s, opnieuw inloggen", path)
            self.login()
            return self.get(path, retry_on_expiry=False)

        if response.status_code != 200:
            raise PortaalError(f"GET {path} gaf HTTP {response.status_code}: {response.text[:200]}")

        try:
            body = response.json()
        except ValueError as exc:
            raise PortaalError(f"GET {path} gaf geen geldige JSON") from exc

        return body.get("data", body) if isinstance(body, dict) else body

    def opvolging(self, leerling_id: str | int) -> list[dict[str, Any]]:
        """Opdrachten met hun labdoelen en scores (het tabblad 'Opvolging')."""
        data = self.get(f"/evaluatie/opvolging/leerling/{leerling_id}/Ouder")
        return data if isinstance(data, list) else []

    def rapporten(self, leerling_id: str | int) -> list[dict[str, Any]]:
        """Gepubliceerde rapporten. Faalt zacht: niet elke school gebruikt dit."""
        try:
            data = self.get(f"/evaluatie/rapporten/publiek/{leerling_id}")
        except PortaalError as exc:
            log.warning("Rapporten ophalen mislukt voor %s: %s", leerling_id, exc)
            return []
        return data if isinstance(data, list) else []


def _first(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if data.get(key):
            return data[key]
    return None


def with_retries(func, attempts: int = 3, delay: int = 20):
    """Voert func uit en probeert opnieuw bij netwerk- of serverfouten."""
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except LoginError:
            raise  # verkeerd wachtwoord lost zich niet op door te herhalen
        except (PortaalError, requests.RequestException) as exc:
            if attempt == attempts:
                raise
            log.warning("Poging %d/%d mislukt (%s); opnieuw over %ds", attempt, attempts, exc, delay)
            time.sleep(delay)
