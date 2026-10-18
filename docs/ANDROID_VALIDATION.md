# Android debug APK validation (development)

Maxkompilator's Android adapter runs an existing Gradle Wrapper's
`:app:clean :app:assembleDebug` task. A successful Gradle exit code is **not**
accepted as sufficient evidence that an APK is valid.

For every APK copied to the job output, the validator:

1. Binds the copied bytes to the original `app/build/outputs/apk/debug/`
   artifact using SHA-256 and the build report's checksum.
2. Requires the same-directory Android Gradle Plugin `output-metadata.json`
   to identify the exact output file, variant `debug`, package ID and version.
3. Runs the Android SDK's `aapt dump badging` against the copied APK. It verifies
   the compiled manifest package, version code, version name and debuggable
   flag against the Gradle metadata. The package line is captured while
   streaming, even when other manifest lines exceed the normal log tail.
4. Runs the SDK's `apksigner.jar verify --verbose --print-certs` via Java.
   It requires a successful verification **and** a SHA-256 signing certificate
   fingerprint. Both aapt and the signer must come from the same installed
   SDK build-tools version.
5. Records `verified=true` only after all checks pass. The report preserves
   the actual validation commands and their results.

**Real example qualified locally on 2026-10-18:** Gradle compiled the APK,
Android SDK verified its metadata/manifest/signature, and an emulator installed
and launched it twice with the compiled resource marker. A real AAB also passed
bundletool validation and decoded-manifest comparison. See the separate
[integration evidence](INTEGRATION_2026-10-18.md). Unit fixtures remain simulated
and do not supply this compilation evidence. Physical devices and Play Store
release signing have not been qualified.

The current implementation handles the non-flavored `:app:assembleDebug`
variant. Flavor-specific variants will require explicit Gradle task and output
selection rather than silently treating a different variant as debug.

## Debug App Bundle signing inspection

The `:app:clean :app:bundleDebug` build path collects `.aab` files under
`app/build/outputs/bundle/*Debug`. The bundle inspector binds every copied AAB
to its source and the SHA-256 report, checks ZIP member safety and CRCs, and
requires nonempty `BundleConfig.pb` and `base/manifest/AndroidManifest.xml`.
It then checks the archive with the installed JDK's `jarsigner -verify`.

**Unsigned debug AABs are expected to occur.** They are retained as generated
artifacts but carry `verified=false` and `signature_status=unsigned`, rather
than being misreported as signed binaries. A signed JAR must yield an actual
`jar verified.` result, contain no unsigned payload entries, and provide a
signing-certificate SHA-256 from `keytool -printcert -jarfile`. Even when these
checks pass, `signature_verified=true` records only cryptographic JAR signing,
while `verified=false` remains until full Android bundle qualification. The
recorded verification explicitly excludes independently
decoding the protobuf manifest, bundletool validation, installability and
Google Play release signing. Debug signing is *not* a production signature.

The new tests cover malicious/altered and unsigned archives. An additional
integration test uses a real JDK (`keytool` + `jarsigner`) to sign a **synthetic
AAB-shaped ZIP**, verify the signature and reject an appended unsigned entry;
this is cryptographic signing-tool evidence, **not** a Gradle or Android SDK
build. The later local integration record provides the actual Gradle AAB build,
independent bundletool/manifest checks, and the explicit distinction between
its unsigned debug bundle and a production-signed release. Production signing
itself remains unconfigured and unqualified.
