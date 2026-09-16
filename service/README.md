# Elster Rev.D NX POC

The central scope, local setup, end-to-end flow, and progress checklist are in
[DEMO.md](../DEMO.md). This README documents the currently implemented low-level
service. Missing finishing/result features below are implementation gaps, not
exclusions from the demo's target scope. Both servers run on this laptop first;
NetBird is deferred.

One Windows service receives a PDF, extracts the eighteen article rows with
OpenAI, builds an independent BASELINE, and later generates requested articles
from its manually programmed setup. Generated files remain on the laptop.
Status callbacks include the current stage, error, workflow outcome/setup path,
per-piece product/stock weights after measurement, and total CSE time after SimEnd.

The 2026-09-16 checks include 41 Python tests and native API simulation of the
external NC files for 73023059 and 73023060 through SimEnd, with zero reported
collisions, limits, gouges or singularities. Downloads stay blocked until this
result is recorded for the exact NC hash. Current acceptance evidence and the
remaining measurement and result-storage work are in DEMO.md.

## Currently Implemented Scope

- Only the supplied single-page Elster Rev.D drawing and its known STAP1-11 model.
- Separate `BASELINE` item, seeded with the first table row's dimensions.
- Native PART, ASSY, CAD4CAM, BLANK, and SETUP files per item.
- BLANK always uses Revolve Outline, a 360-degree revolve, and a 5 mm offset.
- During article geometry update, the first word of the ERPNext material name
  (e.g. `1.4301 - RVS 304` → `1.4301`) selects the material from
  `C:/Heerbaart/Materials/Heerbaart_Materials.xml`. It is assigned to the PART
  product body and `BLANK_REVOLVE_OUTLINE_BODY` before save; NX updates mass on save.
  BLANK's total `NX_Mass` also includes its source WAVE body; measurement therefore
  selects only `BLANK_REVOLVE_OUTLINE_BODY` for stock weight.
- One machine/jaw strategy, with article-dependent opening and clearance values.
- Automatic regeneration of CAM program `O1234` after setup refresh.
- Automatic Okuma posting of `O1234` to `<article>-SETUP.min`.
- External NC simulation after posting; download requires complete, clean CSE
  results for the same NC SHA-256. Native acceptance is tracked in DEMO.md.
- Before simulation, Program Manager's external main program on channel 1 is
  replaced with the article's `.min` and the SETUP is saved. Manual reopening
  therefore keeps the article NC reference instead of the cloned baseline one.
- Immediately after geometry update/save, `measurement` reopens PART/BLANK and measures each
  target body in kilograms. It writes `weights.json` and returns
  `weights: {product_kg, stock_kg}` with an `IN_PROGRESS` callback before setup refresh/CAM.
  The app immediately stores both masses and displays per-piece/order totals while
  processing continues. Later status callbacks without weights preserve those values.
  Retry from `measurement` remeasures, then continues refresh/CAM/post/simulation.
- Successful simulation returns total `MachineTime` as `simulation_time_seconds`.
  The completion callback stores it in the app; the UI shows minutes per piece
  and minutes × quantity. No individual operation times are read or imported.
  Completion is still `ARTICLE_CREATED`,
  at stage `simulation`; full result delivery is needed before `READY`.
- No NATS, database, new UI, or distributed job system.

The service runs directly on Windows, using loopback for the local demo. Legacy
NATS and Docker files have been removed. The original modeling projects are not
needed at runtime. Later remote operation can use native NetBird connectivity.

## Laptop Configuration

Requirements: Windows, Pixi, licensed Siemens NX 2512, and the already-installed
Heerbaart template, machine/device libraries, and HB thread catalog.

Configuration is loaded from `.env` in this directory. `.env.example` lists the
settings. The OpenAI key belongs in this local, Git-ignored `.env`:

```dotenv
OPENAI_API_KEY=your-key-here
```

Important settings:

| Setting | Purpose / default |
| --- | --- |
| `OPENAI_MODEL` | Structured table extraction model; `gpt-4.1`. |
| `NX_INSTALL_DIR` | `C:/Program Files/Siemens/DesigncenterNX2512`. |
| `NX_CUSTOM_DIR` | `C:/Heerbaart/NX2512_Custom/NX2512_Custom`. |
| `NX_SIMULATION_CUSTOM_DIR` | Simulation-only CSE machine/tool library root; this laptop uses `C:/Heerbaart_Custom/__Custom`, matching the working interactive launcher. Other stages and setup references keep `NX_CUSTOM_DIR`. |
| `NX_PYTHON_HOME` | Optional; defaults to the active Pixi Python 3.12 environment. Simulation always uses NX's bundled Python. |
| `NX_JOURNAL_TIMEOUT` | Seconds per NX process; `900`. Increase if full model construction needs longer. |
| `NX_DATA_DIR` | Local uploads, family files, parts, and logs; `data`. |
| `NX_HOST` | `127.0.0.1` locally; set the laptop's NetBird address for remote requests. |
| `NX_PORT` | HTTP port; `9009`. |
| `NX_CALLBACK_URL` | Calling backend's base URL, reachable from the laptop. |
| `NX_CALLBACK_STATUS_PATH` | Callback path; `/jobs/status`. |
| `NX_CALLBACK_API_KEY` | Optional existing backend key, sent as `X-API-Key`. |

For now, bind to loopback and use the callback settings in DEMO.md; the defaults
above do not target the Next.js app. When moving to NetBird, restrict access to
the calling service. NX runs natively on Windows, not in Docker. If NX cannot load the Pixi interpreter,
point `NX_PYTHON_HOME` at the laptop's existing working Python 3.12 environment.
NXOpen is supplied by Siemens, not installed from PyPI.

From `heerbaart-demo/service`, on the laptop:

```powershell
pixi install
pixi run serve
```

The local copy already contains `pixi.lock` and a Pixi Python 3.12 environment;
install only if the environment needs preparation. The API starts one process,
with one worker and no reload.

## Local Stages

For local operation, use the stage command instead of running the HTTP service.
Do not run CLI stages concurrently with the API or another CLI process.

Prepare a complete initial baseline:

```powershell
pixi run stage baseline --drawing "C:\drawings\ELSTER_GEHAEUSE_T73023059_REV_D.pdf"
```

Alternatively, start from a fresh data directory and run the stages separately:

```powershell
pixi run stage extract --drawing ".\ELSTER_GEHAEUSE_T73023059_REV_D.pdf"
pixi run stage part
pixi run stage structure
pixi run stage setup
```

Extraction creates `family.json` once. Do not repeat `extract` or `baseline` to
resume an existing family; use the remaining individual stages instead.

After setup generation, open `BASELINE_SETUP.prt` in NX and manually program it.
Save and close the baseline and its dependencies before releasing it for cloning:

```powershell
pixi run stage ready
pixi run stage article --article 73023060 --material "1.4301 - RVS 304"
```

The first numbered article, `73023059`, is also generated this way if requested.
It is never the family's mutable baseline.

`ready` records the operator's decision; it does not inspect or generate CAM.
The article pipeline finds program group `O1234` by name in Program Order and
regenerates only that group after refresh. It saves the article SETUP, reopens it
and checks statuses/path presence only for operations within `O1234`. Other groups
(including `ONLYNOTES`) are outside this step; a missing `O1234` is an error. This is automatic
within the API flow, without a separate UI button. Native generation/save/reopen
passed for 73023059. Posting then follows `../journal.py`: `DeleteMachineCode`,
`OutputBallCenter=False`, `PostprocessWithPostModeSetting`, postprocessor
`Okuma_MultusU4000_1SW`, PostDefined units/warnings/review, Normal mode. A fresh
run directory prevents stale output counting as success; the nonempty `.min`
is copied to the article directory after saving the setup.
The Okuma post normalizes underscores to hyphens in output filenames; the API
uses `<article>-SETUP.min` directly. Native API posting and service downloads
passed for 73023059 and 73023060 on 2026-09-16 (31 Python tests also pass).
Simulation remains pending. The manual 59 reference has extra coolant codes at
three drilling operations; see DEMO.md N3c before claiming equivalent NC output.

## HTTP Contract

`POST /start/nx-job` accepts multipart form data. `job_id`, `material`, and `amount`
remain required for the existing caller contract. Material and amount are not
used to change the family geometry.

| `action` | Additional fields | Work |
| --- | --- | --- |
| `prepare_quotation` | `drawing`, `article_number` | Prepare a missing family, hand off an existing unreleased baseline, or generate the requested article if released. |
| `approve_baseline_and_generate` | `article_number` | Record saved manual programming, reload the family, then generate the originally requested article. |
| `retry_article` | `article_number`, `resume_from` | Resume `article_clone`, `geometry_update`, `setup_refresh`, `cam_regeneration`, or `postprocessing`; reuse existing article files for all steps after clone. |
| `baseline` (default) | `drawing` PDF upload | Extract table, build PART, structure, and initial SETUP. |
| `extract` | `drawing` PDF upload | Extract and persist the table only. |
| `part` | None | Build BASELINE PART using the persisted first row. |
| `structure` | None | Build BASELINE ASSY, CAD4CAM, and BLANK from existing PART. |
| `setup` | None | Run or resume the five initial setup stages. |
| `ready` | None | Record that manual baseline programming is saved. |
| `article` | `article_number` | Native clone, CAD update, setup refresh, CAM toolpath regeneration, and NC posting. |

Drawing uploads are consumed by `extract`, `baseline`, and `prepare_quotation`. Article numbers
are eight-digit strings looked up in the extracted table, not arbitrary formulas.

Example PowerShell requests after starting the service:

```powershell
curl.exe -X POST "http://127.0.0.1:9009/start/nx-job" -F "job_id=demo001" -F "material=LF2" -F "amount=1" -F "action=baseline" -F "drawing=@C:\drawings\ELSTER_GEHAEUSE_T73023059_REV_D.pdf"
curl.exe "http://127.0.0.1:9009/jobs/demo001"
```

After the baseline is manually programmed and saved:

```powershell
curl.exe -X POST "http://127.0.0.1:9009/start/nx-job" -F "job_id=demo002" -F "material=LF2" -F "amount=1" -F "action=ready"
curl.exe -X POST "http://127.0.0.1:9009/start/nx-job" -F "job_id=demo003" -F "material=1.4301 - RVS 304" -F "amount=1" -F "action=article" -F "article_number=73023060"
```

Submission returns HTTP 201 and `{"job_id":"demo001"}`. Reusing an in-memory job
ID returns 409. Poll `GET /jobs/{job_id}` for the local status. The worker sends
`PENDING` when it picks up a job, then `IN_PROGRESS`, followed by `COMPLETED` or
`FAILED`. Both polling and callbacks include workflow details. For an app request
reusing an unreleased baseline, the completion looks like this (path abbreviated):

```json
{"job_id":"demo001","status":"COMPLETED","stage":"family_check","stage_started_at":"2026-09-16T10:00:00Z","workflow":"baseline","error":null,"outcome":"AWAITING_PROGRAMMING","setup_path":"C:/.../BASELINE/BASELINE_SETUP.prt"}
```

App actions return `AWAITING_PROGRAMMING` or `ARTICLE_CREATED`; the latter only
means the current native pipeline completed. New jobs return weights during
`measurement`, before setup refresh/CAM, and finish at `simulation` with released
NC. Older jobs at `cam_regeneration` only regenerated paths,
and jobs at `setup_refresh` did neither. Posting does not mean simulation passed.
The local app matches callbacks to the current job stored on the quotation.
Low-level actions have no app outcome; use the CLI or service polling for those.
`GET /articles/{article_number}/nc` downloads the latest local `<article>-SETUP.min`.
The app exposes it through its authenticated, organization-scoped download route
only after successful external simulation. NC is not uploaded to S3 yet. Weights
and total simulation time use the existing status callback. Individual operation
times/import remain outside this POC step.
Callback failures are logged without changing the NX outcome. Queue and job
statuses are in memory and are lost on service restart; family data and parts
remain on disk. A new caller job ID does not authorize overwriting existing parts.
The live app's retry keeps the quotation and drawing, with a new current job ID.
Corrections made only to BASELINE are not copied into an existing article on resume.

## Files And Failures

```text
data/
  uploads/<job_id>/drawing.pdf
  elster-rev-d/
    drawing.pdf
    family.json
    BASELINE/BASELINE_{PART,ASSY,CAD4CAM,BLANK,SETUP}.prt
    <article>/<article>_{PART,ASSY,CAD4CAM,BLANK,SETUP}.prt
    work/<stage>_<unique>/request.json
    work/<stage>_<unique>/result.json
    work/<stage>_<unique>/nx.log
```

Each journal gets its own work directory. The API log identifies the corresponding
NX log. Exceptions stop the job; intermediate files remain for laptop diagnosis.
The runner terminates its NX process tree on timeout or service cancellation.

Initial setup stages are `load`, `constraints`, `holders`, `position`, `references`,
each in a separate NX process. `family.json` records the last successfully
completed stage, so `action=setup` continues at the next one. A failed stage may
already have saved partial work; inspect its log before retrying.

Initial PART/structure construction and article cloning refuse existing final
destinations. Failed article jobs do not automatically resume or delete files.
After diagnosis, an operator can archive the failed article directory before
requesting it again. For a fresh family, choose another `NX_DATA_DIR` instead of
overwriting a programmed baseline.

## Known Laptop Work

- Articles with `DT = 180` use an exact straight bore. The cloned PART retains
  its axial sketch split points so the inlet segments become collinear instead
  of collapsing. `DT < 180` remains unsupported; initial BASELINE construction
  still requires `DT > 180`.
- Native cloning, CAD updates, and setup refresh have passed NX 2512 checks for
  `73023059`, `73023060`, `73024126`, and `73024154`. The remaining article
  dimensions and programmed CAM geometry/toolpaths still need verification.
- Jaw geometry selections, library calibration, saved constraints, and retained
  manual CAM data need laptop verification. A changed jaw-device selection is
  rejected rather than silently replacing fixtures.
- Only the five known article-owned parts are cloned. Keep manual baseline work
  within those files; extra article-specific dependent parts need an explicit
  clone-map change.
- Clone library search accepts a changed shared-resource path only when the
  same-named file in the configured resource tree is byte-identical. BASELINE
  source paths remain fixed. This resolved the duplicated old/current jaw library
  on this laptop; native five-part cloning was verified on 2026-09-16 in
  `data/clone-check-b39b4de7`. This check did not rerun update/refresh or CAM.
- A subsequent native clone/update/refresh check passed in
  `data/refresh-check-1eac4448/73023059`. Refresh now recognizes identical jaw
  library copies and uses the loaded jaw instance for stop faces. It reconstructs
  missing old positioning constraints and validates the resulting constraints and
  position after saving/reopening. CAM finishing remains outside this check.

## Code Map

- `api/`: HTTP endpoints, uploads, serial worker, and status callbacks.
- `pipeline.py`: family state and callable stages; no NXOpen imports.
- `pdf_table.py`: actual structured OpenAI table extraction, not CAD generation.
- `nx_runner.py`: native process environment, requests, logs, and results.
- `nx/entry.py`: fixed journal dispatch.
- `nx/model/`: extracted full Elster STAP1-11 geometry and HB thread handling.
- `nx/assembly/`: occurrence alignment, WAVE bodies, and Revolve Outline stock.
- `nx/setup/`: extracted initial workholding and existing-setup refresh.
- `nx/variant.py`: native five-part cloning and copied-expression updates.

Detailed setup-stage and refresh interfaces are in `nx/setup/README.md`.
