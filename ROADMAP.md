# Roadmapa Maxkompilatora

**Wersja v1 ma stały budżet 100 punktów.** Każdy etap dzieli się na kryteria o jawnej wadze; punkty otrzymuje wyłącznie ukończone kryterium ze wskazanym dowodem. Liczba plików, commitów ani przygotowanych planów nie zastępuje testu rzeczywistej funkcji.

Zakres v1: wspólny silnik CLI i GUI, lokalne budowanie Python/Windows, Android i .NET, kwalifikacja rzeczywistych wyników oraz pierwsza obsługa wykonawców Linux/macOS. Kryteria zdalnych wykonawców pozostają planowane do czasu wdrożenia i rzeczywistego sprawdzenia ich działania.

**100% oznacza ukończenie tej listy v1, nie obsługę wszystkich języków świata.** Wagi odzwierciedlają ustalony zakres produktu; nie stanowią prognozy czasu. Zamknięcie większej liczby łatwych zadań nie zwiększa punktacji trudniejszych etapów.

Potwierdzone lokalnie: rozpoznawanie i planowanie trzech technologii, rzeczywiste PYZ i natywne wydanie Linux, podstawowa konfiguracja i raporty, integracja CLI/GUI, anulowanie oraz instalowalny wheel. [Raport walidacji](docs/VALIDATION.md) rozdziela te dowody od przygotowanych recept Android/.NET i oczekującej kwalifikacji Windows/macOS.

## Bieżący postęp

<!-- MAXKOMPILATOR:PROGRESS:START -->

**Postęp v1.0: 52% — 52 / 100 pkt.**

Wynik obejmuje wyłącznie ukończone kryteria z dowodem. Prace w toku nie zwiększają procentu.

| Etap | Waga v1 | Ukończono | Postęp etapu |
|---|---:|---:|---:|
| Fundament projektu i CI | 8 pkt | 6 / 8 pkt | 75% |
| Rozpoznawanie projektu i środowiska | 12 pkt | 12 / 12 pkt | 100% |
| Python i wydania Windows | 16 pkt | 6 / 16 pkt | 37,5% |
| Android: APK i AAB | 14 pkt | 2 / 14 pkt | 14,3% |
| .NET i publikacje Windows | 12 pkt | 2 / 12 pkt | 16,7% |
| Interfejs desktopowy | 12 pkt | 9 / 12 pkt | 75% |
| Profile i powtarzalność wyników | 10 pkt | 5 / 10 pkt | 50% |
| Niezawodność i kwalifikacja wydań | 10 pkt | 8 / 10 pkt | 80% |
| Wykonawcy Linux i macOS | 4 pkt | 2 / 4 pkt | 50% |
| Rozszerzalność i kolejne architektury | 2 pkt | 0 / 2 pkt | 0% |
| **Łącznie** | **100 pkt** | **52 / 100 pkt** | **52%** |

Źródło: [docs/progress.json](docs/progress.json) · aktualizacja danych: **2026-10-17**.

### Kryteria i dowody

#### Fundament projektu i CI — 8 pkt

- [x] **Zakres v1, instrukcje i mierzalne kryteria ukończenia — 2 pkt.** Dowód: README.md i ROADMAP.md: opis zakresu, ograniczeń oraz stałych wag v1. Identyfikator: `foundation.scope`.
- [x] **Podział silnika, adapterów i wykonawców — 2 pkt.** Dowód: docs/ARCHITECTURE.md: przepływ zadania, granice odpowiedzialności i model wyników. Identyfikator: `foundation.architecture`.
- [x] **Instalowalny pakiet i działające wejście CLI — 2 pkt.** Dowód: Wheel i sdist zbudowane; wheel zainstalowany bez indeksu i zależności poza repo, CLI/SVG/PYZ z zasobem oraz smoke PASS — docs/VALIDATION.md i docs/validation-local.json. Identyfikator: `foundation.package`.
- [ ] **Uruchomiony CI z kontrolą jakości i zgodności postępu — 2 pkt.** W toku; punkty zostaną naliczone po spełnieniu kryterium. Identyfikator: `foundation.ci`.

#### Rozpoznawanie projektu i środowiska — 12 pkt

- [x] **Rozpoznawanie projektów Python, Android i .NET — 3 pkt.** Dowód: tests/test_detection.py: rozpoznanie skryptów, projektu Python, Androida i konkretnych csproj; lokalny zestaw PASS — docs/VALIDATION.md. Identyfikator: `discovery.detection`.
- [x] **Jawny wybór typu i punktu startowego przy niejednoznaczności — 3 pkt.** Dowód: tests/test_detection.py: test_multiple_python_scripts_need_explicit_entry, test_mixed_directory_requires_explicit_kind, test_multiple_csprojects_require_concrete_project_path — PASS. Identyfikator: `discovery.ambiguity`.
- [x] **Diagnostyka wymaganych narzędzi z użytecznym opisem braków — 3 pkt.** Dowód: tests/test_engine.py: test_missing_tool_yields_failed_report_without_build; scripts/gui_smoke.py: environment_doctor_and_smoke_flag_scoping — lokalnie PASS. Identyfikator: `discovery.doctor`.
- [x] **Plan budowania dostępny w CLI i JSON bez uruchamiania kompilacji — 3 pkt.** Dowód: tests/test_engine.py: test_inspect_and_plan_are_read_only_and_json_is_parseable; tests/test_adapters.py: test_pyinstaller_plan_is_native_structured_and_has_no_side_effects — PASS. Identyfikator: `discovery.plan`.

#### Python i wydania Windows — 16 pkt

- [x] **Rzeczywista budowa PYZ i test uruchomienia prostego projektu — 4 pkt.** Dowód: tests/test_engine.py: test_zipapp_builds_and_runs_with_resources_outside_source; rzeczywisty examples/hello-python PYZ + smoke PASS na Linux — docs/VALIDATION.md. Identyfikator: `python.zipapp`.
- [x] **Adapter natywnego budowania przez PyInstaller — 2 pkt.** Dowód: maxkompilator/adapters/python_adapter.py oraz rzeczywista budowa i uruchomienie przykładu przez PyInstaller 6.22.3 na Linux — docs/VALIDATION.md. Identyfikator: `python.pyinstaller`.
- [ ] **Rzeczywisty EXE z poprawnym formatem, zasobami i ikoną — 5 pkt.** W toku; punkty zostaną naliczone po spełnieniu kryterium. Identyfikator: `python.exe`.
- [ ] **Uruchomienie zbudowanego EXE na Windows bez instalowania Pythona — 5 pkt.** W toku; punkty zostaną naliczone po spełnieniu kryterium. Identyfikator: `python.windows-runtime`.

#### Android: APK i AAB — 14 pkt

- [x] **Recepty Gradle dla debug APK/AAB i obsługa projektu z wrapperem — 2 pkt.** Dowód: tests/test_adapters.py: test_android_debug_apk_plan_does_not_execute_wrapper i test_android_artifact_patterns_select_only_debug_outputs — PASS; przygotowano recepty, bez kwalifikacji rzeczywistego APK/AAB. Identyfikator: `android.gradle`.
- [ ] **Rzeczywisty APK: manifest, pakiet, wariant i kontrola podpisu — 4 pkt.** W toku; punkty zostaną naliczone po spełnieniu kryterium. Identyfikator: `android.apk`.
- [ ] **Instalacja i uruchomienie APK na emulatorze lub telefonie — 5 pkt.** Planowane. Identyfikator: `android.device`.
- [ ] **Rzeczywisty AAB oraz wyraźne rozdzielenie podpisów debug/release — 3 pkt.** Planowane. Identyfikator: `android.aab`.

#### .NET i publikacje Windows — 12 pkt

- [x] **Adapter dotnet publish z właściwym projektem i celem — 2 pkt.** Dowód: tests/test_adapters.py: test_dotnet_publish_includes_runtime_and_concrete_project oraz ograniczenia WPF/NativeAOT — PASS; sprawdzona recepta bez rzeczywistej publikacji SDK .NET. Identyfikator: `dotnet.recipe`.
- [ ] **Rzeczywista publikacja projektu .NET i sprawdzenie wyników — 4 pkt.** Planowane. Identyfikator: `dotnet.publish`.
- [ ] **Uruchomienie opublikowanej aplikacji na Windows — 4 pkt.** Planowane. Identyfikator: `dotnet.windows-runtime`.
- [ ] **Weryfikacja zależności aplikacji desktopowej i trybu dystrybucji — 2 pkt.** Planowane. Identyfikator: `dotnet.desktop`.

#### Interfejs desktopowy — 12 pkt

- [x] **Ciemny interfejs, własna ikona i oznaczenie by Swir — 3 pkt.** Dowód: maxkompilator/gui.py, assets/maxkompilator.svg; scripts/gui_smoke.py: initial_window_icon_and_controls — PASS na Linux z Qt 6.12 offscreen. Identyfikator: `gui.design`.
- [x] **Wybór projektu, diagnostyka, plan i budowanie z GUI — 3 pkt.** Dowód: scripts/gui_smoke.py: inspect_and_plan_unicode_path_auto_defaults, environment_doctor_and_smoke_flag_scoping, zipapp_build_real_runtime_and_persisted_report — PASS na Linux. Identyfikator: `gui.workflow`.
- [x] **Responsywne logi, praca w tle i anulowanie zadania — 3 pkt.** Dowód: scripts/gui_smoke.py: open_results_and_copy_log_buttons, cancel_button_stops_running_build, cancelled_worker_and_descendant_are_stopped — PASS na Linux. Identyfikator: `gui.responsiveness`.
- [ ] **Test pełnej ścieżki GUI i ponownego uruchomienia na Windows — 3 pkt.** W toku; punkty zostaną naliczone po spełnieniu kryterium. Identyfikator: `gui.windows-test`.

#### Profile i powtarzalność wyników — 10 pkt

- [x] **Zapisane profile projektu i walidacja konfiguracji — 3 pkt.** Dowód: maxkompilator/config.py i examples/hello-python/maxkompilator.toml; tests/test_engine.py: test_invalid_config_has_actionable_error oraz rzeczywista budowa przykładu z konfiguracji — PASS. Identyfikator: `profiles.configuration`.
- [ ] **Ustawienia nazwy, wersji, ikony i dołączanych zasobów — 2 pkt.** W toku; punkty zostaną naliczone po spełnieniu kryterium. Identyfikator: `profiles.resources`.
- [ ] **Przypięte narzędzia i ponowna budowa ze wskazanego profilu — 3 pkt.** Planowane. Identyfikator: `profiles.repeatability`.
- [x] **Osobne wyniki zadania, logi i raport z sumami kontrolnymi — 2 pkt.** Dowód: maxkompilator/engine.py zapisuje raporty per run, logi i SHA-256; tests/test_engine.py: test_build_json_stdout_is_single_report i test_nonzero_exit_is_logged_and_reported — PASS. Identyfikator: `profiles.reports`.

#### Niezawodność i kwalifikacja wydań — 10 pkt

- [x] **Błędy, timeout i anulowanie nie zwracają fałszywego sukcesu — 3 pkt.** Dowód: tests/test_engine.py: test_zero_exit_without_artifact_is_failure, test_running_process_can_be_cancelled, test_process_timeout, test_failed_smoke_is_not_reported_as_success — PASS. Identyfikator: `reliability.failures`.
- [x] **Ścieżki ze spacjami, Unicode i kontrola granic wejścia/wyjścia — 2 pkt.** Dowód: tests/test_detection.py: test_explicit_entry_cannot_escape_project; tests/test_engine.py: test_output_cannot_overwrite_project_root_or_parent; rzeczywisty GUI smoke ze spacjami i Unicode — PASS. Identyfikator: `reliability.paths`.
- [x] **Automatyczne testy integracyjne na znanych projektach — 3 pkt.** Dowód: tests/test_engine.py: integracja CLI, rzeczywista budowa PYZ, zasoby i test uruchomienia; scripts/gui_smoke.py: integracja GUI z podprocesami — lokalnie PASS. Identyfikator: `reliability.integration`.
- [ ] **Wydanie Windows przechodzi obowiązkową kwalifikację w CI — 2 pkt.** W toku; punkty zostaną naliczone po spełnieniu kryterium. Identyfikator: `reliability.release-gate`.

#### Wykonawcy Linux i macOS — 4 pkt

- [x] **Jawna zgodność systemu i architektury z planem zadania — 1 pkt.** Dowód: tests/test_adapters.py: test_pyinstaller_rejects_cross_os_and_architecture oraz test_dotnet_windows_desktop_rejects_linux_target — PASS; jawny wybór celów zamiast pozornej kompilacji między systemami. Identyfikator: `runners.targets`.
- [x] **Budowa i uruchomienie wyniku na wykonawcy Linux — 1 pkt.** Dowód: Rzeczywisty program Linux x86_64 z PyInstaller 6.22.3 zbudowany i uruchomiony z zasobem; scripts/qualify_native.py — PASS, docs/VALIDATION.md. Identyfikator: `runners.linux`.
- [ ] **Zaimplementowany protokół zdalnego wykonawcy i jego możliwości — 1 pkt.** Planowane. Identyfikator: `runners.remote-contract`.
- [ ] **Budowa i uruchomienie wyniku na wykonawcy macOS — 1 pkt.** W toku; punkty zostaną naliczone po spełnieniu kryterium. Identyfikator: `runners.macos`.

#### Rozszerzalność i kolejne architektury — 2 pkt

- [ ] **Udokumentowany i sprawdzony kontrakt dodatkowego adaptera — 1 pkt.** Planowane. Identyfikator: `extensions.adapter-api`.
- [ ] **Jawna macierz dodatkowych architektur z testem wyboru celu — 1 pkt.** Planowane. Identyfikator: `extensions.architectures`.

<!-- MAXKOMPILATOR:PROGRESS:END -->

## Zasady aktualizacji

1. Zrealizuj całe kryterium i uruchom odpowiedni test.
2. Zapisz trwały dowód: plik testu i wynik, raport budowania, identyfikator uruchomienia CI albo opis testu na docelowym urządzeniu wraz z wersją artefaktu.
3. W `docs/progress.json` ustaw `status: "complete"`, uzupełnij `evidence` oraz datę `updated`.
4. Uruchom `python scripts/update_progress.py` i dołącz wygenerowane zmiany do tej samej aktualizacji.
5. Uruchom `python scripts/update_progress.py --check`; CI powinno odrzucić niespójne dane albo zmieniony ręcznie procent.

Stan `in_progress` nie przyznaje częściowych punktów. Jeśli pojawi się regresja unieważniająca dowód, kryterium wraca do `in_progress` lub `pending`, a wynik spada. Zmiana zakresu lub wag wymaga jawnego opisania zmiany wersji planu; nie przeliczamy wag w celu podwyższenia wyniku.

Zielony CI oznacza wyłącznie przejście uruchomionych zadań. Przy oznaczaniu etapów Windows, Android i macOS dowód musi obejmować odpowiedni system lub urządzenie. Symulowane wywołanie narzędzia wystarcza do testu planowania, ale nie do uznania EXE albo APK za działający.

## Kolejne etapy po podstawach v1

| Obszar | Kierunek | Status |
|---|---|---|
| Dodatkowe języki | C/C++, Rust, Go, Java, Swift i kolejne adaptery | Planowane |
| Aplikacje wieloplatformowe | Flutter, Electron i Tauri | Planowane |
| Rozszerzenia | Przeglądarki, VSIX i dodatki z własnym SDK | Planowane |
| Gry | Godot, następnie wybrane integracje Unity/Unreal | Planowane |
| Dystrybucja | MSI, MSIX, AppImage, DEB, RPM, DMG, PKG i profile podpisów | Planowane |
| Automatyzacja | Kolejka wielu projektów, menedżer środowisk, API/MCP | Planowane |

Te pozycje nie otrzymują punktów z puli v1. Szczegółowe kryteria i wagi kolejnego wydania powstaną przy ustalaniu jego zakresu.

[Powrót do README](README.md) · [Architektura](docs/ARCHITECTURE.md)
