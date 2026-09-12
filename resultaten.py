"""Resultaten platslaan, vingerafdrukken maken en vergelijken met de vorige run."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

STATE_VERSION = 1

# Vaste volgorde van de scores in het overzicht; onbekende scores komen erachter.
SCORE_VOLGORDE = ["A+", "A", "B", "C", "NI"]


@dataclass
class Resultaat:
    """Eén beoordeeld labdoel (of één gepubliceerd rapport)."""

    key: str
    soort: str  # "labdoel" of "rapport"
    kind: str
    datum: str = ""
    opdracht: str = ""
    vak: str = ""
    omschrijving: str = ""
    score: str = ""
    feedback: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        ruw = f"{self.score}|{self.feedback}|{self.datum}"
        return hashlib.sha256(ruw.encode("utf-8")).hexdigest()[:16]


def plat_opvolging(kind_naam: str, leerling_id: str, opdrachten: list[dict]) -> list[Resultaat]:
    """Zet de opvolging-API om in losse resultaten, één per beoordeeld labdoel."""
    resultaten: list[Resultaat] = []

    for opdracht in opdrachten:
        code = _tekst(opdracht.get("opdracht_code"))
        titel = _tekst(opdracht.get("titel"))
        opdracht_label = " – ".join(p for p in (code, titel) if p)
        week = _tekst(opdracht.get("projectweek"))

        for doel in opdracht.get("labdoelen") or []:
            score = _tekst(doel.get("score"))
            if not score:
                continue  # opdracht bestaat al, maar is nog niet beoordeeld

            resultaten.append(
                Resultaat(
                    key=f"labdoel:{leerling_id}:{doel.get('labdoel_id')}",
                    soort="labdoel",
                    kind=kind_naam,
                    datum=_tekst(doel.get("datum")),
                    opdracht=opdracht_label,
                    vak=_tekst(doel.get("vak_naam")) or _tekst(opdracht.get("deelproject")),
                    omschrijving=_tekst(doel.get("omschrijving")),
                    score=score,
                    feedback=_tekst(doel.get("feedback")),
                    extra={"projectweek": week},
                )
            )

    return resultaten


def plat_rapporten(kind_naam: str, leerling_id: str, rapporten: list[dict]) -> list[Resultaat]:
    """Gepubliceerde rapporten. De vorm ligt niet vast, dus defensief uitlezen."""
    resultaten: list[Resultaat] = []

    for index, rapport in enumerate(rapporten):
        if not isinstance(rapport, dict):
            continue

        rapport_id = rapport.get("rapport_id") or rapport.get("id") or index
        titel = _tekst(rapport.get("titel") or rapport.get("naam") or rapport.get("periode")) or "Rapport"
        datum = _tekst(rapport.get("datum") or rapport.get("publicatiedatum") or rapport.get("gepubliceerd_op"))

        resultaten.append(
            Resultaat(
                key=f"rapport:{leerling_id}:{rapport_id}",
                soort="rapport",
                kind=kind_naam,
                datum=datum,
                opdracht=titel,
                omschrijving="Er staat een nieuw rapport klaar op het portaal.",
                score="gepubliceerd",
                feedback=_tekst(rapport.get("commentaar")),
            )
        )

    return resultaten


# ---------------------------------------------------------------------- state


def state_laden(pad: Path) -> dict[str, Any]:
    if not pad.exists():
        return {"version": STATE_VERSION, "gezien": {}, "laatste_run": None}

    try:
        state = json.loads(pad.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        log.error("State-bestand %s is onleesbaar (%s); start met een lege staat", pad, exc)
        return {"version": STATE_VERSION, "gezien": {}, "laatste_run": None}

    state.setdefault("gezien", {})
    return state


def state_bewaren(pad: Path, state: dict[str, Any]) -> None:
    """Atomair wegschrijven, zodat een onderbroken run de staat niet sloopt."""
    pad.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(pad.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, pad)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def vergelijk(
    resultaten: list[Resultaat], gezien: dict[str, str]
) -> tuple[list[Resultaat], list[Resultaat]]:
    """Splitst de resultaten in echt nieuwe en sinds vorige keer gewijzigde."""
    nieuw: list[Resultaat] = []
    gewijzigd: list[Resultaat] = []

    for resultaat in resultaten:
        vorige = gezien.get(resultaat.key)
        if vorige is None:
            nieuw.append(resultaat)
        elif vorige != resultaat.fingerprint:
            gewijzigd.append(resultaat)

    sleutel = lambda r: (r.kind, r.datum, r.opdracht, r.omschrijving)
    return sorted(nieuw, key=sleutel), sorted(gewijzigd, key=sleutel)


def _tekst(waarde: Any) -> str:
    if waarde is None:
        return ""
    return str(waarde).strip()


# ------------------------------------------------------------------ overzicht


def normaliseer_score(score: str) -> str:
    """Zet schrijfvarianten om naar de vorm die in het overzicht gebruikt wordt."""
    net = (score or "").strip().upper().replace(" ", "")
    return {"APLUS": "A+", "A PLUS": "A+", "N.I.": "NI", "NI": "NI"}.get(net, net)


def scoreoverzicht(resultaten: list[Resultaat]) -> dict[str, dict]:
    """Telt per kind en per vak hoeveel keer elke score voorkomt.

    Geeft per kind: de kolommen, een rij per vak en de totaalrij.
    Rapporten tellen niet mee, die hebben geen score.
    """
    per_kind: dict[str, dict[str, dict[str, int]]] = {}

    for r in resultaten:
        if r.soort != "labdoel":
            continue
        score = normaliseer_score(r.score)
        if not score:
            continue
        vak = r.vak or "Overig"
        per_kind.setdefault(r.kind, {}).setdefault(vak, {})
        per_kind[r.kind][vak][score] = per_kind[r.kind][vak].get(score, 0) + 1

    overzicht: dict[str, dict] = {}

    for kind, vakken in per_kind.items():
        gevonden = {score for tellingen in vakken.values() for score in tellingen}
        kolommen = [s for s in SCORE_VOLGORDE if s in gevonden]
        kolommen += sorted(gevonden - set(SCORE_VOLGORDE))

        rijen = []
        totalen = {kolom: 0 for kolom in kolommen}
        for vak in sorted(vakken):
            tellingen = {kolom: vakken[vak].get(kolom, 0) for kolom in kolommen}
            for kolom, aantal in tellingen.items():
                totalen[kolom] += aantal
            rijen.append({"vak": vak, "tellingen": tellingen, "totaal": sum(tellingen.values())})

        overzicht[kind] = {
            "kolommen": kolommen,
            "rijen": rijen,
            "totalen": totalen,
            "totaal": sum(totalen.values()),
        }

    return overzicht


def ni_resultaten(resultaten: list[Resultaat]) -> list[Resultaat]:
    """De resultaten met een NI-score (nog niet in orde)."""
    return [r for r in resultaten if normaliseer_score(r.score) == "NI"]
