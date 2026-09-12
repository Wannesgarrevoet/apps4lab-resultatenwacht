# Resultatenwacht voor het Apps 4 LAB ouderportaal

Krijg automatisch een e-mail zodra er een nieuw resultaat van je kind op het
ouderportaal verschijnt, in plaats van zelf elke week te gaan kijken.

Deze wacht logt één keer per dag in op het portaal, vergelijkt wat er staat met
wat je al gezien hebt, en mailt je alleen als er echt iets nieuws bij is.

> **Niet officieel.** Dit is een hobbyproject van een ouder, geen product van
> Apps 4 LAB of van een school. Het gebruikt dezelfde login en dezelfde
> gegevens als de website zelf, niets meer.

---

## Inhoud

1. [Wat je krijgt](#wat-je-krijgt)
2. [Wat je nodig hebt](#wat-je-nodig-hebt)
3. [Snelstart met GitHub](#snelstart-met-github-aanbevolen)
4. [Je schoolcode vinden](#je-schoolcode-vinden)
5. [Een mailserver kiezen](#een-mailserver-kiezen)
6. [Alle instellingen](#alle-instellingen)
7. [Het tijdstip aanpassen](#het-tijdstip-aanpassen)
8. [Commando's om te testen](#commandos-om-te-testen)
9. [De schoolkalender in je Google Agenda](#de-schoolkalender-in-je-google-agenda)
10. [Alternatief: op je eigen pc of server](#alternatief-op-je-eigen-pc-of-server)
11. [Hoe het werkt](#hoe-het-werkt)
12. [Privacy en veiligheid](#privacy-en-veiligheid)
13. [Problemen oplossen](#problemen-oplossen)

---

## Wat je krijgt

Eén mail per keer dat er iets nieuws is, met daarin:

* **een waarschuwing bovenaan** als er een **NI** tussen zit, en dat staat dan
  ook in het onderwerp: `Let op, 1x NI - Sam: 3 nieuwe resultaten ...`
* **een kaartje per resultaat**: opdracht, vak, doel, de score met kleur, en de
  feedback van de leerkracht als die er is
* **een tabel onderaan** met per vak hoe vaak elke score deze periode voorkomt

| Vak | A+ | A | B | C | NI | Tot. |
|---|---|---|---|---|---|---|
| Engels | 5 | 2 | 1 | – | – | 8 |
| Wiskunde | – | 1 | – | 1 | 1 | 3 |
| **Totaal** | **5** | **3** | **1** | **1** | **1** | **11** |

De mail is één kolom van maximaal 600 pixels breed, dus ook op een gsm leesbaar
zonder te zoomen.

Krijg je geen mail, dan is er niets nieuws. Resultaten die later nog aangepast
worden, komen apart terug als "aangepast resultaat". Opdrachten die al
klaarstaan maar nog niet verbeterd zijn, leveren geen mail op.

---

## Wat je nodig hebt

* een **ouderaccount** op portaal.apps4lab.be, met e-mailadres en wachtwoord
  (gebruik je Google om aan te melden, zie [Problemen oplossen](#problemen-oplossen))
* een **gratis GitHub-account** (voor de variant die vanzelf blijft draaien)
* toegang tot een **SMTP-server** om mail te versturen, bijvoorbeeld je
  Gmail-account met een app-wachtwoord (zie [Een mailserver kiezen](#een-mailserver-kiezen))

Programmeren hoef je niet te kunnen. Alles gebeurt met invulvelden op de
GitHub-website.

---

## Snelstart met GitHub (aanbevolen)

Zo draait de wacht in de cloud: je pc mag uit staan, en het kost niets.

### Stap 1 — Maak je eigen kopie

Klik bovenaan deze pagina op **Use this template → Create a new repository**.

* Kies bij visibility **Private**. Dat is belangrijk: zo kan niemand anders
  zien wanneer je kind resultaten krijgt.
* Geef ze een naam, bijvoorbeeld `resultatenwacht`.
* Klik **Create repository**.

> Gebruik dus niet de knop *Fork*: een fork van een publieke repo blijft publiek.

### Stap 2 — Zet Actions aan

Ga in je nieuwe repo naar **Actions**. Staat er een knop
*I understand my workflows, go ahead and enable them*, klik die dan aan.

Zie je links *Resultatenwacht* staan met de melding dat de workflow uit staat,
klik dan rechts op **Enable workflow**. In deze voorbeeldrepo staat ze namelijk
bewust uit, omdat daar geen gegevens van een ouder in zitten.

### Stap 3 — Vul je gegevens in

Ga naar **Settings → Secrets and variables → Actions**.

Onder het tabblad **Secrets** klik je op *New repository secret* en voeg je deze
zeven toe, één voor één:

| Secret | Wat je invult |
|---|---|
| `A4L_EMAIL` | je e-mailadres voor het ouderportaal |
| `A4L_PASSWORD` | je wachtwoord voor het ouderportaal |
| `SMTP_HOST` | de mailserver, bv. `smtp.gmail.com` |
| `SMTP_USER` | de loginnaam voor die mailserver |
| `SMTP_PASSWORD` | het wachtwoord of app-wachtwoord voor die mailserver |
| `MAIL_FROM` | het adres waarvan de mail komt |
| `MAIL_TO` | wie de mail krijgt, meerdere adressen met een komma ertussen |

Onder het tabblad **Variables** zet je de dingen die niet geheim zijn:

| Variabele | Voorbeeld | Betekenis |
|---|---|---|
| `A4L_SCHOOL_ID` | `lab_sn` | je schoolcode, [hier te vinden](#je-schoolcode-vinden) |
| `MELD_UUR` | `16` | om hoe laat je de mail wil |
| `MELD_DAGEN` | `1,2,3,4,5` | 1 = maandag ... 7 = zondag |
| `SMTP_PORT` | `587` | poort van je mailserver |
| `SMTP_SECURITY` | `starttls` | `starttls`, `ssl` of `none` |

Alles wat je niet invult, krijgt de standaardwaarde uit de tabel bij
[Alle instellingen](#alle-instellingen).

### Stap 4 — Eerste keer starten

Ga naar **Actions → Resultatenwacht → Run workflow**, vink **seed** aan en
klik op de groene knop.

Deze eerste keer slaat de wacht op wat er nu al op het portaal staat, **zonder
te mailen**. Anders zou je meteen een mail krijgen met alle resultaten van het
hele jaar.

Loopt de run groen af, dan is alles in orde. Je ziet ook een nieuw bestand
`state.json` in je repo verschijnen: dat is het geheugen van de wacht.

### Stap 5 — Klaar

Vanaf nu kijkt de wacht elke dag op het ingestelde uur. Verschijnt er een nieuw
resultaat, dan krijg je een mail.

Wil je meteen zien hoe zo'n mail eruitziet, start de workflow dan nog eens
handmatig met **meld_alles** aangevinkt: dan behandelt hij alles wat er nu staat
als nieuw en stuurt hij één mail met het volledige overzicht.

---

## Je schoolcode vinden

De wacht moet weten van welke school je kind is. Dat zie je aan het webadres van
het portaal:

```
https://portaal.apps4lab.be/sn/ouder/analytics
                            ^^
                            dit is je korte schoolcode
```

Zet dan in je instellingen:

* `A4L_SCHOOL_ID` = `lab_` gevolgd door die code, dus `lab_sn`
* `A4L_SCHOOL_CODE` mag je leeg laten, die wordt automatisch `sn`

Klopt dat niet voor jouw school, dan kun je de exacte waarde opzoeken: open het
portaal in Chrome, druk **F12**, ga naar het tabblad **Application**, klik links
op **Local storage** en zoek de regel `school_id`. Die waarde hoort in
`A4L_SCHOOL_ID`.

Controleer je instellingen achteraf met `python watcher.py --controleer`
(zie [Commando's om te testen](#commandos-om-te-testen)).

---

## Een mailserver kiezen

De wacht verstuurt mail via SMTP. Drie gangbare mogelijkheden:

### Gmail

Werkt goed, maar Google wil een **app-wachtwoord** in plaats van je gewone
wachtwoord. Zet eerst tweestapsverificatie aan op je Google-account, ga dan naar
*Google-account → Beveiliging → App-wachtwoorden*, maak er een aan en gebruik
die zestien tekens als `SMTP_PASSWORD`.

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=jouw.adres@gmail.com
MAIL_FROM=jouw.adres@gmail.com
```

### Je internetprovider of werkadres

De meeste providers hebben een SMTP-server (bv. `smtp.telenet.be`,
`smtp.office365.com`). De gegevens vind je in de instellingen van je
mailprogramma of op de helppagina van je provider.

### Een verzenddienst

Diensten als Brevo, Mailgun of Mailchimp/Mandrill hebben een gratis
startpakket en geven je een SMTP-adres met een sleutel als wachtwoord. Handig
als je geen van bovenstaande hebt.

> Welke je ook kiest: test ze eerst met `python watcher.py --testmail`.

---

## Alle instellingen

Lokaal zet je deze in een `.env`-bestand (kopie van `.env.example`). Op GitHub
worden het secrets en variabelen. De namen zijn dezelfde.

### Portaal

| Naam | Standaard | Betekenis |
|---|---|---|
| `A4L_EMAIL` | *verplicht* | e-mailadres van je ouderaccount |
| `A4L_PASSWORD` | *verplicht* | wachtwoord van je ouderaccount |
| `A4L_SCHOOL_ID` | `lab_sn` | schoolcode in de lange vorm |
| `A4L_SCHOOL_CODE` | uit `A4L_SCHOOL_ID` | schoolcode in de korte vorm |
| `A4L_LEERLINGEN` | alle | enkel deze leerling-id's volgen, met komma's |
| `A4L_VOLG_RAPPORTEN` | `1` | ook melden bij een nieuw rapport |
| `PORTAAL_URL` | automatisch | link onderaan de mail |

### Mail

| Naam | Standaard | Betekenis |
|---|---|---|
| `SMTP_HOST` | *verplicht* | adres van de mailserver |
| `SMTP_PORT` | `587` | poort |
| `SMTP_SECURITY` | `starttls` | `starttls`, `ssl` of `none` |
| `SMTP_USER` | leeg | loginnaam (leeg = niet aanmelden) |
| `SMTP_PASSWORD` | leeg | wachtwoord of app-wachtwoord |
| `MAIL_FROM` | `SMTP_USER` | afzenderadres |
| `MAIL_FROM_NAAM` | `Resultatenwacht` | naam van de afzender |
| `MAIL_TO` | *verplicht* | ontvangers, gescheiden door komma's |
| `MAIL_BIJ_FOUT` | `1` | mail sturen als de controle stukloopt |

### Planning (alleen GitHub Actions)

| Naam | Standaard | Betekenis |
|---|---|---|
| `MELD_UUR` | `16` | uur van de dag, 0 t/m 23; meerdere mag: `8,16` |
| `MELD_DAGEN` | `1,2,3,4,5,6,7` | 1 = maandag ... 7 = zondag |
| `TIJDZONE` | `Europe/Brussels` | tijdzone waarin dat uur geldt |

### Kalendersync (optioneel)

| Naam | Standaard | Betekenis |
|---|---|---|
| `KALENDER_SOORTEN` | `labAThome,lesvrij,evaluatie,uitstap` | welke soorten je in je agenda wil |
| `KALENDER_SCHOOLBREED` | `1` | ook items die voor de hele school gelden |
| `KALENDER_NAAM_IN_TITEL` | `1` | voornaam van je kind voor de titel zetten |
| `KALENDER_OPRUIMEN` | `1` | geschrapte activiteiten ook uit je agenda halen |
| `KALENDER_SCHOOLJAAR` | automatisch | bv. `2026-2027` |
| `KALENDER_UUR` | `6` | uur waarop de sync draait |
| `GOOGLE_AGENDA_ID` | *verplicht* | de agenda waarin gesynchroniseerd wordt |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | *verplicht* | de sleutel van je serviceaccount |

### Overig

| Naam | Standaard | Betekenis |
|---|---|---|
| `STATE_FILE` | `state.json` | waar het geheugen bewaard wordt |

---

## Het tijdstip aanpassen

Zet de variabelen `MELD_UUR` en `MELD_DAGEN` in **Settings → Secrets and
variables → Actions → Variables**. Je hoeft geen bestanden aan te passen.

Enkele voorbeelden:

| Wat je wil | `MELD_UUR` | `MELD_DAGEN` |
|---|---|---|
| Elke dag om 16 uur | `16` | `1,2,3,4,5,6,7` |
| Enkel op schooldagen, om 17 uur | `17` | `1,2,3,4,5` |
| Zondagavond om 20 uur | `20` | `7` |
| Twee keer per dag, om 8 en 16 uur | `8,16` | `1,2,3,4,5,6,7` |

De planning zelf draait elk uur en stopt meteen als het nog niet het juiste
moment is. Dat kost bijna niets en heeft één groot voordeel: je uur blijft
kloppen, ook na de overgang van zomer- naar wintertijd.

Wil je meerdere momenten per dag, zet dan meerdere uren in `MELD_UUR`,
bijvoorbeeld `8,16` voor 's ochtends en 's avonds.

---

## Commando's om te testen

Deze werken op je eigen pc, met Python 3.10 of nieuwer:

```bash
pip install -r requirements.txt
cp .env.example .env          # en dan invullen
```

| Commando | Wat het doet |
|---|---|
| `python watcher.py --controleer` | logt in en toont je kinderen en resultaten, mailt niets |
| `python watcher.py --testmail` | stuurt één proefmail, om je SMTP-instellingen te testen |
| `python watcher.py --dry-run` | toont wat er gemaild zou worden, verstuurt niets |
| `python watcher.py --seed` | slaat de huidige resultaten op zonder te mailen |
| `python watcher.py` | normale controle |
| `python watcher.py --meld-alles` | mailt alles, ook bij een leeg geheugen |
| `python watcher.py --loop 3600` | blijft draaien en controleert elk uur |
| `python kalender.py --toon` | toont welke kalenderitems geselecteerd worden |
| `python kalender.py --dry-run` | toont wat er in je Google Agenda zou veranderen |
| `python kalender.py` | synchroniseert de kalender echt |

Heb je je `.env` ingevuld en wil je die gegevens naar GitHub zetten zonder ze
over te typen:

```bash
gh auth login
python scripts/secrets_zetten.py
```

---

## De schoolkalender in je Google Agenda

Naast de resultaten kan deze repo ook de **jaarkalender** van het portaal in je
Google Agenda zetten: Lab@Home-dagen, vrije dagen, oudercontacten, uitstappen.
Je kiest zelf welke soorten je wil, en je kunt ze rechtstreeks in je bestaande
gezinsagenda laten komen.

Dit is optioneel. Wil je het niet, laat de workflow *Kalendersync* dan gewoon
uitstaan.

### Welke soorten er zijn

De school deelt haar kalender op in zes soorten. Je kiest ze met de variabele
`KALENDER_SOORTEN` (gescheiden door komma's):

| Soort | Wat erin zit |
|---|---|
| `labAThome` | Lab@Home-dagen: de dagen dat je kind thuis werkt |
| `lesvrij` | vrije dagen, verlof, pedagogische studiedagen |
| `evaluatie` | klassenraden, peer review, oudercontacten, rapporten, examendagen |
| `uitstap` | uitstappen, theater- en filmvoorstellingen, stages |
| `infoavond` | infoavonden en lezingen voor ouders |
| `melding` | algemene meldingen en themaweken |

Standaard staan de eerste vier aan. Wil je bijvoorbeeld alleen de vrije dagen en
de oudercontacten, zet dan `KALENDER_SOORTEN=lesvrij,evaluatie`.

### Wat is "relevant voor mijn kind"?

Elke activiteit hangt aan één of meer klassen. De sync houdt alleen de
activiteiten over die aan de klas van je kind hangen, plus de activiteiten die
voor de hele school gelden. Activiteiten van andere klassen komen er nooit in.

Wil je die schoolbrede items niet, zet dan `KALENDER_SCHOOLBREED=0`. Dan blijft
alleen over wat expliciet voor de klas van je kind is.

Heb je meerdere kinderen op school, dan krijgt elk item de voornaam vooraan
(`Sam: Daguitstap`), zodat je in de gezinsagenda meteen ziet over
wie het gaat. Uitzetten kan met `KALENDER_NAAM_IN_TITEL=0`.

### Google klaarzetten

De sync schrijft in je agenda via een **serviceaccount**: een soort robotgebruiker
van Google waarmee je één agenda deelt. Zo hoef je nooit je eigen
Google-wachtwoord ergens in te vullen.

1. Ga naar [console.cloud.google.com](https://console.cloud.google.com) en maak
   een nieuw project (naam maakt niet uit, bv. *Schoolkalender*).
2. Zoek bovenaan naar **Google Calendar API** en klik op **Enable**.
3. Ga naar **APIs & Services → Credentials → Create credentials →
   Service account**. Geef een naam, klik door en maak hem aan.
4. Klik het nieuwe serviceaccount aan, ga naar **Keys → Add key → Create new key
   → JSON**. Er wordt een bestand gedownload. Bewaar dat goed: het is een
   sleutel, geen wachtwoord dat je kunt terugzien.
5. Noteer het e-mailadres van het serviceaccount. Dat ziet eruit als
   `iets@jouw-project.iam.gserviceaccount.com`.
6. Open [Google Agenda](https://calendar.google.com), ga naar de instellingen van
   de agenda waarin je de schoolitems wil, en kies **Delen met bepaalde personen
   → Persoon toevoegen**. Plak daar het adres van het serviceaccount en geef het
   de rechten **Wijzigingen aanbrengen in afspraken**.
7. In diezelfde instellingen, onderaan bij *Agenda integreren*, staat de
   **agenda-ID**. Die heb je zo nodig.

Zet daarna in je repo:

| Secret | Wat je invult |
|---|---|
| `GOOGLE_AGENDA_ID` | de agenda-ID uit stap 7 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | de **volledige inhoud** van het JSON-bestand uit stap 4 |

En als variabelen: `KALENDER_SOORTEN`, `KALENDER_SCHOOLBREED` en `KALENDER_UUR`
(het uur waarop de sync draait, standaard 6).

Zet tot slot de workflow **Kalendersync** aan bij *Actions*, en start ze één keer
handmatig.

### Eerst eens kijken zonder iets te veranderen

```bash
pip install -r requirements.txt -r requirements-agenda.txt
python kalender.py --toon       # toont welke items geselecteerd worden
python kalender.py --dry-run    # toont wat er in je agenda zou veranderen
python kalender.py              # doet het echt
```

`--toon` heeft je Google-gegevens niet nodig. Handig om eerst te kijken of de
juiste items overblijven.

### Veilig voor je eigen afspraken

De sync zet op elk item dat ze aanmaakt een onzichtbaar merkteken, en zoekt
uitsluitend op dat merkteken. Ze kan je eigen afspraken dus niet wijzigen of
verwijderen, ook niet als je alles in je gewone gezinsagenda laat komen.

Verdwijnt een activiteit van de schoolkalender, dan haalt de sync ze ook uit je
agenda. Wil je dat niet, zet dan `KALENDER_OPRUIMEN=0`.

---

## Alternatief: op je eigen pc of server

### Docker

```bash
cp .env.example .env      # invullen
docker compose run --rm resultatenwacht python watcher.py --seed
docker compose up -d
```

De container controleert elk uur en bewaart het geheugen in `./data`.

### Linux met cron

```
0 16 * * *  cd /opt/resultatenwacht && /usr/bin/python3 watcher.py >> wacht.log 2>&1
```

### Windows met Taakplanner

1. Open **Taakplanner → Taak maken**.
2. Tabblad *Triggers*: dagelijks, om 16:00.
3. Tabblad *Acties*: programma `python`, argumenten `watcher.py`, en bij
   *Beginnen in* de map waar je de bestanden hebt staan.
4. Tabblad *Algemeen*: vink *Uitvoeren ongeacht of de gebruiker is aangemeld* aan.

Let op: bij deze drie manieren moet je pc of server aan staan op dat moment.
De GitHub-variant heeft dat probleem niet.

---

## Hoe het werkt

Het portaal is een webapp die zijn gegevens haalt bij een JSON-API:

```
POST /api/auth/login                              {email, password, schoolId}
GET  /api/evaluatie/opvolging/leerling/<id>/Ouder opdrachten, doelen en scores
GET  /api/evaluatie/rapporten/publiek/<id>        gepubliceerde rapporten
GET  /api/kalender/portaal/<schooljaar>           jaarkalender met soort en klassen
```

Elke call heeft het token van de login mee (`Authorization: Bearer ...`) en de
header `X-School-Id`. Het token is een kwartier geldig; de wacht logt daarom bij
elke controle gewoon opnieuw in.

Van elk beoordeeld doel bewaart de wacht **alleen het id en een korte hash** van
score, feedback en datum in `state.json`. Daardoor kan ze zien dat er iets
veranderd is, **zonder de punten van je kind ergens op te slaan**.

| Bestand | Rol |
|---|---|
| `watcher.py` | startpunt: instellingen, commando's, planning |
| `portaal_client.py` | inloggen en gegevens ophalen |
| `resultaten.py` | vergelijken met de vorige keer, geheugen bijhouden |
| `mailer.py` | de mail opstellen en versturen |
| `kalender.py` | startpunt van de kalendersync |
| `kalender_bron.py` | de jaarkalender ophalen en filteren |
| `google_agenda.py` | items in Google Agenda zetten |

---

## Privacy en veiligheid

* **Zet je repo op private.** Anders kan iedereen zien wanneer je kind
  resultaten krijgt. `state.json` bevat geen punten, maar wel tijdstippen.
* **Je wachtwoord staat als secret op GitHub.** GitHub bewaart die versleuteld
  en maskeert ze in de logs. Beheerders van je eigen repo kunnen ze niet
  uitlezen, alleen overschrijven.
* **Je gegevens gaan nergens anders heen.** Alleen naar het portaal zelf en naar
  je eigen mailserver. Er zit geen analytics of externe dienst in.
* **`.env` hoort niet in de repo.** Hij staat in `.gitignore`; laat dat zo.
* Wil je stoppen, verwijder dan gewoon de repo of zet de workflow uit bij
  *Actions → Resultatenwacht → Disable workflow*.

---

## Problemen oplossen

**"Inloggen geweigerd (401)"**
Je e-mailadres of wachtwoord klopt niet, of je schoolcode is verkeerd. Probeer
eerst of je met dezelfde gegevens op de website zelf binnen raakt. De wacht
stopt na één mislukte poging, zodat je account niet geblokkeerd raakt.

**Ik meld me aan met Google**
Dan werkt deze wacht niet zonder meer: hij heeft een e-mailadres met wachtwoord
nodig. Vraag de school of er voor jouw account een gewoon wachtwoord ingesteld
kan worden, of gebruik *wachtwoord vergeten* op de portaalpagina.

**"School ID ontbreekt" of HTTP 400**
`A4L_SCHOOL_ID` is leeg of verkeerd. Zie [Je schoolcode vinden](#je-schoolcode-vinden).

**Geen mail, maar de run is groen**
Meestal betekent dat gewoon: niets nieuws. Kijk in de log van de run; staat er
*Geen nieuwe resultaten*, dan werkt alles. Twijfel je, start de workflow dan
handmatig met **meld_alles** aangevinkt.

**De mail komt in spam terecht**
Gebruik een afzenderadres (`MAIL_FROM`) van hetzelfde domein als je
SMTP-account, en markeer de eerste mail als "geen spam".

**"SMTPAuthenticationError"**
Je mailserver aanvaardt de login niet. Bij Gmail heb je een app-wachtwoord
nodig, niet je gewone wachtwoord. Test met `python watcher.py --testmail`.

**De planning draait niet meer**
GitHub zet geplande workflows stil in repo's waar 60 dagen niets gebeurt. Deze
wacht commit na elke controle haar geheugen, waardoor dat normaal niet gebeurt.
Merk je het toch, ga dan naar Actions en start de workflow één keer handmatig.

**Ik krijg een mail dat de controle mislukt is**
Dan is het portaal onbereikbaar of is er iets veranderd aan de website. De
volgende controle probeert gewoon opnieuw. Blijft het misgaan, maak dan een
issue aan met de foutmelding uit de log.

---

## Licentie

MIT — doe ermee wat je wil. Geen garantie: het portaal kan altijd veranderen.
