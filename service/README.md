# Elster Rev.D NX POC

One Windows service receives a PDF, extracts the eighteen article rows with
OpenAI, builds an independent BASELINE, and later generates requested articles
from its manually programmed setup. Generated files remain on the laptop.
Only job statuses are sent to the calling service.

The implementation has been reviewed statically. No tests, application runs,
OpenAI requests, dependency installation, or NX execution were performed during
implementation. Installed NX behavior still needs confirmation on the laptop.

## Scope

- Only the supplied single-page Elster Rev.D drawing and its known STAP1-11 model.
- Separate `BASELINE` item, seeded with the first table row's dimensions.
- Native PART, ASSY, CAD4CAM, BLANK, and SETUP files per item.
- BLANK always uses Revolve Outline, a 360-degree revolve, and a 5 mm offset.
- One machine/jaw strategy, with article-dependent opening and clearance values.
- No automatic machining, toolpath regeneration, simulation, or posting.
- No NATS, database, new UI, or distributed job system.

The service runs directly on Windows with native NetBird connectivity. Legacy
NATS and Docker files have been removed. The original modeling projects are not
needed at runtime.

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
| `NX_PYTHON_HOME` | Optional; defaults to the active Pixi Python 3.12 environment. |
| `NX_JOURNAL_TIMEOUT` | Seconds per NX process; `900`. Increase if full model construction needs longer. |
| `NX_DATA_DIR` | Local uploads, family files, parts, and logs; `data`. |
| `NX_HOST` | `127.0.0.1` locally; set the laptop's NetBird address for remote requests. |
| `NX_PORT` | HTTP port; `9009`. |
| `NX_CALLBACK_URL` | Calling backend's base URL, reachable from the laptop. |
| `NX_CALLBACK_STATUS_PATH` | Callback path; `/jobs/status`. |
| `NX_CALLBACK_API_KEY` | Optional existing backend key, sent as `X-API-Key`. |

Keep the port restricted to the calling service through NetBird's access rules.
NX runs natively on Windows, not in Docker. If NX cannot load the Pixi interpreter,
point `NX_PYTHON_HOME` at the laptop's existing working Python 3.12 environment.
NXOpen is supplied by Siemens, not installed from PyPI.

From `heerbaart-demo/service`, on the laptop:

```powershell
pixi install
pixi run serve
```

The obsolete Linux/Python 3.14 lockfile was removed. `pixi install` will resolve
the Windows/Python 3.12 environment and generate a new lockfile; this resolution
has not been run here. The API starts one process, with one worker and no reload.

## Local Stages

For local operation, use the stage command instead of running the HTTP service.
Do not run CLI stages concurrently with the API or another CLI process.

Prepare a complete initial baseline:

```powershell
pixi run stage baseline --drawing "C:\drawings\ELSTER_GEHAEUSE_T73023059_REV_D.pdf"
```

Alternatively, start from a fresh data directory and run the stages separately:

```powershell
pixi run stage extract --drawing "C:\Users\Bob\Desktop\heerbaart-demo\service\ELSTER_GEHAEUSE_T73023059_REV_D.pdf"
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
pixi run stage article --article 73023060
```

The first numbered article, `73023059`, is also generated this way if requested.
It is never the family's mutable baseline.

`ready` records the operator's decision; it does not inspect or generate CAM.
An article's copied toolpaths are not regenerated and may be out of date.

## HTTP Contract

`POST /start/nx-job` accepts multipart form data. `job_id`, `material`, and `amount`
remain required for the existing caller contract. Material and amount are not
used to change the family geometry.

| `action` | Additional fields | Work |
| --- | --- | --- |
| `baseline` (default) | `drawing` PDF upload | Extract table, build PART, structure, and initial SETUP. |
| `extract` | `drawing` PDF upload | Extract and persist the table only. |
| `part` | None | Build BASELINE PART using the persisted first row. |
| `structure` | None | Build BASELINE ASSY, CAD4CAM, and BLANK from existing PART. |
| `setup` | None | Run or resume the five initial setup stages. |
| `ready` | None | Record that manual baseline programming is saved. |
| `article` | `article_number` | Native clone, CAD update, and existing setup refresh. |

Drawing uploads are consumed only by `extract` and `baseline`. Article numbers
are eight-digit strings looked up in the extracted table, not arbitrary formulas.

Example PowerShell requests after starting the service:

```powershell
curl.exe -X POST "http://127.0.0.1:9009/start/nx-job" -F "job_id=demo001" -F "material=LF2" -F "amount=1" -F "action=baseline" -F "drawing=@C:\drawings\ELSTER_GEHAEUSE_T73023059_REV_D.pdf"
curl.exe "http://127.0.0.1:9009/jobs/demo001"
```

After the baseline is manually programmed and saved:

```powershell
curl.exe -X POST "http://127.0.0.1:9009/start/nx-job" -F "job_id=demo002" -F "material=LF2" -F "amount=1" -F "action=ready"
curl.exe -X POST "http://127.0.0.1:9009/start/nx-job" -F "job_id=demo003" -F "material=LF2" -F "amount=1" -F "action=article" -F "article_number=73023060"
```

Submission returns HTTP 201 and `{"job_id":"demo001"}`. Reusing an in-memory job
ID returns 409. Poll `GET /jobs/{job_id}` for the local status. The worker sends
`PENDING` when it picks up a job, then `IN_PROGRESS`, followed by `COMPLETED` or
`FAILED`, using the existing callback shape:

```json
{"job_id": "demo001", "status": "COMPLETED"}
```

No result callback, file download, or machining metadata extraction is performed.
Callback failures are logged without changing the NX outcome. Queue and job
statuses are in memory and are lost on service restart; family data and parts
remain on disk. A new caller job ID does not authorize overwriting existing parts.

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
