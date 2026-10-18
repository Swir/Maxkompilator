# Android integration example

A small Java activity reads a compiled string resource, displays it and writes
`MAXKOMPILATOR_ANDROID_RUNTIME_OK` to logcat. It requests no Android permissions.

The example pins Android Gradle Plugin 8.9.2, Gradle 8.11.1 (with a distribution
SHA-256), JDK 17, compile/target SDK 35 and build-tools 35.0.0. This combination
follows the [AGP 8.9 compatibility table](https://developer.android.com/build/releases/agp-8-9-0-release-notes).
Set `ANDROID_HOME` to an SDK with these platform and build-tools packages.

From the repository root:

```sh
python -m maxkompilator build examples/hello-android --kind android --target android --format apk --json
python -m maxkompilator build examples/hello-android --kind android --target android --format aab --output dist/aab --json
python scripts/qualify_android.py --apk-report examples/hello-android/dist/maxkompilator/build-report.json --aab-report examples/hello-android/dist/aab/build-report.json --bundletool /path/to/bundletool-all-1.18.2.jar --output build/android-qualification.json
```

`qualify_android.py` calls the real Google bundletool to validate the AAB and
decode its manifest, then compares package, version and debug state with the
verified APK. Add `--serial emulator-5554` only when intending to install the
APK on that particular emulator/device and test two independent app launches.
The device must have completed boot; `--adb` and `--java` accept tool paths.
No device is selected or modified without `--serial`.

APK builds use Android's development debug key. The actual Gradle 8.9.2 debug
AAB is unsigned; the engine reports that state explicitly. Bundle validation
does not turn an unsigned AAB into a signed release. No production signing key
or Play Store publication is configured. Keep the copied APK and AAB under
their separate output directories: the next Gradle job cleans `app/build`.
