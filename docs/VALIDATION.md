# Validation records

## Current local validation — 0.1.0.dev2

**Checked on 2026-10-17.** The refreshed application, English documentation and rebuilt Python distribution were checked locally on Linux. The detailed record is [validation-dev2.json](validation-dev2.json).

| Check | Result | Scope |
|---|---|---|
| Engine and integration suite | **84/84 PASS**, 2.631 s | Current source revision, including the English progress generator |
| Source GUI before the font fix | **7/7 groups PASS**, 1.051 s; cancellation 0.150 s | Actual Qt window, CLI subprocesses and build workflow in Linux offscreen mode |
| Source GUI with the font gate | **8/8 groups PASS**, 1.061 s; cancellation 0.163 s | Commit `044e32bebc13e87cf147868e497a2096ab2709f6`; checks actual glyph support for 17 interface font roles before running the build workflow |
| Installed wheel GUI before the font fix | **7/7 groups PASS**, 1.003 s; cancellation 0.150 s | Rebuilt `0.1.0.dev2` wheel installed outside the checkout and launched from `/tmp`; this record does not qualify a new wheel after the font fix |
| Real CLI subprocesses in the installed-wheel test | **PASS**; exit codes `0`, `0`, `0`, `0`, `130` | Four successful operations and the expected cancellation exit code `130` |
| Python distribution before the font fix | **Wheel and sdist built successfully** | The locally installed wheel reports `0.1.0.dev2` and contains the exact application PNG; the later CI distributions are tracked separately |

The new font gate checks a 96-character sample covering Latin letters, digits, Polish characters and interface punctuation against the actual fonts selected for 17 interface roles. It passed on Linux using DejaVu Sans Book and Bold. Two negative scenarios also produced the expected failure before any CLI worker started: an actual empty fontconfig database and an injected font-registration exception. Their report checksums are recorded in [validation-dev2.json](validation-dev2.json).

The desktop icon export is a **512 × 512 PNG**, **334,341 bytes**, with SHA-256 `03ee456da8263cf1ed476a05c60d719948aaf41f8d81316798b73717893f381a`. The original larger 3D master is preserved separately. [images/gui.png](images/gui.png) retains the earlier installed-wheel Linux capture after its real PYZ build and runtime check outside the checkout.

These records qualify the stated local Linux source and installed-wheel scenarios. The eight-check font-gate run does not claim a new local wheel installation after the font fix. Windows qualification has its own evidence below.

## Current Windows qualification — 0.1.0.dev2

**[CI run 39034556183](https://github.com/Swir/Maxkompilator/actions/runs/39034556183): 10/10 jobs SUCCESS**, at commit `044e32bebc13e87cf147868e497a2096ab2709f6`. The Windows source GUI passed **8/8 groups in 1.312 s**, with cancellation in **0.156 s**. The actual packaged application was relocated outside the checkout and completed two independent launches with **10/10 checks and five verified compiled CLI workers per launch**. Both windows exited cleanly after the full workflow, including real PYZ/resource/runtime checks, cancellation and reopening.

The first GUI process was **PID 3492** and reopening used **PID 1524**. Driver launch durations were **2.265 s** and **1.328 s**; total qualification took **3.875 s**. The inner GUI scenarios took **1.313 s** and **1.188 s**, with cancellation in **0.157 s** and **0.125 s**. Each launch verified **96 characters across 17 font roles** using actual Segoe UI Regular/Bold glyphs. Both captures from the SHA-verified downloaded artifact were inspected and contained readable Polish labels and logs; [images/gui-windows.png](images/gui-windows.png) is the actual reopened Windows EXE capture.

This completes **`gui.windows-test` for 3 points**, bringing the defined v1 score to **58%**. The evidence is automated Qt offscreen execution and capture review. A manual interactive Windows 11 release test, a clean Windows machine without Python, real Android SDK/device checks and .NET publishing/runtime qualification remain open. Full process reports, hashes, native results and download metadata are in [CI.md](CI.md) and [ci-evidence-dev2.json](ci-evidence-dev2.json).

## Historical baseline — 0.1.0.dev1

**Recorded on 2026-10-17.** The following historical results describe the `0.1.0.dev1` baseline. [Run 39028988975](https://github.com/Swir/Maxkompilator/actions/runs/39028988975), at commit `aea4aa811f139edab7b167ab86f1518a283a7302`, completed **10/10 jobs successfully**: six Core jobs, three native examples and a Windows desktop bundle. Its direct evidence remains in [ci-evidence.json](ci-evidence.json). Current dev2 qualification is recorded above and in [CI.md](CI.md).

The local qualification environment was **Linux x86_64, glibc 2.39, Python 3.12.14**. Native packaging used **PyInstaller 6.22.3**, and the GUI was tested with **PySide6/Qt 6.12.0** in `offscreen` mode. The source-GUI test exercised a real window, its logic and subprocesses. Packaged Windows GUI execution was a separate open gate at that baseline.

A machine-readable summary is in [validation-local.json](validation-local.json). Test sources and scripts are in the repository; the original temporary paths are not required to reproduce the documented commands.

### Local results and their scope

| Area | Evidence and result | What was checked | Evidence boundary |
|---|---|---|---|
| Engine and integration | **84/84 PASS**, 2.303 s; `python -m unittest discover -s tests -v` | Detection, plans, errors, paths, real PYZ output, CLI integration, reports and progress generation | Some adapter tests inspect command construction without invoking the relevant SDK |
| PYZ | **PASS**; `tests/test_engine.py` and real `examples/hello-python` | Build, package import, bundled resource, execution outside sources and report writing | Requires compatible Python; external dependencies are not automatically bundled |
| Native Python application | **PASS**; `scripts/qualify_native.py` after the final build in a separate job directory | ELF x64, SHA-256, execution outside sources and resource reading with `PYTHONPATH`/`PYTHONHOME` removed and restricted `PATH` | Covers the example on this Linux host, not every distribution or Windows/macOS |
| Qt GUI | **7/7 groups PASS**, 1.202 s; `scripts/gui_smoke.py` | Icon, automatic defaults, paths with spaces and Unicode, inspect/plan/doctor/build, real PYZ runtime check, logs, report, cancellation and descendant termination; cancellation: 0.156 s | Linux offscreen; opening the output folder is checked by intercepting a Qt URL rather than driving a file manager |
| Python package | **PASS**; wheel and sdist built, wheel installed with `--no-index --no-deps` outside the repository | Import/CLI version, packaged icon resources, real PYZ with data and smoke from the installed module | This run installed the wheel; the sdist was built. It does not qualify the desktop EXE bundle |
| Android | **Recipes checked; real APK/AAB unqualified** | Debug plans, clean before build, unsupported format/directory rejection, APK container and signature-checking code | No verified Android SDK build, installation, launch or store release |
| .NET | **Recipes checked; real publishing unqualified** | `dotnet publish`, self-contained mode, concrete project selection and target restrictions | No verified .NET SDK publish or execution of its output |
| Platforms outside Linux | **Remote results recorded separately in CI.md** | Local qualification does not execute Windows or macOS applications | A remote job's status comes from its own logs |

### GitHub Actions

**Core: 6/6 jobs SUCCESS.** Each job checked package installation, the test suite, generated roadmap consistency and a real PYZ example with a runtime test. Historical job IDs are recorded in [ci-evidence.json](ci-evidence.json).

The **84/84 result without skips** belongs to the local Linux run. Detailed Core **Python 3.11** logs showed Linux with **84 passed and 0 skipped**, macOS with **83 passed and 1 skipped**, and Windows with **82 passed and 2 skipped**. All three Python 3.13 jobs also succeeded; the detailed counters recorded here come from the 3.11 logs.

`unittest` includes skipped tests in its `Ran` count. A skipped case is not qualified on that system. The POSIX process-group regression is skipped on Windows, and the frozen Linux library-environment integration is skipped outside Linux. Symlink tests may be skipped when the runner account cannot create them.

**Native examples: 3/3 SUCCESS.** Windows x64 (`pe-x64`), Linux x64 (`elf-x64`) and macOS ARM64 (`mach-o`) passed builds, resource checks and execution outside the sources with restricted `PATH` and removed `PYTHONPATH`/`PYTHONHOME`. All three archives passed validation; the macOS archive preserved four symbolic links. The CI runners had Python installed, so these results do not complete the clean-machine test without an interpreter.

**Windows desktop bundle: SUCCESS.** The source GUI passed **7/7 test groups in 1.422 s**, with cancellation in **0.156 s**. Both executables and the shared runtime were built. The packaged `MaxkompilatorCLI.exe` detected a project, built a real PYZ and passed its smoke test. A complete packaged-GUI workflow, including closing and reopening the window, was still pending at this baseline.

### Packaged CLI worker on Linux

A real `MaxkompilatorCLI` executable built by PyInstaller ran its own engine, created a PYZ and executed it through an external Python interpreter. A separate environment check confirmed external Python and PyInstaller invocation. JSON input/output and resource checks passed. The result and executable checksum are recorded in `validation-local.json`. This historical result covered the Linux console worker; frozen Windows GUI qualification was a separate task at that point.

### Final local native Linux output

- Job ID: `97538f31331547f09f90a5618894965c`.
- Detected format: `elf-x64`.
- Application entry-point SHA-256: `b0a56d501f6d26093231bd15c7cceddfe20161b27b7246c9354070ae9c56b208`.
- Verified application output: `Maxkompilator: build and resource check OK`.
- Qualification launched the program in a temporary directory with a system-only `PATH` and without `PYTHONPATH` or `PYTHONHOME`.

This ran on the same Linux host that built the application. It does not establish installation and execution on a separate clean machine. The checksum identifies the tested executable; the application retains its dependencies in its distribution directory.

#### Native output archive

`scripts/qualify_native.py` creates `native-example-TARGET.tar.gz` containing the entire application directory, build report and qualification report. The script reopens the archive and compares its member list, symlink types and targets, POSIX permissions, and checksums of the executable and reports. This preserves the files needed to run the program after downloading a CI artifact.

The locally verified `native-example-linux-x64.tar.gz` is **11,932,078 bytes**, with SHA-256 `56912d1b7882ddf3c8d72e2f016765b33a4b954a120c581a6cad159053301ddd`. It is a development artifact. Archive validation does not establish release signing or compatibility with every target system.

### Reproduce the main checks

After installing Maxkompilator and the appropriate extras:

```bash
python -m unittest discover -s tests -v
python scripts/update_progress.py --check
python -m maxkompilator build examples/hello-python --format zipapp --smoke-test --json
```

Native packaging requires PyInstaller and runs on the selected operating system:

```bash
python -m pip install -c constraints-ci.txt ".[freeze]"
python -m maxkompilator build examples/hello-python --format executable --smoke-test --json
python scripts/qualify_native.py examples/hello-python/dist/maxkompilator/build-report.json
```

The GUI test selects Qt's `offscreen` platform:

```bash
python -m pip install -c constraints-ci.txt ".[gui]"
python scripts/gui_smoke.py --screenshot build/gui-smoke.png
```

Negative tests cover missing tools, nonzero exits, a successful command producing no artifact, stale output from a previous job, invalid executables, timeouts, cancellation, attempts to overwrite sources and invalid entry points. They verify concrete scenarios rather than every possible project.

### Remaining qualification at this baseline

At the dev1 baseline, open scenarios included the complete built Windows GUI workflow with reopening, a computer without Python, Android with the proper SDK and a device, and real .NET publishing. The current dev2 record above now completes the automated packaged-GUI criterion. The Windows distribution remains the complete folder containing `Maxkompilator.exe`, `MaxkompilatorCLI.exe` and `_internal`. Current acceptance status is tracked in [ROADMAP.md](../ROADMAP.md).

[Scored roadmap](../ROADMAP.md) · [CI results](CI.md) · [Architecture](ARCHITECTURE.md)
