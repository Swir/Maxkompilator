# GitHub Actions qualification

The v1 workflow has 15 required jobs: six engine matrix jobs, three native Python
builds, the packaged Windows GUI, two .NET builds, Android APK/AAB with bundletool,
Windows profiles with Python-free execution, and the mandatory aggregate gate.

**Version 1.0.0: all 15 jobs SUCCESS** in [run 39152793026](https://github.com/Swir/Maxkompilator/actions/runs/39152793026)
for source commit `c39e1f1f3cc32d41a01d57aead1ae88158e3a009`. The final documentation-only commit records
these results without changing the qualified application source.

| Job | Result | Evidence |
|---|---|---|
| Core / ubuntu-latest / Python 3.13 | SUCCESS | [Job 117749692797](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749692797) |
| Core / macos-latest / Python 3.11 | SUCCESS | [Job 117749692971](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749692971) |
| Core / windows-latest / Python 3.13 | SUCCESS | [Job 117749693030](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749693030) |
| Core / ubuntu-latest / Python 3.11 | SUCCESS | [Job 117749693079](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749693079) |
| Core / windows-latest / Python 3.11 | SUCCESS | [Job 117749693087](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749693087) |
| Core / macos-latest / Python 3.13 | SUCCESS | [Job 117749693097](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749693097) |
| Native Python / windows-latest | SUCCESS | [Job 117749927338](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749927338) |
| Windows desktop bundle | SUCCESS | [Job 117749927385](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749927385) |
| Real .NET publish and runtime / windows-latest | SUCCESS | [Job 117749927390](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749927390) |
| Real .NET publish and runtime / ubuntu-latest | SUCCESS | [Job 117749927399](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749927399) |
| Native Python / ubuntu-latest | SUCCESS | [Job 117749927410](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749927410) |
| Real Android APK and AAB | SUCCESS | [Job 117749927412](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749927412) |
| Native Python / macos-latest | SUCCESS | [Job 117749927413](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749927413) |
| Windows profiles and Python-free runtime | SUCCESS | [Job 117749927467](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117749927467) |
| Mandatory release qualification | SUCCESS | [Job 117750831160](https://github.com/Swir/Maxkompilator/actions/runs/39152793026/job/117750831160) |

The complete run metadata is preserved in
`evidence/windows-2026-10-18/ci-release-v1.json`. Earlier failed runs exposed real
portability issues in temporary paths, JDK Unicode paths and Android SDK output;
the corrected source passed the complete matrix. Python-free Windows execution
also passed in the earlier dedicated job 117747360918, whose downloaded evidence
is preserved under `evidence/windows-2026-10-18/ci-profile/`.

[Release qualification](RELEASE_1.0.md) records local package, interactive desktop,
Android emulator and actual compiled-artifact evidence. The following dev2 record
is historical and is not the v1 download recommendation.

## Historical 0.1.0.dev2 qualification

**Verified on 2026-10-17: 10/10 jobs SUCCESS.** This record covers [run 39034556183](https://github.com/Swir/Maxkompilator/actions/runs/39034556183) in [Swir/Maxkompilator](https://github.com/Swir/Maxkompilator), at commit [`044e32bebc13e87cf147868e497a2096ab2709f6`](https://github.com/Swir/Maxkompilator/commit/044e32bebc13e87cf147868e497a2096ab2709f6).

The actual packaged Windows GUI passed **10/10 checks on each of two independent launches**, including its compiled CLI worker, readable interface text, a real PYZ build, cancellation and reopening. Both downloaded captures were also reviewed for readable labels, Polish characters, build output and the 3D icon. Full job metadata, artifact metadata, process evidence, font checks and report hashes are stored in [ci-evidence-dev2.json](ci-evidence-dev2.json).

## Verified jobs

| Job and environment | Result | Evidence |
|---|---|---|
| Engine: Linux, Python 3.11 | SUCCESS | [Job 117401655572](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401655572) |
| Engine: Linux, Python 3.13 | SUCCESS | [Job 117401655649](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401655649) |
| Engine: Windows, Python 3.11 | SUCCESS | [Job 117401655618](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401655618) |
| Engine: Windows, Python 3.13 | SUCCESS | [Job 117401655596](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401655596) |
| Engine: macOS, Python 3.11 | SUCCESS | [Job 117401655670](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401655670) |
| Engine: macOS, Python 3.13 | SUCCESS | [Job 117401655386](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401655386) |
| Native Python: Windows x64 | SUCCESS | [Job 117401756250](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401756250) |
| Native Python: Linux x64 | SUCCESS | [Job 117401756274](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401756274) |
| Native Python: macOS ARM64 | SUCCESS | [Job 117401756296](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401756296) |
| Windows application and packaged GUI qualification | SUCCESS | [Job 117401756236](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401756236) |

Each Core job installs the package, runs the engine and integration suite, checks generated roadmap consistency, and builds and runs a real PYZ with its resource. Skipped tests are tracked separately in each job's logs. The local Linux **84/84 without skips** record has its own environment and timing in [VALIDATION.md](VALIDATION.md); its exact counters are not assigned to every CI platform.

## Actual packaged Windows GUI

[Desktop job 117401756236](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401756236) built `Maxkompilator.exe`, `MaxkompilatorCLI.exe` and their shared runtime. The driver verified that both executables are **PE x64**, with the appropriate Windows GUI and console subsystems. It relocated the complete bundle to a path containing spaces and Unicode outside the checkout, removed `PYTHONPATH` and `PYTHONHOME`, and launched it from an unrelated working directory.

The driver then started the real `Maxkompilator.exe` twice. The second run was a new process after the first window had closed:

| Launch | GUI PID | Checks | Compiled workers | Driver launch duration | GUI scenario duration | Cancellation | GUI exit |
|---|---:|---|---:|---:|---:|---:|---:|
| First launch | 3492 | 10/10 PASS | 5 | 2.265 s | 1.313 s | 0.157 s | 0 |
| Independent reopening | 1524 | 10/10 PASS | 5 | 1.328 s | 1.188 s | 0.125 s | 0 |

The complete driver qualification took **3.875 s**. Driver durations include process startup; GUI scenario timings come from the in-application reports. Each launch used five verified `MaxkompilatorCLI.exe` processes for inspect, plan, doctor, a successful build and a cancelled build, with exit codes **`0`, `0`, `0`, `0`, `130`**. Both windows closed successfully.

The ten check groups cover frozen module and worker origins, window controls and icon, readable text, automatic project detection and planning with Unicode paths, environment diagnostics, a real PYZ/resource/runtime check and persisted report, output-folder and log actions, cancellation, descendant termination, and confirmation that every task used the compiled worker. Process image paths and imported-module origins are included in the JSON evidence.

### Readable text and captures

The Windows offscreen backend registers the runner's available system fonts before qualification. Every launch checked a **96-character sample across 17 interface font roles**, covering Latin letters, digits, Polish characters and punctuation. The actual fonts resolved to **Segoe UI Regular and Bold**, with no missing glyphs or metrics. The check runs before the build workflow and fails qualification when text cannot be rendered.

The qualification artifact was downloaded and its SHA-256 verified. Both `first-launch.png` and `reopened.png` were inspected: labels, fields, buttons, summary and logs are readable, including Polish text. The actual reopened Windows screenshot is retained as [images/gui-windows.png](images/gui-windows.png), with SHA-256 `790de62a937aec74c151d0209ee12508ac93dee5306e9a0c818273476bee0728`.

This is automated **Qt offscreen** execution of the real Windows binaries, plus review of their diagnostic captures. It is not a manual interactive Windows 11 session. The hosted runner has Python installed for the generated PYZ, so qualification on a clean Windows machine without Python remains open.

### Source GUI and packaged-file checks

The Windows source GUI passed **8/8 groups in 1.312 s**, with cancellation in **0.156 s**. Its result is separate from the two packaged launches above. The job also ran the packaged console worker directly and built a real PYZ with a successful runtime test through that worker, then built wheel/sdist distributions.

The packaged PNG is **512 × 512**, **334,341 bytes**, and matches the project icon with SHA-256 `03ee456da8263cf1ed476a05c60d719948aaf41f8d81316798b73717893f381a`. Executable checksums for this build:

- `Maxkompilator.exe`: `f22bd878b9771861a9d836b15b0ed92e22bac7a4d1c7812409dc82f2995dcd97`.
- `MaxkompilatorCLI.exe`: `4f64d3023e5979735b7662347494d2f5db0014cda6c8d20d6218aae2ff5e3dc0`.

Keep the complete application directory, including `_internal`. The executable checksums identify the tested entry points; their runtime files remain part of the distribution.

## Native example qualification

All three native examples passed real builds, resource checks, execution outside the source directory and archive validation:

| Target | Detected format | Build/resource/runtime/archive | Symlinks preserved | Evidence |
|---|---|---|---:|---|
| `win-x64` | `pe-x64` | PASS | 0 | [Job 117401756250](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401756250) |
| `linux-x64` | `elf-x64` | PASS | 0 | [Job 117401756274](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401756274) |
| `macos-arm64` | `mach-o` | PASS | 4 | [Job 117401756296](https://github.com/Swir/Maxkompilator/actions/runs/39034556183/job/117401756296) |

`scripts/qualify_native.py` verifies checksums and runs the output with `PYTHONPATH`/`PYTHONHOME` removed and a restricted `PATH`. It creates `native-example-TARGET.tar.gz` with the complete application, build report and qualification report, then checks archive membership, symbolic links, applicable POSIX permissions and checksums. The macOS archive preserves four symlinks. Exact executable and archive hashes are in [ci-evidence-dev2.json](ci-evidence-dev2.json).

These results qualify the example on the stated CI runners. Those runners have Python installed. They do not complete application icon profiles, a clean Windows machine without Python, Android SDK/device testing or real .NET publishing.

## Download the Windows development application

Open **Actions → [run 39034556183](https://github.com/Swir/Maxkompilator/actions/runs/39034556183) → Artifacts → `Maxkompilator-Windows-x64-dev`**. Extract the entire archive, open `dist/Maxkompilator`, and launch `Maxkompilator.exe`. Keep `MaxkompilatorCLI.exe` and `_internal` in the same folder.

The application artifact is **56,049,987 bytes, approximately 53.5 MiB**, ID **12101593136**, with retention until **2026-10-31 at 12:59:08 UTC**. Its GitHub-reported digest is `sha256:660148c4b83a6b9023ba408e71f2c7335a13215804bf6b28546ee14992a1f374`.

| Artifact | Contents | Artifact ID | GitHub-reported size |
|---|---|---:|---:|
| `Maxkompilator-Windows-x64-dev` | The application: both Windows EXEs and runtime; also wheel/sdist and qualification output | 12101593136 | 56,049,987 bytes |
| `Maxkompilator-Windows-GUI-qualification` | Small evidence package: reports and diagnostic captures; no application runtime | 12101229870 | 237,637 bytes |
| `native-example-windows-latest` | Example Windows application built by Maxkompilator | 12101991267 | 7,993,068 bytes |
| `native-example-ubuntu-latest` | Example Linux application built by Maxkompilator | 12101886672 | 19,842,106 bytes |
| `native-example-macos-latest` | Example macOS application built by Maxkompilator | 12101279103 | 7,216,173 bytes |

`Maxkompilator-Windows-GUI-qualification` is the small evidence package. To run Maxkompilator, download `Maxkompilator-Windows-x64-dev`. Artifact sizes and digests above refer to the GitHub service archives; inner native `.tar.gz` files have separate checksums in their reports.

## Roadmap acceptance

This verified run completes **`gui.windows-test` for 3 points**, bringing the fixed v1 score from **55% to 58%**. Every other criterion weight and status remains unchanged. [ROADMAP.md](../ROADMAP.md) is generated from [progress.json](progress.json).

The separate Windows-without-Python and manual interactive release gates remain open. So do real Android APK/AAB and device qualification, .NET publishing/runtime checks, and icon profiles for applications built by Maxkompilator. The application's refreshed branding does not award those points.

## Earlier records

The `0.1.0.dev1` [run 39028988975](https://github.com/Swir/Maxkompilator/actions/runs/39028988975), at commit `aea4aa811f139edab7b167ab86f1518a283a7302`, passed its ten jobs and established the previous **55%** baseline. It covered source GUI, native examples and a packaged console worker. Its exact job and artifact records remain in [ci-evidence.json](ci-evidence.json), with historical local results in [VALIDATION.md](VALIDATION.md).

An earlier dev2 run, **39033408370**, passed the functional workflow but produced missing-glyph boxes in Windows offscreen captures. That result did not complete the GUI criterion. The current run includes the corrected font setup, a mandatory glyph gate, fresh process reports and visually reviewed readable captures; the superseded finding is preserved in [ci-evidence-dev2.json](ci-evidence-dev2.json).

[Local validation and evidence boundaries](VALIDATION.md) · [Roadmap](../ROADMAP.md) · [Visual identity](DESIGN.md)
