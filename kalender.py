#!/usr/bin/env python3
"""Kalendersync — zet de schoolkalender in je Google Agenda.

Haalt de jaarkalender van het ouderportaal op, houdt alleen de soorten over die
je zelf gekozen hebt, en zet die in je agenda. Items die later van de
schoolkalender verdwijnen, verdwijnen ook weer uit je agenda.

Gebruik:
    python kalender.py --toon        laat zien wat er geselecteerd wordt
    python kalender.py --dry-run     toon wat er in de agenda zou veranderen
    python kalender.py               synchroniseer echt

Instellingen komen uit omgevingsvariabelen of uit .env; zie .env.example.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import kalender_bron as kb
from mailer import portaal_url
from portaal_client import LoginError, PortaalClient, PortaalError, with_retries
from watcher import laad_dotenv, vereist, HIER

log = logging.getLogger("kalendersync")


def gekozen_soorten() -> list[str]:
    ruw = os.environ.get("KALENDER_SOORTEN", "").strip()
    if not ruw:
        return list(kb.STANDAARD_SOORTEN)

    soorten = [s.strip() for s in ruw.replace(";", ",").split(",") if s.strip()]
    onbekend = [s for s in soorten if s not in kb.SOORTEN]
    if onbekend:
        log.warning(
            "Onbekende soort(en) in KALENDER_SOORTEN: %s. Bekend zijn: %s",
            ", ".join(onbekend), ", ".join(kb.SOORTEN),
        )
    return soorten


def _service_account_sleutel() -> str:
    """De sleutel van het serviceaccount, als tekst of uit een bestand."""
    sleutel = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if sleutel:
        return sleutel

    pad = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_FILE", "").strip()
    if pad:
        bestand = Path(pad)
        if not bestand.is_absolute():
            bestand = HIER / bestand
        if not bestand.exists():
            raise SystemExit(f"Sleutelbestand {bestand} bestaat niet.")
        return bestand.read_text(encoding="utf-8")

    raise SystemExit(
        "Vul GOOGLE_SERVICE_ACCOUNT_JSON in (of GOOGLE_SERVICE_ACCOUNT_JSON_FILE "
        "met het pad naar je sleutelbestand). Zie de handleiding."
    )


def verzamel_items() -> tuple[list[kb.AgendaItem], PortaalClient]:
    client = PortaalClient(
        email=vereist("A4L_EMAIL"),
        password=vereist("A4L_PASSWORD"),
        school_id=os.environ.get("A4L_SCHOOL_ID", "lab_sn"),
        school_code=os.environ.get("A4L_SCHOOL_CODE") or None,
    )
    with_retries(client.login)

    alleen = {k.strip() for k in os.environ.get("A4L_LEERLINGEN", "").split(",") if k.strip()}
    kinderen = [
        kind for kind in client.leerlingen
        if not alleen or str(kind.get("leerling_id")) in alleen
    ]

    jaar = os.environ.get("KALENDER_SCHOOLJAAR", "").strip() or kb.schooljaar()
    activiteiten = with_retries(lambda: kb.haal_activiteiten(client, jaar))

    items = kb.selecteer(
        activiteiten,
        kinderen,
        soorten=gekozen_soorten(),
        schoolbreed=os.environ.get("KALENDER_SCHOOLBREED", "1") != "0",
        titel_per_kind=os.environ.get("KALENDER_NAAM_IN_TITEL", "1") != "0",
    )
    return items, client


def toon(items: list[kb.AgendaItem]) -> int:
    if not items:
        print("Geen items geselecteerd. Controleer KALENDER_SOORTEN.")
        return 0

    per_soort: dict[str, int] = {}
    for item in items:
        per_soort[item.soort] = per_soort.get(item.soort, 0) + 1

    print(f"\n{len(items)} items geselecteerd:")
    for soort, aantal in sorted(per_soort.items(), key=lambda p: -p[1]):
        print(f"  {kb.SOORTEN.get(soort, soort):12} {aantal:3}")

    print()
    for item in items:
        periode = item.start.isoformat()
        if item.eind != item.start:
            periode += f" t/m {item.eind.isoformat()}"
        merk = "school" if item.schoolbreed else (item.kind or "klas")
        print(f"  {periode:24} [{merk:7}] {item.titel}")
    print()
    return 0


def synchroniseer(args: argparse.Namespace) -> int:
    items, _ = verzamel_items()

    if args.toon:
        return toon(items)

    agenda_id = vereist("GOOGLE_AGENDA_ID")
    sleutel = _service_account_sleutel()

    if args.dry_run:
        # Zonder te schrijven: tonen wat er zou gebeuren.
        from google_agenda import GoogleAgenda

        agenda = GoogleAgenda(agenda_id, sleutel, portaal_url())
        van = min(i.start for i in items)
        tot = max(i.eind for i in items)
        bestaand = agenda.eigen_items(van, tot)

        nieuw = [i for i in items if i.sleutel not in bestaand]
        gewijzigd = [
            i for i in items
            if i.sleutel in bestaand
            and bestaand[i.sleutel].get("extendedProperties", {}).get("private", {}).get("vingerafdruk")
            != i.vingerafdruk
        ]
        weg = [e.get("summary", s) for s, e in bestaand.items() if s not in {i.sleutel for i in items}]

        print(f"\nZou aanmaken ({len(nieuw)}):")
        for i in nieuw:
            print(f"  {i.start} {i.titel}")
        print(f"\nZou bijwerken ({len(gewijzigd)}):")
        for i in gewijzigd:
            print(f"  {i.start} {i.titel}")
        print(f"\nZou verwijderen ({len(weg)}):")
        for t in weg:
            print(f"  {t}")
        print()
        return 0

    from google_agenda import GoogleAgenda

    agenda = GoogleAgenda(agenda_id, sleutel, portaal_url())
    wijzigingen = agenda.synchroniseer(
        items, opruimen=os.environ.get("KALENDER_OPRUIMEN", "1") != "0"
    )

    if wijzigingen.leeg:
        log.info("Agenda was al bij: %d items, niets gewijzigd.", len(items))
    else:
        log.info("Agenda bijgewerkt: %s", wijzigingen.samenvatting())
        for item in wijzigingen.nieuw:
            log.info("  nieuw      %s  %s", item.start, item.titel)
        for item in wijzigingen.bijgewerkt:
            log.info("  bijgewerkt %s  %s", item.start, item.titel)
        for titel in wijzigingen.verwijderd:
            log.info("  verwijderd %s", titel)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Zet de schoolkalender in je Google Agenda.")
    parser.add_argument("--toon", action="store_true", help="Toon de selectie, raak de agenda niet aan.")
    parser.add_argument("--dry-run", action="store_true", help="Toon wat er in de agenda zou veranderen.")
    parser.add_argument("--verbose", action="store_true", help="Meer logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    laad_dotenv(HIER / ".env")

    try:
        return synchroniseer(args)
    except LoginError as exc:
        log.error("%s", exc)
        return 2
    except (PortaalError, RuntimeError, OSError) as exc:
        log.error("Synchroniseren mislukt: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
