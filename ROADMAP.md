# Maxkompilator roadmap

**v1 has a fixed budget of 100 points.** Each milestone contains criteria with explicit weights. A criterion earns points only when it is complete and has recorded evidence. File counts, commits and prepared plans do not replace a test of the actual feature.

The v1 scope includes a shared CLI/GUI engine, local Python/Windows, Android and .NET builds, qualification of real output, and initial Linux/macOS runner support. Remote worker v1 and adapter API v1 are implemented and exercised by real-process integration tests.

**100% means completion of this v1 checklist.** Additional languages and formats have a separate roadmap. Weights describe the agreed product scope rather than elapsed or remaining development time. Completing easy criteria does not award points to unfinished difficult ones.

Local qualification covers detection and planning for three technologies, a real PYZ and native Linux build, basic configuration and reports, CLI/GUI integration, cancellation and an installable wheel. The dev2 CI run additionally verified native examples on Windows x64, Linux x64 and macOS ARM64 and the actual packaged Windows GUI with its compiled CLI worker. Both independent GUI launches passed all ten checks, including readable interface text, the full workflow, cancellation and reopening. The [validation report](docs/VALIDATION.md) separates these results from the open Python-free Windows, manual interactive release, Android and .NET qualification gates.

The CI foundation is complete based on **six successful Core jobs** for Linux/Windows/macOS and Python 3.11/3.13. Each result refers to a specific run in [docs/CI.md](docs/CI.md). Current local evidence additionally qualifies real Android APK/AAB and device execution, .NET console/WinForms publishing, application profiles and repeated payload hashes. The remaining gates are Python-free Windows execution and full CI/interactive release qualification.

The verified [dev2 run 39034556183](https://github.com/Swir/Maxkompilator/actions/runs/39034556183), at commit `044e32bebc13e87cf147868e497a2096ab2709f6`, completed **10/10 jobs successfully**. Its packaged Windows GUI, font checks, readable captures and reopening proof complete **`gui.windows-test` for 3 points**, moving v1 from **55% to 58%**. All other criterion weights and statuses remain unchanged. The generated table below is the source for the current v1 percentage; English documentation and refreshed branding do not earn additional runtime points.

## Current progress

<!-- MAXKOMPILATOR:PROGRESS:START -->

**v1.0 progress: 93% — 93 / 100 points.**

Only completed criteria with recorded evidence earn points. Work in progress does not increase the percentage.

| Milestone | v1 weight | Earned | Milestone progress |
|---|---:|---:|---:|
| Project foundation and CI | 8 pts | 8 / 8 pts | 100% |
| Project and environment discovery | 12 pts | 12 / 12 pts | 100% |
| Python and Windows builds | 16 pts | 11 / 16 pts | 68.8% |
| Android: APK and AAB | 14 pts | 14 / 14 pts | 100% |
| .NET and Windows publishing | 12 pts | 12 / 12 pts | 100% |
| Desktop interface | 12 pts | 12 / 12 pts | 100% |
| Profiles and repeatable output | 10 pts | 10 / 10 pts | 100% |
| Reliability and release qualification | 10 pts | 8 / 10 pts | 80% |
| Linux and macOS runners | 4 pts | 4 / 4 pts | 100% |
| Extensibility and additional architectures | 2 pts | 2 / 2 pts | 100% |
| **Total** | **100 pts** | **93 / 100 pts** | **93%** |

Source: [docs/progress.json](docs/progress.json) · last updated: **2026-10-18**.

### Criteria and evidence

#### Project foundation and CI — 8 points

- [x] **v1 scope, instructions and measurable completion criteria — 2 points.** Evidence: README.md and ROADMAP.md: scope, limitations and fixed v1 weights. ID: `foundation.scope`.
- [x] **Engine, adapter and runner boundaries — 2 points.** Evidence: docs/ARCHITECTURE.md: job workflow, responsibilities and result model. ID: `foundation.architecture`.
- [x] **Installable package and working CLI entry point — 2 points.** Evidence: Wheel and sdist built; wheel installed without an index or dependencies outside the repository; CLI, packaged icon resources, real PYZ with data and smoke test PASS â€” docs/VALIDATION.md and docs/validation-local.json. ID: `foundation.package`.
- [x] **Working CI with quality and progress consistency checks — 2 points.** Evidence: GitHub Actions run 39028988975 for commit aea4aa811f139edab7b167ab86f1518a283a7302: six Core jobs across Linux/Windows/macOS and Python 3.11/3.13 SUCCESS, including tests, roadmap validation and a real PYZ with a smoke test â€” docs/CI.md; https://github.com/Swir/Maxkompilator/actions/runs/39028988975. ID: `foundation.ci`.

#### Project and environment discovery — 12 points

- [x] **Detect Python, Android and .NET projects — 3 points.** Evidence: tests/test_detection.py: scripts, Python projects, Android projects and concrete csproj detection; local suite PASS â€” docs/VALIDATION.md. ID: `discovery.detection`.
- [x] **Explicit project type and entry point selection when ambiguous — 3 points.** Evidence: tests/test_detection.py: test_multiple_python_scripts_need_explicit_entry, test_mixed_directory_requires_explicit_kind, test_multiple_csprojects_require_concrete_project_path â€” PASS. ID: `discovery.ambiguity`.
- [x] **Required tool diagnostics with actionable missing-tool messages — 3 points.** Evidence: tests/test_engine.py: test_missing_tool_yields_failed_report_without_build; scripts/gui_smoke.py: environment_doctor_and_smoke_flag_scoping â€” local PASS. ID: `discovery.doctor`.
- [x] **CLI and JSON build plans without running the build — 3 points.** Evidence: tests/test_engine.py: test_inspect_and_plan_are_read_only_and_json_is_parseable; tests/test_adapters.py: test_pyinstaller_plan_is_native_structured_and_has_no_side_effects â€” PASS. ID: `discovery.plan`.

#### Python and Windows builds — 16 points

- [x] **Build and run a real PYZ from a simple project — 4 points.** Evidence: tests/test_engine.py: test_zipapp_builds_and_runs_with_resources_outside_source; real examples/hello-python PYZ and smoke test PASS on Linux â€” docs/VALIDATION.md. ID: `python.zipapp`.
- [x] **Native build adapter using PyInstaller — 2 points.** Evidence: maxkompilator/adapters/python_adapter.py and a real example built and run with PyInstaller 6.22.3 on Linux â€” docs/VALIDATION.md. ID: `python.pyinstaller`.
- [x] **Real EXE with a valid format, resources and the built application's icon — 5 points.** Evidence: Actual profiled Windows PE x64 with seven matching embedded icon payloads, version 1.0.0.0, resource and runtime PASS; docs/evidence/windows-2026-10-18/profile-qualification.json. ID: `python.exe`.
- [ ] **Run a built EXE on Windows without installing Python — 5 points.** In progress; points are awarded after the full criterion is met. ID: `python.windows-runtime`.

#### Android: APK and AAB — 14 points

- [x] **Gradle recipes for debug APK/AAB and wrapper-based projects — 2 points.** Evidence: tests/test_adapters.py: test_android_debug_apk_plan_does_not_execute_wrapper and test_android_artifact_patterns_select_only_debug_outputs â€” PASS; recipes checked, real APK/AAB qualification pending. ID: `android.gradle`.
- [x] **Real APK: manifest, package, variant and signature verification — 4 points.** Evidence: Actual Gradle 8.11.1 / AGP 8.9.2 APK build; SDK aapt manifest/package/version/debug and apksigner certificate/SHA-256 checks PASS; docs/evidence/windows-2026-10-18/apk-build-report.json. ID: `android.apk`.
- [x] **Install and launch an APK on an emulator or phone — 5 points.** Evidence: APK installed and launched twice on the Android API 36 x86_64 emulator; independent PIDs 2539/2713 each read the compiled resource and logged MAXKOMPILATOR_ANDROID_RUNTIME_OK; docs/evidence/windows-2026-10-18/android-qualification.json. ID: `android.device`.
- [x] **Real AAB and explicit debug/release signing distinction — 3 points.** Evidence: Actual Gradle debug AAB built; unsigned state explicitly distinguished from production signing; bundletool 1.18.2 validate and decoded package/version/debug manifest comparison PASS; docs/evidence/windows-2026-10-18/android-qualification.json and aab-build-report.json. ID: `android.aab`.

#### .NET and Windows publishing — 12 points

- [x] **dotnet publish adapter with an explicit project and target — 2 points.** Evidence: tests/test_adapters.py: test_dotnet_publish_includes_runtime_and_concrete_project and WPF/NativeAOT restrictions â€” PASS; recipe verified, real .NET SDK publishing pending. ID: `dotnet.recipe`.
- [x] **Publish a real .NET project and verify its output — 4 points.** Evidence: Actual Windows self-contained net8.0 build through Maxkompilator; PE x64 apphost, resource, runtime DLLs and hashes PASS; docs/evidence/windows-2026-10-18/dotnet-build-report.json and dotnet-qualification.json. ID: `dotnet.publish`.
- [x] **Run the published application on Windows — 4 points.** Evidence: Published 188-file application copied outside the sources and executed on Windows x64; MAXKOMPILATOR_DOTNET_RUNTIME_OK and matching copied-tree hashes PASS; docs/INTEGRATION_2026-10-18.md. ID: `dotnet.windows-runtime`.
- [x] **Verify desktop application dependencies and distribution mode — 2 points.** Evidence: Real self-contained WinForms application painted a window, read its resource and exited successfully after relocation; 465 published files include WindowsDesktop dependencies; docs/evidence/windows-2026-10-18/desktop-qualification.json. ID: `dotnet.desktop`.

#### Desktop interface — 12 points

- [x] **Dark interface, original icon and by Swir attribution — 3 points.** Evidence: maxkompilator/gui.py; scripts/gui_smoke.py: initial_window_icon_and_controls â€” PASS on Linux with Qt 6.12 offscreen in the 0.1.0.dev1 qualification. ID: `gui.design`.
- [x] **Project selection, diagnostics, planning and building from the GUI — 3 points.** Evidence: scripts/gui_smoke.py: inspect_and_plan_unicode_path_auto_defaults, environment_doctor_and_smoke_flag_scoping, zipapp_build_real_runtime_and_persisted_report â€” PASS on Linux. ID: `gui.workflow`.
- [x] **Responsive logs, background work and job cancellation — 3 points.** Evidence: scripts/gui_smoke.py: open_results_and_copy_log_buttons, cancel_button_stops_running_build, cancelled_worker_and_descendant_are_stopped â€” PASS on Linux. ID: `gui.responsiveness`.
- [x] **Complete Windows GUI workflow and relaunch test — 3 points.** Evidence: GitHub Actions run 39034556183, job 117401756236, commit 044e32bebc13e87cf147868e497a2096ab2709f6: actual packaged Windows x64 GUI completed two independent launches (PIDs 3492 and 1524), each with 10 passing checks, 5 verified compiled CLI workers and a clean exit â€” docs/CI.md and docs/ci-evidence-dev2.json; https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401756236; Relocated bundle outside the checkout; real PYZ/resource test, cancellation, descendant termination and reopening PASS; 17 font roles passed the 96-character glyph check in each launch, and both downloaded captures were visually checked for readable text. This completes automated GUI qualification; manual interactive and Python-free Windows release gates remain open. ID: `gui.windows-test`.

#### Profiles and repeatable output — 10 points

- [x] **Saved project profiles and configuration validation — 3 points.** Evidence: maxkompilator/config.py and examples/hello-python/maxkompilator.toml; tests/test_engine.py: test_invalid_config_has_actionable_error and a real build using the example configuration â€” PASS. ID: `profiles.configuration`.
- [x] **Application name, version, icon and bundled resource settings — 2 points.** Evidence: Name, version, icon and data verified in actual Python and WinForms PE artifacts; scripts/qualify_windows_profile.py and recorded qualification JSON. ID: `profiles.resources`.
- [x] **Pinned tools and repeat builds from a selected profile — 3 points.** Evidence: Two separate pinned Python 3.12.14 / PyInstaller 6.22.3 builds have identical SHA-256 for every one of 56 payload files; docs/evidence/windows-2026-10-18/profile-qualification.json. ID: `profiles.repeatability`.
- [x] **Separate job output, logs and reports with checksums — 2 points.** Evidence: maxkompilator/engine.py writes per-run reports, logs and SHA-256 checksums; tests/test_engine.py: test_build_json_stdout_is_single_report and test_nonzero_exit_is_logged_and_reported â€” PASS. ID: `profiles.reports`.

#### Reliability and release qualification — 10 points

- [x] **Errors, timeouts and cancellation never report false success — 3 points.** Evidence: tests/test_engine.py: test_zero_exit_without_artifact_is_failure, test_running_process_can_be_cancelled, test_process_timeout, test_failed_smoke_is_not_reported_as_success â€” PASS. ID: `reliability.failures`.
- [x] **Spaces, Unicode and input/output path boundary checks — 2 points.** Evidence: tests/test_detection.py: test_explicit_entry_cannot_escape_project; tests/test_engine.py: test_output_cannot_overwrite_project_root_or_parent; real GUI smoke with spaces and Unicode â€” PASS. ID: `reliability.paths`.
- [x] **Automated integration tests using known projects — 3 points.** Evidence: tests/test_engine.py: CLI integration, a real PYZ build, resources and runtime checks; scripts/gui_smoke.py: GUI integration with subprocesses â€” local PASS. ID: `reliability.integration`.
- [ ] **Windows release passes mandatory CI qualification — 2 points.** In progress; points are awarded after the full criterion is met. ID: `reliability.release-gate`.

#### Linux and macOS runners — 4 points

- [x] **Explicit OS and architecture compatibility in build plans — 1 point.** Evidence: tests/test_adapters.py: test_pyinstaller_rejects_cross_os_and_architecture and test_dotnet_windows_desktop_rejects_linux_target â€” PASS; target selection enforces supported build environments. ID: `runners.targets`.
- [x] **Build and run output on a Linux runner — 1 point.** Evidence: Real Linux x86_64 application built with PyInstaller 6.22.3 and run with its resource; scripts/qualify_native.py â€” PASS, docs/VALIDATION.md. ID: `runners.linux`.
- [x] **Implemented remote runner protocol and capability reporting — 1 point.** Evidence: Implemented JSON-lines worker v1 and strict SSH client, capability reporting, build, cancel and hash-verified downloads; tests/test_remote.py real-process integration PASS; docs/REMOTE_WORKER.md. ID: `runners.remote-contract`.
- [x] **Build and run output on a macOS runner — 1 point.** Evidence: GitHub Actions job 117385587229: real macos-arm64 Mach-O, build/resource/smoke and qualification outside the sources with a restricted PATH PASS; archive preserved 4 symlinks, docs/CI.md and docs/ci-evidence.json; https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385587229. ID: `runners.macos`.

#### Extensibility and additional architectures — 2 points

- [x] **Documented and tested contract for an additional adapter — 1 point.** Evidence: Versioned explicit adapter registration with contract validation; additional text adapter built through real engine in tests/test_extensions.py; docs/EXTENSIONS.md. ID: `extensions.adapter-api`.
- [x] **Explicit additional-architecture matrix with target selection tests — 1 point.** Evidence: Explicit OS/CPU matrix and matching-worker, pointer-width, cross-target rejection and .NET RID tests PASS; docs/EXTENSIONS.md and tests/test_extensions.py. ID: `extensions.architectures`.

<!-- MAXKOMPILATOR:PROGRESS:END -->

## Update rules

1. Implement the entire criterion and run the relevant test.
2. Record durable evidence: a test file and outcome, build report, CI run ID, or a target-device test record with its artifact version.
3. Set `status: "complete"` in `docs/progress.json`, fill in `evidence`, and update the `updated` date.
4. Run `python scripts/update_progress.py` and include the generated documentation in the same change.
5. Run `python scripts/update_progress.py --check`; CI must reject inconsistent data or a manually altered percentage.

`in_progress` earns no partial points. If a regression invalidates the evidence, return the criterion to `in_progress` or `pending`; its points are removed. A change to scope or weights requires an explicit revision of the plan. Weights must not be adjusted to inflate completion.

A green CI run proves that its executed jobs passed. Windows, Android and macOS criteria need evidence from the relevant system or device. A mocked tool invocation can test planning; a real build and runtime check are required to qualify an EXE or APK as working.

## Further development after the v1 foundations

| Area | Direction | Status |
|---|---|---|
| Additional languages | C/C++, Rust, Go, Java, Swift and further adapters | Planned |
| Cross-platform applications | Flutter, Electron and Tauri | Planned |
| Extensions | Browsers, VSIX and extensions with their own SDKs | Planned |
| Games | Godot, followed by selected Unity/Unreal integrations | Planned |
| Distribution | MSI, MSIX, AppImage, DEB, RPM, DMG, PKG and signing profiles | Planned |
| Automation | Multi-project queue, environment manager and API/MCP | Planned |

These items do not earn points from the v1 budget. Detailed criteria and weights for the next release will be defined when its scope is agreed.

[Back to README](README.md) · [Architecture](docs/ARCHITECTURE.md)
