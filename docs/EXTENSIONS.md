# Adapter API v1 and architecture matrix

Applications embedding Maxkompilator can explicitly register trusted adapter
factories with `register_adapter(kind, factory, api_version=1)`. Factories receive
`(Project, target, format, output_dir, python_executable)` and return an immutable
`BuildPlan`. They must preserve the input project and assigned output directory,
declare external `BuildStep` commands and artifact patterns, and leave
`internal_builder=None`. The engine assigns a unique run directory, checks tools,
executes commands, handles cancellation/timeouts, and validates and hashes output.
Planning must not execute project code or write files. A registered factory is
trusted application code, not a security isolation boundary.

Built-in names cannot be replaced. Invalid API versions, names and output
contracts are rejected. `unregister_adapter` removes an extension;
`adapter_kinds` reports registered kinds. No project-local module or entry point
is imported automatically. CLI discovery remains limited to the three built-ins;
embedding applications create an explicit `Project(kind=...)` for their extension.
`tests/test_extensions.py` includes a complete additional text-copy adapter and
executes it through the real engine, checking the artifact and report.

## Target selection

| Family | Python native targets | Managed .NET publish targets |
| --- | --- | --- |
| Windows | x64, x86, arm64 with matching interpreter/worker | win-x64, win-x86, win-arm64 |
| Linux | x64, x86, arm64, arm with matching interpreter/worker | linux-x64, linux-arm64, linux-arm |
| macOS | x64, arm64 with matching interpreter/worker | osx-x64, osx-arm64 |

Python targets require a matching OS, CPU and interpreter pointer width; they
are not cross-compilers. PyInstaller and project dependencies must support that
worker. The table describes selection rules, not a claim that every CPU has been
physically qualified. Actual native CI covers Windows x64, Linux x64 and macOS
arm64. Additional architectures have target-selection and rejection tests.
Managed .NET may publish cross-target output, but runtime tests require the
destination OS/CPU. WinForms/WPF require Windows workers and Windows targets.
NativeAOT, installers and extra language toolchains remain outside v1.

## Exact tool pins

Profiles may contain `[tools]` with string versions: `python` and `pyinstaller`
for Python, `dotnet` for managed .NET, or `java` for Android. Unknown/inapplicable
pins fail planning; mismatches fail environment checks before build commands.
Use `global.json` for .NET SDK selection and a checksum-pinned Gradle wrapper for
Android. Pins check installed tools; they do not install them. Python dependency
locking belongs to the project's build environment.

The portable CI `hello-python-native` profile pins Python 3.12.10 and PyInstaller
6.22.3, matching the official Windows builds available to setup-python. The
earlier local qualification used an explicit Python 3.12.14 pin and remains
recorded with that environment. Repeated qualification uses the same interpreter, dependencies,
`PYTHONHASHSEED=0` and `SOURCE_DATE_EPOCH=1792252800`, and compares every payload
SHA-256 while excluding per-run reports and paths. This is a measured guarantee
for that fixture/environment, not universal reproducible builds for arbitrary code.
