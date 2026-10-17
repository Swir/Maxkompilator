# Walidacja lokalna — 0.1.0.dev1

**Data: 2026-10-17.** Ten zapis obejmuje lokalną kwalifikację przed pierwszym potwierdzonym uruchomieniem przygotowanego workflow GitHub Actions. Dowody aktualizujemy dla konkretnego systemu i formatu.

Środowisko wykonania: **Linux x86_64, glibc 2.39, Python 3.12.14**. Natywne pakowanie wykonano przez **PyInstaller 6.22.3**; GUI sprawdzono z **PySide6/Qt 6.12.0** w trybie `offscreen`. Test offscreen uruchamia rzeczywiste okno, jego logikę i podprocesy, ale nie zastępuje interaktywnej kwalifikacji na Windows.

Skrócone wyniki zapisano również w [validation-local.json](validation-local.json). Źródła testów i skrypty znajdują się w repozytorium; wygenerowane ścieżki robocze nie są wymagane do odtworzenia opisanych komend.

## Wyniki i ich zakres

| Obszar | Dowód i wynik | Co zostało sprawdzone | Granica dowodu |
|---|---|---|---|
| Rdzeń i integracja | **84/84 PASS**, 2,303 s; `python -m unittest discover -s tests -v` | Rozpoznawanie, plany, błędy, ścieżki, rzeczywiste PYZ, integracja CLI, raporty i generator postępu | Część testów adapterów sprawdza konstrukcję poleceń; nie jest kompilacją odpowiednim SDK |
| PYZ | **PASS**; `tests/test_engine.py` i rzeczywisty `examples/hello-python` | Budowa, import pakietu, dołączony zasób, uruchomienie poza źródłami, zapis raportu | Wymaga zgodnego Pythona; zewnętrzne zależności nie są pakowane automatycznie |
| Natywna aplikacja Python | **PASS**; `scripts/qualify_native.py` po końcowej budowie w osobnym katalogu zadania | ELF x64, SHA-256, uruchomienie spoza źródeł i odczyt zasobu po usunięciu `PYTHONPATH`/`PYTHONHOME` i ograniczeniu `PATH` | Sprawdzony przykład na bieżącym Linux; nie jest dowodem działania na każdej dystrybucji ani na Windows/macOS |
| GUI Qt | **7/7 grup PASS**, 1,202 s; `scripts/gui_smoke.py` | Ikona, domyślne wybory auto, ścieżka ze spacjami i Unicode, inspect/plan/doctor/build, rzeczywisty test PYZ, logi, raport, anulowanie i zakończenie potomka; anulowanie: 0,156 s | Linux offscreen; otwieranie folderu sprawdzane przez przechwycenie URL Qt, bez sterowania menedżerem plików |
| Pakiet Python | **PASS**; wheel i sdist zbudowane, wheel zainstalowany z `--no-index --no-deps` poza repozytorium | Import/wersja CLI, SVG w zainstalowanym pakiecie, prawdziwe PYZ z zasobem i smoke z zainstalowanego modułu | Sdist został zbudowany; ten przebieg instalował wheel. Nie kwalifikuje pakietu desktopowego EXE |
| Android | **Recepty sprawdzone; rzeczywisty APK/AAB niezakwalifikowany** | Plan debug, clean przed build, odrzucanie nieobsługiwanych formatów i katalogów, kod kontroli kontenera i podpisu APK | Brak potwierdzonej kompilacji przez Android SDK, instalacji, uruchomienia i wydania sklepowego |
| .NET | **Recepty sprawdzone; rzeczywista publikacja niezakwalifikowana** | `dotnet publish`, tryb self-contained, wybór projektu i ograniczenia celu | Brak potwierdzonej publikacji SDK .NET i uruchomienia jej wyniku |
| Windows i macOS | **Oczekują kwalifikacji** | Przygotowano zadania CI dla obu systemów i skrypt pakowania Windows | Brak lokalnego dowodu EXE, działania GUI Windows albo natywnego wyniku macOS |
| GitHub Actions | **Workflow przygotowany, bez potwierdzonego wyniku w tym zapisie** | Macierze Core, Native Python i Windows desktop w `.github/workflows/ci.yml` | Konfiguracja zadania nie przyznaje punktów za jego przejście |

## Spakowany moduł CLI na Linuxie

Rzeczywisty program `MaxkompilatorCLI` zbudowany przez PyInstaller uruchomił własny silnik, utworzył PYZ i uruchomił je przez zewnętrznego Pythona. Osobne sprawdzenie środowiska potwierdziło wywołanie zewnętrznego interpretera i PyInstaller. Odczyt i zapis JSON oraz zasoby przeszły test. Wynik i suma programu są zapisane w `validation-local.json`. Ten test dotyczy konsolowego modułu Linux; kwalifikacja zamrożonego GUI Windows pozostaje oddzielnym zadaniem.

## Końcowy natywny wynik Linux

- Identyfikator zadania: `97538f31331547f09f90a5618894965c`.
- Wykryty format: `elf-x64`.
- SHA-256 pliku wejściowego aplikacji: `b0a56d501f6d26093231bd15c7cceddfe20161b27b7246c9354070ae9c56b208`.
- Potwierdzony komunikat aplikacji: `Maxkompilator: build and resource check OK`.
- Kwalifikacja uruchomiła program w katalogu tymczasowym, z systemowym `PATH` oraz bez `PYTHONPATH` i `PYTHONHOME`.

Test odbył się na tym samym hoście Linux, na którym wykonano budowanie. Nie oznacza instalacji i testu na oddzielnym czystym komputerze. Hash identyfikuje sprawdzony plik wykonywalny; aplikacja zachowuje zależności w swoim katalogu dystrybucji.

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

Do zamknięcia pozostają rzeczywiste zadania CI Windows/macOS, pełny przebieg pakietu Windows, Android z właściwym SDK i urządzeniem oraz publikacja .NET. Windows ma być dystrybuowany jako cały katalog z `Maxkompilator.exe`, `MaxkompilatorCLI.exe` i `_internal`; samo przygotowanie skryptu nie oznacza gotowego pliku do testowania.

[Roadmapa z punktacją](../ROADMAP.md) · [Architektura](ARCHITECTURE.md)
