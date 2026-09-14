#!/usr/bin/env python3
"""Beslist of een geplande run nu aan de beurt is.

GitHub voert geplande workflows uit wanneer het uitkomt: bij drukte starten ze
uren te laat, of vallen ze helemaal weg. Een planning "elk uur" draait in de
praktijk soms maar een handvol keer per dag, op willekeurige tijdstippen.
Nakijken of het nu precies 16 uur is, werkt daardoor niet: de run van 16 uur
bestaat dan gewoon niet.

Daarom werken we met momenten. We zoeken het laatste geplande moment dat al
voorbij is (bijvoorbeeld vandaag 16:00) en kijken of dat al verwerkt werd.
Start een run pas om 18:42, dan pakt ze het moment van 16:00 alsnog op. Was dat
moment al verwerkt, dan stopt ze meteen.

Gebruikt enkel de standaardbibliotheek, zodat de beslissing valt voor er iets
geïnstalleerd moet worden.

    python3 planning.py controleer --taak resultaten --uren 16 --dagen 1,2,3,4,5 \\
        --tijdzone Europe/Brussels --state state.json [--handmatig]
    python3 planning.py markeer --taak resultaten --state state.json \\
        --moment 2026-09-14T16:00:00+02:00 --gelukt true
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

# Zo ver kijken we terug naar een gemist moment. Ruim genoeg voor een
# wekelijkse planning, zonder oude momenten eindeloos te blijven inhalen.
TERUGKIJKEN_DAGEN = 8


def lees_getallen(tekst: str, minimum: int, maximum: int, naam: str) -> list[int]:
    getallen = set()
    for deel in (tekst or "").replace(";", ",").split(","):
        deel = deel.strip()
        if not deel:
            continue
        try:
            getal = int(deel)
        except ValueError:
            raise SystemExit(f"{naam}: '{deel}' is geen getal.")
        if not minimum <= getal <= maximum:
            raise SystemExit(f"{naam}: {getal} ligt niet tussen {minimum} en {maximum}.")
        getallen.add(getal)
    if not getallen:
        raise SystemExit(f"{naam} is leeg.")
    return sorted(getallen)


def laatste_moment(nu: dt.datetime, uren: list[int], dagen: list[int]) -> dt.datetime | None:
    """Het meest recente geplande moment dat niet in de toekomst ligt."""
    for terug in range(TERUGKIJKEN_DAGEN):
        dag = (nu - dt.timedelta(days=terug)).date()
        if dag.isoweekday() not in dagen:
            continue
        for uur in sorted(uren, reverse=True):
            moment = dt.datetime.combine(dag, dt.time(hour=uur), tzinfo=nu.tzinfo)
            if moment <= nu:
                return moment
    return None


def beslis(
    nu: dt.datetime,
    uren: list[int],
    dagen: list[int],
    planning: dict,
    handmatig: bool = False,
) -> dict[str, str]:
    """Geeft terug of er gedraaid moet worden, voor welk moment, en waarom."""
    moment = laatste_moment(nu, uren, dagen)
    moment_tekst = moment.isoformat() if moment else ""
    eerste_poging = "nee" if planning.get("geprobeerd") == moment_tekst else "ja"

    if handmatig:
        return {"draaien": "ja", "moment": moment_tekst, "eerste_poging": "ja",
                "reden": "Handmatig gestart, dus we draaien."}

    if moment is None:
        return {"draaien": "nee", "moment": "", "eerste_poging": "nee",
                "reden": "Er ligt geen gepland moment in de voorbije dagen."}

    verwerkt = planning.get("verwerkt")
    if verwerkt and dt.datetime.fromisoformat(verwerkt) >= moment:
        return {"draaien": "nee", "moment": moment_tekst, "eerste_poging": "nee",
                "reden": f"Het moment van {moment:%d/%m %H:%M} is al verwerkt."}

    te_laat = nu - moment
    uitleg = f"Moment van {moment:%d/%m %H:%M} is nog niet verwerkt"
    if te_laat > dt.timedelta(minutes=59):
        uitleg += f" (deze run start {int(te_laat.total_seconds() // 60)} minuten later)"
    return {"draaien": "ja", "moment": moment_tekst, "eerste_poging": eerste_poging,
            "reden": uitleg + ", dus we draaien."}


# ---------------------------------------------------------------------- state


def lees_state(pad: Path) -> dict:
    if not pad.exists():
        return {}
    try:
        return json.loads(pad.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def schrijf_state(pad: Path, state: dict) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(pad.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, pad)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def markeer(state: dict, taak: str, moment: str, gelukt: bool) -> dict:
    """Noteert dat een moment geprobeerd is, en verwerkt als het gelukt is.

    Mislukt een run, dan blijft het moment open en probeert de volgende run
    het opnieuw. Via "geprobeerd" weten we dat het niet meer de eerste poging
    is, zodat een foutmelding maar één keer per moment gemaild wordt.
    """
    if not moment:
        return state

    planning = state.setdefault("planning", {}).setdefault(taak, {})
    planning["geprobeerd"] = moment

    if gelukt:
        vorige = planning.get("verwerkt")
        if not vorige or dt.datetime.fromisoformat(moment) > dt.datetime.fromisoformat(vorige):
            planning["verwerkt"] = moment

    return state


# ------------------------------------------------------------------------ cli


def naar_github_output(waarden: dict[str, str]) -> None:
    uitvoer = os.environ.get("GITHUB_OUTPUT")
    if not uitvoer:
        return
    with open(uitvoer, "a", encoding="utf-8") as fh:
        for sleutel in ("draaien", "moment", "eerste_poging"):
            fh.write(f"{sleutel}={waarden[sleutel]}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Beslist of een geplande run aan de beurt is.")
    sub = parser.add_subparsers(dest="actie", required=True)

    c = sub.add_parser("controleer", help="Moet er nu gedraaid worden?")
    c.add_argument("--taak", required=True)
    c.add_argument("--uren", required=True, help="bv. 16 of 8,16")
    c.add_argument("--dagen", default="1,2,3,4,5,6,7", help="1 = maandag ... 7 = zondag")
    c.add_argument("--tijdzone", default="Europe/Brussels")
    c.add_argument("--state", required=True)
    c.add_argument("--handmatig", action="store_true")

    m = sub.add_parser("markeer", help="Noteer dat een moment verwerkt is.")
    m.add_argument("--taak", required=True)
    m.add_argument("--state", required=True)
    m.add_argument("--moment", default="")
    m.add_argument("--gelukt", default="true")

    args = parser.parse_args()
    pad = Path(args.state)

    if args.actie == "controleer":
        try:
            zone = ZoneInfo(args.tijdzone)
        except Exception:
            raise SystemExit(
                f"Tijdzone '{args.tijdzone}' niet gevonden. Klopt de naam (bv. Europe/Brussels)? "
                "Op Windows heb je daarvoor ook het pakket tzdata nodig: pip install tzdata"
            )
        nu = dt.datetime.now(zone)
        uren = lees_getallen(args.uren, 0, 23, "uren")
        dagen = lees_getallen(args.dagen, 1, 7, "dagen")
        planning = lees_state(pad).get("planning", {}).get(args.taak, {})

        uitslag = beslis(nu, uren, dagen, planning, handmatig=args.handmatig)
        print(f"Nu: {nu:%a %d/%m %H:%M} ({args.tijdzone}). Ingesteld: uur {args.uren}, dagen {args.dagen}.")
        print(uitslag["reden"])
        naar_github_output(uitslag)
        return 0

    gelukt = args.gelukt.strip().lower() in ("true", "1", "ja", "success")
    state = markeer(lees_state(pad), args.taak, args.moment, gelukt)
    if args.moment:
        schrijf_state(pad, state)
        print(f"{args.taak}: moment {args.moment} {'verwerkt' if gelukt else 'mislukt, volgende run probeert opnieuw'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
