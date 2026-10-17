# GitHub Actions results

## Current 0.1.0.dev2 gate — pending

The new Windows qualification gate exercises the actual packaged `Maxkompilator.exe` and its packaged CLI worker, including the complete GUI workflow, closing and reopening. **Its Windows CI result has not yet been verified.** Local source and installed-wheel checks for `0.1.0.dev2` are recorded in [VALIDATION.md](VALIDATION.md) and [validation-dev2.json](validation-dev2.json).

The pending gate does not yet earn the three points for `gui.windows-test`. The successful jobs and downloadable artifact below belong to the earlier `0.1.0.dev1` baseline.

## Recorded baseline — 0.1.0.dev1

**Repository:** [Swir/Maxkompilator](https://github.com/Swir/Maxkompilator). **Recorded baseline version:** `0.1.0.dev1`.

This record covers [run 39028988975](https://github.com/Swir/Maxkompilator/actions/runs/39028988975) at commit [`aea4aa811f139edab7b167ab86f1518a283a7302`](https://github.com/Swir/Maxkompilator/commit/aea4aa811f139edab7b167ab86f1518a283a7302), checked on 2026-10-17. A later commit or rerun needs a separate review of its results.

**Entire run: SUCCESS — 10/10 jobs.** The job list, metadata for four artifacts and inspected results are stored in [ci-evidence.json](ci-evidence.json).

### Engine: six verified Core jobs

**6/6 Core jobs completed with SUCCESS.** Each installs the package, runs tests, checks README/ROADMAP progress consistency and builds a real PYZ with its resource and runtime test.

| Environment | Python | Result | Evidence |
|---|---|---|---|
| Linux — `ubuntu-latest` | 3.11 | SUCCESS | [Job 117385484411](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484411) |
| Linux — `ubuntu-latest` | 3.13 | SUCCESS | [Job 117385484154](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484154) |
| Windows — `windows-latest` | 3.11 | SUCCESS | [Job 117385484444](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484444) |
| Windows — `windows-latest` | 3.13 | SUCCESS | [Job 117385484391](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484391) |
| macOS — `macos-latest` | 3.11 | SUCCESS | [Job 117385484318](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484318) |
| macOS — `macos-latest` | 3.13 | SUCCESS | [Job 117385484353](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484353) |

The local **84/84 PASS without skips** result comes from Linux x86_64/Python 3.12.14. Each CI platform has its own executed-case count. `unittest` reports discovered tests and a separate skip count; `skipped` does not mean the scenario passed on that platform.

The POSIX process-group regression is skipped on Windows, and the frozen Linux library-environment integration is skipped on Windows and macOS. Symlink tests may be skipped if the runner cannot create links. Each job's **Unit and integration tests** step contains the exact result.

The inspected detailed Core logs use **Python 3.11**:

| Environment | Discovered | Passed | Skipped | Duration |
|---|---:|---:|---:|---:|
| Linux | 84 | 84 | 0 | 1.773 s |
| macOS | 84 | 83 | 1 | 2.654 s |
| Windows | 84 | 82 | 2 | 3.437 s |

SUCCESS was also verified for all three Python 3.13 jobs. Their detailed timings and skip counts are not represented by this table.

### Native jobs and Windows bundle

These jobs run after Core. Their status and evidence are assessed independently of the six engine jobs.

| Job | Result and tested target | Link |
|---|---|---|
| Native Python — macOS | SUCCESS; `macos-arm64`, Mach-O, build/resource/smoke/archive | [Job 117385587229](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385587229) |
| Native Python — Windows | SUCCESS; `win-x64`, PE x64, build/resource/smoke/archive | [Job 117385587290](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385587290) |
| Native Python — Linux | SUCCESS; `linux-x64`, ELF x64, build/resource/smoke/archive | [Job 117385587311](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385587311) |
| Windows desktop bundle | SUCCESS; source GUI, real EXE bundle and packaged CLI building a PYZ | [Job 117385587321](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385587321) |

#### Native qualification

The job builds `examples/hello-python` with PyInstaller, runs the application and checks its bundled resource. `scripts/qualify_native.py` compares SHA-256 and executes the output outside the sources with `PYTHONPATH`/`PYTHONHOME` removed and `PATH` restricted to system directories.

It then creates `native-example-TARGET.tar.gz`. The script reopens the archive and checks complete membership, symlink types and targets, POSIX permissions, and checksums of the executable and reports. The archive preserves permissions and symlinks when downloaded through the CI artifact service. It is a development package.

All three qualifications passed. The macOS archive preserved **4 symbolic links**. Tested executable checksums:

- macOS ARM64: `47d2993aaebf1673e81af616c23c819a01286d70c775c8a0edefbcdbe5e75cd7`.
- Windows x64: `e9a87d7f865745f02aeca29cb6a7a98333b2692085113833218fa0a5b14222cd`.
- Linux x64: `8a01e5e291672c832843561376381864bbc2c37a06b6ce60b375ab192458713d`.

**The CI runner still has Python installed.** Restricted `PATH` and environment variables provide a concrete independence check, while qualification on a clean machine without Python remains a separate requirement.

#### Windows desktop bundle qualification

Verified steps:

1. Source PySide6 GUI in offscreen mode: **7/7 groups PASS in 1.422 s**, using the real CLI, a PYZ build, resource checks and cancellation in **0.156 s**; descendant termination was confirmed.
2. Distribution folder containing `Maxkompilator.exe`, `MaxkompilatorCLI.exe` and `_internal`: **built successfully**.
3. Packaged console worker: **PASS** for project detection, a real PYZ build and execution of the result.
4. Wheel/sdist build and artifact upload: **PASS**.

These steps qualify the operations described above. At this baseline, the complete built `Maxkompilator.exe` workflow, including window operations, closing and reopening, was still pending. That scenario and the separate machine without Python have distinct roadmap criteria.

### Download the recorded Windows development build

Open **Actions → [run 39028988975](https://github.com/Swir/Maxkompilator/actions/runs/39028988975) → Artifacts → `Maxkompilator-Windows-x64-dev`**. Extract the entire archive, open `dist/Maxkompilator`, and launch `Maxkompilator.exe`. Keep `MaxkompilatorCLI.exe` and `_internal` in the same folder.

| Artifact | Contents | GitHub-reported size |
|---|---|---:|
| `Maxkompilator-Windows-x64-dev` | Windows Maxkompilator tool, both EXEs and runtime; also wheel/sdist and GUI test screenshot | 54,090,240 bytes, approximately 51.6 MiB |
| `native-example-windows-latest` | Example Windows application built by Maxkompilator | 7,995,708 bytes |
| `native-example-ubuntu-latest` | Example Linux application built by Maxkompilator | 19,841,977 bytes |
| `native-example-macos-latest` | Example macOS application built by Maxkompilator | 7,217,509 bytes |

The tool artifact ID is **12099418546**. GitHub reports retention until **2026-10-31 at 11:32:45 UTC** and digest `sha256:4c7d50f97276e9a94551e0e565ccca5c4cd654b68fc80355808fd2b0a16d4af2`. The table's sizes and this digest refer to GitHub service artifacts. Internal `native-example-TARGET.tar.gz` files have their own sizes and checksums in their qualification reports.

### Relationship to roadmap progress

The six successful Core jobs completed `foundation.ci` for **2 points**. The real macOS ARM64 build and runtime check completed `runners.macos` for **1 point**, bringing the recorded baseline to **55%**. The current score is generated in [ROADMAP.md](../ROADMAP.md). Further points require the complete criterion: recipe tests do not qualify real APK/.NET output, and the packaged console worker does not qualify the full Windows GUI workflow.

[Local validation and evidence boundaries](VALIDATION.md) · [Roadmap](../ROADMAP.md)
