# Walidacja — 0.1.0.dev1

**Data: 2026-10-17.** Ten zapis rozdziela lokalną kwalifikację Linux od wyników GitHub Actions. Cały [przebieg 39028988975](https://github.com/Swir/Maxkompilator/actions/runs/39028988975) dla commita `aea4aa811f139edab7b167ab86f1518a283a7302` zakończył się sukcesem: **10/10 zadań**. Obejmuje sześć zadań Core, trzy natywne przykłady i pakiet desktopowy Windows. Bezpośrednie dowody i granice sprawdzeń są zapisane w [CI.md](CI.md) i [ci-evidence.json](ci-evidence.json).

Środowisko lokalnej kwalifikacji: **Linux x86_64, glibc 2.39, Python 3.12.14**. Natywne pakowanie wykonano przez **PyInstaller 6.22.3**; GUI sprawdzono z **PySide6/Qt 6.12.0** w trybie `offscreen`. Test offscreen uruchamia rzeczywiste okno, jego logikę i podprocesy, ale nie zastępuje interaktywnej kwalifikacji zbudowanego GUI na Windows.

Skrócone wyniki zapisano również w [validation-local.json](validation-local.json). Źródła testów i skrypty znajdują się w repozytorium; wygenerowane ścieżki robocze nie są wymagane do odtworzenia opisanych komend.

## Wyniki lokalne i ich zakres

| Obszar | Dowód i wynik | Co zostało sprawdzone | Granica dowodu |
|---|---|---|---|
| Rdzeń i integracja | **84/84 PASS**, 2,303 s; `python -m unittest discover -s tests -v` | Rozpoznawanie, plany, błędy, ścieżki, rzeczywiste PYZ, integracja CLI, raporty i generator postępu | Część testów adapterów sprawdza konstrukcję poleceń; nie jest kompilacją odpowiednim SDK |
| PYZ | **PASS**; `tests/test_engine.py` i rzeczywisty `examples/hello-python` | Budowa, import pakietu, dołączony zasób, uruchomienie poza źródłami, zapis raportu | Wymaga zgodnego Pythona; zewnętrzne zależności nie są pakowane automatycznie |
| Natywna aplikacja Python | **PASS**; `scripts/qualify_native.py` po końcowej budowie w osobnym katalogu zadania | ELF x64, SHA-256, uruchomienie spoza źródeł i odczyt zasobu po usunięciu `PYTHONPATH`/`PYTHONHOME` i ograniczeniu `PATH` | Sprawdzony przykład na bieżącym Linux; nie jest dowodem działania na każdej dystrybucji ani na Windows/macOS |
| GUI Qt | **7/7 grup PASS**, 1,202 s; `scripts/gui_smoke.py` | Ikona, domyślne wybory auto, ścieżka ze spacjami i Unicode, inspect/plan/doctor/build, rzeczywisty test PYZ, logi, raport, anulowanie i zakończenie potomka; anulowanie: 0,156 s | Linux offscreen; otwieranie folderu sprawdzane przez przechwycenie URL Qt, bez sterowania menedżerem plików |
| Pakiet Python | **PASS**; wheel i sdist zbudowane, wheel zainstalowany z `--no-index --no-deps` poza repozytorium | Import/wersja CLI, SVG w zainstalowanym pakiecie, prawdziwe PYZ z zasobem i smoke z zainstalowanego modułu | Sdist został zbudowany; ten przebieg instalował wheel. Nie kwalifikuje pakietu desktopowego EXE |
| Android | **Recepty sprawdzone; rzeczywisty APK/AAB niezakwalifikowany** | Plan debug, clean przed build, odrzucanie nieobsługiwanych formatów i katalogów, kod kontroli kontenera i podpisu APK | Brak potwierdzonej kompilacji przez Android SDK, instalacji, uruchomienia i wydania sklepowego |
| .NET | **Recepty sprawdzone; rzeczywista publikacja niezakwalifikowana** | `dotnet publish`, tryb self-contained, wybór projektu i ograniczenia celu | Brak potwierdzonej publikacji SDK .NET i uruchomienia jej wyniku |
| Platformy poza Linuxem | **Wyniki zdalne opisane osobno w CI.md** | Lokalny test nie wykonuje aplikacji Windows ani macOS | Stan konkretnego zdalnego zadania wynika z jego logów, a nie z lokalnej kwalifikacji |

## GitHub Actions

**Core: 6/6 zadań SUCCESS**. W każdym z nich sprawdzono instalację pakietu, zestaw testów, zgodność wygenerowanej roadmapy i prawdziwe PYZ z uruchomieniem przykładu. Bezpośrednie linki do zadań znajdują się w [CI.md](CI.md).

Wynik **84/84 bez pominięć** odnosi się do lokalnego przebiegu Linux. W odczytanych logach Core **Python 3.11** było: Linux **84 zaliczone, 0 pominiętych**, macOS **83 zaliczone, 1 pominięty**, Windows **82 zaliczone, 2 pominięte**. Wszystkie trzy zadania z Pythonem 3.13 również zakończyły się sukcesem; zapis szczegółowych liczników pochodzi z logów 3.11.

`unittest` uwzględnia w liczbie `Ran` również testy oznaczone jako `skipped`; pominiętego przypadku nie liczymy jako sprawdzonego na danym systemie. Regresja grup procesów POSIX jest pomijana na Windows, a integracja środowiska bibliotek zamrożonego procesu Linux jest pomijana poza Linuxem. Testy dowiązań mogą zostać pominięte, gdy użytkownik wykonawcy nie może ich utworzyć.

**Natywne przykłady: 3/3 SUCCESS.** Windows x64 (`pe-x64`), Linux x64 (`elf-x64`) i macOS ARM64 (`mach-o`) przeszły budowanie, test zasobu oraz uruchomienie spoza źródeł z ograniczonym `PATH` i usuniętymi `PYTHONPATH`/`PYTHONHOME`. Walidacja wszystkich trzech archiwów zakończyła się pozytywnie; paczka macOS zachowała cztery dowiązania symboliczne. Wykonawcy CI mieli zainstalowanego Pythona, dlatego ten dowód nie kończy testu na czystej maszynie bez interpretera.

**Windows desktop bundle: SUCCESS.** Źródłowe GUI przeszło **7/7 grup testów w 1,422 s**, z anulowaniem w **0,156 s**. Zbudowano oba EXE i wspólny runtime; spakowany `MaxkompilatorCLI.exe` rozpoznał projekt oraz rzeczywiście zbudował PYZ z pozytywnym smoke. Pełna próba interaktywnego, spakowanego GUI i jego ponownego otwarcia pozostaje do wykonania.

## Spakowany moduł CLI na Linuxie

Rzeczywisty program `MaxkompilatorCLI` zbudowany przez PyInstaller uruchomił własny silnik, utworzył PYZ i uruchomił je przez zewnętrznego Pythona. Osobne sprawdzenie środowiska potwierdziło wywołanie zewnętrznego interpretera i PyInstaller. Odczyt i zapis JSON oraz zasoby przeszły test. Wynik i suma programu są zapisane w `validation-local.json`. Ten test dotyczy konsolowego modułu Linux; kwalifikacja zamrożonego GUI Windows pozostaje oddzielnym zadaniem.

## Końcowy natywny wynik Linux

- Identyfikator zadania: `97538f31331547f09f90a5618894965c`.
- Wykryty format: `elf-x64`.
- SHA-256 pliku wejściowego aplikacji: `b0a56d501f6d26093231bd15c7cceddfe20161b27b7246c9354070ae9c56b208`.
- Potwierdzony komunikat aplikacji: `Maxkompilator: build and resource check OK`.
- Kwalifikacja uruchomiła program w katalogu tymczasowym, z systemowym `PATH` oraz bez `PYTHONPATH` i `PYTHONHOME`.

Test odbył się na tym samym hoście Linux, na którym wykonano budowanie. Nie oznacza instalacji i testu na oddzielnym czystym komputerze. Hash identyfikuje sprawdzony plik wykonywalny; aplikacja zachowuje zależności w swoim katalogu dystrybucji.

### Archiwum natywnego wyniku

`scripts/qualify_native.py` tworzy `native-example-TARGET.tar.gz` z całym katalogiem aplikacji, raportem budowania i raportem kwalifikacji. Skrypt ponownie odczytuje archiwum, porównuje listę elementów, typy dowiązań i ich cele, uprawnienia POSIX oraz sumy pliku wykonywalnego i raportów. Pozwala to zachować dane wymagane do uruchomienia programu po pobraniu artefaktu CI.

Lokalnie sprawdzone archiwum `native-example-linux-x64.tar.gz` ma rozmiar **11 932 078 bajtów** i SHA-256 `56912d1b7882ddf3c8d72e2f016765b33a4b954a120c581a6cad159053301ddd`. Jest artefaktem rozwojowym; kontrola archiwum nie oznacza podpisania wydania ani testu na wszystkich systemach docelowych.

## Odtworzenie najważniejszych sprawdzeń

Po zainstalowaniu Maxkompilatora i odpowiednich dodatków:

```bash
python -m unittest discover -s tests -v
python scripts/update_progress.py --check
python -m maxkompilator build examples/hello-python --format zipapp --smoke-test --json
```

Pakowanie natywne wymaga PyInstallera i odbywa się na wybranym systemie:

```bash
python -m pip install -c constraints-ci.txt ".[freeze]"
python -m maxkompilator build examples/hello-python --format executable --smoke-test --json
python scripts/qualify_native.py examples/hello-python/dist/maxkompilator/build-report.json
```

Test GUI sam wybiera platformę Qt `offscreen`:

```bash
python -m pip install -c constraints-ci.txt ".[gui]"
python scripts/gui_smoke.py --screenshot build/gui-smoke.png
```

Testy negatywne obejmują m.in. brak narzędzia, kod wyjścia różny od zera, pozornie udaną komendę bez artefaktu, stary wynik z poprzedniego zadania, fałszywy plik wykonywalny, timeout, anulowanie, próbę nadpisania źródeł i błędny punkt startowy. Są to sprawdzenia konkretnych scenariuszy, nie gwarancja obsługi dowolnego projektu.

## Kolejna kwalifikacja

Do zamknięcia pozostają niepotwierdzone jeszcze scenariusze z [CI.md](CI.md), pełny przebieg zbudowanego GUI Windows wraz z ponownym uruchomieniem, test na komputerze bez Pythona, Android z właściwym SDK i urządzeniem oraz publikacja .NET. Windows jest przygotowywany jako cały katalog z `Maxkompilator.exe`, `MaxkompilatorCLI.exe` i `_internal`; sprawdzenie samego modułu konsolowego nie kwalifikuje pełnej ścieżki GUI.

[Roadmapa z punktacją](../ROADMAP.md) · [Wyniki CI](CI.md) · [Architektura](ARCHITECTURE.md)
