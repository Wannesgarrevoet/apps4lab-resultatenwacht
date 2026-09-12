"""E-mail opstellen en versturen via een gewone SMTP-server.

De opmaak is gemaakt voor mailclients: tabellen in plaats van flexbox, alle
stijlen inline, en één kolom van maximaal 600 pixels breed zodat het op een gsm
zonder zoomen leesbaar blijft.
"""

from __future__ import annotations

import html
import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from resultaten import Resultaat, ni_resultaten, normaliseer_score, scoreoverzicht

log = logging.getLogger(__name__)

def portaal_url() -> str:
    """Link naar het ouderportaal van de eigen school.

    Standaard afgeleid uit de schoolcode (sn -> /sn/ouder/analytics); met
    PORTAAL_URL in de instellingen kun je hem volledig zelf bepalen.
    """
    eigen = os.environ.get("PORTAAL_URL", "").strip()
    if eigen:
        return eigen
    code = os.environ.get("A4L_SCHOOL_CODE", "").strip()
    if not code:
        code = os.environ.get("A4L_SCHOOL_ID", "lab_sn").removeprefix("lab_")
    return f"https://portaal.apps4lab.be/{code}/ouder/analytics"

# Tekstkleur en achtergrond per score.
SCORE_KLEUREN = {
    "A+": ("#0f5132", "#d1e7dd"),
    "A": ("#2e7d32", "#e2f0d9"),
    "B": ("#7a5c00", "#fff3cd"),
    "C": ("#8a4b08", "#ffe5d0"),
    "NI": ("#9b1c1c", "#fde2e2"),
}
NEUTRAAL = ("#1f2933", "#e9edf2")


@dataclass
class SmtpConfig:
    host: str
    port: int = 587
    security: str = "starttls"  # starttls | ssl | none
    user: str = ""
    password: str = ""
    afzender: str = ""
    afzender_naam: str = "Resultatenwacht"
    ontvangers: tuple[str, ...] = ()
    timeout: int = 30


def verstuur(config: SmtpConfig, onderwerp: str, tekst: str, html_body: str) -> None:
    bericht = EmailMessage()
    bericht["Subject"] = onderwerp
    bericht["From"] = formataddr((config.afzender_naam, config.afzender))
    bericht["To"] = ", ".join(config.ontvangers)
    bericht["Date"] = formatdate(localtime=True)
    bericht.set_content(tekst)
    bericht.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()

    if config.security == "ssl":
        server = smtplib.SMTP_SSL(config.host, config.port, timeout=config.timeout, context=context)
    else:
        server = smtplib.SMTP(config.host, config.port, timeout=config.timeout)

    with server:
        server.ehlo()
        if config.security == "starttls":
            server.starttls(context=context)
            server.ehlo()
        if config.user:
            server.login(config.user, config.password)
        server.send_message(bericht)

    log.info("Mail verstuurd naar %s", ", ".join(config.ontvangers))


# ------------------------------------------------------------------ onderwerp


def onderwerp_voor(nieuw: list[Resultaat], gewijzigd: list[Resultaat]) -> str:
    kinderen = sorted({r.kind for r in nieuw + gewijzigd})
    wie = " en ".join(kinderen) if kinderen else "je kind"

    delen = []
    if nieuw:
        delen.append("1 nieuw resultaat" if len(nieuw) == 1 else f"{len(nieuw)} nieuwe resultaten")
    if gewijzigd:
        delen.append(
            "1 aangepast resultaat" if len(gewijzigd) == 1
            else f"{len(gewijzigd)} aangepaste resultaten"
        )

    ni = ni_resultaten(nieuw + gewijzigd)
    kop = f"Let op, {len(ni)}x NI - " if ni else ""

    return f"{kop}{wie}: {' en '.join(delen)} op het LAB-portaal"


# ---------------------------------------------------------------- platte tekst


def tekst_voor(
    nieuw: list[Resultaat], gewijzigd: list[Resultaat], alle: list[Resultaat] | None = None
) -> str:
    regels: list[str] = []
    ni = ni_resultaten(nieuw + gewijzigd)

    if ni:
        regels.append("!! LET OP - NI-SCORE !!")
        for r in ni:
            regels.append(f"   {r.kind}: {r.omschrijving or r.opdracht} ({r.vak})")
        regels.append("")

    for titel, groep in (("NIEUWE RESULTATEN", nieuw), ("AANGEPASTE RESULTATEN", gewijzigd)):
        if not groep:
            continue
        regels.append(titel)
        regels.append("=" * len(titel))
        for r in groep:
            regels.append(f"\n{r.kind} - {r.datum or 'geen datum'}")
            regels.append(f"  Opdracht : {r.opdracht or '-'}")
            regels.append(f"  Vak      : {r.vak or '-'}")
            regels.append(f"  Doel     : {r.omschrijving or '-'}")
            regels.append(f"  Score    : {r.score}")
            if r.feedback:
                regels.append(f"  Feedback : {r.feedback}")
        regels.append("")

    for kind, gegevens in scoreoverzicht(alle or []).items():
        kolommen = gegevens["kolommen"]
        breedte = max([len(rij["vak"]) for rij in gegevens["rijen"]] + [10])
        regels.append(f"OVERZICHT DEZE PERIODE - {kind}")
        regels.append(
            "  " + "Vak".ljust(breedte) + "".join(k.rjust(6) for k in kolommen) + "totaal".rjust(8)
        )
        for rij in gegevens["rijen"]:
            regels.append(
                "  " + rij["vak"].ljust(breedte)
                + "".join(str(rij["tellingen"][k] or "-").rjust(6) for k in kolommen)
                + str(rij["totaal"]).rjust(8)
            )
        regels.append(
            "  " + "Totaal".ljust(breedte)
            + "".join(str(gegevens["totalen"][k]).rjust(6) for k in kolommen)
            + str(gegevens["totaal"]).rjust(8)
        )
        regels.append("")

    regels.append(f"Alles bekijken: {portaal_url()}")
    return "\n".join(regels)


# ----------------------------------------------------------------------- HTML


def html_voor(
    nieuw: list[Resultaat], gewijzigd: list[Resultaat], alle: list[Resultaat] | None = None
) -> str:
    ni = ni_resultaten(nieuw + gewijzigd)

    inhoud = []
    if ni:
        inhoud.append(_waarschuwing(ni))
    if nieuw:
        inhoud.append(_kaarten("Nieuwe resultaten", nieuw))
    if gewijzigd:
        inhoud.append(_kaarten("Aangepaste resultaten", gewijzigd))
    for kind, gegevens in scoreoverzicht(alle or []).items():
        inhoud.append(_overzichtstabel(kind, gegevens))

    body = "".join(inhoud)
    ondertitel = esc(_kinderen(nieuw + gewijzigd))
    link = portaal_url()

    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>Nieuwe resultaten</title>
<style>
  @media only screen and (max-width:480px) {{
    .omhulsel {{ padding:12px 8px !important; }}
    .blok {{ padding:4px 14px 18px !important; }}
    .titel {{ font-size:19px !important; }}
    .knop {{ display:block !important; text-align:center !important; }}
    .cel {{ padding:9px 4px !important; font-size:14px !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:#eef1f5;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
  style="background:#eef1f5;">
 <tr><td align="center" class="omhulsel" style="padding:24px 12px;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0"
    style="width:100%;max-width:600px;background:#ffffff;border-radius:14px;overflow:hidden;
    box-shadow:0 1px 3px rgba(16,24,40,.12);font-family:-apple-system,BlinkMacSystemFont,
    'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1f2933;">

   <tr><td style="padding:22px 24px;background:#1565c0;">
    <div class="titel" style="font-size:21px;font-weight:700;color:#ffffff;line-height:1.3;">
     Nieuwe resultaten op het LAB-portaal</div>
    <div style="margin-top:4px;font-size:14px;color:#cfe0f5;">{ondertitel}</div>
   </td></tr>

   <tr><td class="blok" style="padding:4px 24px 24px;">
    {body}
    <div style="margin-top:26px;">
     <a href="{link}" class="knop" style="display:inline-block;padding:14px 22px;
       background:#1565c0;color:#ffffff;text-decoration:none;border-radius:8px;
       font-weight:600;font-size:16px;">Bekijk op het portaal</a>
    </div>
   </td></tr>

   <tr><td style="padding:16px 24px;background:#f7f9fb;border-top:1px solid #e4e9ef;
     font-size:12px;color:#68758a;line-height:1.5;">
    Automatisch bericht van je resultatenwacht.
   </td></tr>

  </table>
 </td></tr>
</table>
</body></html>"""


def _waarschuwing(ni: list[Resultaat]) -> str:
    regels = "".join(
        f'<li style="margin:6px 0;">{esc(r.omschrijving or r.opdracht)}'
        f'<span style="color:#7a2020;"> &mdash; {esc(r.vak or r.kind)}</span></li>'
        for r in ni
    )
    meervoud = "resultaten staan" if len(ni) > 1 else "resultaat staat"

    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
      style="margin-top:22px;background:#fde2e2;border-left:5px solid #d92d20;border-radius:8px;">
     <tr><td style="padding:16px 18px;">
      <div style="font-size:16px;font-weight:700;color:#9b1c1c;">
       Let op: {len(ni)} {meervoud} op NI</div>
      <ul style="margin:8px 0 0;padding-left:20px;font-size:15px;color:#7a2020;line-height:1.5;">
       {regels}</ul>
     </td></tr>
    </table>"""


def _kaarten(titel: str, groep: list[Resultaat]) -> str:
    kaarten = []

    for r in groep:
        kop = " &middot; ".join(x for x in (esc(r.datum), esc(r.vak), esc(r.kind)) if x)
        feedback = (
            f'<div style="margin-top:10px;padding:10px 12px;background:#f4f6f9;border-radius:6px;'
            f'font-size:14px;color:#3e4c59;line-height:1.5;">{esc(r.feedback)}</div>'
            if r.feedback else ""
        )
        kaarten.append(f"""
     <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="margin-top:12px;border:1px solid #e4e9ef;border-radius:10px;">
      <tr><td style="padding:16px 18px;">
       <div style="font-size:12px;color:#68758a;text-transform:uppercase;
         letter-spacing:.5px;">{kop}</div>
       <div style="margin-top:6px;font-size:16px;font-weight:600;line-height:1.4;">
        {esc(r.opdracht) or '&mdash;'}</div>
       <div style="margin-top:4px;font-size:15px;color:#3e4c59;line-height:1.5;">
        {esc(r.omschrijving)}</div>
       <div style="margin-top:12px;">{_badge(r.score)}</div>
       {feedback}
      </td></tr>
     </table>""")

    return f"""
    <h2 style="margin:26px 0 2px;font-size:13px;font-weight:700;text-transform:uppercase;
      letter-spacing:.8px;color:#68758a;">{esc(titel)} ({len(groep)})</h2>
    {''.join(kaarten)}"""


def _overzichtstabel(kind: str, gegevens: dict) -> str:
    kolommen = gegevens["kolommen"]

    koppen = "".join(
        f'<th class="cel" style="padding:10px 6px;text-align:center;font-size:13px;'
        f'font-weight:700;color:{SCORE_KLEUREN.get(k, NEUTRAAL)[0]};'
        f'border-bottom:2px solid #e4e9ef;">{esc(k)}</th>'
        for k in kolommen
    )

    rijen = []
    for rij in gegevens["rijen"]:
        cellen = "".join(
            f'<td class="cel" style="padding:10px 6px;text-align:center;font-size:15px;'
            f'border-bottom:1px solid #eef1f5;{_celkleur(k, rij["tellingen"][k])}">'
            f'{rij["tellingen"][k] or "&ndash;"}</td>'
            for k in kolommen
        )
        rijen.append(
            f'<tr><td class="cel" style="padding:10px 8px;font-size:15px;font-weight:600;'
            f'border-bottom:1px solid #eef1f5;">{esc(rij["vak"])}</td>{cellen}'
            f'<td class="cel" style="padding:10px 6px;text-align:center;font-size:15px;'
            f'color:#68758a;border-bottom:1px solid #eef1f5;">{rij["totaal"]}</td></tr>'
        )

    totaalcellen = "".join(
        f'<td class="cel" style="padding:11px 6px;text-align:center;font-size:15px;'
        f'font-weight:700;">{gegevens["totalen"][k] or "&ndash;"}</td>'
        for k in kolommen
    )

    return f"""
    <h2 style="margin:30px 0 2px;font-size:13px;font-weight:700;text-transform:uppercase;
      letter-spacing:.8px;color:#68758a;">Overzicht deze periode &mdash; {esc(kind)}</h2>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
      style="margin-top:10px;border:1px solid #e4e9ef;border-radius:10px;
      border-collapse:separate;border-spacing:0;overflow:hidden;">
     <tr style="background:#f7f9fb;">
      <th class="cel" style="padding:10px 8px;text-align:left;font-size:13px;font-weight:700;
        color:#68758a;border-bottom:2px solid #e4e9ef;">Vak</th>
      {koppen}
      <th class="cel" style="padding:10px 6px;text-align:center;font-size:13px;font-weight:700;
        color:#68758a;border-bottom:2px solid #e4e9ef;">Tot.</th>
     </tr>
     {''.join(rijen)}
     <tr style="background:#f7f9fb;">
      <td class="cel" style="padding:11px 8px;font-size:15px;font-weight:700;">Totaal</td>
      {totaalcellen}
      <td class="cel" style="padding:11px 6px;text-align:center;font-size:15px;
        font-weight:700;">{gegevens["totaal"]}</td>
     </tr>
    </table>"""


def _celkleur(score: str, aantal: int) -> str:
    if not aantal:
        return "color:#c3cbd6;"
    voorgrond, achtergrond = SCORE_KLEUREN.get(score, NEUTRAAL)
    return f"color:{voorgrond};background:{achtergrond};font-weight:700;"


def _badge(score: str) -> str:
    voorgrond, achtergrond = SCORE_KLEUREN.get(normaliseer_score(score), NEUTRAAL)
    return (
        f'<span style="display:inline-block;padding:5px 16px;border-radius:20px;'
        f'background:{achtergrond};color:{voorgrond};font-weight:700;font-size:16px;">'
        f"{esc(score)}</span>"
    )


def _kinderen(resultaten: list[Resultaat]) -> str:
    kinderen = sorted({r.kind for r in resultaten})
    return " en ".join(kinderen) if kinderen else ""


def esc(waarde: str) -> str:
    return html.escape(waarde or "", quote=True)
