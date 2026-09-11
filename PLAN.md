# Elster Rev.D Minimal POC Plan

## Goal

Build the smallest functional Elster Rev.D pipeline on the Windows NX laptop:

```text
PDF upload
  -> OpenAI extracts the ordered article table
  -> first row supplies BASELINE dimensions
  -> generate BASELINE PART / ASSY / CAD4CAM / BLANK / SETUP
  -> manually program and save BASELINE
  -> request an article number
  -> clone BASELINE and update its expressions and dependencies
  -> save the article's updated SETUP
```

This POC stops at an updated `_SETUP`. Automatic machining, toolpath regeneration, simulation, and posting are outside its scope.

## Implementation Status

The standalone implementation is prepared under `service`.
Configuration, commands, API fields, output paths, and remaining laptop work are
documented in [its README](service/README.md).

Per the implementation request, no tests, application runs, OpenAI requests,
dependency installation, or NX execution have been performed. Review is static
only; the laptop will provide the actual integration feedback.

All eighteen rows are extracted and stored. The two `DT = 180` articles currently
fail explicitly before cloning because the inherited inlet topology cannot
represent them without changes. Full eighteen-article coverage remains an
acceptance target, not a verified result.

## Rules

- No overengineering. Build the most minimal functional prototype.
- Support only the supplied Elster Rev.D family.
- Reuse the existing full STAP1-11 model and the known machine/jaw strategy.
- Use explicit functions, local files, and the existing serial HTTP worker.
- Extract active functionality from the existing projects; do not rewrite or import all of them wholesale.
- Do not add NATS, Docker deployment, a database, a UI, a generic family framework, baseline versioning, or an audit framework.
- Preserve NX save/reopen boundaries where the existing code requires them.
- Do not silently substitute missing functionality: hardcoded rows are not PDF extraction, and mocked NX execution is not an NX result.
- Leave the original projects under `heerbaart-bob` unchanged.
- Keep generated files and detailed logs on the NX server. The caller receives status updates only.

## Baseline Decision

BASELINE is an independent, non-saleable family item. It is not article `73023059` with a different label.

The first table row supplies BASELINE's initial dimensions, but BASELINE owns separate NX files. Numbered articles are generated only on request by cloning BASELINE. Editing an article must not affect BASELINE or another article.

Manual machining is saved in `BASELINE_SETUP.prt`. A generated article receives a cloned setup and article-owned dependencies. Shared machine, jaw, and tool-library resources remain shared.

```text
BASELINE/
  BASELINE_PART.prt
  BASELINE_ASSY.prt
  BASELINE_CAD4CAM.prt
  BASELINE_BLANK.prt
  BASELINE_SETUP.prt

73023060/
  73023060_PART.prt
  73023060_ASSY.prt
  73023060_CAD4CAM.prt
  73023060_BLANK.prt
  73023060_SETUP.prt
```

## Project Layout

Keep one Pixi environment in the service project.

```text
heerbaart-demo/
  PLAN.md
  service/
    pixi.toml
    .env.example
    api/                      HTTP API and worker
    pipeline.py               stage orchestration
    pdf_table.py              OpenAI table extraction
    nx_runner.py              NX process execution
    nx/                       extracted NX builders and variant code
    data/
      elster-rev-d/
        drawing.pdf
        family.json
        BASELINE/
        <article-number>/
```

`family.json` stores the ordered table rows, the initial BASELINE source row, and `baseline_ready`. NX expressions remain in the native parts; the JSON stores only article values and minimal workflow state.

## Configuration

Place the OpenAI key in:

`heerbaart-demo/service/.env`

```dotenv
OPENAI_API_KEY=your-key-here
```

This file is already ignored by Git. Add an empty `OPENAI_API_KEY=` placeholder to `.env.example` during implementation. Never put the key in NX journals, job JSON, or logs.

Use the same configuration location for the OpenAI model, callback settings, NX executable, custom resource paths, and data directory.

## Reuse Map

| Source | Reuse |
| --- | --- |
| `service/api` | Reused connector HTTP functionality: multipart upload, caller-owned job IDs, serial queue, status callbacks, and polling. No NATS dependency. |
| `ELSTER_UITLEZEN/src/nieuw_project/elster_family` | Active STAP1-11 model builders, public expressions, and PDF rendering. Replace its literal-row table reader. |
| `heerbaart_poc` | PART preparation, parent assembly, CAD4CAM WAVE link, and Revolve Outline BLANK construction. |
| `Setup_Generator` | Active Flows 1, 2, 5, and 6 for initial setup construction. Retain necessary separate NX sessions. |

The blank must always use native Revolve Outline, a 360-degree revolve, and the existing 5 mm offset. Do not expose cylinder or block alternatives.

## Build Steps

1. **Prepare Pixi and configuration**

   Target Windows NX 2512 with Python 3.12, matching the supplied NX launchers. Retain Linux support for non-NX development. Add API launch and individual stage tasks. Run one API process with one worker and no development reload on the laptop. Do not add or run tests for this implementation pass.

2. **Keep communication status-only**

   Reuse `POST /start/nx-job`, existing job IDs, the serial queue, and `GET /jobs/{job_id}`. Add only the request fields needed to distinguish baseline preparation from article generation and select an article number. Keep `PENDING`, `IN_PROGRESS`, `COMPLETED`, and `FAILED` callbacks. Do not send result callbacks for this POC.

3. **Implement table extraction**

   Render the PDF table with PyMuPDF and use one structured OpenAI extraction call. Extract all eighteen visible rows in visual order, normalize decimal commas, and retain article number, class, schedule, and nominal `DT`, `FA`, `DR`, `FR`, `FB`, `DS`, and `DL` values. Persist the result in `family.json`; do not sort it or use the existing hardcoded row as live extraction.

4. **Add the NX runner and callable stages**

   Keep FastAPI separate from NXOpen. Launch configured journals through `run_journal.exe`, passing paths and small JSON inputs. Wait without blocking the HTTP event loop and surface actual process failures. Keep a fixed set of callable stages, not a workflow/plugin system.

5. **Construct BASELINE_PART**

   Adapt the full Elster STAP1-11 path to accept the initial table row and explicit destinations. Retain the known Rev.D construction and change only article-specific output, path, and first-row assumptions needed for BASELINE. Verify that the seven public expressions drive saved geometry.

6. **Construct BASELINE structure and setup**

   Reuse the associative `PART -> CAD4CAM -> BLANK` WAVE chain inside ASSY. Preserve assembly-based axis alignment rather than transforming PART geometry. Run the active setup sequence with explicit paths and save `BASELINE_SETUP.prt`.

7. **Hand off for manual programming**

   Baseline construction ends after the setup is saved. The operator manually programs and saves `BASELINE_SETUP.prt`, then invokes a simple `mark_baseline_ready()` action. This flag means manual programming is available; it does not generate or inspect CAM automatically.

8. **Prove native cloning, then generate articles on demand**

   Implement native cloning using the documented Siemens NX Python UF interface. On the laptop, confirm the installed bindings and that all five article-owned files' assembly and WAVE references resolve to the article-local files. Do not use filesystem copying as a fallback.

   For a requested article: look up the saved row, require `baseline_ready`, clone BASELINE, update the copied PART expressions, update CAD4CAM and BLANK dependencies, refresh numeric setup values such as jaw opening and clearance points, then save the article `_SETUP`. Do not rerun initial setup creation from the machine template.

9. **Deploy and fix against NX**

   Perform static code review locally, without tests or manual runs. After transfer, the operator will run baseline construction, clone/update trials, and saved-file reopen checks on the laptop. Fix NX API, reference, geometry, and resource-path issues using that feedback.

## Function Surface

| Function | Purpose |
| --- | --- |
| `read_family(pdf_path)` | Extract and persist the ordered article table. |
| `create_baseline_part(family)` | Build the complete BASELINE model from the first row. |
| `create_structure(item_dir)` | Prepare ASSY, CAD4CAM, and Revolve Outline BLANK. |
| `create_setup(item_dir)` | Construct the initial machine setup. |
| `prepare_baseline(pdf_path)` | Call initial stages in order. |
| `mark_baseline_ready(family)` | Record completion of manual baseline programming. |
| `generate_article(family, article_number)` | Clone BASELINE, update the requested article, and save its SETUP. |

These are coordination functions. Existing NX builders can remain in focused source files where necessary.

## NX Checks Deferred Until Laptop Access

- Exact NX 2512 journal runtime and native assembly-clone interface.
- Remapping of the five files' assembly and WAVE references.
- Preservation of manually prepared CAM data after cloning.
- Final-model behavior when changing all seven public expressions.
- The `DT = 180` rows, which currently collapse inlet-profile segments.
- ASME 600 dimensions propagating through the complete model, blank, and setup.
- Reopening saved article files without article references back to BASELINE.

Do not claim these behaviors work before exercising them in NX.

## Acceptance Criteria

- Uploaded PDF produces eighteen ordered article rows.
- BASELINE exists independently from every numbered article.
- Initial generation creates BASELINE only.
- An operator can manually program and save `BASELINE_SETUP.prt`.
- A requested article gets its own PART, ASSY, CAD4CAM, BLANK, and SETUP files.
- Requested dimensions, dependent stock, and setup values are updated.
- The copied setup retains manual baseline machining data.
- BASELINE and existing article files remain unchanged.
- The caller receives status updates only.
- Automatic machining, toolpath regeneration, simulation, and posting are not required for POC success.
