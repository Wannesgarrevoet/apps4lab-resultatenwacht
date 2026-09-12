"""Agenda-items wegschrijven naar Google Agenda.

Belangrijk: deze module raakt **alleen items aan die ze zelf gemaakt heeft**.
Elk item krijgt een onzichtbaar merkteken mee (`extendedProperties.private`),
en er wordt uitsluitend gezocht op dat merkteken. Je eigen afspraken in
dezelfde agenda blijven dus onaangeroerd, ook als de sync opruimt.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from typing import Any

from kalender_bron import AgendaItem, omschrijving_voor

log = logging.getLogger(__name__)

BRON = "apps4lab-resultatenwacht"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


@dataclass
class Wijzigingen:
    nieuw: list[AgendaItem]
    bijgewerkt: list[AgendaItem]
    verwijderd: list[str]

    @property
    def leeg(self) -> bool:
        return not (self.nieuw or self.bijgewerkt or self.verwijderd)

    def samenvatting(self) -> str:
        return (
            f"{len(self.nieuw)} nieuw, {len(self.bijgewerkt)} bijgewerkt, "
            f"{len(self.verwijderd)} verwijderd"
        )


class GoogleAgenda:
    def __init__(self, agenda_id: str, service_account_json: str, portaallink: str = "") -> None:
        # De Google-bibliotheken zijn alleen nodig als er echt gesynct wordt,
        # daarom pas hier importeren.
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        try:
            gegevens = json.loads(service_account_json)
        except ValueError as exc:
            raise RuntimeError(
                "GOOGLE_SERVICE_ACCOUNT_JSON bevat geen geldige JSON. Plak de volledige "
                "inhoud van het sleutelbestand dat je bij Google gedownload hebt."
            ) from exc

        inloggegevens = service_account.Credentials.from_service_account_info(
            gegevens, scopes=SCOPES
        )
        self.dienst = build("calendar", "v3", credentials=inloggegevens, cache_discovery=False)
        self.agenda_id = agenda_id
        self.portaallink = portaallink
        self.service_account_email = gegevens.get("client_email", "")

    # ------------------------------------------------------------- uitlezen

    def eigen_items(self, van: dt.date, tot: dt.date) -> dict[str, dict[str, Any]]:
        """Alle items in de agenda die door deze sync gemaakt zijn."""
        gevonden: dict[str, dict[str, Any]] = {}
        pagina = None

        while True:
            antwoord = (
                self.dienst.events()
                .list(
                    calendarId=self.agenda_id,
                    privateExtendedProperty=f"bron={BRON}",
                    timeMin=dt.datetime.combine(van, dt.time.min).isoformat() + "Z",
                    timeMax=dt.datetime.combine(tot, dt.time.min).isoformat() + "Z",
                    singleEvents=False,
                    showDeleted=False,
                    maxResults=250,
                    pageToken=pagina,
                )
                .execute()
            )

            for event in antwoord.get("items", []):
                sleutel = (event.get("extendedProperties", {}).get("private", {})).get("sleutel")
                if sleutel:
                    gevonden[sleutel] = event

            pagina = antwoord.get("nextPageToken")
            if not pagina:
                break

        log.info("In de agenda staan al %d items van deze sync", len(gevonden))
        return gevonden

    # -------------------------------------------------------------- schrijven

    def _body(self, item: AgendaItem) -> dict[str, Any]:
        return {
            "summary": item.titel,
            "description": omschrijving_voor(item, self.portaallink),
            "start": {"date": item.start.isoformat()},
            "end": {"date": item.eind_exclusief.isoformat()},
            # Niet als "bezet" tellen: het zijn dagvullende schoolitems.
            "transparency": "transparent",
            "extendedProperties": {
                "private": {
                    "bron": BRON,
                    "sleutel": item.sleutel,
                    "vingerafdruk": item.vingerafdruk,
                    "soort": item.soort,
                }
            },
        }

    def synchroniseer(self, items: list[AgendaItem], opruimen: bool = True) -> Wijzigingen:
        """Zet de agenda gelijk met de lijst items. Raakt niets anders aan."""
        if not items:
            log.warning("Geen items om te synchroniseren; er wordt niets gewijzigd.")
            return Wijzigingen([], [], [])

        van = min(i.start for i in items) - dt.timedelta(days=1)
        tot = max(i.eind for i in items) + dt.timedelta(days=2)
        bestaand = self.eigen_items(van, tot)

        nieuw: list[AgendaItem] = []
        bijgewerkt: list[AgendaItem] = []

        for item in items:
            huidig = bestaand.get(item.sleutel)
            if huidig is None:
                self.dienst.events().insert(
                    calendarId=self.agenda_id, body=self._body(item)
                ).execute()
                nieuw.append(item)
                continue

            eigenschappen = huidig.get("extendedProperties", {}).get("private", {})
            if eigenschappen.get("vingerafdruk") != item.vingerafdruk:
                self.dienst.events().update(
                    calendarId=self.agenda_id, eventId=huidig["id"], body=self._body(item)
                ).execute()
                bijgewerkt.append(item)

        verwijderd: list[str] = []
        if opruimen:
            actueel = {i.sleutel for i in items}
            for sleutel, event in bestaand.items():
                if sleutel in actueel:
                    continue
                self.dienst.events().delete(
                    calendarId=self.agenda_id, eventId=event["id"]
                ).execute()
                verwijderd.append(event.get("summary", sleutel))

        return Wijzigingen(nieuw, bijgewerkt, verwijderd)
