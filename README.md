<p align="center">
  <img src="assets/maxkompilator.png" alt="Maxkompilator multicolor 3D application icon" width="160">
</p>

# Maxkompilator

**One build workspace — by [Swir](https://github.com/Swir).**

*An extensible build orchestrator for desktop and Android projects. One project workflow, explicit toolchain requirements, and build results backed by evidence.*

Maxkompilator takes a project from its source folder through detection, environment checks, a build plan, execution and verified output. The first implementation covers **Python, Android and .NET**, with Windows and Android as the main delivery targets.

**Development version: `0.1.0.dev2` — working engine and experimental desktop interface.** This iteration introduces English documentation and a vivid, futuristic 3D visual identity. The interface keeps its Polish labels. Current capabilities and open qualification gates are described below.

**Last recorded CI baseline: 10/10 jobs successful for `0.1.0.dev1`.** Six jobs checked the engine on Linux, Windows and macOS with Python 3.11 and 3.13. Three built and ran a native example with its resource on **Windows x64, Linux x64 and macOS ARM64**. The desktop job built the **Windows Maxkompilator bundle** and tested its packaged CLI worker. These results belong to the specific commit recorded in [CI results](docs/CI.md); they do not automatically qualify a later revision.

**Still awaiting qualification:** the complete packaged Windows GUI workflow and reopening, a Windows machine without Python, real APK/AAB builds with Android SDK, and actual .NET publishing. The native results cover the tested example on the stated CI runners.

[Roadmap and percentages](ROADMAP.md) · [Architecture](docs/ARCHITECTURE.md) · [Validation results](docs/VALIDATION.md) · [Verified CI jobs](docs/CI.md) · [GitHub Actions](https://github.com/Swir/Maxkompilator/actions)

## v1 progress

<!-- MAXKOMPILATOR:PROGRESS:START -->

**v1.0 progress: 55% — 55 / 100 points.**

Only completed criteria with recorded evidence earn points. Work in progress does not increase the percentage.

| Milestone | v1 weight | Earned | Milestone progress |
|---|---:|---:|---:|
| Project foundation and CI | 8 pts | 8 / 8 pts | 100% |
| Project and environment discovery | 12 pts | 12 / 12 pts | 100% |
| Python and Windows builds | 16 pts | 6 / 16 pts | 37.5% |
| Android: APK and AAB | 14 pts | 2 / 14 pts | 14.3% |
| .NET and Windows publishing | 12 pts | 2 / 12 pts | 16.7% |
| Desktop interface | 12 pts | 9 / 12 pts | 75% |
| Profiles and repeatable output | 10 pts | 5 / 10 pts | 50% |
| Reliability and release qualification | 10 pts | 8 / 10 pts | 80% |
| Linux and macOS runners | 4 pts | 3 / 4 pts | 75% |
| Extensibility and additional architectures | 2 pts | 0 / 2 pts | 0% |
| **Total** | **100 pts** | **55 / 100 pts** | **55%** |

Source: [docs/progress.json](docs/progress.json) · last updated: **2026-10-17**.

<!-- MAXKOMPILATOR:PROGRESS:END -->

**100% means completion of the defined v1 release.** Additional languages, installers and integrations have their own future scope. The percentage measures accepted criteria, not time remaining until release.

## Download the Windows development build

The recorded baseline build is available from GitHub Actions:

1. Open [successful CI run 39028988975](https://github.com/Swir/Maxkompilator/actions/runs/39028988975).
2. Under **Artifacts**, select **`Maxkompilator-Windows-x64-dev`**.
3. Extract the entire archive and open its `dist/Maxkompilator` folder.
4. Keep **`Maxkompilator.exe`, `MaxkompilatorCLI.exe` and `_internal`** together. Launch **`Maxkompilator.exe`**.

GitHub reports an artifact size of **54,090,240 bytes, approximately 51.6 MiB**, with retention until **2026-10-31**. These details describe the recorded `0.1.0.dev1` artifact. The `native-example-*` artifacts contain small test applications; select `Maxkompilator-Windows-x64-dev` for the build tool itself.

This bundle was produced by a real Windows job. Its source GUI passed seven test groups, and its packaged console worker detected a project, built a PYZ and ran the result. The complete packaged window and reopening scenario remains a separate qualification gate.

## Current technology support

| Project | Detected input | Prepared output | Required environment |
|---|---|---|---|
| Python | A `.py` script or project folder | `.pyz` through zipapp; native application through PyInstaller | Python 3.11+; PyInstaller and application dependencies for native packaging |
| Android | Gradle project with an application configuration | Debug `.apk` or `.aab` | Compatible JDK, Android SDK, Gradle configuration and available project dependencies |
| .NET | A concrete `.csproj` file | `dotnet publish` output directory | A .NET SDK compatible with the project and its libraries |
| Maxkompilator GUI | Optional desktop interface | Project selection, diagnostics, plans, builds, logs and cancellation | Source GUI tested offscreen on Linux and Windows; full packaged-window qualification remains open |

Full support for C/C++, Rust, Go, Java, Flutter, Electron/Tauri, extensions and game engines is **planned**. A remote runner protocol for Linux/macOS is also future work. The shared interface will use build environments that are actually available and connected.

## Run from source

From the repository directory, using Python 3.11 or newer:

```bash
python -m pip install .
python -m maxkompilator --help
```

The CLI engine uses the Python standard library. The GUI and PyInstaller are optional extras:

```bash
python -m pip install -c constraints-ci.txt ".[gui,freeze]"
python -m maxkompilator gui
```

These commands install Maxkompilator. Android SDK, .NET SDK and the dependencies of the application being built need their own configuration. Tool versions must match the selected project.

### Desktop interface

![Maxkompilator GUI after building and running a PYZ](docs/images/gui.png)

The screenshot shows `0.1.0.dev2` installed from its rebuilt wheel outside the checkout, after a real PYZ build and runtime check in **Linux, Qt 6.12, offscreen** mode. See [local validation](docs/VALIDATION.md) for the installed-wheel results and [docs/CI.md](docs/CI.md) for the separately tracked Windows qualification. The visual direction combines a multicolor 3D icon, illuminated accents and readable dark panels. [Visual identity](docs/DESIGN.md) documents the icon, palette and interface rules for this project and future Swir applications.

### Inspect, diagnose and plan

```bash
python -m maxkompilator inspect ./project --json
python -m maxkompilator doctor ./project --format zipapp
python -m maxkompilator plan ./project --target native --format zipapp --json
```

`inspect` reports the detected project, `doctor` checks requirements, and `plan` describes the build. The `native` target selects the current runner's operating system and architecture. Cross-platform output requires a compatible toolchain and runner.

### Build a Python project

The repository includes `examples/hello-python`, a small example with a package and a data file:

```bash
python -m maxkompilator build ./examples/hello-python --target native --format zipapp --smoke-test
```

`--smoke-test` also runs the Python output outside the source directory. To select your own script explicitly:

```bash
python -m maxkompilator build ./project --kind python --entry main.py --target native --format zipapp
```

The default output directory is `dist/maxkompilator` inside the project. `--output` chooses another directory; relative paths are resolved from the project root. Each job report contains the exact artifact paths and runtime test result.

Use `--entry` to select an entry point and `--kind` to resolve the project type (`python`, `android` or `dotnet`). Quote paths containing spaces. Command help lists the available arguments:

```bash
python -m maxkompilator build --help
```

**A PYZ requires an installed, compatible Python interpreter.** Maxkompilator packages project sources and resources; it does not bundle the interpreter or automatically vendor external dependencies into a PYZ. See the [Python zipapp documentation](https://docs.python.org/3/library/zipapp.html) for the format and native-extension limitations.

### Native Python applications

After installing PyInstaller and the application's dependencies, native packaging uses the current operating system:

```bash
python -m maxkompilator plan ./project --kind python --entry main.py --target native --format executable --json
python -m maxkompilator build ./project --kind python --entry main.py --target native --format executable
```

The initial PyInstaller adapter creates an **application directory**. Keep all its files, including its libraries. Windows output includes an EXE; Linux and macOS produce their native formats. Changing a file extension does not change the build platform.

`--python` selects the build interpreter. Diagnostics check its OS and architecture, which must match the target and runner. The native example passed real builds, resource checks and execution outside the sources on Linux x64, Windows x64 and macOS ARM64 in the recorded CI baseline.

### Android

The initial Android adapter requires an application module named `app` and a Gradle wrapper in the project root:

```bash
python -m maxkompilator plan ./android-app --kind android --target android --format apk --json
python -m maxkompilator build ./android-app --kind android --target android --format apk
```

`--format aab` selects a debug App Bundle. Use APK for installation on a phone. ABI and variant configuration belong to the Gradle project. The job runs `:app:clean` before building to exclude stale output, and Maxkompilator's output directory must be outside `app/build`.

The engine checks APK container structure and requires successful signature verification with Android SDK's `apksigner`. This path has not yet been qualified by building and installing a real Android application. AAB structure checks do not qualify its signing or store distribution.

### .NET

The .NET adapter accepts a concrete project with one target framework:

```bash
python -m maxkompilator plan ./dotnet-app/App.csproj --kind dotnet --target native --format directory --json
python -m maxkompilator build ./dotnet-app/App.csproj --kind dotnet --target native --format directory
```

The publish plan sets `--self-contained true`; keep the complete output directory. NativeAOT and publishing multiple frameworks in one job require further support. The initial adapter requires a Windows runner for WPF/WinForms projects. Recipes and their restrictions have been tested; real .NET SDK publishing is still awaiting qualification.

### Project configuration

Store basic settings in `maxkompilator.toml` at the project root:

```toml
[project]
kind = "python"
entry = "main.py"

[build]
format = "zipapp"
target = "native"

[python]
data = ["hello/message.json"]
```

Data paths are relative to the project root. Command arguments select settings for an individual job. A complete profile editor, tool version management and signing profiles remain on the roadmap.

## Output and logs

In this table, `BASE` is `--output` or the default `dist/maxkompilator`; `UUID` identifies one job.

| Content | Location |
|---|---|
| Python archive | `BASE/project-name.pyz` |
| Native Python application or .NET publish output | `BASE/runs/UUID/` |
| Copied Android output | `BASE/artifacts/`, preserving the module path |
| Most recent job report | `BASE/build-report.json` |
| Individual job report and log | `BASE/.maxkompilator/UUID/build-report.json` and `build.log` |

Each native build receives its own output directory, so files from a previous attempt cannot satisfy a new job. An output-directory lock prevents two jobs from writing to the same destination concurrently. Reports contain the requested plan, executed plan, artifact paths, SHA-256 checksums and runtime test status.

In the CLI, `--json` leaves one report on standard output and sends build logs to standard error. `--timeout` limits each build step, while `--smoke-timeout` limits the runtime test. Ctrl+C requests job cancellation.

## Build and runtime verification

Qualification records distinguish these results:

| Result | Required evidence |
|---|---|
| Project detected | Configuration files read and an adapter selected |
| Plan prepared | Concrete runner, commands, requirements and expected output |
| Built | Successful execution and expected new output files |
| Artifact checked | Format, integrity and required metadata verified |
| Executed | A real runtime test on the specified OS or device |

Reports state which checks actually ran. An exit code of `0`, an existing file or a passing recipe test alone cannot establish that an application runs on Windows or a phone.

Automatic `--smoke-test` currently supports Python adapter output. Android and .NET retain `not_run` when no suitable runtime scenario is available. If a requested Python runtime check fails or times out, the entire job fails.

### Platform and format boundaries

- **Windows EXE through PyInstaller:** build in a suitable Windows environment. PyInstaller bundles the interpreter, and the result depends on the build OS and architecture. See [PyInstaller's operating mode](https://pyinstaller.org/en/stable/operating-mode.html).
- **Android:** initial recipes target debug variants. APKs can be installed; AABs are used for subsequent processing and distribution. Release builds require the appropriate key. See [building Android from the command line](https://developer.android.com/build/building-cmdline).
- **.NET:** runtime behavior depends on the project and publishing settings. Each application must support its selected target. See [dotnet publish](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-publish).
- **Linux and macOS runners:** a roadmap entry does not provide a remote machine. An adapter needs a runner that satisfies the job's requirements.

Build projects you own or trust. Compilers, Gradle/MSBuild configuration and packaging hooks can execute project code with the current user's permissions. Maxkompilator orchestrates these tools; a local subprocess does not provide OS-level isolation.

## Development and quality checks

```bash
python -m unittest discover -s tests -v
python scripts/update_progress.py --check
```

The recorded `0.1.0.dev1` local Linux baseline passed **84/84 core and integration tests** and **7/7 GUI test groups**. All ten recorded CI jobs passed. Detailed Python 3.11 Core logs showed Linux with 84 passed, macOS with 83 passed and one skipped, and Windows with 82 passed and two skipped. See [docs/VALIDATION.md](docs/VALIDATION.md) and [docs/CI.md](docs/CI.md) for the exact evidence and skip rules.

With the `gui` extra installed, test the source GUI without a desktop:

```bash
python scripts/gui_smoke.py --screenshot build/gui-smoke.png
```

Build and qualify the native example sequentially:

```bash
python -m maxkompilator build examples/hello-python --format executable --smoke-test --json
python scripts/qualify_native.py examples/hello-python/dist/maxkompilator/build-report.json
```

Qualification compares SHA-256 and runs the application from another directory with `PYTHONPATH`/`PYTHONHOME` removed and a restricted `PATH`. This checks the example on the current system. The script also creates `native-example-TARGET.tar.gz`, preserving executable permissions and symbolic links.

CI covers Linux/Windows/macOS with Python 3.11 and 3.13, native Python builds on all three systems, and a Windows desktop bundle. [docs/CI.md](docs/CI.md) records outcomes for a specific commit and distinguishes the source GUI, packaged console worker and clean-machine runtime qualification.

### Build the Windows Maxkompilator bundle

Run the packaging script in a Windows environment:

```bash
python -m pip install -c constraints-ci.txt ".[gui,freeze]"
python scripts/build_windows.py
```

The distribution is the entire `dist/Maxkompilator` folder, containing **`Maxkompilator.exe`, `MaxkompilatorCLI.exe` and their shared `_internal` directory**. The first executable opens the GUI, and the second handles console jobs. Keep the folder together.

SDKs used to build other projects remain separate tools. For example, native Python builds launched from packaged Maxkompilator require an available build interpreter and PyInstaller; select the interpreter with `--python` when needed.

### Update roadmap percentages

Update [docs/progress.json](docs/progress.json). A criterion can be `pending`, `in_progress` or `complete`; only `complete` with a nonempty `evidence` list earns its fixed weight:

```bash
python scripts/update_progress.py
```

The script regenerates the English progress blocks in README and ROADMAP. `--check` validates the weights, presence of evidence and generated content. It does not judge the truth of an evidence description: inspect the cited test or result before completing a criterion.

## Development direction

Maxkompilator has a shared GUI/CLI engine, a dark desktop interface, its own 3D icon, basic TOML configuration and readable logs. Full profiles, a multi-project queue, remote runners and API/MCP integration are subsequent steps. New technologies will join through adapters with explicit capability matrices.

The intended workflow is **project → plan → build → verified output**, with the supported environment and proof recorded for each technology.
