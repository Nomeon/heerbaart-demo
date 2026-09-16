# Codex handoff: connect the Elster app to real NX processing

## Start here

The quotation UI is built and has been tried by the user. The user now has access
to the Windows NX laptop. Continue by implementing the real server/app connection
and the remaining NX automation.

**Implement in three passes:**

1. Connect the existing BASELINE → programmer handoff → article workflow, with
   actual stage updates.
2. Automate CAM regeneration, times, weights, posting, and simulation on the laptop.
3. Finalize real result delivery and connect it to the app's result UI.

This is the current handoff. [FLOW.md](FLOW.md) contains the agreed end-to-end
flow and proposed contracts. The original [PLAN.md](PLAN.md) and parts of
[service/README.md](service/README.md) describe the earlier, status-only POC;
their exclusion of regeneration, measurements, posting, and simulation is the old
delivery boundary. Those capabilities are now required.

The app-specific plan is `heerbaart-app/PLAN.md` in the sibling repository. Its
NX contracts were deliberately left as TODOs until the laptop functions could be
implemented. Treat wire examples in FLOW.md as proposals to confirm against the
real implementation, not APIs that already exist.

## 1. Agreed requirements — keep this a small POC

- **One family only:** Elster Rev.D, with the existing family key `elster-rev-d`.
- Select the requested article by its **eight-digit article number**. Resolve
  `DT`, `FA`, `DR`, `FR`, `FB`, `DS`, and `DL` from the extracted family table.
- **One material.** The ERPNext display label matches the NX material name.
  Pass the name through directly; an additional material-mapping service is not
  needed. Confirm the exact name on the laptop.
- **Trust programmer approval.** Clicking “Programmering gereed” is sufficient
  to set the baseline ready. Reuse the existing simple file/setup checks and
  readiness flag. Do not add an internal CAM approval framework or validation
  layer before accepting the programmer's decision.
- Show actual processing stages in the app throughout the run.
- Generate fresh CAM toolpaths for the requested dimensions, obtain NX operation
  estimates, measure product and raw-stock weight, simulate, and return posted
  NC files to the app.
- ERPNext provides the existing customer/material data. Creating ERP finished
  Items or sales Quotations is outside this POC.
- Keep the existing serial Python worker, local family files, journal runner,
  and HTTP integration. Use a few direct functions, not a generic family/workflow
  platform, new queue service, or baseline-versioning system.

Normal NX failures still stop the job and identify the failed stage. Trusting the
programmer does not mean reporting an unsuccessful NX execution as successful.

## 2. Current implementation

### NX service: `heerbaart-demo/service`

| File | Current responsibility / integration gap |
| --- | --- |
| `api/main.py` | Multipart `POST /start/nx-job`, `GET /jobs/{job_id}`, and a basic `GET /` service response |
| `api/schema.py` | Existing request fields and four job statuses |
| `api/worker.py` | One serial worker; currently discards the pipeline output and does not pass material/amount into it |
| `api/notifier.py` | Status callbacks only; supports outbound `X-API-Key` through configuration |
| `api/config.py` | Environment configuration, callback URL/path/key, data directory |
| `api/store.py` | In-memory job status and duplicate-ID tracking |
| `pipeline.py` | Family state, baseline creation, readiness flag, article orchestration |
| `pdf_table.py` | Actual PDF/table extraction for the supported single-page drawing |
| `nx_runner.py` | Launches native NX journals on Windows; request/result JSON and `nx.log` per stage |
| `nx/entry.py` | Fixed dispatch into the NX journal functions |
| `nx/variant.py` | Native five-file cloning and expression/dependency updates |
| `nx/setup/` | Initial setup construction and refresh of copied setup references/positioning |

Existing pipeline functions:

```text
read_family(pdf_path)
create_baseline_part(family)
create_structure(family)
create_setup(family)
prepare_baseline(pdf_path)
mark_baseline_ready(family)
generate_article(family, article_number)
run_job(action, ...)
```

`generate_article()` currently executes **clone → update → refresh**. It does
not yet regenerate CAM, extract machining times or mass, simulate, or post NC.

`mark_baseline_ready()` saves a new family dictionary with `baseline_ready = true`.
It does not mutate the caller's dictionary. Reload the saved family before calling
`generate_article()` in the same approval job.

The user has confirmed that **posting and simulation work interactively on the
laptop**. Callable automation for those steps has not yet been established in
this repository. Locate the actual machine/post/simulation configuration and
record or implement the required journals against it.

### Existing HTTP behavior

```text
POST /start/nx-job                    multipart/form-data
  job_id                             caller-owned, /^[a-z][a-z0-9]{1,31}$/
  material                           display-name string; currently unused by pipeline
  amount                             quantity; currently unused by pipeline
  action                             defaults to baseline
  drawing                            required for extract/baseline
  article_number                     required for article

Actions: extract, baseline, part, structure, setup, ready, article
Response: 201 {"job_id":"demo001"}

GET /jobs/demo001
Response: {"job_id":"demo001","status":"COMPLETED"}

Status callback body uses that same job_id/status shape.
Statuses: PENDING → IN_PROGRESS → COMPLETED | FAILED
```

Duplicate in-memory job IDs return `409`; unknown polled jobs return `404`.
The queue/status store is lost on restart; native files and family state remain.
A new job ID does not authorize overwriting existing native files.

### App: `heerbaart-app`

The app has a working **local-only preview**, accessible after login through
**Offertes → Flowdemo**, at `/app/quotation-preview`.

| File | Current use |
| --- | --- |
| `src/components/offertes/quotation-preview.tsx` | Local fixture data, demo timers, baseline-ready flag, local operations and ordering |
| `src/components/offertes/quotation-views.tsx` | Reusable overview/detail, `QuotationViewData`, stage list, programming handoff, measurements, simulation, file section |
| `src/components/offertes/quotation-request-form.tsx` | Article-aware form with supplied handlers and reused validation |
| `src/components/offertes/quotation-drawing-field.tsx` | PDF input shared with the existing live form |
| `src/components/offertes/quotation-operation-fields.tsx` | Shared operation editor; optional drag/touch/keyboard reordering handler |
| `src/components/offertes/quotation-operations.tsx` | Existing live server-action wrapper for operation editing |
| `src/app/(app)/app/quotation-form/actions.ts` | Existing live request creation/upload/NX dispatch |
| `src/app/api/nx/status/route.ts` | Existing status receiver; currently equates COMPLETED with quotation READY |
| `src/app/api/nx/result/route.ts` | Currently logs a JSON body; does not save results or files |
| `prisma/schema.prisma` | Existing Quotation and QuotationOperation models |

Preview results, its material placeholder, and its NC example file are synthetic.
Do not reuse them as real server results. The preview has already covered both
flows, programming approval, failure states, results, and local-only interactions.
App lint/type checks and production build passed; the existing result endpoint
has an unrelated unused-variable warning.

The user requested **dragging operations instead of editing sequence numbers**.
That is implemented in the preview. New operations append at the end; move/add/
delete renumbers them. Preserve this UI when connecting real data.

If only `heerbaart-demo` is present on the laptop, complete the server work and
return the finalized contract and an actual sample result for the app handoff.
The app remains a separate repository. Inspect current worktrees before editing:
the UI changes may be staged or uncommitted, so do not reset them to an older branch.

## 3. First laptop tasks: establish the actual starting state

These details were not available when writing the handoff. Inspect the laptop
configuration and ask the operator only for values that cannot be established.
Record non-secret choices below; keep credentials in ignored environment files.

| Detail | To establish |
| --- | --- |
| Reachable NX service URL | Laptop NetBird address and port; app must reach it |
| App callback base URL | Address the laptop can reach; not necessarily the laptop's localhost |
| Existing data directory | Actual absolute `NX_DATA_DIR` |
| BASELINE state | Absent, partially built, waiting for programming, or already programmed/ready |
| Supported source PDF | Actual Elster Rev.D drawing location |
| POC material | Exact shared ERPNext/NX display name; the preview name is a placeholder |
| NX resources | Actual NX/custom paths, machine template, tool/jaw libraries, material library |
| Postprocessor | Working configuration and output files/extensions, including any subprograms |
| Simulation | Working mode, required inputs, and how to obtain its completion/outcome |

- [ ] Read the repository instructions and inspect the laptop's current source and
      environment before changing code or running a generation job.
- [ ] Confirm Windows, NX 2512, Python 3.12/Pixi, licensing, journal execution, and
      the existing Heerbaart resources. NXOpen comes from Siemens, not PyPI.
- [ ] Preserve any programmed BASELINE and existing articles. Use the existing
      programmed baseline for finishing trials; use a separate fresh data root
      for the fresh-start acceptance run.
- [ ] Confirm app → laptop and laptop → app connectivity.
- [ ] Run one API instance with one worker. Stop it before running individual CLI
      stages; do not execute both against the same files concurrently.

From `heerbaart-demo/service`, the existing commands are:

```powershell
pixi install
pixi run serve
```

Inspect the existing environment/lockfile first and install if needed. In another
terminal, HTTP availability can be checked with:

```powershell
curl.exe http://127.0.0.1:9009/
```

That only establishes HTTP availability, not a valid NX license or successful
machining execution.

For an isolated local trial, with the API stopped and a fresh data root selected:

```powershell
pixi run stage baseline --drawing "<actual Elster Rev.D PDF path>"
# Programmer opens BASELINE_SETUP.prt, programs it, saves and closes the files.
pixi run stage ready
pixi run stage article --article 73023059
```

These are existing commands. Until pass 2 is implemented, the article command
stops at updated native files. Do not rerun `baseline` or `extract` over an
existing family to resume it; inspect its state and use the remaining individual
`part`, `structure`, or `setup` stages.

Configuration reminders:

- The service normally loads `service/.env`; `ENV_FILE` can select a file explicitly.
- `NX_HOST` defaults to `127.0.0.1`, `NX_PORT` to `9009`. Bind the intended NetBird
  interface for remote app access.
- Set `NX_CALLBACK_URL` to the actual app address and
  `NX_CALLBACK_STATUS_PATH=/api/nx/status`; the current default is `/jobs/status`.
- The existing `NX_CALLBACK_API_KEY` is an **outbound** `X-API-Key` header. It
  does not authenticate incoming job submissions, and the app's current custom
  callback handlers do not yet check it.
- Add result-callback configuration when implementing delivery, keeping route
  and configuration names consistent on both sides.
- The existing NX timeout is per journal process, normally 900 seconds. Detailed
  output is retained under the family's `work/` stage directories.

## 4. Pass 1 — real workflow and live stages

### Server tasks

- [ ] Add a small quotation coordinator using the fixed Elster family:
      absent → prepare BASELINE; prepared but not ready → programming handoff;
      ready → generate requested article. Report an incomplete previous build
      rather than treating its directory as ready or overwriting it.
- [ ] Accept the requested article number, confirm it occurs in the extracted
      table before expensive initial construction, and retain it for the
      originating quotation. BASELINE still uses the first row's dimensions.
- [ ] Pass the material name and quantity through the worker instead of dropping
      them. Generate one article/program; quantity is for quote/order totals.
- [ ] Complete baseline preparation with an explicit **awaiting programming**
      outcome and its `BASELINE_SETUP.prt` location. Free the worker while the
      programmer works.
- [ ] Add the app's programmer-ready action: record readiness, reload family state,
      then generate the original requested article in a new job.
- [ ] Emit the current stage before each actual pipeline/NX call; report ordinary
      failures with the stage and a useful message.
- [ ] Retain returned pipeline output in the worker and expose enough information
      to deliver outcomes, rather than discarding it.

Reuse `POST /start/nx-job` and the existing serial worker. FLOW.md proposes
`prepare_quotation` and `approve_baseline_and_generate` as two added action values.
They can be direct branches around current functions. Confirm the final fields
and outcomes in this pass, keeping the low-level CLI stages usable.

Report the actual baseline stages: extraction, PART, structure, then setup load,
constraints, holders, position, and references. Article stages start with clone,
geometry update, and setup refresh. Preserve existing NX save/reopen boundaries.
Stage identifiers can be mapped to the UI's Dutch labels; preview-local IDs are
not a wire contract.

### App tasks for this pass

- [ ] Save the article number and associate **each action/job** with the quotation.
      The same quotation needs a baseline job and later an approval/article job;
      do not reuse its quotation ID as every new job ID.
- [ ] Keep new job IDs compatible with the existing service format; hyphenated
      UUIDs currently do not pass its validation.
- [ ] Add the waiting-for-programming state and current stage/error storage.
- [ ] Connect the form and ready button to the real server actions.
- [ ] Retain the klantvraag/PDF on dispatch failure. The current action deletes
      them if NX dispatch fails.
- [ ] Replace the status handler's unconditional `COMPLETED → READY` mapping.
      Baseline completion means waiting for programming. While only the existing
      native-file pipeline is connected, do not claim that final machining/results
      are ready before passes 2 and 3 exist.
- [ ] Feed real state into the reusable views and refresh while processing, for
      example by refreshing the authenticated detail page about every two seconds.
      Live execution must not use the preview timer.
- [ ] Authenticate job requests/callbacks using the configured HTTP key convention
      and validate payloads at the HTTP boundary with the existing schema tools.
      Look up the stored job/quotation association before updating records. In
      particular, never pass an absent `job_id` into Prisma `updateMany`.

**Pass 1 acceptance:** the first real request reaches “Wacht op programmeren” with
live stages; programmer approval starts its own article; the next article uses
the ready baseline directly. Native files are real, but the full result-ready
state is reserved for the completed finishing/delivery work below.

## 5. Pass 2 — implement NX finishing against the working laptop setup

Keep related SDK-specific code together, for example in `service/nx/finish.py`,
and invoke it through `nx/entry.py` and `nx_runner.py`. Extend `generate_article()`
after clone/update/refresh. A separate function or module per small check is not
needed.

- [ ] Locate/record the working NX operations and verify the installed NX 2512
      Python bindings. Do not guess SDK methods from an unrelated version.
- [ ] Apply/use the identically named POC material for the product and stock bodies.
- [ ] **Regenerate CAM** on the copied article's updated geometry. Preserve the
      programmer's machining strategy and normal NX save boundaries.
- [ ] **Extract operation estimates after regeneration.** Return operation identity,
      execution order/name, and durations with explicit units. Establish whether
      the actual NX value includes rapid motion/tool changes by comparing with NX.
- [ ] **Measure product mass** from the finished solid in `<article>_PART.prt`.
- [ ] **Measure raw-stock mass** from `BLANK_REVOLVE_OUTLINE_BODY` in the generated
      `<article>_BLANK.prt`. Use its assigned material/density. Do not sum the SETUP
      assembly, fixtures, or linked duplicate product bodies.
- [ ] Normalize mass to kg. If using volume and density, convert units explicitly:
      `mm³ × kg/m³ × 10^-9 = kg`.
- [ ] **Postprocess** using the installed working postprocessor. Collect the actual
      main program and all required subprogram/output files.
- [ ] **Simulate** using the configured working mode. If it consumes posted NC,
      post first. Obtain the actual simulation outcome rather than assuming that
      a successful post or journal process exit proves it passed.
- [ ] Report finishing stages as they execute. The existing process-per-stage
      pattern gives the HTTP worker a natural place to emit progress between calls.
- [ ] Save the result metadata and NC output locally so delivery can be retried
      independently of NX generation.

The app labels time as **NX estimates**. Return per-piece values and let the app
derive order totals from quantity. A sum of operation estimates is not necessarily
a synchronized multichannel machine-cycle time. Manual setup/programming time
remains separate.

If an interactive step cannot yet be automated in the configured journal/runtime,
record the exact blocker and the working manual procedure. Do not substitute a
fixture, copied stale estimate, or fabricated success status.

**Pass 2 acceptance:** one requested article has freshly regenerated machining,
NX-verified time/weight values, an actual simulation outcome, and actual NC files.

## 6. Pass 3 — finalize results and connect the app

### Result contents to agree on

| Group | Required information |
| --- | --- |
| Correlation | Job ID and its quotation association; requested article and fixed family |
| Business outcome | Awaiting programming or article ready, distinct from transport/job completion |
| Material | Shared material display name actually used |
| Times | Ordered operation identity/name/duration, explicit unit and per-piece basis, aggregate estimate and its source |
| Weights | Finished-product and raw-stock kg per piece |
| Simulation | Actual outcome and useful explanation on failure |
| Files | Required NC filenames and contents/attachments; setup location for the programming handoff |
| Errors | Failed stage and readable error information |

FLOW.md proposes a multipart result callback with a JSON metadata field and NC
attachments. Confirm this against the actual output files, then implement it on
both sides. Use `job_id` consistently; the app's current result stub uses `jobId`.

- [ ] Implement result delivery in `api/notifier.py`; send/acknowledge the result
      before final job completion. Keep native `.prt` files and detailed logs on
      the laptop; send result metadata and NC files to the app.
- [ ] Implement the app's result receiver, replacing the logging stub. Save NC
      attachments in its existing S3 storage, using app-owned object keys.
- [ ] Persist measurements, NX operation rows, simulation outcome, and artifact
      references. Mark the quotation ready only after required results are saved.
- [ ] Make duplicate delivery harmless and ignore older-job updates once a newer
      action is active. Retry sending saved output with the same job ID; do not
      rerun cloning because a callback failed.
- [ ] Preserve manually added operations when importing NX results.
- [ ] Persist drag ordering through an organization-scoped app action that updates
      the quotation's operation sequence together. This changes **quotation order**,
      not NX toolpaths or machining strategy. Keep actual server-side CAM changes
      separate from the UI reorder action.
- [ ] Provide authenticated NC downloads from stored app references. A Windows
      setup path is copyable operator information, not a browser file URL.
- [ ] Connect live quotation overview/detail routes to the reusable UI. Keep the
      explicit local preview available for rehearsals, not as an error fallback.
- [ ] Update FLOW.md with the finalized contract and a sanitized **real** example
      request/result after the laptop test.

### Existing UI data expectations

Read `QuotationViewData` in `quotation-views.tsx` when wiring the app. Important
current expectations are:

- Quotation states: `QUEUED`, `PROCESSING`, `AWAITING_PROGRAMMING`, `READY`, `FAILED`.
- Workflow: baseline/article path, ordered display stages, current stage index,
  stage-start time, and readable error.
- Measurements: `minutesPerPiece`, `productKg`, and `stockKg`. Missing measurements
  remain missing, displayed as “Nog niet berekend”, not zero.
- Operations: ID, `NX`/`MANUAL` source, sequence, name, `timeMinutes`, and hourly
  rate. The existing editor receives duration/rate strings. NX is not the source
  of quotation hourly rates; handle unset rates explicitly in app persistence.
- Simulation presentation: pending, running, passed, failed.
- Files: identifier, name, availability, and an app-supplied download action.

Map the finalized server data into that presentation shape. Server durations may
use seconds; convert deliberately to app minutes. Keep displayed order totals
derived from the quotation quantity.

The app already has product `Quotation.weight` and `QuotationOperation` storage.
Add only the missing article, stock weight, result metadata, and small job/state
association needed for this flow. The single baseline's readiness remains in
the service's `family.json`.

## 7. End-to-end completion checks

- [ ] From a fresh test data root, request article 73023059 using the supported
      drawing, actual material, and quantity 5. Show real stages in the app.
- [ ] Baseline construction finishes at “Wacht op programmeren”, with the correct
      setup location; it does not falsely become a ready quotation.
- [ ] The programmer saves/closes BASELINE, marks it ready in the app, and the
      original article is generated without submitting another quotation.
- [ ] Request article 73023060. It reuses the ready baseline and completes without
      another programming handoff.
- [ ] Compare both weight measurements and operation estimates with the actual
      NX values for the generated article. Check kg/minute conversions and totals.
- [ ] Show the actual simulation outcome and download NC output identical to the
      laptop's postprocessed files.
- [ ] Reopen the generated article and confirm its article-owned dependencies are
      local to that article. BASELINE and the first article remain unchanged after
      generating the second.
- [ ] An NX failure shows its real stage and preserves the klantvraag; it does not
      fabricate result readiness. A delivery retry does not create another article.
- [ ] Repeated callbacks do not duplicate operations or remove manual rows. Saved
      drag ordering remains consistent after reloading the quotation.
- [ ] Reject missing/unknown job IDs and unauthenticated callbacks without changing
      unrelated quotations.
- [ ] Run the app's `bun run check` and `bun run build` for app changes, and the
      relevant existing Python checks/tests plus focused contract checks for server
      changes. Native NX behavior is verified on the laptop, not by mocked tests.

Existing generation refuses occupied destinations. Inspect retained stage logs
and partial files before retrying. Use the existing stage tools for baseline
recovery and an explicitly chosen fresh/archived article destination when needed;
do not delete a programmed baseline to make a retry succeed.

## 8. What to hand back at the end of the laptop session

- Which of the three passes works, which articles were exercised, and any exact
  blockers still requiring operator input.
- Actual non-secret material/machine/post/simulation choices and where the new
  callable journals/functions live.
- Final request, progress, outcome/error, and file-delivery contracts, with one
  sanitized real result and explicit units.
- How to run the service and repeat the two demo scenarios safely with the selected
  data root, preserving the programmed baseline.
- Remaining app work if its repository was not available on the laptop.

Keep credentials, tokens, and private keys out of this document, sample payloads,
logs, and commits. Follow repository instructions for edits and verification;
do not stage, commit, or push unless the user requests it.
