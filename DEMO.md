# Heerbaart-demo: klantvraag → NX → resultaten

Dit is de centrale bron voor scope, flow, afspraken, werkvolgorde en voortgang van
`heerbaart-demo` en de naastgelegen `heerbaart-app`. Het vervangt de eerdere
PLAN.md, TODO.md en FLOW.md in deze repository. Het app-plan is alleen nog
achtergrond bij de gebouwde UI-preview; technische READMEs beschrijven de
bestaande implementatie. Bij een verschil geldt dit document voor het doel;
de code en uitgevoerde controles bepalen wat werkelijk gereed is.

**Laatste codecontrole: 16 september 2026. Huidige fase: 1 — lokaal verbinden.**
Beide servers gaan nu op deze Windows-laptop draaien. NetBird volgt later en
is geen voorwaarde voor de lokale demo. De volledige keten werkt nog niet.

## 1. Doel en vaste afspraken

- Eén familie: **Elster Rev.D**, sleutel `elster-rev-d`, de bestaande enkelbladige PDF.
- Een achtcijferig artikelnummer kiest één van de 18 uitgelezen tabelregels.
  `DT`, `FA`, `DR`, `FR`, `FB`, `DS`, `DL` komen uit die regel, in millimeters.
  Extractie bewaart de afgedrukte volgorde, klasse, schedule en nominale waarden;
  geen hardcoded vervanging of afgeleide tabelwaarden.
- BASELINE is een zelfstandig familiesjabloon met de afmetingen van de eerste
  tabelregel. Het is geen verkoopartikel. Artikelen krijgen eigen bestanden.
- Eén materiaal: de ERPNext-displaynaam wordt rechtstreeks als NX-materiaalnaam
  gebruikt. De exacte naam en dichtheid moeten nog worden vastgelegd.
- De programmeur programmeert BASELINE in NX, slaat op, sluit de relevante
  bestanden en klikt in de app op **Programmering gereed — genereer artikel**.
  Vertrouw deze bevestiging met de bestaande eenvoudige bestands/setupcontroles;
  voeg geen apart CAM-goedkeuringssysteem toe.
- Toon echte voortgang en retourneer verse NX-bewerkingstijden, product- en
  ruwgewicht, werkelijke simulatie-uitkomst en geposte NC-bestanden.
- ERPNext levert klanten/materialen en ondersteunt de bestaande klantaanmaak.
  ERP-eindartikelen, ERP-verkoopoffertes en verkoopprijscalculatie vallen buiten
  deze POC. Bestaande ERPNext-, S3- en databasevoorzieningen blijven bruikbaar;
  twee lokale servers betekent niet dat alle externe diensten lokaal worden.
- Behoud de seriële Python-worker, lokale familiebestanden, HTTP-koppeling en
  NX-processen per stap. Geen nieuwe queue-dienst, generiek familieplatform,
  baselineversiesysteem of NX-container nodig.
- Hergebruik STAP1–11, de associatieve structuur en bestaande machine/kaakstrategie.
  Behoud NX-save/heropen-grenzen. Oorspronkelijke bronprojecten blijven ongemoeid.

## 2. Voortgang bijhouden

Gebruik de checklist-ID's hieronder in werknotities. Vink een taak alleen af als
het genoemde resultaat is aangetoond; code aanwezig is geen bewijs van een
geslaagde NX-run. Zet bij een blokkade het taak-ID, de oorzaak en de volgende
actie in het logboek. Werk dit document bij bij wijzigingen aan scope, contract
of status; maak geen nieuwe parallelle PLAN/TODO/FLOW aan.

| Fase | Status | Gereed wanneer |
| --- | --- | --- |
| 0. Inventarisatie en consolidatie | Gereed | Code, lokale data en gaps gecontroleerd; één voortgangsdocument |
| 1. Lokaal verbinden | Open | App, NX-service en callbacks bereikbaar; starttoestand vastgelegd |
| 2. Echte workflow | Open | Aanvraag → programmeeroverdracht → eigen artikel, met echte stappen |
| 3. NX-afwerking | Open | Verse CAM, gecontroleerde tijden/gewichten, NC en simulatie |
| 4. Resultaten en live UI | Open | Resultaten opgeslagen, weergegeven en downloadbaar; herbezorging werkt |
| 5. Einddemo | Open | Beide scenario's en foutcontroles aantoonbaar geslaagd |

### Gecontroleerde uitgangssituatie

| Onderdeel | Aanwezig / bewijs | Wat nog ontbreekt |
| --- | --- | --- |
| ERP/S3/offerte | [ERP](../heerbaart-app/src/server/erp.ts), [storage](../heerbaart-app/src/server/storage.ts), [aanmaakactie](../heerbaart-app/src/app/(app)/app/quotation-form/actions.ts) | Lokale bereikbaarheid controleren; artikelnummer en nieuwe workflow aansluiten |
| Live verzending | Stuurt offerte-ID als job-ID, PDF, materiaalnaam en aantal | Geen actie/artikelnummer; start standaard opnieuw `baseline`; verwijdert offerte/PDF bij verzendfout |
| UI-preview | [quotation-preview.tsx](../heerbaart-app/src/components/offertes/quotation-preview.tsx), route `/app/quotation-preview` | Voorbeeldwaarden, timers, lokale vrijgave en voorbeeld-NC; niet verbonden met NX |
| Herbruikbare UI | [quotation-views.tsx](../heerbaart-app/src/components/offertes/quotation-views.tsx), request-form, drawing-field en operation-fields | Live detailpagina gebruikt nog eenvoudige weergave; slepen heeft nog geen live opslagactie |
| NX-basis | [pipeline.py](service/pipeline.py), [nx/entry.py](service/nx/entry.py), [variant.py](service/nx/variant.py), [setup](service/nx/setup/README.md) | Artikelpad eindigt bij clone → update → refresh; geen automatische afwerking |
| Worker/API | [api](service/api/main.py), [worker](service/api/worker.py), [notifier](service/api/notifier.py) | Worker laat materiaal/aantal en pipeline-output vallen; alleen vier statussen, geen stappen/resultaten |
| App-callbacks | [status](../heerbaart-app/src/app/api/nx/status/route.ts), [result](../heerbaart-app/src/app/api/nx/result/route.ts) | `COMPLETED` wordt ten onrechte `READY`; resultaat logt alleen `jobId/output`; geen sleutel-/payloadcontrole |
| Database | [schema.prisma](../heerbaart-app/prisma/schema.prisma): offerte, productgewicht, NX/MANUAL-bewerkingen | Artikelnummer, wachtstatus, ruwgewicht, jobs/actieve job en resultaatmetadata |
| Lokale bestanden | `service/data/elster-rev-d`: 18 regels, vijf BASELINE-parts, `setup_stage=references`, `baseline_ready=false` | Handmatige programmering/vrijgave nog bevestigen; geen artikelmappen gezien bij inventarisatie |
| Verificatie | 8 bestaande Python-unittests geslaagd op 16-09-2026 | Testobjecten bewijzen geen NX/CAM; app-build, live verbindingen en end-to-end-run nog niet uitgevoerd in deze review |

De service-README meldt eerdere NX 2512-controles voor 73023059, 73023060,
73024126 en 73024154; die zijn hier niet opnieuw uitgevoerd. `DT=180` heeft
inmiddels codeondersteuning bij klonen; `DT<180` blijft uitgesloten en initiële
BASELINE-opbouw vereist `DT>180`. Volledige validatie van alle 18 varianten,
kaakselecties en behoud van handmatige CAM blijft open.

## 3. Lokale opstelling en starten

```text
Browser → Next.js op localhost:3000 → NX-service op 127.0.0.1:9009
                ↑                              │
                └── /api/nx/status, /result ────┘
                ├── PostgreSQL: klantvragen, jobs, resultaten
                ├── ERPNext: klanten/materialen
                └── S3: tekeningen en ontvangen NC-bestanden
```

Beoogde startwijze: Next.js rechtstreeks op de Windows-host met Bun; NX-service
natief met Pixi. PostgreSQL kan als enige lokale Compose-service worden gestart.
De huidige Compose-app gebruikt een NetBird-sidecar: start niet de hele stack
voor deze lokale route. Bij later gebruik van containers moeten hostadressen
opnieuw worden bepaald; container-localhost verwijst niet naar Windows.

**Nog in te stellen/controleren; dit document wijzigt geen `.env`-bestanden:**

| Bestand | Lokale instelling |
| --- | --- |
| `heerbaart-app/.env` | `NX_WORKER_URL=http://127.0.0.1:9009` |
| `heerbaart-app/.env` | `BETTER_AUTH_URL=http://localhost:3000`, `NEXT_PUBLIC_APP_URL=http://localhost:3000` |
| `heerbaart-app/.env` | Werkende `DATABASE_URL`; bij bestaande lokale Compose-Postgres hostpoort `5632` |
| `service/.env` | `NX_HOST=127.0.0.1`, `NX_PORT=9009` |
| `service/.env` | `NX_CALLBACK_URL=http://localhost:3000`, `NX_CALLBACK_STATUS_PATH=/api/nx/status` |
| `service/.env` | `NX_CALLBACK_RESULT_PATH=/api/nx/result` — configuratie/code nog toevoegen |
| `service/.env` | `NX_DATA_DIR=C:/Users/Bob/Desktop/DEMO/heerbaart-demo/service/data` voor de bestaande familie |
| `service/.env` | `NX_INSTALL_DIR=C:/Program Files/Siemens/DesigncenterNX2512`, `NX_CUSTOM_DIR=C:/Heerbaart/NX2512_Custom/NX2512_Custom` |
| Beide | HTTP-sleutels en verificatie nog aansluiten; bestaande `NX_CALLBACK_API_KEY` is alleen uitgaand `X-API-Key` |

Bij controle wees de app nog naar `fedora.netbird.selfhosted:9009`; service-host
en callbacks ontbraken in zijn `.env`. Zonder overrides zijn de callbacks
`http://localhost:8001/jobs/status`. De service laadt `.env` via dotenv;
`ENV_FILE` kan expliciet een bestand kiezen, procesvariabelen gaan voor.
Bewaar sleutels uitsluitend in genegeerde configuratie, nooit in dit document.

Startcommando's, na fase 1-configuratie, in aparte terminals:

```powershell
# Vanuit heerbaart-app; dependencies/client ontbreken in de gecontroleerde kopie.
bun install
bun run db:generate
# Alleen als de bestaande lokale PostgreSQL nodig is:
docker compose up -d postgres
# Pas bestaande migraties toe op de bedoelde lokale ontwikkel-database.
bun run db:migrate
bun run dev
```

```powershell
# Vanuit heerbaart-demo/service; .pixi en pixi.lock zijn al aanwezig.
# pixi install alleen wanneer de omgeving nog niet bruikbaar is.
pixi run serve
# In een andere terminal: alleen HTTP-bereikbaarheid, geen NX-bewijs.
curl.exe http://127.0.0.1:9009/
```

NX gebruikt Python 3.12 en Siemens' NXOpen; installeer NXOpen niet via PyPI.
`NX_PYTHON_HOME` is optioneel; standaard de actieve Pixi-omgeving.
`NX_JOURNAL_TIMEOUT` is per proces, standaard 900 seconden.
Gebruik één API-proces/worker, zonder reload. Stop de API voordat CLI-stages
dezelfde familie bewerken; de seriële queue beschermt niet tegen een tweede proces.

## 4. Gewenste flow

### A. Eerste klantvraag, BASELINE ontbreekt

1. Vraag artikel **73023059**, aantal **5**, afgesproken materiaal en PDF aan.
   De app bewaart offerte/PDF en een eigen jobrecord vóór verzending.
2. NX leest de 18 tabelregels en controleert het gevraagde artikel vóór dure
   modelbouw. BASELINE gebruikt de eerste tabelregel.
3. Bouw PART, ASSY/CAD4CAM/BLANK en SETUP; stuur de echte stappen door.
4. Lever `AWAITING_PROGRAMMING` en het pad naar `BASELINE_SETUP.prt`.
   De job eindigt en de worker komt vrij. De offerte wacht op programmeren.
5. De programmeur programmeert, bewaart/sluit en bevestigt in de app.
6. Een nieuwe job voor dezelfde offerte markeert BASELINE gereed en genereert
   het oorspronkelijk gevraagde artikel. Herlaad `family.json` na
   `mark_baseline_ready()`: die functie muteert het meegegeven dict niet.
7. Kloon de vijf parts, wijzig geometrie/afhankelijkheden, ververs de opspanning,
   regenereer CAM, meet, post en simuleer met de werkende laptopconfiguratie.
8. Lever resultaten en NC. Pas na geaccepteerde opslag wordt de offerte `READY`.

### B. Volgende klantvraag, BASELINE gereed

Vraag **73023060** aan. Dezelfde aanvraagactie ziet `baseline_ready=true`,
gebruikt de opgeslagen tabel en voert direct stap 7–8 uit. Geen nieuwe
BASELINE en geen tweede programmeeroverdracht. De nieuwe PDF blijft bij de
offerte; vervangt niet stilzwijgend de familietabel. Gebruik dezelfde revisie.

| Familietoestand | Beslissing |
| --- | --- |
| Afwezig | Extractie/opbouw → programmeeroverdracht |
| Setup compleet, niet vrijgegeven | Bestaande setup hergebruiken → programmeeroverdracht |
| Vrijgegeven | Gevraagd artikel genereren |
| Onvolledige eerdere opbouw | Fout/onvolledige stap melden; gericht hervatten na diagnose |

Een bestaande map is geen vrijgave. De huidige lokale familie hoort bij de tweede
rij, voor zover de opgeslagen toestand en aanwezige bestanden aangeven.

### Status en zichtbare stappen

Jobstatus blijft `PENDING → IN_PROGRESS → COMPLETED | FAILED`. Offertestatus:

```text
QUEUED → PROCESSING → AWAITING_PROGRAMMING → QUEUED → PROCESSING → READY
QUEUED → PROCESSING → READY                         (BASELINE al gereed)
Actieve uitvoering → FAILED + echte stap/foutmelding
```

`COMPLETED` alleen maakt een offerte nooit gereed; het geaccepteerde resultaat
bepaalt wachten of gereed. Een artikelfout hoeft BASELINE-vrijgave niet terug te draaien.

Onderstaande wire-ID's zijn het doelcontract, nog te implementeren. Meld de stap
vóór de werkelijke aanroep. Behoud de mislukte stap bij een fout.

| BASELINE | Artikel |
| --- | --- |
| `pdf_extract` — Tekening uitlezen | `article_clone` — BASELINE kopiëren |
| `baseline_part` — Basismodel maken | `geometry_update` — Afmetingen aanpassen |
| `baseline_structure` — Assemblage en ruwdeel maken | `setup_refresh` — Opspanning bijwerken |
| `setup_load` — Machine laden | `cam_regeneration` — Gereedschapsbanen genereren |
| `setup_constraints` — Opspanrelaties aanbrengen | `measurement` — Tijden en gewichten uitlezen |
| `setup_holders` — Klemmen plaatsen | `postprocessing` — NC-programma maken |
| `setup_position` — Product positioneren | `simulation` — Simuleren |
| `setup_references` — Referenties koppelen | `result_delivery` — Resultaten versturen |
| `result_delivery` — Resultaten versturen | |

De browser ververst appgegevens ongeveer elke twee seconden zolang een job actief
is; stopt bij wachten/einde/fout. Geen gesimuleerde percentages. Setup-pad is
kopieerbare laptopinformatie, geen downloadlink. Ontbrekende metingen blijven
“Nog niet berekend”. Houd NX-schattingen en handmatige offertebewerkingen apart.

## 5. HTTP- en gegevensafspraken

**Dit is het te implementeren contract, geen beschrijving van reeds werkende APIs.**
Huidig: `POST /start/nx-job` kent `extract`, `baseline` (default), `part`,
`structure`, `setup`, `ready`, `article`; status/polling bevat alleen `job_id/status`.
Behoud die lage CLI/API-acties. Bevestig de nieuwe afspraken in fase 2 en leg na
fase 5 een geanonimiseerd werkelijk request/resultaat vast in dit document.

### App → NX

`POST /start/nx-job`, multipart, met `X-API-Key` (controle nog toevoegen):

| Veld | Regel |
| --- | --- |
| `job_id` | Nieuw per actie, app-eigendom, `^[a-z][a-z0-9]{1,31}$`; geen UUID met streepjes |
| `quotation_id` | Verwijst naar vooraf opgeslagen job/offerteverband |
| `action` | `prepare_quotation` of `approve_baseline_and_generate` |
| `article_number` | Acht ASCII-cijfers; moet voorkomen in familietabel |
| `material` | Exacte afgesproken ERPNext/NX-displaynaam |
| `amount` | Positief geheel aantal; één artikel/programmageneratie, aantal alleen voor totalen |
| `drawing` | PDF bij voorbereiding, weggelaten bij goedkeuring |

Acceptatie: `201 {"job_id":"cnxjob001"}`. Ongeldige invoer: `422`;
reeds geclaimd job-ID: `409`. Uitvoeringsfouten komen asynchroon als `FAILED`.
Huidige grenzen: app-PDF maximaal 25 MiB, service-upload 32 MiB; stem nieuwe
NC-resultaatlimieten af op echte uitvoer. Valideer ook niet-lege materiaalnaam/aantal.

### NX → app: voortgang

`POST /api/nx/status`, JSON, `X-API-Key`; geaccepteerd: `204`.
`GET /jobs/{job_id}` krijgt dezelfde velden; onbekend ID blijft `404`.

```json
{"job_id":"cnxjob001","quotation_id":"cquote001","status":"IN_PROGRESS","stage":"setup_holders","stage_started_at":"2026-09-16T09:15:00Z","error":null}
```

Stap/tijd mogen in de wachtrij null zijn. Een fout bevat de mislukte stap en
bruikbare tekst. Valideer sleutel, schema en opgeslagen jobverband vóór updates;
een ontbrekend ID mag nooit in een ongefilterde `updateMany` belanden.

### NX → app: uitkomst en bestanden

`POST /api/nx/result`, multipart met `result` als JSON-string en bestandsvelden
volgens `nc_files[].field`; `X-API-Key`, geaccepteerd: `204`.

| Resultaatgroep | Velden |
| --- | --- |
| Gemeenschappelijk | `job_id`, `quotation_id`, `outcome`, `family`, `article_number`, `material` |
| BASELINE | `outcome=AWAITING_PROGRAMMING`, `baseline_setup_path`; geen NC |
| Artikel | `outcome=ARTICLE_READY`, `amount`, `timing`, `weight`, `simulation`, `nc_files` |
| `timing` | `source=nx_toolpath_estimate`, `basis=per_piece`, `operations[]` met `operation_id`, `sequence`, `name`, `seconds`; `operation_sum_seconds` |
| `weight` | `product_kg_per_piece`, `stock_kg_per_piece` |
| `simulation` | Werkelijke `status`, met fout/toelichting waar nodig; UI kent pending/running/passed/failed |
| `nc_files[]` | `field`, `filename`; corresponderende multipart-bytes, inclusief nodige subprogramma's |

Bestandsnamen/extensies volgen de werkende postprocessor, niet het previewvoorbeeld.
Een mislukte simulatie mag niet als geslaagd/gereed worden afgeleverd; bevestig de
concrete foutpayload bij implementatie. Bewaar native parts en uitvoerlogs op de laptop.

Verwerkingsregels:

- Geef elke actie een eigen job en sla het verband vóór dispatch op. Zoek offerte
  en organisatie via die job; vertrouw een meegestuurd offerte-ID niet op zichzelf.
- Negeer verouderde callbacks zodra een nieuwere job actief is. Ontvangen
  resultaten worden niet teruggedraaid door vertraagde statusmeldingen.
- Verstuur resultaat vóór `COMPLETED`. Bewaar NC in S3 met app-gegenereerde sleutels;
  pas daarna metadata, bewerkingen, verwijzingen en offertestatus samen in de DB toe.
- Registreer geaccepteerde resultaten. Herhaling krijgt `204` zonder duplicaten
  of overschrijven van latere gebruikersaanpassingen.
- Bewaar resultaat/NC lokaal. Beperkt opnieuw bezorgen met hetzelfde job-ID;
  blijvende bezorgfout is `FAILED` op `result_delivery`. Herbezorgen start geen NX-run.
- Download via een geauthenticeerde app-route, bijvoorbeeld
  `/api/quotations/{quotation_id}/nc/{file_id}`, met organisatiecontrole en
  opslagkey uit de DB. Behoud offerte/PDF bij dispatchfouten.

### Opslag, eenheden en bewerkingen

Breid `Quotation` uit met artikelnummer, wachtstatus, `stockWeight`, resultaat-JSON
en actieve job. Behoud `weight` als product-kg/stuk. Een gerelateerd jobrecord
bevat ID, offerte-ID, actie, status, stap/starttijd, fout en resultaat-geaccepteerd.
Geen aparte familie/baseline-tabellen: `family.json` blijft bron voor vrijgave.

Lees tijden na CAM-regeneratie. Gebruik unieke geprogrammeerde operatienamen als
identiteit; bewaar de NX-volgorde en ruwe resultaatsnapshot. Controleer in NX de
eenheid en of luchtgangen/gereedschapswissels meetellen. Som van operatietijden
is een **NX-schatting**, geen bewezen gesynchroniseerde multichannel-cyclustijd.

- `minuten/stuk = seconden / 60`; ordertijd = stukschatting × aantal.
- Productmassa: afgewerkte solid in `<artikel>_PART.prt`.
- Ruwmassa: `BLANK_REVOLVE_OUTLINE_BODY` in `<artikel>_BLANK.prt`, met juiste
  materiaal/dichtheid. Geen SETUP, klemmen of dubbele WAVE-bodies meetellen.
- Indien afgeleid: `mm³ × kg/m³ × 10^-9 = kg`; ordergewicht = kg/stuk × aantal.
- Eén ruwdeel per stuk, native Revolve Outline, 360°, offset 5 mm. De huidige
  Cylinder/Blok/Casting-invoer bepaalt dit niet; toon “NX-gegenereerd ruwdeel”.
- Importeer in `QuotationOperation.timeMinutes` met `source=NX`. Een nieuwe
  berekening vervangt NX-rijen, behoudt MANUAL-rijen; meld dat NX-edits dan vervallen.
- NX levert geen uurtarief. Bestaande verplichte `hourlyRate` kan voor import 0
  als oningevulde waarde gebruiken, zichtbaar als “Niet ingesteld”.
- Slepende offertevolgorde opslaan met organisatiecontrole en gezamenlijke
  hernummering; dit wijzigt geen NX-gereedschapsbanen. Nieuwe bewerkingen onderaan.

## 6. Stappenplan en afvinkbare uitvoering

### Fase 1 — lokale starttoestand

- [ ] **L1** App-dependencies/Prisma-client voorbereiden; bedoelde lokale database,
  login, ERPNext en S3 controleren. App op poort 3000 starten.
- [ ] **L2** Lokale URL's uit §3 instellen; NX-service op poort 9009 starten en
  app → service en service → app aantonen. Nog geen NetBird-inrichting.
- [ ] **L3** NX 2512, Python 3.12, licentie, journalrunner, templates, machine-,
  gereedschap-, kaak- en HB-bibliotheken controleren. Bestaande BASELINE bewaren;
  bepalen of handmatige CAM al is opgeslagen en bruikbaar is.
- [ ] **L4** Exacte materiaalnaam/dichtheid, postprocessor, uitvoerextensies en
  simulatiemodus/invoer vastleggen in §8. Automatisering baseren op geïnstalleerde bindings.
- [ ] **L5** Werkwijze voor een al bestaand artikel, dubbelklik op vrijgave,
  gelijktijdige klantvragen en herstel na serviceherstart vastleggen in §8.

### Fase 2 — workflow en echte stappen

- [ ] **W1** `api/schema.py`/`main.py`: twee app-acties, offerteverband en
  artikelvalidatie; PDF bewaren bij `prepare_quotation`; HTTP-sleutelcontrole.
- [ ] **W2** `pipeline.py`: familiebeslissing uit §4; gevraagd artikel controleren
  na extractie vóór modelbouw; programmeeroverdracht leveren; goedkeuren → herladen
  → oorspronkelijk artikel. Lage CLI-stages blijven beschikbaar.
- [ ] **W3** `worker.py`/`store.py`/`notifier.py`: materiaal/aantal doorgeven,
  output behouden, echte stap/starttijd/fout melden en polling uitbreiden.
- [ ] **W4** App-Prisma + migratie: artikel, wachtstatus, jobverband/actieve job,
  resultaatvelden en ruwgewicht; bestaande offertes met ontbrekende data blijven leesbaar.
- [ ] **W5** Live formulier/serveractie: artikelnummer, juiste materiaal/ruwdeelbasis,
  aparte job-ID; offerte/PDF behouden bij verzendfout; programmeringsactie toevoegen.
- [ ] **W6** App-callbacks: authenticatie, schemas, jobverband, veilige volgorde en
  BASELINE-uitkomst opslaan. Verwijder de onvoorwaardelijke `COMPLETED → READY` mapping.
- [ ] **W7** Gedeelde detail-UI aansluiten voor live stappen, fouttekst, setup-pad,
  programmeerknop en refresh zolang actief. Geen previewtimers in live flow.
- [ ] **W8** Beide paden aantonen tot echte artikelbestanden. Zolang afwerking en
  resultaatopslag ontbreken, geen volledige resultaatgereedheid claimen.

### Fase 3 — NX-afwerking

- [ ] **N1** Materiaal op product/ruwdeel toepassen; verse CAM regenereren na
  geometrie/setup-refresh, met behoud van geprogrammeerde strategie.
- [ ] **N2** Operaties/volgorde/tijden en beide massa's uitlezen; eenheden en waarden
  met NX vergelijken. Aantal verandert totalen, niet de geometrie of het aantal clones.
- [ ] **N3** Werkende postprocessor automatiseren; hoofd- en subprogramma's verzamelen.
- [ ] **N4** Werkende simulatie automatiseren en echte uitkomst uitlezen. Als de
  simulatie NC gebruikt: eerst posten. Procesexit of post-succes is geen simulatiebewijs.
- [ ] **N5** Afwerking via `nx/entry.py`/`nx_runner.py` na clone/update/refresh
  aanroepen, bijvoorbeeld met samenhangende code in nieuw `nx/finish.py`.
  Stappen melden en metadata/NC opslaan voor latere herbezorging.

Als een interactieve NX-stap nog niet in de journalruntime kan worden uitgevoerd,
noteer de concrete blokkade en handmatige procedure; vink de automatisering niet af.

### Fase 4 — resultaatlevering en live presentatie

- [ ] **R1** Resultaatconfiguratie/notifier en multipart-ontvanger bouwen volgens §5;
  begrensde retries en herbezorging van opgeslagen output, vóór eindstatus.
- [ ] **R2** NC naar S3; metingen, NX-bewerkingen, simulatie en bestandsverwijzingen
  opslaan. Duplicaten negeren, handmatige rijen behouden, pas daarna `READY`.
- [ ] **R3** Downloads met organisatiecontrole; opslagfouten/herhaling en verwijderen
  van offertes met nieuwe NC-bijlagen consequent afhandelen.
- [ ] **R4** Live overzicht/formulier/detail aan de herbruikbare UI koppelen:
  artikel, stuk/orderwaarden, simulatie, bestanden en lege/fouttoestanden.
- [ ] **R5** Drag/touch/toetsenbordvolgorde duurzaam opslaan en hernummeren;
  live ERP-opties/PDF gebruiken. Behoud normale validatie, focus, smalle schermen,
  licht/donker en reduced motion. Preview blijft herkenbaar lokaal, geen foutfallback.
- [ ] **R6** Contract en schemas vergelijken met echte output; geanonimiseerd
  werkelijk request/resultaat en definitieve eenheden hier vastleggen.

### Fase 5 — acceptatie en herhaling

- [ ] **A1** Geïsoleerde nieuwe `NX_DATA_DIR`: 73023059, aantal 5, juiste PDF en
  materiaal → echte BASELINE-stappen → wachten met correct setup-pad.
- [ ] **A2** BASELINE programmeren/opslaan/sluiten, vrijgeven in app → hetzelfde
  gevraagde artikel zonder nieuwe formulierinzending → verse CAM/resultaten.
- [ ] **A3** 73023060 aanvragen → direct artikelpad; nieuwe dimensies/tijden/gewichten
  controleren in NX. Simulatie is echt; gedownloade NC is identiek aan lokale uitvoer.
- [ ] **A4** Parts heropenen: vijf artikelafhankelijkheden verwijzen naar eigen
  bestanden; BASELINE en eerste artikel blijven ongewijzigd; handmatige CAM behouden.
- [ ] **A5** NX-fout toont werkelijke stap; onbereikbare service behoudt klantvraag;
  dubbel resultaat geeft geen duplicaten; MANUAL en opgeslagen volgorde blijven behouden.
- [ ] **A6** Ontbrekende/onbekende IDs en onjuiste sleutels wijzigen geen offertes;
  oude events overschrijven geen nieuwere job; dubbelklik start geen dubbele generatie.
- [ ] **A7** Callback-/S3-fout herstellen via herbezorging, zonder clone/CAM opnieuw;
  serviceherstart en bestaande artikelbestemming volgen de afgesproken procedure.
- [ ] **A8** App: `bun run check` en `bun run build`; Python: relevante bestaande
  tests en gerichte contractchecks. Noteer NX-bewijs apart; mocks bewijzen geen CAM.

## 7. Native bestanden en herstel

```text
<NX_DATA_DIR>/
  uploads/<job_id>/drawing.pdf
  elster-rev-d/
    drawing.pdf, family.json
    BASELINE/BASELINE_{PART,ASSY,CAD4CAM,BLANK,SETUP}.prt
    <artikel>/<artikel>_{PART,ASSY,CAD4CAM,BLANK,SETUP}.prt
    <artikel>/nc/                       beoogde geposte uitvoer
    work/<stage>_<uniek>/request.json, result.json, nx.log
```

Alleen de vijf genoemde parts worden native gekloond. Machine/kaak/toolresources
blijven gedeeld. Extra artikelgebonden parts vereisen een expliciete clone-mapwijziging.
Geen filesystem-copyfallback. Een benodigde andere kaakselectie wordt momenteel
afgewezen; geen automatische fixturewissel. Behoud deze grenzen bij afwerking.

Bestaande CLI, vanuit `service`, **API gestopt**:

```powershell
# Alleen met een bewust gekozen lege NX_DATA_DIR:
pixi run stage baseline --drawing .\ELSTER_GEHAEUSE_T73023059_REV_D.pdf
# Of afzonderlijk: extract --drawing <pdf>, part, structure, setup.
# Na daadwerkelijk programmeren, opslaan en sluiten:
pixi run stage ready
pixi run stage article --article 73023059
```

Vandaag stopt `article` na setup-refresh. Gebruik `extract`/`baseline` nooit als
hervatcommando boven een bestaande familie. `setup` hervat na de laatst opgeslagen
setup-stap; een mislukte stap kan wel gedeeltelijke bestanden hebben achtergelaten.
Inspecteer log/bestanden voordat je opnieuw probeert. Artikelen weigeren bestaande
bestemmingen; archiveer een mislukte map pas bewust na diagnose. Verwijder geen
geprogrammeerde BASELINE om een proef te laten slagen.

De runner beëindigt zijn NX-procesboom bij timeout/cancel. Queue en jobstatussen
zijn momenteel alleen in geheugen; herstart verliest die informatie. De app moet
hiervoor een afgesproken herstelroute krijgen, geen onbeperkte automatische rerun.

## 8. Open keuzes en bewijslogboek

| Onderwerp | Stand / in te vullen besluit |
| --- | --- |
| Runtime | Besloten: beide servers lokaal op deze laptop; NetBird pas later |
| Materiaal | Open: exacte gedeelde naam, NX-dichtheid en bron |
| Handmatige BASELINE-CAM | Open: opgeslagen programmering bevestigen; flag momenteel false |
| Postprocessor | Open: configuratiepad/naam, extensies en subprogramma's |
| Simulatie | Open: modus, NC/toolpath-invoer, aanroep en resultaatdetectie |
| Bestaand artikel | Open: expliciet hergebruik of gecontroleerde herberekening; niet overschrijven |
| Meerdere aanvragen | Open: gedrag bij wachten op dezelfde BASELINE en dubbele vrijgave vastleggen |
| Herstart/verzendfout | Open: statusherstel, onzekere dispatch en opnieuw bezorgen afspreken |
| HTTP-sleutels | Open: configuratienamen/controle aan beide kanten; waarden niet documenteren |
| Alle 18 varianten | Open: na de twee demoscenario's dekking uitbreiden; geen volledige dekking claimen |

| Datum | Taak/bewijs | Uitkomst / volgende stap |
| --- | --- | --- |
| 2026-09-16 | Statische controle van beide repos en lokale familiedata | Uitgangssituatie in §2; consolidatie afgerond; start bij L1–L5 |
| 2026-09-16 | `.pixi/envs/default/python.exe -B -m unittest discover -s tests -v` vanuit `service` (review) | 8 tests geslaagd; geen nieuwe NX-run of app-build |

Voeg bij volgende sessies datum, taak-ID, relevante bestands-/loglocatie,
uitgevoerde controle en uitkomst toe. Leg niet alleen “werkt” vast. Actualiseer
de checklist en fase bovenaan op basis van dat bewijs. Nog geen werkelijk
end-to-end-resultaat beschikbaar voor opname; previewmetingen zijn fictief.
