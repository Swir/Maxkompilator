# Wyniki GitHub Actions

**Repozytorium:** [Swir/Maxkompilator](https://github.com/Swir/Maxkompilator). **Wersja:** `0.1.0.dev1`.

Ten zapis dotyczy [przebiegu 39028988975](https://github.com/Swir/Maxkompilator/actions/runs/39028988975) dla commita [`aea4aa811f139edab7b167ab86f1518a283a7302`](https://github.com/Swir/Maxkompilator/commit/aea4aa811f139edab7b167ab86f1518a283a7302), sprawdzonego 2026-10-17. Kolejny commit lub ponowne uruchomienie wymaga osobnego odczytania wyników.

**Cały przebieg: SUCCESS — 10/10 zadań.** Lista zadań, metadane czterech artefaktów i odczytane wyniki są zapisane w [ci-evidence.json](ci-evidence.json).

## Rdzeń: sześć potwierdzonych zadań

**6/6 zadań Core zakończyło się wynikiem SUCCESS.** Każde instaluje pakiet, uruchamia testy, sprawdza zgodność procentów README/ROADMAP i buduje rzeczywisty PYZ z zasobem oraz testem uruchomienia.

| Środowisko | Python | Wynik | Dowód |
|---|---|---|---|
| Linux — `ubuntu-latest` | 3.11 | SUCCESS | [Job 117385484411](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484411) |
| Linux — `ubuntu-latest` | 3.13 | SUCCESS | [Job 117385484154](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484154) |
| Windows — `windows-latest` | 3.11 | SUCCESS | [Job 117385484444](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484444) |
| Windows — `windows-latest` | 3.13 | SUCCESS | [Job 117385484391](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484391) |
| macOS — `macos-latest` | 3.11 | SUCCESS | [Job 117385484318](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484318) |
| macOS — `macos-latest` | 3.13 | SUCCESS | [Job 117385484353](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385484353) |

Lokalny wynik **84/84 PASS bez pominięć** pochodzi z Linux x86_64/Python 3.12.14. Nie przypisujemy tej samej liczby wykonanych przypadków każdej platformie CI. `unittest` pokazuje liczbę wykrytych testów oraz osobną liczbę pominięć; `skipped` nie jest zaliczonym testem danego scenariusza.

Regresja grup procesów POSIX jest pomijana na Windows, a integracja środowiska bibliotek zamrożonego procesu Linux jest pomijana na Windows i macOS. Testy dowiązań mogą być pomijane, jeśli wykonawca nie ma możliwości ich utworzenia. Dokładny wynik znajduje się w kroku **Unit and integration tests** każdego zadania.

Odczytane szczegółowe logi Core dotyczą **Pythona 3.11**:

| Środowisko | Wykrytych testów | Zaliczone | Pominięte | Czas |
|---|---:|---:|---:|---:|
| Linux | 84 | 84 | 0 | 1,773 s |
| macOS | 84 | 83 | 1 | 2,654 s |
| Windows | 84 | 82 | 2 | 3,437 s |

Status SUCCESS potwierdzono również dla wszystkich trzech zadań Python 3.13. Powyższych liczników czasu i pominięć nie przypisujemy do ich logów.

## Zadania natywne i pakiet Windows

Te zadania następują po Core. Ich status i dowody oceniamy niezależnie od sześciu udanych zadań rdzenia.

| Zadanie | Wynik i sprawdzony cel | Link |
|---|---|---|
| Native Python — macOS | SUCCESS; `macos-arm64`, Mach-O, build/resource/smoke/archiwum | [Job 117385587229](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385587229) |
| Native Python — Windows | SUCCESS; `win-x64`, PE x64, build/resource/smoke/archiwum | [Job 117385587290](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385587290) |
| Native Python — Linux | SUCCESS; `linux-x64`, ELF x64, build/resource/smoke/archiwum | [Job 117385587311](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385587311) |
| Windows desktop bundle | SUCCESS; źródłowe GUI, rzeczywisty pakiet EXE i spakowany CLI z budową PYZ | [Job 117385587321](https://github.com/Swir/Maxkompilator/actions/runs/39028988975/job/117385587321) |

### Co sprawdza natywna kwalifikacja

Job buduje `examples/hello-python` przez PyInstaller, uruchamia aplikację i sprawdza dołączony zasób. `scripts/qualify_native.py` porównuje SHA-256 i uruchamia wynik spoza źródeł, po usunięciu `PYTHONPATH`/`PYTHONHOME` i ograniczeniu `PATH` do katalogów systemowych.

Następnie powstaje `native-example-TARGET.tar.gz`. Skrypt odczytuje utworzone archiwum i sprawdza kompletność elementów, typy i cele dowiązań, uprawnienia POSIX oraz sumy pliku wykonywalnego i raportów. Archiwum umożliwia zachowanie uprawnień i dowiązań przy pobieraniu przez usługę artefaktów CI. Ten wynik jest paczką rozwojową.

Wszystkie trzy kwalifikacje zakończyły się pozytywnie. Archiwum macOS zachowało **4 dowiązania symboliczne**. Sumy sprawdzonych plików wykonywalnych:

- macOS ARM64: `47d2993aaebf1673e81af616c23c819a01286d70c775c8a0edefbcdbe5e75cd7`.
- Windows x64: `e9a87d7f865745f02aeca29cb6a7a98333b2692085113833218fa0a5b14222cd`.
- Linux x64: `8a01e5e291672c832843561376381864bbc2c37a06b6ce60b375ab192458713d`.

**Wykonawca CI nadal ma zainstalowanego Pythona.** Ograniczenie `PATH` i zmiennych środowiska jest konkretnym testem niezależnego uruchomienia, lecz nie zastępuje testu na czystej maszynie bez Pythona.

### Co sprawdza Windows desktop bundle

Potwierdzone kroki zadania:

1. Test źródłowego GUI PySide6 w trybie offscreen: **7/7 grup PASS w 1,422 s**, z prawdziwym CLI, budowaniem PYZ, testem zasobu i anulowaniem w **0,156 s**; potwierdzono zatrzymanie potomka.
2. Zbudowanie folderu dystrybucji zawierającego `Maxkompilator.exe`, `MaxkompilatorCLI.exe` i `_internal` — **PASS**.
3. Uruchomienie spakowanego modułu konsolowego, rozpoznanie projektu oraz rzeczywista budowa i test PYZ przez ten moduł — **PASS**.
4. Budowanie wheel/sdist i przesłanie artefaktów — **PASS**.

Zaliczenie tych kroków potwierdza dokładnie opisane operacje. Nie stanowi jeszcze pełnego testu zbudowanego `Maxkompilator.exe` obejmującego wszystkie operacje okna, jego zamknięcie i ponowne otwarcie. Taki scenariusz oraz osobny komputer bez Pythona pozostają kryteriami roadmapy.

## Pobieranie gotowego narzędzia Windows

Wejdź w **Actions → [przebieg 39028988975](https://github.com/Swir/Maxkompilator/actions/runs/39028988975) → Artifacts → `Maxkompilator-Windows-x64-dev`**. Wypakuj całe archiwum, przejdź do `dist/Maxkompilator` i uruchom `Maxkompilator.exe`. Zachowaj w tym samym folderze `MaxkompilatorCLI.exe` oraz `_internal`.

| Artefakt | Zawartość | Rozmiar według GitHub |
|---|---|---:|
| `Maxkompilator-Windows-x64-dev` | Narzędzie Maxkompilator dla Windows, oba EXE i runtime; dodatkowo wheel/sdist i zrzut testu GUI | 54 090 240 bajtów, około 51,6 MiB |
| `native-example-windows-latest` | Przykład aplikacji Windows zbudowany przez Maxkompilator | 7 995 708 bajtów |
| `native-example-ubuntu-latest` | Przykład aplikacji Linux zbudowany przez Maxkompilator | 19 841 977 bajtów |
| `native-example-macos-latest` | Przykład aplikacji macOS zbudowany przez Maxkompilator | 7 217 509 bajtów |

Identyfikator artefaktu samego narzędzia to **12099418546**; termin przechowywania według GitHub: **2026-10-31, 11:32:45 UTC**. Jego digest zgłoszony przez GitHub: `sha256:4c7d50f97276e9a94551e0e565ccca5c4cd654b68fc80355808fd2b0a16d4af2`. Rozmiary i digest tej tabeli dotyczą artefaktów usługi GitHub; wewnętrzne pliki `native-example-TARGET.tar.gz` mają własne rozmiary i sumy zapisane w raporcie kwalifikacji.

## Związek z procentem roadmapy

Sześć udanych zadań Core zamyka `foundation.ci` za **2 punkty**, a rzeczywista budowa i uruchomienie macOS ARM64 zamyka `runners.macos` za **1 punkt**. Wynik zdefiniowanej v1 wynosi **55%**. Pozostałe punkty są przyznawane wyłącznie po spełnieniu pełnego kryterium, zgodnie z [ROADMAP.md](../ROADMAP.md). Test samej recepty nie kończy kwalifikacji APK/.NET, a spakowany moduł konsolowy nie zamyka pełnej kwalifikacji GUI Windows.

[Walidacja lokalna i granice dowodów](VALIDATION.md) · [Roadmapa](../ROADMAP.md)
