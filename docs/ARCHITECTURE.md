# Maxkompilator architecture

## Purpose and scope

Maxkompilator orchestrates build tools. One project and job model serves the CLI, optional GUI and future API/MCP interfaces. Each technology has an adapter that describes detection, requirements, the build plan and expected output.

The first implementation includes a local Python 3.11+ engine, zipapp/PyInstaller, Android Gradle and `dotnet publish` adapters. The optional PySide6 GUI launches jobs through the shared CLI. Real Python output and GUI integration were checked locally on Linux; results from other platforms are recorded in [VALIDATION.md](VALIDATION.md). Remote runners, a multi-project queue, full profiles and a public plugin interface are planned. Their intended architectural boundaries are included below.

## Layers

| Layer | Responsibility | Dependencies |
|---|---|---|
| CLI/GUI interface | Collect parameters; display plans, logs and results | Public engine operations |
| Detection | Read project files and describe candidates | Filesystem; no application-code imports |
| Adapter | Technology requirements, supported targets, plan and artifact validator | Project and runner model |
| Local runner | Execute concrete steps; handle logs, timeouts and cancellation | Processes and an explicit job directory |
| Reporting | Job state, files, checksums and completed checks | Runner and validator output |
| Future remote runner | Execute the same job on a connected Windows/Linux/macOS environment | Explicit protocol, authentication and runner capabilities |

The CLI engine does not import PySide6. Both interfaces use the same planning and execution logic; the GUI does not maintain a separate collection of compiler commands. The window uses `QProcess`, receives logs and a JSON report, locks input settings during a job, and forwards cancellation to the worker. In the Windows bundle, `MaxkompilatorCLI.exe` provides console streams while `Maxkompilator.exe` opens the window without a console.

## Job workflow

1. **Detect.** Read the directory and known configuration files. When multiple projects are possible, selection must be explicit, for example through `--kind` or a concrete project file. Select a Python entry point with `--entry`.
2. **Diagnose.** Check required tools, runner capabilities and basic configuration. A version probe may execute a bounded diagnostic command, but it does not build the project.
3. **Plan.** Describe concrete steps, arguments, working directories and expected output. `plan --json` exposes this data for inspection and automation. Planning does not execute build commands.
4. **Build.** Run the plan in the selected directory and forward progress to the interface. Record exit codes and logs.
5. **Validate.** Check that expected new files were produced. Format-specific validators add structure, metadata and signature checks.
6. **Report.** Record the build result and the tests actually performed. `--smoke-test` runs Python output from a separate temporary directory; other adapters need an appropriate runtime scenario or device.

## Design contracts

The names below describe required information. They include intended extensions beyond the currently implemented fields and public API.

| Model | Information |
|---|---|
| Project | Source path, type, selected file/project, entry point and detected configuration |
| Target | Operating system, architecture, format, variant and tool requirements |
| Plan | Adapter, runner, steps with argument arrays, working directories and expected artifacts |
| Requirement | Tool name, probe command, result and guidance when missing |
| Artifact | Path, size, format, checksum and verification results |
| Job result | State, exit code, timing, logs, artifacts and completed tests |

A format identifier cannot imply capabilities that the technology does not support. `native` means the current runner. A `windows` setting alone does not provide Windows or a compiler able to target it.

## Runners and execution boundaries

Commands are constructed as an executable and an argument list. Arbitrary project text must not be concatenated into shell commands. Platform wrappers such as a Gradle `.bat` file require explicit, restricted handling appropriate to the OS. Arguments must preserve spaces and Unicode.

A runner has a defined working directory, a timeout and cancellation handling for the worker and its children. Cancellation or timeout cannot become success merely because an old output file remains on disk. Native Python and .NET builds use `BASE/runs/UUID`; reports preserve both the requested plan and the execution plan with its adjusted paths. A PYZ is created in a temporary directory and atomically installed as `BASE/name.pyz`. Android runs `:app:clean` before its debug task, then copies module output into `BASE/artifacts`.

Every job writes its own `build.log` and `build-report.json` under `BASE/.maxkompilator/UUID`. `BASE/build-report.json` holds the most recent job report. An output-directory lock prevents competing jobs from writing concurrently. Artifacts receive SHA-256 checksums, and format checks inspect content rather than only the filename extension. The APK path also calls `apksigner verify`, which must succeed. Qualification of this complete path with a real Android SDK remains open.

Detection and planning do not import application sources or execute project configuration. Building can execute project code through Python hooks, Gradle/MSBuild scripts and dependency tools. A local subprocess has the user's privileges. Isolating untrusted projects requires a separate container, virtual machine or otherwise restricted runner.

Jobs in the future remote protocol will have unique identifiers. Runners must declare their OS, architecture and available tools; a server must not accept arbitrary host paths as artifacts. Source upload, authentication and result downloads must respect the environment's boundaries. Signing keys belong in the runner's secret store or signing profile, outside ordinary configuration, logs and source archives.

## States and evidence

The current report separates job state (`running`, `built`, `failed`, `cancelled`) from artifact verification and the `smoke_test` field. A timeout ends the job as `failed` with a concrete error; cancellation produces `cancelled`. Runtime test states are `not_run`, `passed`, `failed` and `cancelled`. A successful build requires successful execution and expected output; installation and runtime results are recorded separately.

The CLI returns `0` after a successful operation or build, `1` for a build failure, `2` for invalid input or plans, `3` for failed environment diagnostics, and `130` for build cancellation. A requested runtime test failure fails the entire job. In JSON mode, build logs go to stderr and the final report is one object on stdout.

Each test records its scope: planning, building, artifact structure, signing, installation or execution. A mocked process can verify error handling but cannot prove a real SDK build.

Product weights and completion evidence are stored in [progress.json](progress.json). `scripts/update_progress.py` validates the data and generates the English README/ROADMAP views. It checks structure and consistency; evidence must still be assessed against the cited code, tests and actual job results.

## Extending the system

A new adapter should declare supported inputs and targets, tool requirements, a plan and output verification. It should include a small fixture project with expected behavior. Each additional OS or architecture requires its own build and runtime evidence rather than inheriting qualification from another platform.

Basic `maxkompilator.toml` configuration stores the project type, entry point, format, target and Python data files. Full profiles, a dependency manager, a job queue and API/MCP integration are future extensions. They must preserve one engine shared by every interface.
