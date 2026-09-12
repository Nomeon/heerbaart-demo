# NX Structure And Setup Interface

These builders run **inside NX 2512**. They do not launch NX, clone assemblies,
build PART, or regenerate CAM operations. The runner must make this project's
`nx` package importable; there is no import or `sys.path` dependency on the
original projects.

## Request

All entry points accept a dictionary containing absolute `item_dir`, `work_dir`
and `custom_dir` paths, and an item `name` (default `BASELINE`). `work_dir` is
scratch space, separate from `item_dir` and outside the custom resource tree.
The item directory must already exist. Do not include `_PART` or another part
suffix in `name`.

`custom_dir` is the NX custom root containing `MACH/resource`. Setup loads
`MACH/resource/template_part/metric/template_part_setup_NX2512.prt` and uses
`MACH/resource/library/device/graphics` for the existing device assemblies and
their nested `_PART` components. NX's machine/device resource tables must be
configured for this same custom library so `RetrieveDeviceAndMount` resolves
the selected device by its native library name.

At each setup open/reopen, the loader opens the fixed template's chuck,
template helpers, and machine door from `custom_dir` before opening the setup.
This resolves legacy saved paths without changing the shared library files.
Remaining setup load failures report NX's part names and error descriptions.
Product lookup ignores unloaded unrelated occurrences, but requires exactly one
loaded prototype match and still verifies the item-local product paths.

## Initial Sequence

1. Build and save `<item_dir>/<name>_PART.prt` with the model entry point.
2. Call `nx.build_structure.build_structure(request)` in NX. It returns
   `{"assy": <absolute path>, "cad4cam": <absolute path>, "blank": <absolute path>}`.
3. Call `nx.build_setup.build_setup(request)` **five times in separate NX
   processes**, using the `setup_stage` values below in exactly this order.

| `setup_stage` | Active source sequence |
| --- | --- |
| `load` | Root `nx_setup_step3.py`, stage 1: template, product, three complete jaw devices, save/reopen |
| `constraints` | Root `nx_setup_constraints_stage2.py`: six AlignLock and three Touch constraints, in a fresh NX session |
| `holders` | `flow2/flow2_attach_holders.py`: populate MAIN holders, retain existing jaw occurrences |
| `position` | `flow5/flow4_attach_holders.py`: local p3, product center, flange stop and top parallel |
| `references` | Active `flow6/flow6_attach_holders.py`: its full positioning sequence plus MAIN curve, points and body links |

Every setup stage returns
`{"setup": "<item_dir>/<name>_SETUP.prt", "setup_stage": "<stage>"}`.
Each completed stage publishes that canonical SETUP. Intermediate native saves
remain in `work_dir`; later stages never scan for old output suffixes. `load`
refuses an existing SETUP. The later initial stages are not a variant refresh API.

Structure construction preserves the existing PART feature graph and does not
save PART. Its alignment and color are ASSY occurrence overrides. The WAVE
chain remains `PART -> CAD4CAM -> BLANK`, with `CAD4CAM_BODY` and
`BLANK_REVOLVE_OUTLINE_BODY` as the named bodies. BLANK uses only native
Revolve Outline, a full 360-degree revolve, and the existing 5 mm offset.

## Variant Refresh

Call `nx.build_setup.refresh_setup(request)` with the article's paths after
native cloning has remapped and **saved all five article-owned files**, and
after the parent has updated and saved the copied PART expressions and the
ASSY/CAD4CAM/BLANK dependencies. No `setup_stage` is required. Prefer a fresh NX
process; an already loaded canonical SETUP is also selected as display/work
part. The reopen boundaries discard unsaved component changes, so the parent
must save its dependency edits before handing off.

The return value is `{"setup": <absolute article SETUP path>, "jaw_p3": <number>}`.
Refresh does not load the machine template, mount holders, replace the product
occurrence, copy an inherited jaw constraint, delete a CAM program, or regenerate
toolpaths. It edits the existing setup-local `p3` and point expressions, updates
the existing MAIN WAVE curve/body and MAIN_BL01 stock link, and recreates only
the three generated positioning constraints. Their stable names are
`ELSTER_AXIS_TOUCH`, `FLOW5_AXIAL_TOUCH` and `FLOW5_TOP_PARALLEL`. Manual CAM
objects and user-added model-history visibility are not rebuilt or reset.

Product occurrence lookup uses the prototype `FullPath` stem and verifies the
item-local prototype paths. Native cloning may leave occurrence display names
such as `BASELINE_ASSY`; **renaming them is not required by these builders**.
The parent may rename article-owned occurrences for navigator readability, but
must not replace their identities or rename the fixed machine occurrences.
Machine/jaw occurrence literals and template feature IDs remain the recorded
native selectors. Cloning must preserve the generated constraint/feature names.

The jaw strategy retains the active source's calibrated lowest gripping-edge
diameter `335.714642124` at source `p3 = 75`. Refresh applies
`p3 = 75 + (spanning_diameter - 335.714642124) / 2` to the existing local override.
It fails if the selected device range differs from the three cloned devices;
it does not silently substitute a new workholding device. MAIN_OUTSIDE uses
the largest blank cylinder radius plus 50 mm in local X and 10 mm in local Z;
MAIN_INSIDE keeps local Z at 10 mm.

## Unverified NX Details

Only static extraction and review have been performed. No application, NX,
tests, installs, linters or formatters were run. In particular, the installed
NX behavior still needs verification for inherited constraint/expression
ownership, native clone remapping, WAVE assembly-context transforms, recorded
face selections across the Elster rows, and preservation of manually programmed
CAM data through save/reopen. Ownership checks deliberately fail rather than
write a shared library object. Setup saves never request `SaveComponents=True`.
