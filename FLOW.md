# Elster POC: klantvraag → BASELINE → artikel → NX-resultaten

## 1. Goal and agreed scope

Demonstrate the complete interaction between the offerteformulier in
`heerbaart-app` and the NX service in `heerbaart-demo`, running on a separate
Windows laptop with NX installed.

The demonstration has two paths:

1. **First request:** create a missing BASELINE, show that programming is needed,
   let the programmer finish it in NX and mark it ready in the app, then generate
   the article requested by that original klantvraag.
2. **Next request:** use the programmed BASELINE to generate another article in
   the family automatically, including CAM, simulation, NC output, times, and weights.

Agreed choices:

- Support only the existing **Elster Rev.D** family, `elster-rev-d`.
- Select the requested variant by its **article number**. Its seven expressions
  (`DT`, `FA`, `DR`, `FR`, `FB`, `DS`, `DL`) come from the extracted PDF table.
- Use **one material** for the demo. ERPNext and NX already use the same material
  names, so pass the ERPNext **display label** directly to NX.
- **Trust programmer approval.** Clicking “Programmering gereed” means the saved
  BASELINE is ready. Reuse the current readiness flag and ordinary file checks;
  do not add a CAM approval/validation subsystem.
- Display real processing stages while NX is working.
- Return NX operation-time estimates, finished-product weight, raw-stock weight,
  simulation outcome, and the posted NC files to the app.
- Use ERPNext for the existing customer/material data. The resulting article and
  calculations are presented in the app; ERP Item/Quotation creation is outside
  this demonstration.
- Keep the implementation close to the existing serial worker, local family
  files, HTTP callbacks, and app database/storage.

This is an implementation plan. The proposed actions, payload fields, and result
handling below still need to be built. It extends the original [POC plan](PLAN.md),
whose delivery boundary was updated NX files and status-only callbacks.

## 2. Current starting point

| Area | Already implemented | Work for this flow |
| --- | --- | --- |
| Offerteformulier | Customer/material selection, PDF upload, local quotation, NX dispatch | Article-number input and the programming handoff |
| PDF and BASELINE | Extract the 18-row table; build PART, ASSY, CAD4CAM, BLANK, SETUP | Choose the workflow based on existing family state; report stages/results |
| Programming ready | `mark_baseline_ready()` records a boolean after basic setup/file checks | App button and continuation to the originating article |
| Article generation | Native clone, expression update, geometry/dependency update, setup refresh | Regenerate CAM, measure, postprocess, simulate |
| Material | App sends the material label | Worker currently discards it; pass it into NX and apply the named material |
| Status | `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED` callbacks | Include the current stage and separate job completion from quotation readiness |
| App results | Weight field and editable operation table | Result callback currently only logs; persist measurements and NC files |
| Posting/simulation | Working interactive configuration on the NX laptop | Record/implement callable automation against that configuration |

**Important:** the app currently maps any `COMPLETED` callback to “Gereed”. That
is wrong for a completed BASELINE build: the next business state is
**“Wacht op programmeren”**.

The service's current article pipeline ends after cloning and setup refresh.
Copied CAM data is not evidence that the new article's toolpaths have been
regenerated, simulated, or posted.

## 3. Responsibilities and files

```text
Browser
  ↕ authenticated app pages/actions + progress polling
heerbaart-app
  ├─ klantvraag, job association, displayed state, operations and measurements
  ├─ existing S3 storage: original PDF + returned NC files
  ├─ existing ERPNext customer/material integration
  │
  ├─ POST /start/nx-job ──────────────────────────────┐
  │                                                 ▼
  │                                   heerbaart-demo on NX laptop
  │                                     ├─ one serial worker
  │                                     ├─ family.json + native NX files
  │                                     └─ NX journals, CAM, posting, simulation
  │                                                 │
  └─ /api/nx/status and /api/nx/result ◀───────────────┘
```

The app server talks to the laptop. The browser reads progress from the app.
The NX service owns the engineering decisions and the local BASELINE state.
The app owns the klantvraag and its presentation.

Native files keep the existing layout:

```text
<NX_DATA_DIR>/elster-rev-d/
  drawing.pdf
  family.json
  BASELINE/
    BASELINE_PART.prt
    BASELINE_ASSY.prt
    BASELINE_CAD4CAM.prt
    BASELINE_BLANK.prt
    BASELINE_SETUP.prt
  73023059/
    73023059_PART.prt
    73023059_ASSY.prt
    73023059_CAD4CAM.prt
    73023059_BLANK.prt
    73023059_SETUP.prt
    nc/                         proposed destination for postprocessor output
```

BASELINE is an independent family template. The first table row supplies its
initial dimensions; it is not itself a numbered article. Each requested article
gets its own five files. Machine, jaw, and tool-library resources remain shared.
Keep manual article-owned work within the five files covered by the existing
clone map.

## 4. Flow A — first klantvraag, no BASELINE

Example: article **73023059**, quantity **5**, the agreed material, and the
supported Elster Rev.D PDF.

1. **Submit the offerteformulier.** Save the quotation and drawing in the app.
   Create an NX job associated with that quotation and dispatch it to the laptop.
2. **Prepare the family.** The service sees that the BASELINE is absent, extracts
   the table, and checks that the requested article occurs in it before starting
   the expensive NX construction.
3. **Generate BASELINE files.** Run the existing part, structure, and setup stages.
   Report their progress as they happen.
4. **Hand off to the programmer.** Return `AWAITING_PROGRAMMING` with the setup
   location. The app shows “Wacht op programmeren”. This job has finished; it does
   not remain running while the programmer works.
5. **Program in NX.** Open `BASELINE_SETUP.prt`, prepare the machining program,
   then save and close the relevant NX files.
6. **Mark programming ready in the app.** The app starts a new job for the same
   quotation and requested article. The service calls `mark_baseline_ready()` and
   immediately continues to article generation. The programmer's assertion is
   sufficient; there is no additional approval procedure.
7. **Generate article 73023059.** Clone BASELINE, apply that article's expressions,
   update its geometry/dependencies, and refresh its setup.
8. **Finish in NX.** Regenerate the copied CAM toolpaths, obtain times and weights,
   run the configured postprocessor, and run the configured simulation.
9. **Deliver results.** Send measurements, simulation outcome, and all required
   NC files to the app. The app saves them and shows “Gereed”.

The simulation step must match the working laptop setup. For simulation of
posted NC, posting precedes simulation, as shown here. Establish that exact
automation sequence on the laptop rather than inferring success from a completed
postprocessor invocation.

```text
Klantvraag → BASELINE genereren → Wacht op programmeren
                                      │
                         programmer saves + marks ready
                                      ▼
                Artikel genereren → NX-afwerking → Resultaten → Gereed
```

If article generation fails after the programmer's approval, the baseline can
remain ready. The quotation shows the failed article stage and its error.

## 5. Flow B — another article, BASELINE ready

Example: a new klantvraag requests **73023060**, using the same material.

1. Submit the form with the requested article number.
2. The service loads the existing family and sees `baseline_ready = true`.
3. Look up 73023060 in the saved table; reuse its stored expressions.
4. Run the same article-generation and NX-finishing path used in Flow A.
5. Deliver the results and NC files; the app becomes “Gereed” automatically.

```text
Klantvraag → BASELINE gereed → Artikel genereren → NX-afwerking → Resultaten → Gereed
```

The original family table is reused. The new request's uploaded drawing remains
attached to its klantvraag; it does not silently replace the existing family.
For this POC, use the same supported family drawing/revision in both requests.

### Small baseline decision table

| Existing state | Action |
| --- | --- |
| No family/BASELINE | Extract the table and build BASELINE, then wait for programming |
| BASELINE setup complete, readiness flag false | Return the same programming handoff; reuse its files |
| Readiness flag true | Generate the requested article immediately |
| Earlier construction left an incomplete family | Show the failed/incomplete stage; use the existing stage tooling to continue after diagnosis |

Do not treat “directory exists” as “ready”, or resubmit the complete baseline
build over existing files. The current pipeline deliberately refuses overwrites.

## 6. Visible stages and app presentation

### Stage identifiers

Emit an `IN_PROGRESS` update when entering each stage. Advancing to the next
stage means the preceding call succeeded; a failure stays attached to its stage.

| BASELINE stage | App label |
| --- | --- |
| `pdf_extract` | Tekening uitlezen |
| `baseline_part` | Basismodel maken |
| `baseline_structure` | Assemblage en ruwdeel maken |
| `setup_load` | Machine laden |
| `setup_constraints` | Opspanrelaties aanbrengen |
| `setup_holders` | Klemmen plaatsen |
| `setup_position` | Product positioneren |
| `setup_references` | Referenties koppelen |
| `result_delivery` | Resultaten versturen |

| Article stage | App label |
| --- | --- |
| `article_clone` | BASELINE kopiëren |
| `geometry_update` | Afmetingen aanpassen |
| `setup_refresh` | Opspanning bijwerken |
| `cam_regeneration` | Gereedschapsbanen genereren |
| `measurement` | Tijden en gewichten uitlezen |
| `postprocessing` | NC-programma maken |
| `simulation` | Simuleren |
| `result_delivery` | Resultaten versturen |

Pass a small progress callback from the worker through the pipeline and report
around the actual stage calls. The existing setup already has separate NX calls
for load, constraints, holders, position, and references.

Use that same process-per-stage approach for the new finishing stages, with the
related NX code kept together. Save the outputs needed by the next stage. This
provides live stage changes through the existing Python worker; NX journals do
not need to call the app themselves.

The app polls its own persisted progress approximately **every two seconds while
a job is active**. A small client component can call `router.refresh()` to reread
the quotation and its active job through the existing authenticated server page.
Stop that interval when the job finishes. Show completed steps, the current step,
upcoming steps, and elapsed time. A long NX call remains on its real stage with a
running timer; do not manufacture intermediate percentages or completion events.

### Quotation states

Reuse `QUEUED`, `PROCESSING`, `READY`, and `FAILED`, and add
`AWAITING_PROGRAMMING`.

```text
QUEUED → PROCESSING → AWAITING_PROGRAMMING
                            │ programmer marks ready
                            ▼
                         QUEUED → PROCESSING → READY

Ready-baseline request: QUEUED → PROCESSING → READY
Any active job can fail: show FAILED + the stage and error.
```

Transport/job status and quotation state are separate. A `COMPLETED` status
callback alone never changes the quotation to `READY`; the accepted result
determines whether it is awaiting programming or ready.

### Detail page

Use the existing quotation detail page, with a progress section above the
measurements and operations. While programming is required, show:

- **Wacht op programmeren**.
- The exact `BASELINE_SETUP.prt` location and save/close instructions.
- **Programmering gereed — genereer artikel**.

The setup path is a location on the NX laptop: offer a copyable path for the
programmer, rather than pretending it is a browser-download URL.

Example completed view; all numbers here are illustrative:

```text
Artikel 73023059 · Elster Rev.D                         Gereed
Materiaal: <shared ERPNext/NX material name>             Aantal: 5

NX-bewerkingstijd/stuk       Voor 5 stuks
20 min                      100 min

Productgewicht/stuk         Ruwgewicht/stuk
24,6 kg                     31,2 kg

Totaal productgewicht       Totaal ruwgewicht
123 kg                      156 kg

Bewerkingen                 NX-schatting per stuk
Buitendraaien                12 min
Boren                       8 min

Simulatie                   Geslaagd
NC-programma                Download 73023059_MAIN.nc
```

Label the machining time as an **NX estimate**. Keep manually entered operations
and setup/programming time distinguishable from that estimate.

## 7. Proposed API contracts

Keep `POST /start/nx-job`, `GET /jobs/{job_id}`, and the app's two existing callback
routes. Add two explicit app-facing action values to the current action list:

- `prepare_quotation`: inspect family state and build BASELINE or generate an article.
- `approve_baseline_and_generate`: record programmer approval, then generate the
  article requested by the originating quotation.

These are small branches around existing functions, not a new workflow engine.
The existing low-level actions remain useful for the current CLI and laptop work.

### 7.1 App → NX: start a job

`POST /start/nx-job`, `multipart/form-data`:

| Field | Meaning |
| --- | --- |
| `job_id` | New app-owned job ID for this action, matching the existing lowercase CUID-compatible format |
| `quotation_id` | The app quotation associated with this job |
| `action` | One of the two app-facing actions above |
| `article_number` | Eight-digit requested article number |
| `material` | Exact shared ERPNext/NX material display name |
| `amount` | Positive integer quantity; used for order totals, not to clone the part repeatedly |
| `drawing` | PDF for `prepare_quotation`; omitted for programmer approval |

Example form fields:

```text
job_id=cnxjob001
quotation_id=cquote001
action=prepare_quotation
article_number=73023059
material=<shared ERPNext/NX material name>
amount=5
drawing=<Elster Rev.D PDF file>
```

Response: `201 Created` with the existing response shape:

```json
{ "job_id": "cnxjob001" }
```

The programmer button sends a second request:

```text
job_id=cnxjob002
quotation_id=cquote001
action=approve_baseline_and_generate
article_number=73023059
material=<shared ERPNext/NX material name>
amount=5
```

The second quotation uses `prepare_quotation` again, with its own quotation/job
IDs and article 73023060. The service chooses the ready-baseline path.

Keep immediate request errors separate from job failures: malformed/missing fields
return `422`, and an already-claimed job ID returns `409`. A failure discovered
during extraction or NX execution is reported asynchronously as `FAILED`.

### 7.2 NX → app: progress

`POST /api/nx/status`, `application/json`:

```json
{
  "job_id": "cnxjob001",
  "quotation_id": "cquote001",
  "status": "IN_PROGRESS",
  "stage": "setup_holders",
  "stage_started_at": "2026-09-16T09:15:00Z",
  "error": null
}
```

Keep the existing four job statuses. `stage` and `stage_started_at` can be null
while queued; retain the current stage when reporting a failure. For example:

```json
{
  "job_id": "cnxjob002",
  "quotation_id": "cquote001",
  "status": "FAILED",
  "stage": "postprocessing",
  "stage_started_at": "2026-09-16T09:40:00Z",
  "error": "The configured postprocessor did not produce the expected NC output."
}
```

Extend `GET /jobs/{job_id}` to return the same status shape for laptop diagnosis.
An unknown job returns `404`. The status callback returns `204` after an accepted
update. The normal browser progress path reads the app database, not the laptop
directly.

### 7.3 NX → app: outcome and NC files

Use `POST /api/nx/result`, `multipart/form-data`, for both successful outcomes:

- `result`: a JSON string containing the metadata.
- Named file parts matching `nc_files[].field` for an article result.

**BASELINE prepared:** `result` contains the following JSON; there are no NC
attachments yet.

```json
{
  "job_id": "cnxjob001",
  "quotation_id": "cquote001",
  "outcome": "AWAITING_PROGRAMMING",
  "family": "elster-rev-d",
  "article_number": "73023059",
  "material": "<shared ERPNext/NX material name>",
  "baseline_setup_path": "C:\\Heerbaart\\demo-data\\elster-rev-d\\BASELINE\\BASELINE_SETUP.prt"
}
```

**Article complete:** illustrative metadata, not measured NX output:

```json
{
  "job_id": "cnxjob002",
  "quotation_id": "cquote001",
  "outcome": "ARTICLE_READY",
  "family": "elster-rev-d",
  "article_number": "73023059",
  "material": "<shared ERPNext/NX material name>",
  "amount": 5,
  "timing": {
    "source": "nx_toolpath_estimate",
    "basis": "per_piece",
    "operations": [
      {
        "operation_id": "TURN_OD",
        "sequence": 1,
        "name": "Buitendraaien",
        "seconds": 720
      },
      {
        "operation_id": "DRILL",
        "sequence": 2,
        "name": "Boren",
        "seconds": 480
      }
    ],
    "operation_sum_seconds": 1200
  },
  "weight": {
    "product_kg_per_piece": 24.6,
    "stock_kg_per_piece": 31.2
  },
  "simulation": {
    "status": "passed"
  },
  "nc_files": [
    {
      "field": "nc_main",
      "filename": "73023059_MAIN.nc"
    }
  ]
}
```

The multipart body also contains `nc_main`, holding the actual postprocessor
output bytes. Include additional file entries/parts if the configured post emits
subprograms. The example `.nc` name is illustrative; use the working post's actual
output names and extensions.

The app stores these attachments in its existing S3 storage, using app-generated
object keys associated with the quotation and job. It stores the resulting file
references with the metadata. Return `204` after accepting either outcome.

Provide an authenticated app download route such as
`GET /api/quotations/{quotation_id}/nc/{file_id}`. Resolve its storage key from the
saved result, and check the user's organization owns the quotation. Native `.prt`
files and detailed NX logs stay on the laptop.

### 7.4 Small integration rules

- Use `job_id` consistently, replacing the current result handler's `jobId` naming.
- Give each action its own job record. Persist its quotation association before
  dispatch, so an immediate callback can be matched correctly.
- Use the existing `X-API-Key` callback convention and check the key at the app.
  Add the same simple header check on the job API. Use the existing request-schema
  approach for IDs, actions, file parts, numbers, and outcomes at the HTTP boundary.
- Resolve quotation ownership from the stored job. A missing ID must never
  reach an unfiltered database update. Ignore late status changes for a quotation's
  earlier job once a newer action is active.
- Send the result before the final `COMPLETED` notification. Accepted results
  determine quotation state and are not undone by late status callbacks.
- Save NC attachments, then apply the measurements, operations, file references,
  and quotation outcome together in the app database. Set `READY` only then.
- Record that a job result was accepted. A repeated delivery receives `204`
  without duplicating operations or overwriting subsequent user edits.
- Keep the completed result and NC files on the laptop. Retry result delivery a
  small bounded number of times with the same job ID; a delivery failure is
  `FAILED` at `result_delivery` and can be resent from saved output. It must not
  trigger another clone or CAM run.
- If dispatch fails, retain the saved klantvraag and drawing and display the
  failure. The current app deletes them on dispatch failure; change that behavior.

## 8. Times, material, and weight

### Material

Keep sending `material.label` from the app. Pass it through `api/worker.py`,
`pipeline.py`, and the NX request JSON. Use the identically named NX material for
the generated product and stock body. Restrict the demo form to the agreed
material name. Reuse the existing name match rather than introducing a mapping
table or conversion service.

### Machining estimates

Read the programmed operations **after regenerating the requested article's
toolpaths**. For this family, use the programmed operation names as identifiers
and keep them unique in the baseline. Return the ordered operation list and
normalize durations to seconds at the NX boundary.

Compare one extracted duration with NX on the laptop to establish the API's
units and treatment of cutting/rapid motion. Record the actual source used.
These are toolpath estimates; manually measured shop-floor time and setup time
are separate quantities.

```text
displayed operation minutes = returned seconds / 60
estimated machining minutes per piece = operation_sum_seconds / 60
estimated machining minutes for order = per-piece estimate × quantity
```

The sum is an operation-time estimate. In particular, do not label it as a
synchronized multichannel cycle time merely because its operations belong to
the same machine.

Reuse `QuotationOperation.timeMinutes`, converting from seconds. Import rows as
`source = NX`; replace previous NX rows when applying a genuinely new calculation,
and retain `MANUAL` rows. Preserve the returned NX snapshot in the result metadata.
Explain that a new calculation replaces edits to NX-derived rows.

NX does not supply an hourly rate. For this POC, the existing required
`hourlyRate` can use `0` as an unset import placeholder, displayed as “Niet
ingesteld” on those NX rows until a rate is entered. The metric cards report time
and weight, not a calculated selling price.

### Product and raw-stock weight

- Measure the finished solid in `<article>_PART.prt` for product mass.
- Measure the generated stock body in `<article>_BLANK.prt`, identified by the
  existing `BLANK_REVOLVE_OUTLINE_BODY` name, for raw-stock mass.
- Apply/use the agreed NX material and its density on the measured bodies.
- Exclude machine/fixture parts and linked duplicate product bodies. Measuring
  the whole SETUP or every body in BLANK would count the wrong geometry.
- Normalize the returned mass to kilograms. If the NX implementation combines
  volume and density, convert units explicitly: `mm³ × kg/m³ × 10^-9 = kg`.

```text
product mass for order = product kg per piece × quantity
raw-stock mass for order = stock kg per piece × quantity
```

Assume one generated blank per piece for this demo. The stock is the existing NX
Revolve Outline blank with its 5 mm offset. Present that stock basis in the app;
the current Cylinder/Blok/Casting selection does not control this NX pipeline and
must not be presented as the basis of the calculated raw weight.

## 9. Concrete implementation work

### `heerbaart-demo`

| Location | Focused change |
| --- | --- |
| `service/api/schema.py`, `service/api/main.py` | Add the two action values, quotation association, stage fields and outcomes; save drawings for `prepare_quotation`; require article/material/quantity for app actions |
| `service/api/worker.py` | Pass material and quantity through, report stages, retain pipeline output, deliver the result before completion |
| `service/api/notifier.py`, `service/api/config.py` | Extend status payloads; add multipart result delivery and its callback path |
| `service/api/store.py` | Store the current stage/time/error with the existing in-memory job status |
| `service/pipeline.py` | Add the family-state decision; connect programmer approval to initial article generation; extend article generation with finishing stages |
| `service/nx/entry.py` | Dispatch the new finishing calls through the existing journal entrypoint |
| `service/nx/finish.py` (new) | Keep related material, CAM regeneration, measurement, posting, and simulation code together, using the laptop's working setup |

Keep the function surface small:

| Function | Treatment |
| --- | --- |
| `prepare_baseline()` | Reuse; add progress and material propagation. Check the requested row after extraction and before building the part. |
| `mark_baseline_ready()` | Reuse the programmer assertion and current basic file/setup checks. |
| `generate_article()` | Reuse clone/update/refresh; append the finishing calls and return their combined result. |
| `prepare_quotation(...)` | New small coordinator for the baseline decision table. |
| `run_job(...)` | Add the approval branch: mark ready, reload the saved family, then generate the requested article. Reloading matters because the current readiness function saves a new dict rather than mutating its argument. |
| NX finishing entrypoint | Run the requested finishing step against the saved article; keep SDK-specific code together and let normal NX failures surface. |
| Notifier `send_status(...)` / `send_result(...)` | Extend the existing status method and add result delivery. |

The NX SDK calls for regeneration, simulation, posting, and mass/time extraction
must be recorded or implemented against **NX 2512 on the laptop**. A working
interactive configuration is the starting point, not yet a callable journal.
Reuse the configured machine, tools, simulation, and postprocessor directly.

### `heerbaart-app`

Paths below are relative to the sibling `heerbaart-app` repository.

| Location | Focused change |
| --- | --- |
| `src/lib/offerte-form.ts`, `src/components/offertes/offerte-form.tsx` | Add an eight-digit article number; use the agreed material and identify the NX-generated stock basis |
| `src/app/(app)/app/quotation-form/actions.ts` | Create a job association, dispatch `prepare_quotation`, retain the request on dispatch failure |
| `prisma/schema.prisma` + migration | Add article number, stock weight, waiting-for-programming status, result metadata, and job tracking |
| `src/app/api/nx/status/route.ts` | Check callback key/payload/job association; store stage and errors instead of equating completion with quotation readiness |
| `src/app/api/nx/result/route.ts` | Parse multipart results, save NC files, apply the outcome and measurements |
| `src/app/(app)/app/quotations/[id]/actions.ts` | Add the programmer-ready action using the stored article/material/quantity |
| `src/app/(app)/app/quotations/[id]/page.tsx` and its components | Progress polling, programming handoff, measurement cards, simulation outcome, NC downloads |
| `src/components/offertes/quotation-operations.tsx` | Display imported NX estimates and preserve the existing manual-operation workflow |
| New NC download route under `src/app/api/quotations/` | Serve saved NC files after the normal session/organization check |

Reuse `Quotation` as the klantvraag. Keep its existing product `weight` field,
define it as kg per piece, and add `stockWeight` with the same basis. Store the
NX-specific output snapshot and artifact references in a result JSON field.

A small related job record is enough: ID, quotation ID, action, status, current
stage/start time, error, and whether its result has been applied. The quotation
tracks its active job. This supports the separate initial and programmer-ready
actions without introducing family or baseline database models. `family.json`
remains the source of the single baseline's readiness.

## 10. Laptop setup and implementation order

### Before the connected demo

Use the existing [service setup instructions](service/README.md). Confirm:

- NX 2512, Python/Pixi, journal execution, licensing, and the existing Heerbaart
  machine/jaw/tool resources work on the laptop.
- The agreed material label matches NX exactly and has usable density data.
- The interactive postprocessor and simulation are available, and their automated
  calls have been exercised on a programmed article.
- The app server can reach the laptop over the configured NetBird connection,
  and the laptop can call the app back.
- Set the existing `NX_HOST`, `NX_PORT`, `NX_DATA_DIR`, `NX_INSTALL_DIR`, and
  `NX_CUSTOM_DIR` for that laptop. `NX_HOST` currently defaults to localhost;
  bind the intended reachable interface for this demo.
- Set app `NX_WORKER_URL` to the laptop URL. Set service `NX_CALLBACK_URL` to the
  app, `NX_CALLBACK_STATUS_PATH=/api/nx/status`, and add
  `NX_CALLBACK_RESULT_PATH=/api/nx/result` during implementation.
- Configure matching HTTP keys. The existing service `NX_CALLBACK_API_KEY` is
  outbound only; implement its verification in the app and configure a key check
  for incoming NX job requests. Keep credentials in environment configuration.
- Run one API instance and its single worker. Keep the API running through both
  scenarios; its job queue/status store currently lives in memory.

### Build in this order

1. **Make progress and the programming handoff visible.** Add article/job
   association, the two actions, stage callbacks, the `AWAITING_PROGRAMMING`
   result, and its app state. Exercise the existing baseline/clone path with the app.
2. **Prove NX finishing on the laptop.** Automate the working regeneration,
   measurement, posting, and simulation sequence; compare its outputs with NX.
3. **Complete article result delivery.** Persist operations and weights, upload
   NC files, and expose downloads. Make accepted results drive quotation readiness.
4. **Rehearse both paths end to end.** Use a fresh data root for the first path,
   then reuse its programmed baseline for the second.

Use the project's existing checks for changed application code and focused
contract checks for callback/result handling. Native NX behavior must be exercised
on the laptop; local mocked checks do not establish CAM or simulation correctness.

## 11. Demo script and completion checks

### Scenario A: fresh start

- [ ] Select a new `NX_DATA_DIR` for the rehearsal so an existing programmed
      baseline is not overwritten.
- [ ] Submit article 73023059, the supported PDF, the chosen material, quantity 5.
- [ ] Show the live baseline stage list advancing in the app.
- [ ] Show “Wacht op programmeren” and the correct setup path, rather than “Gereed”.
- [ ] Program and save BASELINE in NX; click “Programmering gereed” in the app.
- [ ] Show the initial requested article generating without a second form submission.
- [ ] Show article stages, NX estimates, both weights, and simulation outcome.
- [ ] Download the actual NC output and compare it with the laptop's posted file.

### Scenario B: ready BASELINE

- [ ] Submit article 73023060 with the same material and family drawing.
- [ ] Show the service taking the article path without a programming handoff.
- [ ] Show changed dimensions and freshly regenerated estimates/results in NX and
      the app, rather than measurements inherited from the baseline.
- [ ] Check that BASELINE and the first article still have their original files
      and values; the second article uses its own cloned dependencies.

### Small failure/replay checks

- [ ] An NX failure is visible at its actual stage and does not produce “Gereed”.
- [ ] An unavailable laptop leaves the saved klantvraag visible with a dispatch error.
- [ ] Sending the same successful result twice does not duplicate operations;
      manually added operations remain present.
- [ ] Missing/unknown job IDs and unauthenticated callbacks are rejected without
      changing quotations.

Current article generation refuses existing destinations. After a failed native
stage, inspect the retained NX log and files before another attempt. Use the
existing stage tooling for baseline recovery and archive a partial article when
a fresh generation is needed. A failed callback is a delivery retry, not a reason
to rerun NX or overwrite a programmed baseline.
