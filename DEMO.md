# Heerbaart-demo — klantvraag → NX → resultaten

Dit is de centrale bron voor scope, flow, werkvolgorde en voortgang van
`heerbaart-demo` en `heerbaart-app`. Het vervangt PLAN.md, TODO.md en FLOW.md in
deze repo. Het app-plan is historische achtergrond bij de UI-preview; technische
READMEs beschrijven de implementatie. Code of een mocktest alleen bewijst geen NX-run.

**Belangrijk: dit is een lokale proof of concept op deze laptop. We bouwen de
happy flow.** Gebruik de bestaande seriële worker en directe HTTP-koppeling.
Geen extra queue-dienst, jobhistorieplatform, generieke familielaag, automatische
herstelketens of extra API-sleutelbeheer voor deze lokale stap. NetBird volgt
later. Bestaande app-login, organisatiecontrole en invoervalidatie blijven.

**Uitvoering zonder GUI blijft een harde eis voor modelleren, CAM en externe NC-simulatie.**
Uitzondering op verzoek van de gebruiker (17-09-2026): het instelblad via Siemens
Machining Setup Instructions gebruikt een aparte grafische NX-sessie. Deze opent
en sluit automatisch na de PDF-export en vereist een ingelogde Windows-desktop.
De simulatiestap gebruikt de meegeleverde NX-Python, zodat het journal en de
CSE-driver dezelfde runtime gebruiken; API/Pixi en de overige batchstappen blijven
hun bestaande omgeving gebruiken. Volledige externe simulatie op 59 en 60 is
via de API bevestigd; zie het bewijslogboek.

**Simulatie gebruikt de bibliotheken van `Heerbaart_NX2512.bat`:**
`NX_SIMULATION_CUSTOM_DIR=C:/Heerbaart_Custom/__Custom`. Dit stuurt uitsluitend
de CSE-machinebibliotheek en toolgraphics tijdens `simulation`. Clone, update,
refresh, CAM, post, artikelreferenties en het laden van de setup behouden hun
bestaande paden onder `NX_CUSTOM_DIR`. De twee Okuma-kits zijn niet byte-identiek;
de gebruiker bevestigt dat de kit onder `Heerbaart_Custom` interactief werkt.
De aparte instelbladexport gebruikt de normale GUI-startomgeving uit dit batchbestand;
de artikelreferenties blijven ook daar onder `NX_CUSTOM_DIR`.

**Stand 16 september 2026:** lokale verbindingen gereed. Echte aanvraag →
PDF-opslag → NX → programmeeroverdracht getest. Formulier, overzicht en detail
gebruiken de preview-componenten met echte data. De programmeerknop is aangesloten.
De eerste artikelrun stopte bij setup-refresh; daarna blokkeerde een nieuwe clone
op twee identieke kaakbibliotheekkopieën met verschillende paden. Die clonefout
is opgelost en native getest in een aparte map. Daarna zijn ook de kaakpadcontrole
en het opnieuw opbouwen van positioneringsconstraints in refresh hersteld:
clone, update en volledige refresh van 73023059 zijn native geslaagd op een testkopie.
Gebruiker bevestigt nu dat 73023059 én 73023060 werken en CAM-operaties in NX bevatten.
Toolpath-regeneratie is aangesloten als automatische stap 5 van de artikelflow.
Na de serverherstart zijn de bestaande offertes voor 73023059 en 73023060 eenmalig
via de bestaande API hervat vanaf `cam_regeneration`, met behoud van offerte en
artikelbestanden. De eerste runs stopten op `ONLYNOTES` buiten het artikelprogramma.
De selectie is daarom beperkt tot programmagroep `O1234` (47 bewerkingen).
Regeneratie/save/heropen is voor 59 geslaagd en door gebruiker bevestigd.
Posten is aangesloten op basis van `journal.py`: dezelfde Okuma-instellingen,
automatisch na CAM, uitvoer per artikel. Beide API-runs (59/60) zijn geslaagd;
Externe NC-simulatie is nu ook voor beide artikelen via de API geslaagd, zonder
GUI. Beide bestaande offertes zijn hervat en melden `ARTICLE_CREATED`, stage
`simulation`, zonder fout. NC-download via de service is bytegelijk aan de
gesimuleerde lokale bestanden.

**Nieuwe vrijgaveregel:** geposte NC is nog niet downloadbaar. Eerst **External
Program Simulation** van het daadwerkelijke `<artikel>-SETUP.min` via de Okuma
CSE-driver; interne toolpath-simulatie telt niet. Volledig einde + nul collisions,
limits, gouges en singularities vereist. Afgebroken/mislukte/nog niet uitgevoerde
simulatie blokkeert download in zowel app als NX-service. `simulation.json` bewaart
de uitkomst en SHA-256 van de gecontroleerde NC; gewijzigde NC of opnieuw posten
maakt vrijgave ongeldig. Voor 59 en 60 is HTTP 409 tijdens simulatie en HTTP 200
na succesvolle afronding gecontroleerd.

**Simulatie gereed voor deze twee artikelen:** `SuppressAll` voorkomt de blokkade
bij 4,620 s; `SuppressGraphics` alleen niet. De werkende interactieve CSE-kit
wordt uitsluitend voor simulatie geladen. Kanaal `1`, één `PlayForward()`, echt
SimEnd en nul gerapporteerde fouttellers zijn op beide artikelen bevestigd.
Geen handmatige stappen of interactieve NX-sessie nodig.

**Bevestigd door gebruiker op 16 september 2026:** A1–A3 zijn al getest en werken;
de browserdownload levert de NC-code op. N3c vervalt: het verschil in de
referentie kwam door een handmatige wijziging en is niet relevant voor deze flow.
**Gewichten aangesloten:** materiaaltoekenning gebeurt vroeg in de geometrie-update
(N1c). Direct na de geometrie-update leest `measurement` de product- en ruwdeelbody
afzonderlijk in kg. Een voortgangscallback bewaart beide gewichten op de offerte;
de UI toont stuk/ordertotalen terwijl setup-refresh, CAM, post en simulatie doorgaan.
**Simulatietijd aangesloten:** één totale tijd uit CSE `MachineTime`, pas na
SimEnd en geslaagde simulatie. Geen afzonderlijke operatietijden/import voor deze
POC-stap. **Nog open:** overige simulatiedetails en afronding (R1).
De opgeslagen machinebewerking met totale simulatietijd per stuk (R3) is gereed,
evenals artikel-/concept-BOM-aanmaak via de knop in [ERPNext.md](ERPNext.md).
Lokale NC-opslag en de bestaande download
volstaan voor deze POC; NC naar S3 is niet vereist. Pas na volledige
resultaatlevering, inclusief de machinebewerking, volgt `READY`.
De artikelflow voert nu clone → geometrie-update → gewichten uitlezen/teruggeven → setup-refresh →
gereedschapsbanen genereren → NC-programma maken → externe NC-simulatie →
NC-download/tijd vrijgeven → instelblad als PDF maken en download vrijgeven uit.
Geen aparte actieknop. Bij een fout in `setup_sheet` hervat alleen de PDF-export;
de geslaagde simulatie en CSE-tijd blijven bewaard.
Materiaal wordt vóór setup-refresh/CAM/post toegekend; de totale simulatietijd volgt na SimEnd.

## 1. Vaste afspraken

- Eén familie: **Elster Rev.D**, sleutel `elster-rev-d`, de bestaande enkelbladige
  PDF met 18 tabelregels. Achtcijferig artikelnummer kiest de regel;
  `DT`, `FA`, `DR`, `FR`, `FB`, `DS`, `DL` komen daaruit, in millimeters.
  Bewaar afgedrukte volgorde, klasse, schedule en nominale waarden.
- BASELINE is een zelfstandig familiesjabloon met de eerste tabelregel als
  maatvoering, geen verkoopartikel. Ieder artikel krijgt eigen bestanden.
- **Ruwdeel is geen formulierkeuze meer, ook niet in de preview.** Altijd native
  **Revolve Outline, 360°, offset 5 mm**, één ruwdeel per stuk. Het bestaande
  databaseveld `materialShape` krijgt vast `Revolve Outline`; geen Cylinder/Blok/
  Casting-route. Ruwgewicht blijft wel een gewenst resultaat.
- Materiaalcode is het eerste woord van de gekozen ERPNext-naam, bijvoorbeeld
  `1.4301 - RVS 304` → `1.4301`. Deze code matcht de NX-materiaalnaam in
  `C:/Heerbaart/Materials/Heerbaart_Materials.xml`; dichtheid komt uit die bibliotheek.
  Materialen bestaan volgens afspraak altijd; geen extra validatie of fallback.
  Tijdens de geometrie-update wordt het materiaal per artikel toegekend aan de
  product-solid in PART en `BLANK_REVOLVE_OUTLINE_BODY` in BLANK, vóór opslaan.
  De bestaande NX-instelling werkt massa bij op save. BASELINE blijft ongewijzigd.
- De programmeur programmeert BASELINE, bewaart/sluit de bestanden en bevestigt
  in de app. Vertrouw deze bevestiging; geen apart CAM-goedkeuringssysteem.
- Volg de preview-UI met echte data: geen gesimuleerde stappen of voorbeeld-NC.
  Ontbrekende metingen blijven “Nog niet berekend”. Setup-paden zijn lokale locaties.
- ERPNext levert klanten/materialen en bestaande klantaanmaak. Artikel- en
  BOM-aanmaak via een knop zijn aangesloten volgens [ERPNext.md](ERPNext.md).
  Eén machinebewerking met de totale CSE-tijd per stuk wordt onder R3 vastgelegd;
  de vier overige tijden vult de gebruiker in. Verkoopoffertes en
  verkoopprijscalculatie blijven buiten deze POC.
- Hergebruik STAP1–11, associatieve structuur, machine/kaakstrategie en NX-save/
  heropen-grenzen. Oorspronkelijke bronprojecten blijven ongemoeid.

## 2. Lokaal starten

```text
Browser → Next.js localhost:3000 → NX-service 127.0.0.1:9009
              ↑                         │
              └── /api/nx/status ────────┘
              ├── PostgreSQL: klantvragen + huidige job/voortgang
              ├── ERPNext: klanten/materialen
              └── S3: PDF-tekeningen (NC blijft lokaal voor deze POC)
```

Beide servers draaien op Windows. ERPNext en S3 blijven de ingestelde externe
diensten. Alleen PostgreSQL hoeft in Compose te draaien; de volledige Compose-app
met NetBird-sidecar is voor deze lokale route niet nodig.

| Configuratie | Waarde |
| --- | --- |
| App `NX_WORKER_URL` | `http://localhost:9009` |
| App `BETTER_AUTH_URL`, `NEXT_PUBLIC_APP_URL` | `http://localhost:3000` |
| Lokale PostgreSQL | `localhost:5632` |
| Service `NX_HOST`, `NX_PORT` | `127.0.0.1`, `9009` |
| Service `NX_CALLBACK_URL`, `NX_CALLBACK_STATUS_PATH` | `http://localhost:3000`, `/api/nx/status` |
| `NX_DATA_DIR` | Standaard `data`, relatief aan `service` |
| `NX_INSTALL_DIR` | `C:/Program Files/Siemens/DesigncenterNX2512` |
| `NX_CUSTOM_DIR` | `C:/Heerbaart/NX2512_Custom/NX2512_Custom` |

Vanuit `heerbaart-app`:

```powershell
# Alleen wanneer PostgreSQL nog niet draait:
docker compose up -d postgres
bun run dev
```

Vanuit `heerbaart-demo/service`, in een tweede terminal:

```powershell
pixi run serve
```

Dependencies, seed en migraties zijn hier uitgevoerd. Nieuwe installatie:
`bun install`, `bun run db:generate`, `bun run prisma migrate deploy`,
`bun run db:seed`; service: `pixi install`. Na Prisma-wijzigingen de app herstarten.
De seed draait rechtstreeks met Bun en leest `SEED_OWNER_NAME`, `SEED_OWNER_EMAIL`,
`SEED_OWNER_PASSWORD` uit `.env`. Opnieuw seeden zet het eigenaarswachtwoord terug;
niet bij iedere start doen. Bewaar sleutels alleen in genegeerde configuratie.

Serviceconfiguratie komt uit `.env`; `ENV_FILE` kan een ander bestand kiezen,
procesvariabelen gaan voor. NX gebruikt Python 3.12 en Siemens NXOpen, niet PyPI.
`NX_PYTHON_HOME` is optioneel, standaard Pixi; `NX_JOURNAL_TIMEOUT` is 900 seconden
per proces. Eén API-worker, zonder reload; geen gelijktijdige CLI op dezelfde familie.

## 3. Happy flow

1. **Aanvragen:** klant, referentie, artikel, leverdatum, materiaal, aantal en PDF.
   App controleert ERP-opties, bewaart offerte/PDF en huidige job-ID vóór dispatch.
   Bij dispatchfout blijven aanvraag en PDF bewaard.
2. **Familie bepalen:** `prepare_quotation` controleert artikel. Ontbreekt de
   familie, dan extractie → PART → structuur → vijf setup-stappen. Artikelvalidatie
   gebeurt na extractie vóór modelbouw; BASELINE gebruikt altijd de eerste regel.
3. **Programmeeroverdracht:** complete, niet-vrijgegeven BASELINE hergebruiken →
   `AWAITING_PROGRAMMING` met setup-pad. Worker komt vrij. Een map alleen is geen
   vrijgave; een onvolledige opbouw geeft een fout en vraagt gericht lokaal vervolg.
4. **Programmeren/vrijgeven:** open `BASELINE_SETUP.prt`, programmeer, bewaar/sluit.
   App-knop start nieuwe job voor dezelfde offerte: `approve_baseline_and_generate`.
   Service markeert gereed, herlaadt `family.json` en start het oorspronkelijke artikel.
5. **Artikel maken:** vijf parts native klonen → geometrie aanpassen en gekozen
   materiaal aan PART/BLANK toekennen, opslaan → gewichten meten en direct
   terugmelden (zie hieronder) → opspanning
   bijwerken → automatisch **Gereedschapsbanen genereren** (`cam_regeneration`,
   stap 5 in de artikel-UI). NX zoekt programmagroep `O1234` op naam in de
   programmaboom en genereert uitsluitend die groep en onderliggende bewerkingen via
   `CAMSetup.GenerateToolPath`, controleert toolpaths/statussen en bewaart/heropent
   de artikelsetup. Ook de controle na heropenen geldt alleen voor `O1234`.
   `ONLYNOTES` en andere programmagroepen blijven buiten deze stap; ontbreekt
   `O1234`, dan volgt een fout. Daarna automatisch **NC-programma maken**:
   `DeleteMachineCode`, `OutputBallCenter=False`, `PostprocessWithPostModeSetting`
   met `Okuma_MultusU4000_1SW`, `PostDefined` voor units/warnings/review, `Normal`.
   Eerst naar een verse runmap, daarna de niet-lege `<artikel>-SETUP.min` naar de
   artikelmap kopiëren en setup opslaan. Callback eindigt op `postprocessing` /
   `ARTICLE_CREATED` is historisch de post-eindstatus. De nieuwe flow gaat direct
   verder naar `simulation`; pas na succesvolle externe simulatie is NC downloadbaar.
   Oude aanvragen die bij setup-refresh eindigden krijgen dat label niet alsnog.
6. **Simulatie:** expliciet extern bestand op kanaal `1`, echte CSE-driver,
   machine-/tool-/IPW-controles, wachten op SimEnd en daarna foutentellers uitlezen.
7. **Gewichten (vroeg in stap 5):** direct na geometrie-update heropent `measurement` de opgeslagen
   PART/BLANK en meet uitsluitend de product-solid en `BLANK_REVOLVE_OUTLINE_BODY`
   via NX `NewMassProperties`, expliciet in kg. `weights.json` bewaart de massa's
   per stuk. Callback: `IN_PROGRESS` op `measurement`, met `weights.product_kg`
   en `weights.stock_kg`; de app bewaart deze als `weight`/`stockWeight` met zes
   decimalen. UI: direct kg/stuk en kg/stuk × aantal tijdens “In verwerking”, via de
   bestaande polling (circa twee seconden). Latere callbacks zonder gewichten
   wissen deze niet. Na simulatie eindigt de aanvraag op `ARTICLE_CREATED` / `simulation`.
   Tijd blijft “Nog niet berekend” totdat de externe simulatie succesvol is afgerond.
   De eindcallback levert `simulation_time_seconds` uit CSE `MachineTime`,
   opgeslagen als `Quotation.simulationTimeSeconds` met millisecondeprecisie.
   De UI toont minuten per stuk en minuten × aantal. Geen CAM-operatie-import.
   De eindcallback bewaart ook één machinebewerking met dezelfde tijd, naast vier
   handmatig in te vullen regels. Artikel/concept-BOM exporteert de gebruiker via
   de knop; zie ERPNext.md. **Nog bouwen:** overige simulatiedetails opslaan/tonen.
   NC blijft lokaal met de bestaande download. Pas na volledige resultaatlevering `READY`.

Volgende aanvraag, bijvoorbeeld **73023060**: `baseline_ready=true` start direct
het artikelpad. Opgeslagen familietabel blijft leidend; nieuwe PDF vervangt die
niet. Gebruik dezelfde revisie. De huidige laptopfamilie is vrijgegeven.

```text
QUEUED → PROCESSING → AWAITING_PROGRAMMING
                           ↓ bevestiging in app
                     QUEUED → PROCESSING → ARTICLE_CREATED
Al vrijgegeven: QUEUED → PROCESSING → ARTICLE_CREATED
Fout: actieve uitvoering → FAILED + werkelijke stap/fout
Later: artikelafwerking + resultaatopslag → READY
```

Browser ververst circa iedere twee seconden zolang actief, stopt bij wachten/
einde/fout. Bij bestaande BASELINE toont de live flow alleen de familiecontrole,
geen opnieuw uitgevoerde bouwreeks. Handmatige bewerkingen en sleepvolgorde worden
in de app opgeslagen; deze veranderen geen NX-gereedschapsbanen.

## 4. Huidige implementatie en contract

| Onderdeel | Code |
| --- | --- |
| Aanvraag/dispatch | App `quotation-form/actions.ts`, `src/server/nx.ts` |
| Gedeelde UI | `quotation-request-form.tsx`, `quotation-views.tsx`, `quotation-live.tsx`; mapping `src/lib/nx-workflow.ts` |
| App-opslag | `Quotation`: artikel, unieke huidige `nxJobId`, stap/tijd, workflow, fout en setup-pad; migratie `20260916000000_connect_local_nx_flow` toegepast |
| NX-workflow | `service/pipeline.py`, `service/api/{main,schema,worker,store,notifier}.py` |
| Callback | App `src/app/api/nx/status/route.ts` |

**App → NX:** `POST /start/nx-job`, multipart met `job_id` (nieuw per actie,
`[a-z][a-z0-9]{1,31}`), `action` (`prepare_quotation` of
`approve_baseline_and_generate`), `article_number` (acht cijfers), `material`
(ERP-displaynaam), `amount` (positief geheel), `drawing` (PDF alleen bij voorbereiding).
Acceptatie `201 {"job_id":"..."}`, invoerfout `422`, bekend in-memory ID `409`.
App-uploadlimiet 25 MiB; service 32 MiB. Lage acties `extract`, `baseline`, `part`,
`structure`, `setup`, `ready`, `article` blijven beschikbaar voor lokaal werk.

**NX → app:** `POST /api/nx/status`, JSON. `GET /jobs/{job_id}` op de service levert
dezelfde momentopname. Voorbeeld van de geteste overdracht (ID/pad/tijd vereenvoudigd):

```json
{"job_id":"cdemojob001","status":"COMPLETED","stage":"family_check","stage_started_at":"2026-09-16T10:00:00Z","workflow":"baseline","error":null,"outcome":"AWAITING_PROGRAMMING","setup_path":"C:/.../BASELINE/BASELINE_SETUP.prt"}
```

Jobstatus: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`. Bij `COMPLETED` vereist
de app expliciet `outcome` (`AWAITING_PROGRAMMING` of `ARTICLE_CREATED`) en setup-pad.
Geen automatische `COMPLETED → READY`. Schema en huidige jobverband worden
gecontroleerd: geldig `204`, onbekend/oud job-ID `404`, ongeldige payload `400`.
Vertraagde updates draaien een eindstatus niet terug. Geen aparte jobtabel/historie;
actuele jobgegevens staan direct op de offerte.

Stap-ID's: `family_check`, `pdf_extract`, `baseline_part`, `baseline_structure`,
`setup_load`, `setup_constraints`, `setup_holders`, `setup_position`,
`setup_references`, `article_clone`, `geometry_update`, `measurement`, `setup_refresh`, `cam_regeneration`, `postprocessing`, `simulation`, `setup_sheet`.
`setup_sheet` maakt `<artikel>_INSTELBLAD.pdf` in de artikelmap, met een downloadknop in de app.
Een CAM-fout meldt de operatie en houdt de aanvraag op `FAILED` bij stap 5;
de bestaande retry hervat CAM en gaat daarna verder met posten. Bij een postfout
herhaalt retry posten en daarna simulatie; bij een simulatiefout alleen de bestaande
NC extern simuleren. Retry vanaf `measurement` meet de gewichten opnieuw en gaat
daarna door met setup-refresh, CAM, post en simulatie. Retry vanaf een latere stap
behoudt de al opgeslagen gewichten. Een oude toolpath is geen succes als NX nog `Regen`
meldt. `Repost` is toegestaan bij de controle vóór het posten.

De statuscallback draagt ook de overdrachtsuitkomst, de gewichten en de totale
simulatietijd. Beide massa's worden direct tijdens verwerking opgeslagen; de tijd
direct na geslaagde simulatie, bij de start van `setup_sheet`, voor de huidige job.
`/api/nx/result` is nog een
loggingstub zonder echte resultaatopslag; `NX_CALLBACK_RESULT_PATH` wordt nog niet
gebruikt. Bouw één eenvoudige resultaatlevering met overige simulatiedetails voor
de huidige job. De machinebewerking wordt met dezelfde vroege tijdcallback opgeslagen.
Bewaar de koppeling naar de lokale NC;
NC naar S3 is geen vereiste vóór `READY`. Downloaden blijft via
app-login/organisatiecontrole. Definitieve payload
baseren op echte NX-uitvoer. Geen uitgebreid retry/herbezorgingssysteem voor de POC.
Voor nu downloadt de app de lokale `.min` via `GET /articles/{artikel}/nc`, met
app-login/organisatiecontrole op `/api/quotations/{id}/nc`. Geen S3-kopie van NC;
de lokale POC bewaart de laatste uitvoer per artikel. De service geeft HTTP 409
zolang geen geslaagde externe simulatie voor exact de huidige NC bestaat.

Afspraken voor die resultaten:

- Gebruik uitsluitend de totale CSE `MachineTime` na SimEnd en geslaagde externe
  NC-simulatie. De ruwe `HH:MM:SS.mmm` blijft in `simulation.json`; de callback
  levert seconden. Minuten/stuk = seconden / 60; ordertijd = tijd/stuk × aantal.
  Dit is de tijd volgens de machine-/controllerconfiguratie in de simulatie,
  exclusief handmatig instel- en programmeerwerk. Aantal verandert geen geometrie.
- Geen uitlezing/import van individuele CAM-operatietijden voor deze POC-stap.
- Wel één automatische machinebewerking op de aanvraag: de gebruikte machine
  plus de totale CSE-simulatietijd per stuk (minuten = seconden / 60). Gebruik
  dezelfde tijd als de tijdkaart, niet de met aantal vermenigvuldigde ordertijd.
  Werk bij een nieuwe succesvolle berekening dezelfde automatische bewerking bij;
  maak geen dubbele regel en tel tijdkaart en bewerkingsregel niet bij elkaar op.
  De regel gebruikt `Draaifrezen` / `Draaifreesmachine` / `Okuma MULTUS U4000`;
  de knop voor artikel/concept-BOM is aangesloten volgens ERPNext.md.
- Productmassa: afgewerkte solid in `<artikel>_PART.prt`. Ruwmassa:
  `BLANK_REVOLVE_OUTLINE_BODY` in `<artikel>_BLANK.prt`, juiste materiaal/dichtheid.
  Geen klemmen/machine/dubbele WAVE-bodies. `mm³ × kg/m³ × 10^-9 = kg`;
  ordergewicht = kg/stuk × aantal.
  De totale `NX_Mass` van BLANK telt ook `BLANK_SOURCE_BODY` mee; gebruik die
  totale partmassa dus niet als ruwgewicht. Dit is native bevestigd bij N1c.
- De POC gebruikt de vaste volgorde ingangscontrole → draaifrezen → meten →
  stempelen → verpakken. De vier handmatige tijden blijven behouden bij een
  NX-herberekening en staan los van de totale simulatietijdkaart.
  Uurtarief komt niet uit NX; 0 kan “Niet ingesteld” vertegenwoordigen.
- Verzamel hoofd- en subprogramma's volgens echte postprocessor/extensies. Parts
  en uitvoerlogs lokaal bewaren. Simulatie werkelijk uitlezen: post/procesexit
  alleen is geen bewijs. Bij NC-simulatie eerst posten; mislukking is geen `READY`.

## 5. Stappenplan en voortgang

### Lokale basis — gereed

- [x] **L1** App/DB/ERPNext/S3 ingericht; seed geslaagd; DB-query, ERP Customer/Raw
  Material en S3-buckettoegang gecontroleerd.
- [x] **L2** Beide servers en HTTP-richtingen gecontroleerd; echte PDF-opslag en
  gekoppelde callback vervolgens ook getest (W7).

### Workflow — gebouwd, eerste overdracht getest

- [x] **W1** Twee app-acties, artikelnummer en PDF in service-API.
- [x] **W2** Familie ontbreekt/bestaand/vrijgegeven → juiste route; vrijgave herlaadt
  familie en start oorspronkelijk artikel. Gerichte unittests.
- [x] **W3** Materiaal/aantal, output, echte stap/tijd/fout doorgeven; volledige polling.
- [x] **W4** Prisma-velden/statussen en migratie toegepast; client gegenereerd.
- [x] **W5** Live formulier, ERP, PDF, dispatch en programmeerknop aangesloten.
  Ruwdeel-keuze verwijderd; vaste Revolve Outline.
- [x] **W6** Callback via huidige job; overdracht/fout bewaren; geen vals `READY`.
- [x] **W7** Preview-UI live. Echte aanvraag 73023059/aantal 5 bereikt
  `AWAITING_PROGRAMMING`; detail toont juiste pad en programmeerknop.
- [x] **W8** Gebruiker bevestigt werkende artikelen 73023059 en 73023060 en behoud
  van CAM-operaties in NX. Toolpath-regeneratie is een afzonderlijke vervolgstap.

### NX-afwerking — volgende bouwfase

- [x] **N1a** Automatische CAM-regeneratie na setup-refresh aangesloten; echte
  statuscallback, save/heropen-controle en retry vanaf `cam_regeneration`.
- [x] **N1b** Eerste echte API-regeneratie (59), save/heropen-controle en bevestiging gebruiker.
- [x] **N1c** ERPNext-materiaalcode uit het begin van de gekozen naam; bibliotheekmateriaal
  toekennen aan PART-productbody en BLANK-ruwdeelbody tijdens geometrie-update.
  Native clone/update/save/heropen getest met `1.4301 - RVS 304`: beide bodies
  hebben `1.4301`, dichtheid 7900 kg/m³; massa wordt op save bijgewerkt.
- [x] **N2a** Product- en ruwmassa uit de juiste afzonderlijke bodies meten in kg,
  lokaal bewaren en direct na geometrie-update via voortgangscallback teruggeven.
  Native test op aparte kopie geslaagd; gebruiker bevestigt de live flow voor
  73023060 / 1.4462 - Duplex F51 op 16-09-2026.
- [x] **N2** Eén totale CSE-simulatietijd na geslaagde SimEnd teruggeven; geen
  operatie-import. Opslag/weergave getest met echte opgeslagen simulatie-uitvoer.
- [x] **N3a** Postprocessor/extensie uit `journal.py` aangesloten, artikelgebonden `.min`, retry en download in bestaande UI.
- [x] **N3b** Native API-post en service-download voor 73023059 en 73023060 geslaagd.
- [x] **N3c — vervallen** Het verschil in koelmiddelcodes van de referentie van 59
  kwam door een handmatige wijziging. Gebruiker bevestigt op 16-09-2026 dat dit
  niet relevant is; geen verder onderzoek nodig.
- [x] **N4** Externe `.min` op kanaal 1, één headless `PlayForward()`, SimEnd en echte fouttellers uitlezen; native bewezen op 59 en 60.
- [x] **N4a** Externe NC verplicht vóór download; oude geposte aanvragen blijven
  geblokkeerd. API-retry vanaf `simulation`, uitkomst en bestandsvingerafdruk bewaren.
- [x] **N4b** Headless externe CSE-uitvoering t/m SimEnd op 59 en 60; nul fouttellers,
  callbacks ontvangen en vrijgegeven downloads bytegelijk aan gecontroleerde NC.
- [x] **N4c** Artikel-NC blijvend koppelen in Program Manager en SETUP opslaan
  vóór simulatie; gebruiker bevestigt op 17-09-2026 dat dit werkt bij handmatig openen.
- [x] **N5** CAM → post → simulatie automatisch aangesloten na clone/update/refresh,
  met echte stappen, lokale resultaten en API-retry; gewichtsmeting direct na update.
  Totale simulatietijd aangesloten; overige resultaatopslag blijft bij R1 open.
  Ketentests A1–A3 zijn bevestigd.

### Resultaten en einddemo — open

- [x] **R1a** Product-/ruwgewicht via huidige job opslaan op de offerte;
  migratie `20260916010000_add_quotation_weights` toegepast.
- [ ] **R1** Overige simulatiedetails leveren, opslaan en tonen; afronding naar
  `READY` na volledige resultaatlevering, inclusief R3. Lokale NC-opslag en de
  bestaande download volstaan voor de POC; NC naar S3 is niet vereist.
- [x] **R2a** Gewichtskaarten met echte kg/stuk en ordertotalen; callback → DB → UI
  getest met native meetuitvoer en aantal 5. Live door gebruiker bevestigd:
  138,49 kg product en 190,89 kg ruwdeel bij aantal 1, al zichtbaar tijdens
  setup-refresh. Tijdens deze vroege stap blijft de simulatietijd nog leeg.
- [x] **R2** Tijdkaart gebruikt de totale simulatietijd; stuk/ordertotalen getest.
  Geen individuele CAM-operatie-import; handmatige tijden blijven behouden.
- [x] **R3** Eén automatische bewerkingsregel met totale CSE-tijd per stuk,
  gekoppeld aan de Okuma; vier overige regels krijgen handmatige tijden.
  Opslag en UI aangesloten, ook voor de bestaande aanvraag. Herberekening werkt
  de Okuma-tijd bij zonder duplicaten of verlies van handmatige tijden.
  Artikel/concept-BOM via knop, ERP-links en acceptatie staan in [ERPNext.md](ERPNext.md).
- [x] **R4** Automatisch Siemens-instelblad als PDF na simulatie, lokaal in de
  artikelmap en downloadbaar in de app. Aparte NX-GUI-sessie; geen handmatige klikken.
- [x] **A1** Bewust lege `NX_DATA_DIR`: 73023059/aantal 5 → nieuwe BASELINE →
  programmeren/vrijgeven → artikel, simulatie en NC. Bestaande BASELINE behouden.
  Door gebruiker op 16-09-2026 bevestigd als getest en werkend; metingen zijn
  inmiddels aangesloten, inclusief machinebewerking. Overige resultaatlevering
  blijft onder R1 open.
- [x] **A2** 73023060 direct artikel; afmetingen, simulatie en NC-download werken.
  Door gebruiker op 16-09-2026 bevestigd; service-download bytegelijk aan lokale
  uitvoer. Tijd is onder N2 aangesloten; gewichten onder N2a/R1a/R2a.
- [x] **A3** Vijf parts heropenen: eigen afhankelijkheden; BASELINE en eerste artikel
  ongewijzigd; handmatige CAM behouden. Door gebruiker op 16-09-2026 bevestigd
  als getest en werkend.
- [x] **A4** App-check en productiebuild geslaagd; 13 Python-tests geslaagd.
  Dit bewijst codecontroles; de NX/CAM-praktijktests zijn afzonderlijk bevestigd.

## 6. Bestanden en eenvoudige foutafhandeling

```text
service/data/
  uploads/<job_id>/drawing.pdf
  elster-rev-d/
    drawing.pdf, family.json
    BASELINE/BASELINE_{PART,ASSY,CAD4CAM,BLANK,SETUP}.prt
    <artikel>/<artikel>_{PART,ASSY,CAD4CAM,BLANK,SETUP}.prt
    work/<stage>_<uniek>/request.json, result.json, nx.log
```

`family.json` is bron voor vrijgave. Bij overdrachtstest: 18 regels, vijf
BASELINE-parts, `setup_stage=references`, `baseline_ready=false`. Test zette deze
flag niet op true en startte geen native generatie.

Stop API vóór CLI-stages. `extract`/`baseline` zijn voor nieuwe familie, niet
hervatten; `setup` hervat na laatst opgeslagen stap. Na echte programmering kan
lokaal `pixi run stage ready`, dan
`pixi run stage article --article 73023059 --material "1.4301 - RVS 304"`;
voor de demo gebruiken we de app-knop.

Artikelen weigeren bestaande clonebestemmingen. De live detailpagina heeft bij
`FAILED` een knop **Opnieuw proberen**: dezelfde offerte/PDF, een nieuwe huidige
job-ID. Artikelretry gebruikt `retry_article` met `resume_from=article_clone`,
`geometry_update`, `setup_refresh`, `cam_regeneration`, `postprocessing`, `simulation` of `measurement`. Update/refresh/CAM/post hervatten op bestaande
artikelparts, zonder opnieuw klonen. Wijzigingen alleen in BASELINE worden dan
niet naar het bestaande artikel gekopieerd. Retry vóór artikelbouw verstuurt de
bestaande aanvraag opnieuw; gedeeltelijke BASELINE-opbouw vraagt nog lokaal herstel.
Herstart de service na wijzigingen aan API/pipeline om deze retry-route te laden.

Bij fout eerst melding/log/bestanden bekijken; alleen bij opnieuw klonen een
mislukte artikelmap bewust archiveren vóór nieuwe poging. Geen
geprogrammeerde BASELINE verwijderen om een test te laten slagen. Callbackfouten
worden gelogd zonder automatische herbezorging. Queue/statussen zijn in geheugen;
herstart hervat werk niet. Houd servers tijdens demo aan, één aanvraag tegelijk.
De runner beëindigt zijn NX-procesboom bij timeout/cancel.

Alleen vijf parts native klonen; machine/kaak/toolresources blijven gedeeld.
Extra artikelgebonden parts vereisen clone-mapwijziging. Geen filesystem-copyfallback.
Andere kaakselectie wordt afgewezen. `DT=180` ondersteund bij klonen, `DT<180` niet;
initiële BASELINE vereist `DT>180`. Eerdere servicechecks melden 73023059, 73023060,
73024126 en 73024154 getest in NX 2512; deze sessie heeft dat niet herhaald.
Alle 18 varianten blijven buiten de eerste twee scenario's; geen volledige dekking
claimen. Runtime/licentie/templates/bibliotheken en behoud van CAM bevestigen bij W8.

## 7. Bewijslogboek

| Datum | Controle | Uitkomst |
| --- | --- | --- |
| 2026-09-16 | Inventarisatie/consolidatie | Eén DEMO.md; oude PLAN/TODO/FLOW in deze repo vervangen. |
| 2026-09-16 | Lokale setup/HTTP | Bun-seed hersteld; DB/ERP/S3 en servers bereikbaar. Eerste losse status/resultaatprobes bewezen alleen verbinding. |
| 2026-09-16 | Workflow-code | Migratie toegepast; Prisma gegenereerd; `bun run check`, `bun run build` geslaagd; 13 Python-tests inclusief familiepaden, vrijgave/herladen en foutstap. NX-aanroepen in tests zijn mocks. |
| 2026-09-16 | Echte ingelogde aanvraag | ERP-keuzes + Elster-PDF, 73023059/aantal 5 → S3/DB → NX → callback → `AWAITING_PROGRAMMING`. Detail HTTP 200 met setup-pad/programmeerknop. App-herstart na Prisma-migratie nodig. |
| 2026-09-16 | Clonefout onderzocht en hersteld | Kaakpart `SMW_GG-4002_012479_258-431MM_EXT.prt` onder oude `C:/Heerbaart_Custom/__Custom` en huidige `C:/Heerbaart/NX2512_Custom/NX2512_Custom` library heeft dezelfde SHA-256. Zoekpoging slaagde, maar padvergelijking wees die identieke kopie af. Alleen byte-identieke gedeelde libraryparts mogen nu wisselen; BASELINE-parts niet. NX-laadfouten worden vóór de referentievergelijking gemeld. |
| 2026-09-16 | Native clone + regressietests | Vijf parts succesvol aangemaakt onder `service/data/clone-check-b39b4de7/73023059`; logs in de bijbehorende `work`-map. Bestaande artikelparts niet gewijzigd. 21 Python-tests geslaagd, inclusief retry vanaf foutstap en identieke/verschillende librarykopieën. Update/refresh niet opnieuw uitgevoerd in deze clonetest. |
| 2026-09-16 | Native clone → update → refresh | Geslaagd op `service/data/refresh-check-1eac4448/73023059`. Refresh herkent drie identieke kaakparts over beide librarypaden en gebruikt de daadwerkelijk geladen kaak bij aanslagvlakcontrole. Ontbrekende oude positioneringsconstraints worden opnieuw opgebouwd; eindpositie/constraints blijven na save/heropen gevalideerd. `jaw_p3=102.142678938`; 22 Python-tests geslaagd. Bestaande live artikelparts niet gewijzigd. |

Bewaarde testaanvraag:
[`cmu44ou0r0000s8wi8eff3uae`](http://localhost:3000/app/quotations/cmu44ou0r0000s8wi8eff3uae),
oorspronkelijke overdrachtsjob `ca6cd9af251ff4e0496ec89e8`. W8 is door gebruiker bevestigd. Nog geen echte tijden, massa's,
of simulatieresultaten uit de nieuwe app-flow; echte NC-uitvoer is hieronder vastgelegd.

Toolpath-stap toegevoegd op 16-09-2026: 29 Python-tests en app ESLint/TypeScript
geslaagd. Alleen-lezen NX-inspectie vond 55 operaties, grotendeels `Regen` met
oude toolpaths. `CreateCamSession` en `GenerateToolPath` zijn gecontroleerd via de
geïnstalleerde NX 2512-bindings. De eerste API-runs strandden op acht `ONLYNOTES`-
bewerkingen buiten `O1234`. Na beperking tot `O1234` meldt de nieuwe native run
47 te regenereren bewerkingen. 59 voltooide save/heropen; gebruiker bevestigt werking.

Posten getest op 16-09-2026: 31 Python-tests en app ESLint/TypeScript geslaagd
(één bestaande lintwaarschuwing in de result-stub). De Okuma-post vervangt `_` in
de uitvoernaam door `-`; de integratie gebruikt daarom direct `<artikel>-SETUP.min`.
API-job 59 `c0b4a3d63a6d84bb38fb2057e` eindigde op `postprocessing` zonder fout,
log `service/data/elster-rev-d/work/post_ifw_h_4w/nx.log`, NC 297968 bytes.
API-job 60 `c06f54764c4fd46d0a91c6eed` voltooide CAM → post, log
`service/data/elster-rev-d/work/post_fdy_04ly/nx.log`, NC 298793 bytes.
Beide service-downloads: HTTP 200 en bytegelijk aan de lokale `.min`. De app-route
zonder sessie geeft 401; de gebruiker bevestigt inmiddels dat browserdownload
werkt en de NC-code oplevert. Ten tijde van deze posttest waren de bestanden nog
niet gesimuleerd; de geslaagde simulaties staan hieronder. Het verschil met de
handmatige referentie is door gebruiker als handmatige wijziging verklaard;
N3c is daarmee vervallen.

Externe simulatie afgerond op 16-09-2026. Twee oorzaken zijn vastgesteld:
`SuppressAll` is nodig voor headless CSE; alleen graphics onderdrukken blokkeert
bij de eerste toolwissel. Daarnaast gebruikte batch een andere Okuma-driver dan
de werkende interactieve snelkoppeling. De oorspronkelijke kit stopte bij
`TD=130010` met ontbrekende `GV_nPositionNr`, reproduceerbaar via Python en C#.
Alleen de simulatiestap gebruikt nu de CSE-/toolbibliotheken van
`C:/Heerbaart_Custom/__Custom`; overige stappen en artikelreferenties behouden
hun paden. De definitieve uitvoering blijft Python/API, kanaal 1, één
`PlayForward()`, zonder GUI of handmatige stappen.

| Artikel | API-job | CSE-eindtijd | Bewijslog onder `service/data/elster-rev-d/work` |
| --- | --- | --- | --- |
| 73023059 | `cb6a3190573df4a5e8ec20a38` | `01:04:48.790` | `simulation_9v10dy0m/nx.log` |
| 73023060 | `cbf15dfc41285470a8281afbd` | `01:04:55.880` | `simulation_hlvbc290/nx.log` |

Beide: SimEnd, nul collisions/limits/gouges/singularities, app-callback
`ARTICLE_CREATED` op stage `simulation`, geen fout. HTTP 409 tijdens verwerking,
daarna HTTP 200 met byte-identieke NC. 59: 298076 bytes, SHA-256
`4199872eaa1508061967e2888f60a813ed782a066dd4c2290f76ba0ad42e6061`.
60: 298793 bytes, SHA-256
`f7179623d8f800d5e157d84f17127dc4032dda0a398b4e4614ddf5ae4d44b050`.
De log van 60 bevestigt vooraf alle ingestelde controles actief; zijn vijf parts
en NC zijn vóór/na simulatie byte-identiek. De gebruiker bevestigt dat alles werkt.
37 Python-regressietests geslaagd, inclusief bibliotheekscheiding per stage,
onvolledige simulatie, collision en gewijzigde NC. Gewichten/tijden uitlezen en
resultaatopslag/-weergave blijven open; materiaaltoekenning is hieronder bevestigd.

Gebruikersbevestiging op 16-09-2026 voor N3c, A1–A3 en browserdownload:
N3c betrof een handmatige wijziging en is niet relevant. A1–A3 waren al getest
en werken prima; de browserdownload geeft de NC-code terug. Deze punten zijn
op basis van die praktijkbevestiging afgesloten, zonder nieuwe runs in deze
documentatie-update. Er zijn hiervoor geen nieuwe job-ID's of logs aangeleverd.

Opruiming: losse proefscripts, 21 diagnostische testmappen, verouderde testlogs
en uitgebreide CSE-traces verwijderd (circa 28,6 MB). De twee geslaagde API-runs
houden hun compacte `nx.log`, `request.json` en `result.json`. Artikelbestanden,
`simulation.json`, bronjournals en vaste regressietests blijven beschikbaar.

Materiaaltoekenning N1c getest op 16-09-2026, lokale test `material-check-20260916`:
native clone → geometrie-update → save → heropen van 73023059 met
`1.4301 - RVS 304`. PART-productbody en BLANK-ruwdeelbody hebben materiaal
`1.4301` en dichtheid 7900 kg/m³. De ingestelde massa-update op save werkt zonder
GUI. Gemeten bodies: product 143,396632 kg; ruwdeel 196,507583 kg.
BLANK-partattribuut `NX_Mass` is 339,904243 kg: inclusief de bronbody, dus niet
bruikbaar als ruwgewicht. N2a meet daarom uitsluitend de benoemde ruwdeelbody.
Een herhaalde geometrie-update met hetzelfde materiaal slaagt; BASELINE-hashes
zijn ongewijzigd. Bewijs onder `service/data/material-check-20260916/`:
`work/clone_129bziya/nx.log`, `work/update_8z938xjg/nx.log`,
`work/update_m3p3s20o/nx.log`, `verify.log` en `verified.json`.
37 Python-regressietests geslaagd. Deze test wijzigde alleen de aparte testkopie;
bestaande offertes/artikelen zijn niet opnieuw uitgevoerd.

Gewichtslevering N2a/R1a/R2a getest op 16-09-2026, testkopie
`service/data/material-check-20260916/73023059`: de productie-meetfunctie geeft
143,396632404 kg product en 196,507583286 kg ruwdeel terug. Log:
`work/measurement_2tghr225/nx.log`; uitvoer: `73023059/weights.json` en
`weights-callback.json` onder dezelfde testroot. De echte callback-handler,
PostgreSQL-opslag en gerenderde offerte-UI zijn getest met deze payload via
`heerbaart-app/tests/nx-weights.integration.mjs`: beide kg/stuk, totalen voor
aantal 5, lege bewerkingstijd en beschikbare NC kloppen. Tijdelijke testgegevens
zijn verwijderd; bestaande offertes zijn niet hervat of gewijzigd.
39 Python-tests geslaagd, app ESLint/TypeScript geslaagd (bestaande lintwaarschuwing
in result-stub). Een nieuwe volledige aanvraag is niet gestart in deze controle.

Vroege gewichtslevering op 16-09-2026: `measurement` verplaatst naar direct na
geometrie-update/save, vóór setup-refresh en CAM. Callback en UI tonen beide
gewichten al bij `IN_PROGRESS`; ze blijven behouden bij volgende stappen of een
latere fout. NC blijft geblokkeerd tot geslaagde simulatie. 40 Python-tests slagen,
inclusief levering vóór CAM en behoud bij CAM-fout. De database/UI-integratietest
bevestigt zichtbare stuk-/ordertotalen tijdens verwerking, behoud bij callbacks
zonder gewichten en NC-vrijgave pas bij simulatie. App ESLint/TypeScript slaagt
(lintwaarschuwingen zonder fouten). Bestaande offertes niet hervat of aangepast.

Gebruikersbevestiging op 16-09-2026: vroege gewichtslevering werkt in de echte app.
Screenshot van aanvraag `DEMO-GEWICHT`, artikel 73023060, materiaal
`1.4462 - Duplex F51`, aantal 1 toont productgewicht 138,49 kg en ruwgewicht
190,89 kg terwijl `setup_refresh` nog actief is. N2a/R1a/R2a zijn daarmee ook
in de live flow bevestigd. Het gedeelde aanvraagformulier start voortaan met
aantal 1 (voorheen 5); bestaande aanvragen blijven ongewijzigd.

Scopebesluit N2 op 16-09-2026: gebruiker wil uitsluitend de totale tijd die de
externe simulatie geeft, na SimEnd. Het eerdere voorstel om individuele
operatietijden uit CAM op te tellen vervalt voor deze POC-stap.
`MachineTime` werd al vastgelegd in `simulation.json`; nu geeft de geslaagde
simulatiestap ook `simulation_time_seconds` terug en draagt de eindcallback deze
over aan de app. Migratie `20260916020000_add_simulation_time` toegepast.
Test met echte opgeslagen tijd van 73023059: `01:04:45.790` = 3885,790 seconden.
Callback → DB → UI inclusief aantal 5 geslaagd; vóór afronding blijft de tijd leeg,
na afronding kloppen minuten/stuk en ordertotalen. Geen operatieregels aangemaakt.
41 Python-tests geslaagd, ESLint/TypeScript geslaagd met bestaande lintwaarschuwingen.
Geen bestaande offertes hervat of achteraf ingevuld; live bevestiging van deze
nieuwe tijdlevering volgt bij een nieuwe run. App en NX-service zijn daarna
herstart; de nieuwe callbackvelden zijn op beide draaiende servers gecontroleerd.

Scope en gebruikersbevestiging op 17-09-2026: N4c werkt bij handmatig openen en is
afgevinkt. Lokale NC-opslag en de bestaande browserdownload zijn voldoende voor
de POC; NC naar S3 vervalt als eis voor R1. R1 blijft open voor overige
simulatiedetails en afronding. Nieuw open punt R3: één opgeslagen bewerking voor
de gebruikte machine met de totale simulatietijd per stuk, zodat deze later naar
ERPNext kan voor de BOM. Geen individuele CAM-operaties importeren. Deze update
wijzigt alleen de afspraken/documentatie; R1 en R3 zijn nog niet geïmplementeerd.

ERPNext-uitbreiding uitgevoerd op 17-09-2026: migratie
`20260917010000_erp_bom_operations`, vijf opgeslagen bewerkingsregels en knop voor
artikel/concept-BOM. Bestaande aanvraag 73023059 heeft dezelfde routing gekregen,
met behoud van de berekende NX-tijd en aanvankelijk lege handmatige tijden.
Tijdens de eindcontrole is deze aanvraag inmiddels via de app geëxporteerd naar
`BOM-73023059-001`: concept, 1 Piece, vijf juiste bewerkingen en 198,995021 Kg MAT-14404;
alleen-lezen geverifieerd. R3 is gereed; R1 blijft open voor overige simulatiedetails
en `READY`. Echte ERP-integratietest en browsertest geslaagd op tijdelijke aanvragen;
de test-BOMs, testartikelen en lokale testgegevens zijn verwijderd. Vier overige
werkplekken hergebruikt; Okuma/Draaifrezen/Draaifreesmachine aangemaakt met €0/u.
De gebruiker autoriseerde uitsluitend de Kg-conversiecorrectie van MAT-14462;
stock-UOM Meter en overige materiaalgegevens zijn behouden. Zie ERPNext.md.

Instelbladexport getest op 17-09-2026: artikel 73023059, 64 pagina's via de
geïnstalleerde Siemens-app. Automatisch starten/exporteren/sluiten geslaagd;
de vijf NX-parts, NC en `simulation.json` blijven bytegelijk. Bewijs:
`service/data/elster-rev-d/work/setup_sheet_94euptb_/` en
`service/data/elster-rev-d/73023059/73023059_INSTELBLAD.pdf`.
45 Python-tests en app ESLint/TypeScript geslaagd (bestaande waarschuwingen).
Callback → database → UI getest, inclusief vroege CSE-tijd en PDF-downloadknop.
Standaard Siemens-layout behouden zoals afgesproken; geen nieuwe infrastructuur.
Nieuwe runs exporteren automatisch; bestaande aanvragen zijn niet opnieuw gedraaid.

Voeg volgende controles toe met datum, taak-ID, bestand/log en uitkomst. Vink
praktische NX-stappen pas af na hun eigen bewijs; maak geen parallel PLAN/TODO/FLOW.
