<p align="center">
  <img src="assets/maxkompilator.svg" alt="Oryginalna ikona Maxkompilatora" width="144">
</p>

# Maxkompilator

**Wspólne centrum budowania aplikacji — by [Swir](https://github.com/Swir).**

*An extensible build orchestrator for desktop and Android projects. One project workflow, explicit toolchain requirements, and build results backed by evidence.*

Maxkompilator ma prowadzić od folderu ze źródłami do gotowego programu: rozpoznać projekt, sprawdzić środowisko, pokazać plan, uruchomić właściwe narzędzie i zebrać wyniki. Pierwszy zakres obejmuje **Python, Android i .NET**, z naciskiem na wydania do testowania na Windows i Androidzie.

**Status: `0.1.0.dev1` — działający rdzeń i eksperymentalny interfejs desktopowy.** Lokalnie przeszły rzeczywista budowa i uruchomienie PYZ, natywnego programu Linux z zasobem oraz test GUI Qt w trybie offscreen. Pakiet wheel został zainstalowany i sprawdzony poza repozytorium. Szczegóły i granice dowodów opisuje [walidacja](docs/VALIDATION.md).

**Windows EXE, APK/AAB z Android SDK, publikacja .NET oraz wydanie macOS wymagają jeszcze rzeczywistej kwalifikacji.** Implementacja adaptera oznacza możliwość sterowania narzędziem; poprawne działanie jego wyników sprawdzamy osobno na docelowym systemie.

[Roadmapa i procenty](ROADMAP.md) · [Architektura](docs/ARCHITECTURE.md) · [Wyniki walidacji](docs/VALIDATION.md) · [CI i artefakty](https://github.com/Swir/Maxkompilator/actions)

## Postęp v1

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

<!-- MAXKOMPILATOR:PROGRESS:END -->

**100% oznacza ukończenie opisanej wersji v1.** Dodatkowe języki, instalatory i integracje mają osobne plany rozwoju. Procent nie jest oceną czasu pozostałego do premiery.

## Zakres pierwszej implementacji

| Projekt | Rozpoznawane wejście | Przygotowywany wynik | Co trzeba zapewnić |
|---|---|---|---|
| Python | Skrypt `.py` lub folder projektu | `.pyz` przez zipapp; natywna aplikacja przez PyInstaller | Python 3.11+; PyInstaller i zależności aplikacji dla pakowania natywnego |
| Android | Projekt Gradle z konfiguracją aplikacji | Debug `.apk` lub `.aab` | Zgodne JDK, Android SDK, konfiguracja Gradle i dostępne zależności projektu |
| .NET | Projekt `.csproj` | Katalog wynikowy `dotnet publish` | SDK .NET zgodne z projektem i jego biblioteki |
| GUI Maxkompilatora | Opcjonalny interfejs desktopowy | Wybór projektu, diagnostyka, plan, budowanie, logi i anulowanie | PySide6; test offscreen na Linux zaliczony, Windows oczekuje kwalifikacji |

Kompletna obsługa C/C++, Rust, Go, Java, Flutter, Electron/Tauri, rozszerzeń i silników gier jest **planowana**. Własny protokół zdalnych wykonawców Linux/macOS również należy do dalszych prac. Docelowy wspólny interfejs będzie sterował środowiskami rzeczywiście podłączonymi do programu.

## Uruchomienie ze źródeł

W katalogu repozytorium, z Pythonem 3.11 lub nowszym:

```bash
python -m pip install .
python -m maxkompilator --help
```

Rdzeń CLI korzysta ze standardowej biblioteki Pythona. GUI i PyInstaller są dodatkami:

```bash
python -m pip install -c constraints-ci.txt ".[gui,freeze]"
python -m maxkompilator gui
```

Powyższe polecenia instalują Maxkompilator. SDK Androida, SDK .NET oraz zależności budowanej aplikacji wymagają własnej konfiguracji. Wersje narzędzi muszą pasować do konkretnego projektu.

### Aktualny interfejs

![Maxkompilator — działające GUI po budowie PYZ](docs/images/gui.png)

Rzeczywiste okno po budowie i uruchomieniu PYZ podczas testu **Linux, Qt 6.12, offscreen**. Test Windows pozostaje do wykonania.

### Rozpoznanie i sprawdzenie projektu

```bash
python -m maxkompilator inspect ./projekt --json
python -m maxkompilator doctor ./projekt --format zipapp
python -m maxkompilator plan ./projekt --target native --format zipapp --json
```

`inspect` pokazuje rozpoznany projekt, `doctor` sprawdza wymagania, a `plan` przygotowuje opis budowania. Wybór `native` wskazuje bieżący system i architekturę wykonawcy. Nie jest deklaracją kompilacji na dowolną platformę.

### Budowanie prostego projektu Python

W repozytorium jest mały przykład `examples/hello-python` z pakietem i plikiem danych:

```bash
python -m maxkompilator build ./examples/hello-python --target native --format zipapp --smoke-test
```

`--smoke-test` zleca również uruchomienie zbudowanego wyniku Python poza katalogiem źródeł. Własny skrypt można wskazać jawnie:

```bash
python -m maxkompilator build ./projekt --kind python --entry main.py --target native --format zipapp
```

Domyślny katalog wynikowy to `dist/maxkompilator` wewnątrz projektu. Argument `--output` wskazuje katalog; ścieżka względna jest liczona od katalogu projektu. Dokładne ścieżki plików i wynik testu znajdują się w raporcie zadania.

`--entry` pozwala wskazać punkt startowy, a `--kind` rozstrzygnąć typ projektu (`python`, `android` lub `dotnet`). Przy ścieżkach ze spacjami używaj cudzysłowów. Pomoc danej komendy zawiera aktualną listę argumentów:

```bash
python -m maxkompilator build --help
```

**PYZ wymaga zainstalowanego, zgodnego Pythona.** Maxkompilator pakuje źródła i zasoby projektu; interpreter i zewnętrzne zależności nie są dołączane do PYZ. Format i ograniczenia rozszerzeń natywnych opisuje [dokumentacja Python zipapp](https://docs.python.org/3/library/zipapp.html).

### Natywny program, Android i .NET

Po zainstalowaniu PyInstallera oraz zależności aplikacji natywne pakowanie korzysta z bieżącego systemu:

```bash
python -m maxkompilator plan ./projekt --kind python --entry main.py --target native --format executable --json
python -m maxkompilator build ./projekt --kind python --entry main.py --target native --format executable
```

Pierwszy adapter PyInstaller tworzy **katalog aplikacji**. Zachowaj całą jego zawartość, łącznie z bibliotekami. Na Windows wynik zawiera EXE, na Linux program natywny; wybranie rozszerzenia pliku nie zmienia systemu budowania.

`--python` pozwala wskazać interpreter przeznaczony do budowania. Diagnostyka sprawdza jego system i architekturę; cel musi odpowiadać interpreterowi i wykonawcy. Działający natywny przykład został dotąd zakwalifikowany na Linux x86_64.

Początkowy adapter Android wymaga modułu aplikacji o nazwie `app` i wrappera Gradle w katalogu projektu:

```bash
python -m maxkompilator plan ./aplikacja-android --kind android --target android --format apk --json
python -m maxkompilator build ./aplikacja-android --kind android --target android --format apk
```

`--format aab` wybiera debug App Bundle. Do instalacji na telefonie wybierz APK. Konfigurację ABI i wariantów przechowuje projekt Gradle. Zadanie wykonuje `:app:clean` przed budowaniem, żeby wykluczyć stare wyniki. Wynikowy katalog Maxkompilatora musi znajdować się poza `app/build`.

Kod sprawdza strukturę kontenera APK i wymaga pozytywnego sprawdzenia podpisu przez `apksigner` z Android SDK. Ta ścieżka nie została jeszcze zakwalifikowana przez kompilację i instalację rzeczywistej aplikacji Android. Dla AAB kontrola struktury nie stanowi kwalifikacji podpisu ani dystrybucji sklepowej.

Adapter .NET przyjmuje konkretny projekt z jednym frameworkiem docelowym:

```bash
python -m maxkompilator plan ./aplikacja-dotnet/App.csproj --kind dotnet --target native --format directory --json
python -m maxkompilator build ./aplikacja-dotnet/App.csproj --kind dotnet --target native --format directory
```

Plan publikacji ustawia `--self-contained true` i wymaga zachowania całego katalogu wynikowego. NativeAOT oraz publikowanie wielu frameworków jednym zadaniem wymagają dalszej obsługi. Projekty WPF/WinForms w pierwszym adapterze wymagają wykonawcy Windows. Dotychczas sprawdzono recepty i ich ograniczenia; rzeczywista publikacja SDK .NET pozostaje do przetestowania.

### Konfiguracja projektu

Podstawowe ustawienia można zapisać w `maxkompilator.toml` w katalogu projektu:

```toml
[project]
kind = "python"
entry = "main.py"

[build]
format = "zipapp"
target = "native"

[python]
data = ["hello/message.json"]
```

Pliki danych są wskazywane względem katalogu projektu. Argumenty polecenia pozwalają wybrać ustawienia konkretnego zadania. Pełny edytor profili, wersji narzędzi i podpisów pozostaje w roadmapie.

### Gdzie znajdują się wyniki i logi

W tabeli `BASE` oznacza katalog `--output` lub domyślny `dist/maxkompilator`; `UUID` jest identyfikatorem konkretnego zadania.

| Zawartość | Położenie |
|---|---|
| Archiwum Python | `BASE/nazwa-projektu.pyz` |
| Natywna aplikacja Python lub publikacja .NET | `BASE/runs/UUID/` |
| Skopiowane wyniki Androida | `BASE/artifacts/` z zachowaną ścieżką modułu |
| Raport ostatniego zadania | `BASE/build-report.json` |
| Raport i log konkretnego zadania | `BASE/.maxkompilator/UUID/build-report.json` oraz `build.log` |

Nowe budowanie natywne otrzymuje własny katalog, dzięki czemu plik z poprzedniej próby nie zaliczy kolejnego zadania. Blokada katalogu wynikowego zapobiega równoczesnemu zapisowi dwóch zadań w to samo miejsce. Raport zawiera plan, rzeczywiście wykonany plan, ścieżki artefaktów, sumy SHA-256 i stan testu uruchomienia.

W CLI `--json` pozostawia pojedynczy raport na standardowym wyjściu i kieruje logi budowy na wyjście błędów. `--timeout` ustawia limit pojedynczego etapu; `--smoke-timeout` limit testu uruchomienia. Przerwanie przez Ctrl+C uruchamia anulowanie zadania.

## Budowa i test działania to osobne wyniki

Przy każdej kwalifikacji rozróżniamy:

| Wynik | Wymagany dowód |
|---|---|
| Rozpoznano projekt | Odczytane pliki konfiguracji i wybrany adapter |
| Przygotowano plan | Konkretny wykonawca, polecenia, wymagania i oczekiwane wyniki |
| Zbudowano | Poprawne zakończenie zadania i obecność oczekiwanych nowych plików |
| Sprawdzono artefakt | Weryfikacja formatu, integralności i wymaganych metadanych |
| Uruchomiono | Rzeczywisty test programu na wskazanym systemie lub urządzeniu |

Raport musi wskazywać, które sprawdzenia wykonano. Sam kod wyjścia `0`, obecność pliku albo zielony test recepty nie wystarczają do ogłoszenia, że aplikacja działa na Windowsie lub telefonie.

Automatyczny `--smoke-test` obsługuje obecnie wyniki adaptera Python. Dla Androida i .NET raport zachowuje `not_run`, jeśli nie ma właściwego scenariusza testowego; nie jest to zaliczony test działania. Jeśli zlecony test Python się nie powiedzie lub przekroczy limit, całe zadanie otrzymuje stan błędu.

### Granice platform i formatów

- **Windows EXE przez PyInstaller:** wymaga budowania w odpowiednim środowisku Windows. PyInstaller dołącza interpreter do aplikacji, a wynik jest związany z systemem i architekturą środowiska budowy. Zobacz [dokumentację PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html).
- **Android:** recepty początkowe dotyczą wariantów debug. APK można instalować; AAB służy dalszej dystrybucji i przetwarzaniu. Wydanie release wymaga właściwego klucza. Zobacz [budowanie Androida z wiersza poleceń](https://developer.android.com/build/building-cmdline).
- **.NET:** sposób uruchamiania publikacji zależy od ustawień projektu i dystrybucji. Jedna recepta nie zapewnia zgodności każdej aplikacji .NET z każdym systemem. Zobacz [dotnet publish](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-publish).
- **Linux i macOS:** nazwa platformy w roadmapie nie oznacza dostępności zdalnego komputera. Adapter będzie korzystał z wykonawcy spełniającego wymagania zadania.

Buduj własne lub zaufane projekty. Kompilatory, konfiguracje Gradle/MSBuild i procesy pakowania mogą wykonywać kod projektu z uprawnieniami bieżącego użytkownika. Maxkompilator jest narzędziem orkiestracji; sama praca w podprocesie nie zapewnia izolacji systemowej.

## Rozwój i kontrola jakości

```bash
python -m unittest discover -s tests -v
python scripts/update_progress.py --check
```

**Lokalnie: 80/80 testów rdzenia i integracji PASS; GUI: 7/7 grup PASS.** Opis przebiegu i ograniczeń znajduje się w [docs/VALIDATION.md](docs/VALIDATION.md). GUI można sprawdzić bez pulpitu, po zainstalowaniu dodatku `gui`:

```bash
python scripts/gui_smoke.py --screenshot build/gui-smoke.png
```

Rzeczywistą budowę i dodatkowe sprawdzenie natywnego przykładu uruchamia się kolejno:

```bash
python -m maxkompilator build examples/hello-python --format executable --smoke-test --json
python scripts/qualify_native.py examples/hello-python/dist/maxkompilator/build-report.json
```

Kwalifikacja porównuje SHA-256 i uruchamia aplikację z innego katalogu, przy usuniętych `PYTHONPATH`/`PYTHONHOME` i ograniczonym `PATH`. To test konkretnego przykładu na bieżącym systemie.

Konfiguracja CI zawiera macierz rdzenia dla Linux/Windows/macOS z Pythonem 3.11 i 3.13, natywne budowanie Python dla trzech systemów oraz pakiet desktopowy Windows. Sam plik workflow nie potwierdza, że te zadania zostały już wykonane; wyniki weryfikujemy w [GitHub Actions](https://github.com/Swir/Maxkompilator/actions).

### Przygotowanie pakietu Maxkompilatora dla Windows

W repozytorium jest skrypt wymagający środowiska Windows:

```bash
python -m pip install -c constraints-ci.txt ".[gui,freeze]"
python scripts/build_windows.py
```

Przygotowany format dystrybucji to folder `dist/Maxkompilator` zawierający **`Maxkompilator.exe`, `MaxkompilatorCLI.exe` oraz wspólny katalog `_internal`**. Cały folder musi pozostać razem. Pierwszy plik otwiera GUI, drugi obsługuje zadania konsolowe. Pakiet Windows oczekuje rzeczywistej budowy i kwalifikacji; bieżący lokalny test Linux go nie zastępuje.

SDK używane do budowania cudzych projektów pozostają odrębnymi narzędziami. Przykładowo budowanie aplikacji Python przez zapakowanego Maxkompilatora wymaga dostępnego interpretera budowania i PyInstallera, wskazywanego w razie potrzeby przez `--python`.

### Aktualizacja procentu roadmapy

Postęp aktualizujemy w [docs/progress.json](docs/progress.json). Kryterium może mieć stan `pending`, `in_progress` albo `complete`. Tylko `complete` z niepustą listą `evidence` otrzymuje punkty:

```bash
python scripts/update_progress.py
```

Skrypt odświeża README i roadmapę. Tryb `--check` sprawdza sumę wag, obecność dowodów i zgodność wygenerowanych bloków, dzięki czemu procenty nie rozjeżdżają się pomiędzy plikami. Sam skrypt nie rozstrzyga prawdziwości opisu dowodu — przed zaznaczeniem kryterium trzeba sprawdzić wskazany test lub wynik.

## Kierunek rozwoju

Maxkompilator ma już ciemny interfejs z niebieskimi akcentami, własną ikonę, podstawową konfigurację TOML, czytelne logi i wspólny silnik GUI/CLI. Pełne profile, kolejka wielu projektów, zdalni wykonawcy oraz API/MCP są kolejnymi etapami. Nowe technologie będą dołączane jako adaptery z jawną macierzą możliwości.

Wspólnym celem jest powtarzalna droga **projekt → plan → budowa → sprawdzony wynik**, opisana dla każdej obsługiwanej technologii.
