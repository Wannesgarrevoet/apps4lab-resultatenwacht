#!/usr/bin/env python3
"""Zet de inhoud van je .env als secrets en variabelen in je GitHub-repo.

Zo hoef je de wachtwoorden niet met de hand over te typen in de webinterface,
en komen ze nergens in je shell-geschiedenis terecht.

Vereist de GitHub CLI (https://cli.github.com) en een aangemelde account:

    gh auth login
    python scripts/secrets_zetten.py

Het script toont nooit de waarden zelf, alleen welke instelling gezet is.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Gevoelig: gaat als secret naar GitHub (versleuteld, niet leesbaar in de logs).
SECRETS = [
    "A4L_EMAIL",
    "A4L_PASSWORD",
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "MAIL_FROM",
    "MAIL_TO",
]

# Niet gevoelig: gaat als variabele, zodat je ze in de webinterface kunt nalezen.
VARIABELEN = [
    "A4L_SCHOOL_ID",
    "A4L_SCHOOL_CODE",
    "A4L_LEERLINGEN",
    "A4L_VOLG_RAPPORTEN",
    "SMTP_PORT",
    "SMTP_SECURITY",
    "MAIL_FROM_NAAM",
    "MAIL_BIJ_FOUT",
    "MELD_UUR",
    "MELD_DAGEN",
    "TIJDZONE",
]


def lees_env(pad: Path) -> dict[str, str]:
    if not pad.exists():
        sys.exit(f"{pad} bestaat niet. Kopieer eerst .env.example naar .env en vul hem in.")

    instellingen: dict[str, str] = {}
    for regel in pad.read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel or regel.startswith("#") or "=" not in regel:
            continue
        sleutel, waarde = regel.split("=", 1)
        waarde = waarde.strip()
        if not waarde.startswith(("'", '"')):
            waarde = waarde.split(" #", 1)[0]
        instellingen[sleutel.strip()] = waarde.strip().strip("'\"")
    return instellingen


def main() -> int:
    if subprocess.run(["gh", "--version"], capture_output=True).returncode != 0:
        sys.exit("De GitHub CLI (gh) is niet gevonden. Installeer ze via https://cli.github.com")

    env = lees_env(Path(__file__).resolve().parent.parent / ".env")
    fouten = 0

    print("\nSecrets:")
    for naam in SECRETS:
        waarde = env.get(naam, "")
        if not waarde:
            print(f"  {naam:20} overgeslagen (leeg in .env)")
            continue
        # De waarde gaat via stdin, niet via de opdrachtregel: zo staat ze
        # niet in je shell-geschiedenis of in de procestabel.
        resultaat = subprocess.run(
            ["gh", "secret", "set", naam], input=waarde, text=True, capture_output=True
        )
        if resultaat.returncode == 0:
            print(f"  {naam:20} gezet")
        else:
            fouten += 1
            print(f"  {naam:20} FOUT: {resultaat.stderr.strip()[:150]}")

    print("\nVariabelen:")
    for naam in VARIABELEN:
        waarde = env.get(naam, "")
        if not waarde:
            continue
        resultaat = subprocess.run(
            ["gh", "variable", "set", naam, "--body", waarde], capture_output=True, text=True
        )
        if resultaat.returncode == 0:
            print(f"  {naam:20} = {waarde}")
        else:
            fouten += 1
            print(f"  {naam:20} FOUT: {resultaat.stderr.strip()[:150]}")

    if fouten:
        print(f"\n{fouten} instelling(en) zijn niet gelukt. Kijk of je in de juiste map staat")
        print("en of 'gh repo view' jouw repo toont.")
        return 1

    print("\nKlaar. Start nu de workflow één keer handmatig met 'seed' aangevinkt.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
