# De Vierkante Paal — voorbereidingstool

Lokale tool om een aflevering van de podcast rond **Royal Antwerp FC** voor te bereiden.
Ze verzamelt automatisch de feiten en cijfers; de teksten schrijf je zelf.

De tool is verdeeld in **tabbladen** bovenaan: Vorige wedstrijd · Voorbeschouwing ·
Statistieken · Diagnose · Export.

## Wat de tool toont

### Vorige wedstrijd
- **Match-kiezer** bovenaan: standaard de recentste match, maar je kan een oudere kiezen
  (handig bij een uitgestelde opname). Alles op de pagina volgt mee.
- **Opstellingen van beide ploegen op een veldje** met **vaste lijnen** (doelman ·
  verdedigers · verdedigende mid · mid · aanvallende mid · aanvallers) zodat elke formatie
  er consistent uitziet; rugnummers, rating per speler, doelpuntenmakers, bank.
- **Wedstrijdverloop in twee kolommen**: links de thuisploeg, rechts de uitploeg.
- **Teamstatistieken**: balbezit, xG, schoten, grote kansen, passes, duels…
- **Spelerscores** — Sofascore én FotMob automatisch, WhoScored vul je zelf in. Sorteerbaar
  (klik **Gemiddelde** om te zien wie de hoogste score haalde). Knoppen openen de match op
  elke site in een nieuw tabblad.

### Voorbeschouwing
- **Opstelling van de tegenstander** (bevestigde ploeg als die er al is, anders hun vorige).
- **Scheidsrechter** + zijn gemiddelde gele/rode kaarten per match.
- **Reeksen & mijlpalen** (ongeslagen, over/onder X goals, kaarten-reeksen, onderlinge reeksen).
- **Diepere vorm**: laatste 5 W/D/L, goals voor/tegen, clean sheets, ongeslagen-reeks,
  scoren-op-rij, plus thuis/uit-splitsing.
- **Alle onderlinge duels** + grootste zege/nederlaag.
- **Uitgebreid klassement** (W/G/V, doelpunten, saldo, punten).
- **Pro League topschutters & assists** (Antwerp-spelers in het rood).
- **Sterkhouders** van de tegenstander.
- **Afwezigen tegenstander** (blessures/schorsingen) en **connecties** — ex-Antwerp-spelers
  bij de tegenstander en omgekeerd. *Deze twee komen van een aparte knop, zie hieronder.*

### Statistieken
Per speler: wedstrijden, goals, assists, **gele en rode kaarten**, minuten en gemiddelde
Sofascore-rating. **Sorteerbaar** op elke kolom, met het verschil sinds de vorige verversing.
Bovenaan de **geschorste** (mist de volgende match) en geblesseerde Antwerp-spelers.

### Diagnose
Spelers/clubs die de tool niet automatisch kon koppelen tussen de bronnen, plus een
formulier om een **alias** toe te voegen (zodat het voortaan wél lukt).

### Export
Alles als Markdown kopiëren · opslaan als **aflevering** (met eigen notities) ·
**afdrukken / PDF**: opent een afdrukvriendelijke pagina in een nieuw tabblad, waar meteen
het afdrukvenster verschijnt. Kies daar als bestemming **"Opslaan als PDF"** (of
"Microsoft Print to PDF") in plaats van een echte printer.

**Beker- of Europese wedstrijden:** het klassement blijft dat van de Jupiler Pro League
(met een duidelijke melding dat het enkel ter info is). Al de rest werkt voor elke tegenstander.

**Oefenwedstrijden** worden overal genegeerd — in de match-kiezer, de vorm, de onderlinge
duels en alle vergelijkingen.

## Starten

**Eén keer:** dubbelklik **`start.bat`** (± 1 minuut installatie). Het venster sluit vanzelf;
de tool draait daarna **onzichtbaar op de achtergrond** en opent in je browser op
<http://localhost:8756>.

**Handige snelkoppeling:** dubbelklik **`snelkoppeling-maken.bat`**. Dat zet een icoon
*"De Vierkante Paal"* op je bureaublad (opent de tool met één klik, zonder venster) en
vraagt of de tool ook automatisch mag meestarten met Windows. Kies je dat, dan hoef je
nooit meer iets te starten — gewoon de bladwijzer <http://localhost:8756> openen.

**Stoppen:** de tool **sluit zichzelf af** ongeveer anderhalve minuut nadat je het
laatste tabblad sluit. Wil je meteen stoppen, klik dan onderaan op **"✕ Tool
afsluiten"**. Wil je net dat ze altijd op de achtergrond blijft draaien (bv. omdat
ze meestart met Windows), vink dan onderaan **"op de achtergrond laten draaien"** aan —
dan sluit ze niet meer automatisch af.

Vereist (voor deze ontwikkelopstelling): Python 3.11 of nieuwer
([python.org](https://www.python.org/downloads/), vink bij de installatie
"Add Python to PATH" aan).

## Delen met redactieleden

Andere redactieleden hebben **geen Python of installatie nodig**. Er is een
installatieprogramma dat alles meebrengt.

**Het pakket maken (één keer, op deze pc):**

```bash
powershell -ExecutionPolicy Bypass -File installer\bouw-installer.ps1
```

Of alles ineens (Windows + Mac, DVP + Aftrap, na de tests):

```bash
powershell -ExecutionPolicy Bypass -File installer\bouw-alles.ps1
```

Dat haalt een ingebouwde Python + alle onderdelen op, stopt de app erbij en maakt
één bestand: **`installer\uit\Installeer De Vierkante Paal.exe`** (± 25 MB).
Nodig op deze bouw-pc: internet (eenmalig) en Python in PATH.

> **OneDrive-tip:** `installer\build`, `installer\build-mac`, `installer\cache` en
> `installer\uit` zijn samen ± 250 MB tijdelijke bestanden. Zet die vier mappen in
> OneDrive op *"altijd behouden op dit apparaat"* uit, of sluit ze uit van sync.

**Delen:** stuur dat `.exe` (samen met `installer\LEESMIJ-redactie.txt`) via
WeTransfer, Google Drive of OneDrive. Mail blokkeert `.exe`-bijlagen meestal.

**Wat het redactielid doet:** dubbelklikken → bij de SmartScreen-melding
*"Meer informatie" → "Toch uitvoeren"* (het bestand is niet ondertekend) → de
wizard controleert de pc, vraagt een installatiemap, zet alles klaar, maakt een
bureaublad-snelkoppeling en haalt meteen een eerste keer de data op. Verwijderen
kan later via **Windows → Apps**.

Een nieuwe versie uitbrengen = `bouw-installer.ps1` opnieuw draaien en het nieuwe
`.exe` doorsturen; wie het over de vorige installatie heen zet, behoudt zijn
bewaarde afleveringen en data.

### Mac

Er is ook een Mac-versie. Die wordt op deze Windows-pc gebouwd (geen Mac nodig):

```bash
py installer\mac\bouw-mac.py
```

Resultaat: **`installer\uit\De Vierkante Paal (Mac).zip`** (± 75 MB, werkt op Apple
Silicon én Intel). Met `py installer\mac\bouw-mac.py --arm64` krijg je een kleinere
zip (± 38 MB) die enkel op Apple Silicon werkt.

De Mac-gebruiker pakt de zip uit, sleept **De Vierkante Paal.app** naar Programma's
en opent ze (eerste keer: rechtermuisklik → *Open*, of via *Systeeminstellingen →
Privacy en beveiliging → "Toch openen"* — zie `installer\uit\LEESMIJ-mac.txt`).
Op Mac staat de app in de Dock zolang de tool draait; afsluiten via Cmd+Q of de
knop in de tool.

> **Let op:** de Mac-build kan vanaf Windows niet getest worden. Laat iemand met
> een Mac ze één keer proberen voor je ze breed verdeelt.

### Generieke variant ("Aftrap") — zelf een ploeg kiezen

Naast de vaste DVP-versie kan je uit dezelfde broncode een **generieke variant**
bouwen waarin de gebruiker bij de eerste start zelf een ploeg kiest (uit de hoogste
klasse van Engeland, Spanje, Duitsland, Italië, Frankrijk, Nederland, België en
Portugal + de Engelse Championship en de Belgische Challenger Pro League).

```bash
powershell -ExecutionPolicy Bypass -File installer\bouw-installer.ps1 -Variant generiek
py installer\mac\bouw-mac.py --variant generiek
```

Levert **`Installeer Aftrap.exe`** en **`Aftrap (Mac).zip`**. Bij de eerste start
kiest de gebruiker competitie → ploeg, bevestigt de koppeling met Sofascore/FotMob/
Transfermarkt, en de tool haalt de data op. Wisselen van ploeg kan bovenaan; de
bewaarde afleveringen blijven per ploeg gescheiden.

De verschillen tussen de twee varianten zitten volledig in **`merk.json`** (wordt door
het build-script in het pakket gezet). Zonder `merk.json` = de DVP-versie. Beide
kunnen naast elkaar geïnstalleerd staan, maar draaien op dezelfde poort 8756 — dus
één tegelijk gebruiken.

## Gebruik per aflevering

1. Klik **↻ Ververs alles**. Dat gebeurt nu **op de achtergrond** — je ziet bovenaan een
   balkje met de voortgang (Sofascore ✓ · Transfermarkt ✓ · …) en de pagina blijft
   bruikbaar. Als je de tool opent en de data is ouder dan 8u, ververst ze zichzelf.
2. Vul in de tab *Vorige wedstrijd* de WhoScored-cijfers in → **Scores bewaren**.
3. Kopieer alles via *Export* of gebruik **Print / PDF** om je notities mee te nemen.
4. Geef in *Export* de aflevering een titel en klik **Bewaren**.

De verschil-kolom bij de statistieken werkt pas vanaf de tweede verversing.

### De knop "voorbeschouwing"

Blessures/schorsingen van de tegenstander en de ex-speler-connecties vereisen een 10-tal
extra Transfermarkt-pagina's. Die worden **24u gecachet**: *Ververs alles* haalt ze enkel
opnieuw op als ze verouderd zijn of als de tegenstander veranderde. Met de aparte knop
**voorbeschouwing** forceer je een verse ophaling.

## Bewaren als aflevering

Onder *Export* → **Bewaar als aflevering** schrijft de tool het volledige overzicht (plus
je **eigen notities**, als je die invult) weg als een **Markdown-bestand in de map
`afleveringen/`** naast `start.bat` (bestandsnaam = datum + titel), plus een kopie in
`data/dvp.sqlite`. De lijst eronder linkt naar een nette weergave van elke bewaarde aflevering.

## Data & bronnen

Alle data komt van openbare API's/pagina's van Sofascore, FotMob en Transfermarkt, met lage
frequentie opgehaald. Alles wordt lokaal bewaard in `data/dvp.sqlite` en de map
`afleveringen/` — niets gaat naar buiten.

De **opstellingen op het veld komen van Sofascore** (standaard); FotMob wordt enkel gebruikt
als terugval en voor de FotMob-rating in de scoretabel. De interface is donker ("dark mode").

Instellingen (club-id's, seizoen, speler-aliassen) staan in `dvp/config.py`.
De 10 competities voor de generieke variant staan in `dvp/competities.py`;
welke variant er draait wordt bepaald door `dvp/merk.py` (leest `merk.json`).

## Tests

```bash
py -m unittest discover -s tests
```

De scrapers draaien tegen **opgenomen responses** (`tests/fixtures/`), dus geen
internet nodig. Faalt een test na een sitewijziging? `py tests\opnemen.py` vernieuwt
de fixtures. Zie `tests/LEESMIJ.md`.

## Mappen

```
start.bat                 eenmalige installatie + starten (ontwikkelopstelling)
snelkoppeling-maken.bat   bureaublad-icoon + (optioneel) meestarten met Windows
tests/                    unittest-suite (scrapers tegen opgenomen responses)
installer/                installatieprogramma om te delen met redactieleden
  bouw-alles.ps1         tests + alle 4 de deelbestanden in één keer
  bouw-installer.ps1      maakt "Installeer De Vierkante Paal.exe" (Windows)
  installeer.ps1          de installatiewizard (draait op de doel-pc)
  uninstall.ps1           verwijderscript (komt mee in de installatie)
  sfx.cs                  zelf-uitpakkende stub (wordt gecompileerd)
  LEESMIJ-redactie.txt    korte uitleg voor de redactieleden
  assets/aftrap-logo.png  logo voor de generieke variant ("Aftrap")
  mac/bouw-mac.py         maakt de Mac-.zip (op Windows) — -Variant / --variant
  mac/LEESMIJ-mac.txt     korte uitleg voor de Mac-gebruikers
dvp/                      de tool
  config.py               instellingen om aan te passen
  launch.py               onzichtbare starter (server + browser)
  static/logo.png         het logo (header + favicon + snelkoppeling-icoon)
  sources/                ophalen per bron (sofascore, fotmob, transfermarkt, preview)
  mdrender.py             mini Markdown -> HTML (nette afleveringen + print)
  templates/              de webpagina
data/dvp.sqlite           lokale opslag (wordt automatisch aangemaakt)
afleveringen/             bewaarde afleveringen als Markdown-bestand
```
