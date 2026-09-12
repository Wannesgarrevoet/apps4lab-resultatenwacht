"""De jaarkalender van het portaal ophalen en filteren.

Het portaal geeft het volledige schooljaar terug als een lijst van dagen, met
per dag de activiteiten. Elke activiteit heeft een soort (`type`) en de klassen
waarvoor ze geldt. Staat er geen klas bij, dan is ze schoolbreed.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# De soorten die de school gebruikt, met een leesbare naam erbij.
SOORTEN = {
    "labAThome": "Lab@Home",
    "lesvrij": "Vrije dag",
    "evaluatie": "Evaluatie",
    "uitstap": "Uitstap",
    "infoavond": "Infoavond",
    "melding": "Melding",
}

STANDAARD_SOORTEN = ["labAThome", "lesvrij", "evaluatie", "uitstap"]


@dataclass
class AgendaItem:
    """Eén activiteit, klaar om in een agenda gezet te worden."""

    sleutel: str          # uniek en stabiel: waarop we terugvinden wat we zelf gemaakt hebben
    titel: str
    soort: str
    start: dt.date
    eind: dt.date         # laatste dag waarop het item loopt (inclusief)
    beschrijving: str = ""
    kind: str = ""
    klassen: list[str] = field(default_factory=list)
    schoolbreed: bool = False

    @property
    def eind_exclusief(self) -> dt.date:
        """Google verwacht bij dagvullende items de dag ná de laatste dag."""
        return self.eind + dt.timedelta(days=1)

    @property
    def vingerafdruk(self) -> str:
        ruw = f"{self.titel}|{self.beschrijving}|{self.start}|{self.eind}"
        return hashlib.sha256(ruw.encode("utf-8")).hexdigest()[:16]


def schooljaar(vandaag: dt.date | None = None) -> str:
    """Het lopende schooljaar in de vorm die het portaal gebruikt: 2026-2027."""
    vandaag = vandaag or dt.date.today()
    start = vandaag.year if vandaag.month >= 8 else vandaag.year - 1
    return f"{start}-{start + 1}"


def haal_activiteiten(client, jaar: str | None = None) -> dict[str, dict[str, Any]]:
    """Alle activiteiten van het schooljaar, ontdubbeld op id.

    Een activiteit van meerdere dagen komt bij elke dag terug; met het id als
    sleutel houden we er één over.
    """
    jaar = jaar or schooljaar()
    dagen = client.get(f"/kalender/portaal/{jaar}")

    activiteiten: dict[str, dict[str, Any]] = {}
    for dag in dagen if isinstance(dagen, list) else []:
        for activiteit in dag.get("activiteiten") or []:
            if activiteit.get("id"):
                activiteiten[str(activiteit["id"])] = activiteit

    log.info("Kalender %s: %d activiteiten", jaar, len(activiteiten))
    return activiteiten


def _datum(waarde: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat((waarde or "").strip())
    except ValueError:
        return None


def _klassen(activiteit: dict[str, Any]) -> list[str]:
    return [k.strip() for k in (activiteit.get("klassen") or "").split(";") if k.strip()]


def selecteer(
    activiteiten: dict[str, dict[str, Any]],
    kinderen: list[dict[str, Any]],
    soorten: list[str],
    schoolbreed: bool = True,
    titel_per_kind: bool = True,
) -> list[AgendaItem]:
    """Zet de activiteiten om in agenda-items, gefilterd op soort en klas.

    Een activiteit hoort bij een kind als ze voor zijn klas bedoeld is.
    Schoolbrede activiteiten (zonder klas) horen bij iedereen; die komen één
    keer in de agenda, niet één keer per kind.
    """
    gekozen = {s.strip() for s in soorten if s.strip()}
    items: list[AgendaItem] = []

    for activiteit_id, activiteit in sorted(activiteiten.items(), key=lambda p: int(p[0]) if p[0].isdigit() else 0):
        soort = (activiteit.get("type") or "").strip()
        if soort not in gekozen:
            continue

        start = _datum(activiteit.get("startdatum"))
        eind = _datum(activiteit.get("einddatum")) or start
        if not start:
            log.warning("Activiteit %s heeft geen bruikbare startdatum, overgeslagen", activiteit_id)
            continue
        if eind < start:
            eind = start

        titel = (activiteit.get("titel") or "").strip() or SOORTEN.get(soort, soort)
        beschrijving = (activiteit.get("beschrijving") or "").strip()
        klassen = _klassen(activiteit)

        if not klassen:
            if not schoolbreed:
                continue
            items.append(
                AgendaItem(
                    sleutel=f"a4l-{activiteit_id}",
                    titel=titel,
                    soort=soort,
                    start=start,
                    eind=eind,
                    beschrijving=beschrijving,
                    klassen=[],
                    schoolbreed=True,
                )
            )
            continue

        for kind in kinderen:
            klas = (kind.get("klas") or "").strip()
            if not klas or klas not in klassen:
                continue

            naam = (kind.get("voornaam") or "").strip() or str(kind.get("leerling_id"))
            items.append(
                AgendaItem(
                    sleutel=f"a4l-{activiteit_id}-{kind.get('leerling_id')}",
                    titel=f"{naam}: {titel}" if titel_per_kind else titel,
                    soort=soort,
                    start=start,
                    eind=eind,
                    beschrijving=beschrijving,
                    kind=naam,
                    klassen=klassen,
                )
            )

    items.sort(key=lambda i: (i.start, i.titel))
    log.info("Geselecteerd: %d agenda-items (soorten: %s)", len(items), ", ".join(sorted(gekozen)))
    return items


def omschrijving_voor(item: AgendaItem, portaallink: str = "") -> str:
    """De tekst die in het agenda-item komt te staan."""
    regels = []
    if item.beschrijving:
        regels.append(item.beschrijving)
        regels.append("")

    regels.append(f"Soort: {SOORTEN.get(item.soort, item.soort)}")
    if item.klassen:
        regels.append(f"Klas: {', '.join(item.klassen)}")
    elif item.schoolbreed:
        regels.append("Geldt voor de hele school")
    if portaallink:
        regels.append("")
        regels.append(portaallink)

    return "\n".join(regels)
