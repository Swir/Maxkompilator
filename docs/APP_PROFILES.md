# Project-owned application profiles (development)

Maxkompilator reads `maxkompilator.toml` from the selected project's root. The
following `[app]` metadata is implemented for **.NET and Python native builds** in
this development change:

```toml
[app]
name = "BrightDemo"
version = "1.2.3"
icon = "branding/app.ico"
```

- `name` overrides the published .NET assembly name using
  `-p:AssemblyName=BrightDemo`. It must be a safe, single filename component.
- `version` is passed to `dotnet publish` as `-p:Version=1.2.3`. Numeric
  components are bounded; prerelease versions such as `1.2.3-beta.1` are
  accepted.
- `icon` is project-relative and may not escape the source directory through
  symlinks or traversal. Windows `win-*` targets require an `.ico` file.
  Managed .NET publish currently rejects the `icon` setting for both Linux
  and macOS targets because it cannot guarantee a native embedded icon there.
- Python native builds use `name` for the PyInstaller executable name, and
  `icon` for `.ico` (Windows) or `.icns` (macOS). Linux icon embedding is
  deliberately rejected rather than claiming an icon was added.
- On Windows, `[app].version` creates a validated PyInstaller `VSVersionInfo`
  resource as a separate build step, outside the directory cleared by
  PyInstaller `--clean`; plans do not create files. Python native version
  resources on other targets are not yet implemented.
- Python zipapps may override the output name but cannot embed an icon or
  version resource. Explicit attempts are rejected.
- Missing `[app]` settings preserve existing project defaults. Reading this
  profile is read-only; it does not start compilers or write output files.
- For Python builds, `[python].data` continues to define bundled resources.
  Android manifest, package icons and bundle verification remain pending.

## Qualification limits

The checked tests verify profile parsing, rejected unsafe inputs and the
commands prepared for `dotnet publish` and PyInstaller. A real SDK build, examination of
version and icon resources in the output, and a native application launch are
required before the corresponding roadmap item can be marked complete.

Never use a template or a unit-test fixture as evidence that a production
binary has been compiled. Store target-specific evidence with the build report.
