# Handoff integration and real toolchain evidence

Checked locally on Windows x64 on 18 October 2026. This is an integrated
development candidate, not a new release or a claim of successful candidate CI.

## Source continuity

Both remote branches were read at `989b9ba773f5a07686a5143ba0c141c2a6c8151d`.
The work used a fresh checkout of that repository; no existing checkout was
reset. All six payload files matched the handoff manifest. The original patches
remain unchanged in the transfer directory. They were integrated in v6, v7, v8 order.

v6 applied normally. The v7 engine diff had been produced from excerpts: its
line offsets and extra blank lines at excerpt boundaries did not match the
full engine. Six hunks were reconciled using exact, unique source context,
trimming only blank context at hunk boundaries. No changed lines were discarded.
v8 needed one missing blank context line at the end of ANDROID_VALIDATION.md;
its code hunks then applied normally. The complete repository was tested after
these adjustments. A test's assumed absent JAVA_HOME was made explicit so it
does not depend on the developer's machine configuration.

The original multicolor 3D icon is unchanged. Both source and packaged PNG
copies have SHA-256 `03ee456da8263cf1ed476a05c60d719948aaf41f8d81316798b73717893f381a`.
No schedule was created or resumed. No GitHub write was attempted.

## Actual results

| Check | Result | Evidence |
|---|---|---|
| Full unit/integration suite | 184 run, 180 passed, 4 platform-specific skips | [suite log](evidence/windows-2026-10-18/unittest.log) |
| .NET publish | Real net8.0 C# app, .NET SDK 10.0.402, win-x64, self-contained | [build report](evidence/windows-2026-10-18/dotnet-build-report.json) |
| .NET native runtime | Complete 188-file tree copied outside sources; matching hashes, PE x64 host, runtime DLLs, resource and success marker | [qualification](evidence/windows-2026-10-18/dotnet-qualification.json) |
| APK | Real AGP 8.9.2 / Gradle 8.11.1 / JDK 17.0.20 build; manifest/package/version/debug state, SHA-256 and signer verified with SDK tools | [APK report](evidence/windows-2026-10-18/apk-build-report.json) |
| AAB | Real debug bundle; unsigned state correctly reported; bundletool 1.18.2 validates and decodes matching package/version/debug manifest | [AAB report](evidence/windows-2026-10-18/aab-build-report.json), [independent qualification](evidence/windows-2026-10-18/android-qualification.json) |
| Device runtime | APK installed on x86_64 Android API 36 emulator (36.1 image), two new app PIDs, compiled-resource marker from each | [device commands and output](evidence/windows-2026-10-18/android-qualification.json) |

The initial sandbox run could not resolve its own temporary directories or
stop test children reliably. The successful suite ran with normal Windows
permissions and temporary files under the workspace. The first .NET build
reported missing NuGet sources; the example now explicitly uses nuget.org in
its own NuGet.Config. No machine-wide package sources were changed.

The emulator used a separate data directory, no snapshot persistence and
read-only mode. No existing user application was replaced; the fixture has
its own package ID and requests no Android permissions.

## Reproduce

Run the standard unittest and progress checks from README. For .NET:

```sh
python -m maxkompilator build examples/hello-dotnet --kind dotnet --target native --format directory --smoke-test --json
python scripts/qualify_dotnet.py examples/hello-dotnet/dist/maxkompilator/build-report.json
```

Install the package first (`python -m pip install .`) so standalone qualification
scripts can import it. The [Android example instructions](../examples/hello-android/README.md)
provide the real APK/AAB and optional explicitly selected device commands.

## Acceptance and boundaries

These results complete the existing criteria `dotnet.publish` (4),
`dotnet.windows-runtime` (4), `android.apk` (4), `android.device` (5) and
`android.aab` (3): 20 additional points, 78/100 for this local candidate.
The AAB criterion is an actual bundle plus an explicit debug/release signing
distinction; the unsigned debug bundle is not a production-signed artifact.
No weights or criterion definitions changed. The last remote source remains
the 58-point baseline until synchronization and exact-commit CI are completed.

Still open: clean Windows without Python; complete Python icon/version output
qualification; profile repeatability; .NET WPF/WinForms dependency/distribution
qualification; manual Windows release review; remote runner/adapter extensions;
production Android signing and store delivery. The newly integrated GUI was
not repackaged or manually reviewed in this run, and the Android app is a
small integration example rather than a mobile Maxkompilator product.
