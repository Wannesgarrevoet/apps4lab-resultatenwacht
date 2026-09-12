#!/usr/bin/env python3
"""Resultatenwacht — verwittigt per e-mail als er nieuwe resultaten op het
Apps 4 LAB ouderportaal verschijnen.

Gebruik:
    python watcher.py                 eenmalige controle
    python watcher.py --seed          staat vullen zonder te mailen (eerste keer)
    python watcher.py --dry-run       tonen wat er gemaild zou worden
    python watcher.py --loop 3600     blijven draaien, elk uur controleren

Instellingen komen uit omgevingsvariabelen (of een .env-bestand ernaast).
Zie .env.example voor de volledige lijst.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import sys
import time
from pathlib import Path

import mailer
import resultaten as res
from portaal_client import LoginError, PortaalClient, PortaalError, with_retries

log = logging.getLogger("resultatenwacht")

HIER = Path(__file__).resolve().parent


def laad_dotenv(pad: Path) -> None:
    """Minimale .env-lezer, zodat er geen extra dependency nodig is."""
    if not pad.exists():
        return
    for regel in pad.read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel or regel.startswith("#") or "=" not in regel:
            continue
        sleutel, waarde = regel.split("=", 1)
        waarde = waarde.strip()
        if not waarde.startswith(("'", '"')):
            waarde = waarde.split(" #", 1)[0].split("	#", 1)[0]  # inline commentaar
        os.environ.setdefault(sleutel.strip(), waarde.strip().strip("'\""))


def vereist(naam: str) -> str:
    waarde = os.environ.get(naam, "").strip()
    if not waarde:
        raise SystemExit(f"Instelling {naam} ontbreekt. Zie .env.example.")
    return waarde


def smtp_config() -> mailer.SmtpConfig:
    afzender = os.environ.get("MAIL_FROM", "").strip() or os.environ.get("SMTP_USER", "").strip()
    ontvangers = tuple(
        adres.strip() for adres in vereist("MAIL_TO").replace(";", ",").split(",") if adres.strip()
    )
    return mailer.SmtpConfig(
        host=vereist("SMTP_HOST"),
        port=int(os.environ.get("SMTP_PORT", "587")),
        security=os.environ.get("SMTP_SECURITY", "starttls").lower(),
        user=os.environ.get("SMTP_USER", "").strip(),
        password=os.environ.get("SMTP_PASSWORD", ""),
        afzender=afzender,
        afzender_naam=os.environ.get("MAIL_FROM_NAAM", "Resultatenwacht"),
        ontvangers=ontvangers,
    )


def controleer(args: argparse.Namespace) -> int:
    state_pad = Path(os.environ.get("STATE_FILE", str(HIER / "state.json")))
    state = res.state_laden(state_pad)

    client = PortaalClient(
        email=vereist("A4L_EMAIL"),
        password=vereist("A4L_PASSWORD"),
        school_id=os.environ.get("A4L_SCHOOL_ID", "lab_sn"),
        school_code=os.environ.get("A4L_SCHOOL_CODE") or None,
    )

    with_retries(client.login)

    if not client.leerlingen:
        log.warning("Geen kinderen gevonden bij deze account.")

    alleen = {k.strip() for k in os.environ.get("A4L_LEERLINGEN", "").split(",") if k.strip()}
    volg_rapporten = os.environ.get("A4L_VOLG_RAPPORTEN", "1") != "0"

    alle: list[res.Resultaat] = []

    for kind in client.leerlingen:
        leerling_id = str(kind.get("leerling_id"))
        if alleen and leerling_id not in alleen:
            continue

        naam = " ".join(p for p in (kind.get("voornaam"), kind.get("naam")) if p) or leerling_id
        opdrachten = with_retries(lambda lid=leerling_id: client.opvolging(lid))
        alle += res.plat_opvolging(naam, leerling_id, opdrachten)

        if volg_rapporten:
            alle += res.plat_rapporten(naam, leerling_id, client.rapporten(leerling_id))

        log.info("%s: %d beoordeelde resultaten opgehaald", naam, len(alle))

    gezien: dict[str, str] = state["gezien"]
    eerste_run = not gezien
    nieuw, gewijzigd = res.vergelijk(alle, gezien)

    if eerste_run and not args.seed and not args.meld_alles:
        log.info(
            "Eerste run: %d bestaande resultaten worden als gekend opgeslagen, geen mail verstuurd.",
            len(alle),
        )
        nieuw, gewijzigd = [], []

    if args.seed:
        log.info("Seed-modus: %d resultaten opgeslagen zonder te mailen.", len(alle))
        nieuw, gewijzigd = [], []

    if nieuw or gewijzigd:
        onderwerp = mailer.onderwerp_voor(nieuw, gewijzigd)
        tekst = mailer.tekst_voor(nieuw, gewijzigd, alle)
        html_body = mailer.html_voor(nieuw, gewijzigd, alle)

        if args.dry_run:
            print(f"\n--- ONDERWERP ---\n{onderwerp}\n\n--- TEKST ---\n{tekst}\n")
            log.info("Dry-run: geen mail verstuurd, staat niet bijgewerkt.")
            return 0

        mailer.verstuur(smtp_config(), onderwerp, tekst, html_body)
    else:
        log.info("Geen nieuwe resultaten.")

    if args.dry_run:
        return 0

    for resultaat in alle:
        gezien[resultaat.key] = resultaat.fingerprint

    state["gezien"] = gezien
    state["laatste_run"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    state["aantal_gekend"] = len(gezien)
    res.state_bewaren(state_pad, state)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verwittigt bij nieuwe resultaten op het LAB-portaal.")
    parser.add_argument("--seed", action="store_true", help="Huidige resultaten opslaan zonder te mailen.")
    parser.add_argument("--dry-run", action="store_true", help="Tonen wat er gemaild zou worden.")
    parser.add_argument("--loop", type=int, metavar="SECONDEN", help="Blijven draaien met dit interval.")
    parser.add_argument("--testmail", action="store_true", help="Eén proefmail sturen en stoppen.")
    parser.add_argument(
        "--controleer", action="store_true",
        help="Inloggen en tonen wat er gevonden wordt, zonder te mailen of op te slaan.",
    )
    parser.add_argument(
        "--meld-alles", action="store_true",
        help="Ook bij een lege staat mailen (alle huidige resultaten gelden dan als nieuw).",
    )
    parser.add_argument("--verbose", action="store_true", help="Meer logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    laad_dotenv(HIER / ".env")

    if args.testmail:
        return _testmail()

    if args.controleer:
        return _controleer_instellingen()

    if not args.loop:
        return _veilig(args)

    log.info("Loop-modus: elke %d seconden controleren.", args.loop)
    while True:
        _veilig(args)
        args.seed = False  # seeden hoeft maar één keer
        time.sleep(args.loop)


def _controleer_instellingen() -> int:
    """Logt in, toont de gevonden kinderen en resultaten en stopt. Verstuurt niets."""
    client = PortaalClient(
        email=vereist("A4L_EMAIL"),
        password=vereist("A4L_PASSWORD"),
        school_id=os.environ.get("A4L_SCHOOL_ID", "lab_sn"),
        school_code=os.environ.get("A4L_SCHOOL_CODE") or None,
    )
    client.login()

    print()
    print(f"Inloggen gelukt als {client.email}")
    print(f"Schoolcode : header {client.school_id!r}, login {client.school_code!r}")
    print(f"Kinderen   : {len(client.leerlingen)}")

    for kind in client.leerlingen:
        leerling_id = str(kind.get("leerling_id"))
        naam = " ".join(p for p in (kind.get("voornaam"), kind.get("naam")) if p) or leerling_id
        gevonden = res.plat_opvolging(naam, leerling_id, client.opvolging(leerling_id))
        print(f"  - {naam} (id {leerling_id}): {len(gevonden)} beoordeelde resultaten")
        for kind_naam, gegevens in res.scoreoverzicht(gevonden).items():
            for rij in gegevens["rijen"]:
                tellingen = ", ".join(f"{k}: {v}" for k, v in rij["tellingen"].items() if v)
                print(f"      {rij['vak']}: {tellingen}")

    ontvangers = os.environ.get("MAIL_TO", "").strip()
    print()
    print(f"Mail zou gaan naar: {ontvangers or '<MAIL_TO is niet ingevuld>'}")
    print("Instellingen zien er goed uit. Test de mail met --testmail.")
    print()
    return 0


def _testmail() -> int:
    """Stuurt één proefmail met verzonnen resultaten, om de SMTP-instellingen te testen."""
    vandaag = dt.date.today().isoformat()
    voorbeeld = [
        res.Resultaat(
            key="test1", soort="labdoel", kind="Proefbericht", datum=vandaag,
            opdracht="TEST A - Proefopdracht", vak="Wiskunde",
            omschrijving="Dit is een testmail van je resultatenwacht.",
            score="A+", feedback="Als je dit ziet, werken de mailinstellingen.",
        ),
        res.Resultaat(
            key="test2", soort="labdoel", kind="Proefbericht", datum=vandaag,
            opdracht="TEST B - Proefopdracht", vak="Engels",
            omschrijving="Zo ziet een NI-waarschuwing eruit.", score="NI",
        ),
    ]
    config = smtp_config()
    mailer.verstuur(
        config,
        "Resultatenwacht: testmail",
        mailer.tekst_voor(voorbeeld, [], voorbeeld),
        mailer.html_voor(voorbeeld, [], voorbeeld),
    )
    log.info("Proefmail verstuurd naar %s", ", ".join(config.ontvangers))
    return 0


def _veilig(args: argparse.Namespace) -> int:
    """Eén controle; fouten worden gelogd en gemeld, niet doodgezwegen."""
    try:
        return controleer(args)
    except LoginError as exc:
        log.error("%s", exc)
        _meld_fout(f"Inloggen op het portaal lukt niet: {exc}")
        return 2
    except (PortaalError, OSError) as exc:
        log.error("Controle mislukt: %s", exc)
        _meld_fout(f"De controle is mislukt: {exc}")
        return 1


def _meld_fout(boodschap: str) -> None:
    """Stuurt optioneel een mail als de wacht zelf stukloopt (MAIL_BIJ_FOUT=1)."""
    if os.environ.get("MAIL_BIJ_FOUT", "0") != "1":
        return
    try:
        mailer.verstuur(
            smtp_config(),
            "Resultatenwacht: controle mislukt",
            f"{boodschap}\n\nDe volgende geplande controle probeert het opnieuw.",
            f"<p>{mailer.esc(boodschap)}</p><p>De volgende geplande controle probeert het opnieuw.</p>",
        )
    except Exception as exc:  # een kapotte foutmail mag de exitcode niet verbergen
        log.error("Foutmelding kon niet gemaild worden: %s", exc)


if __name__ == "__main__":
    sys.exit(main())
