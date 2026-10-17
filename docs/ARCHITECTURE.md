# Architektura Maxkompilatora

## Cel i granice

Maxkompilator jest orkiestratorem narzędzi budowania. Jeden model projektu i zadania ma obsłużyć CLI, opcjonalne GUI oraz przyszłe API/MCP. Każda technologia otrzymuje adapter, który opisuje rozpoznawanie, wymagania, plan budowy i oczekiwane wyniki.

Pierwszy zakres implementacji obejmuje lokalny rdzeń Python 3.11+, adapter zipapp/PyInstaller, Android Gradle i `dotnet publish`. GUI PySide6 jest opcjonalne i uruchamia zadania przez wspólne CLI. Rzeczywiste wyniki Python oraz integrację GUI sprawdzono lokalnie na Linux; status pozostałych platform przedstawia [VALIDATION.md](VALIDATION.md). Zdalni wykonawcy, kolejka wielu projektów, pełne profile i publiczny interfejs wtyczek są planowane; poniższy projekt opisuje także ich przyszłe miejsce.

## Warstwy

| Warstwa | Odpowiedzialność | Zależności |
|---|---|---|
| Interfejs CLI/GUI | Zebranie parametrów, prezentacja planu, logów i wyniku | Publiczne operacje rdzenia |
| Wykrywanie | Odczyt plików projektu i opis kandydatów | System plików; bez importowania kodu aplikacji |
| Adapter | Wymagania technologii, obsługiwane cele, plan i walidator artefaktu | Model projektu i wykonawcy |
| Wykonawca lokalny | Uruchomienie konkretnych kroków, logi, timeout, anulowanie | Procesy i wskazany katalog zadania |
| Raportowanie | Stan zadania, pliki, sumy kontrolne, wykonane sprawdzenia | Wynik wykonawcy i walidatora |
| Przyszły wykonawca zdalny | To samo zadanie na podłączonym Windows/Linux/macOS | Jawny protokół, uwierzytelnienie i możliwości wykonawcy |

Rdzeń nie importuje PySide6 przy pracy z CLI. Interfejsy korzystają z tego samego planowania i wykonania; GUI nie przechowuje osobnego zestawu poleceń kompilacji. Okno wykorzystuje `QProcess`, odbiera logi i raport JSON, blokuje zmianę parametrów na czas zadania oraz przekazuje żądanie anulowania do procesu roboczego. W planowanym pakiecie Windows osobny `MaxkompilatorCLI.exe` zapewnia wyjścia konsolowe, a `Maxkompilator.exe` otwiera okno bez konsoli.

## Przepływ zadania

1. **Rozpoznanie.** Odczyt katalogu i znanych konfiguracji. Przy wielu możliwych projektach wybór musi być jawny, na przykład przez `--kind` lub konkretny plik. Punkt startowy Python można wskazać przez `--entry`.
2. **Diagnostyka.** Sprawdzenie wymaganych narzędzi, możliwości wykonawcy i podstawowej konfiguracji. Odczyt wersji narzędzia może uruchomić jego ograniczone polecenie diagnostyczne, ale nie uruchamia budowania projektu.
3. **Plan.** Powstaje konkretny opis kroków, argumentów, katalogów i spodziewanych wyników. `plan --json` udostępnia go do inspekcji i automatyzacji. Sam plan nie wykonuje poleceń budowy.
4. **Budowanie.** Wykonawca uruchamia plan w wybranym katalogu i przekazuje postęp interfejsowi. Zapisywane są kod zakończenia i logi.
5. **Walidacja.** Sprawdzenie, czy powstały oczekiwane nowe pliki. Walidatory właściwe dla formatu rozszerzają to o strukturę, metadane oraz podpis.
6. **Raport.** Udokumentowanie wyniku budowy i faktycznie wykonanych testów. Flaga `--smoke-test` uruchamia wynik Python w osobnym katalogu tymczasowym; pozostałe adaptery wymagają odpowiedniego scenariusza testowego lub urządzenia.

## Kontrakty projektowe

Nazwy poniżej opisują wymagane dane; nie są deklaracją zakończenia implementacji każdego pola lub publicznego API.

| Model | Informacje |
|---|---|
| Projekt | Ścieżka źródeł, typ, wskazany plik/projekt, punkt startowy, wykryte konfiguracje |
| Cel | System, architektura, format, wariant, wymagania narzędzi |
| Plan | Adapter, wykonawca, kroki z tablicami argumentów, katalogi, oczekiwane artefakty |
| Wymaganie | Nazwa narzędzia, sposób sprawdzenia, wynik, pomoc przy brakach |
| Artefakt | Ścieżka, rozmiar, format, suma kontrolna, wyniki kontroli |
| Wynik zadania | Stan, kod zakończenia, czas, logi, artefakty i lista wykonanych testów |

Identyfikator formatu nie może udawać możliwości niedostępnej dla danej technologii. `native` oznacza bieżącego wykonawcę. Ustawienie `windows` w konfiguracji nie zapewnia obecności Windowsa ani kompilatora obsługującego ten cel.

## Wykonawcy i granice wykonania

Polecenia są konstruowane jako program i lista argumentów. Nie wolno łączyć dowolnego tekstu projektu z poleceniem powłoki. Wrappery platformowe, takie jak plik Gradle `.bat`, wymagają jawnej, ograniczonej obsługi właściwej dla systemu. Argumenty muszą zachowywać spacje i Unicode.

Wykonawca ma określony katalog roboczy, limit czasu i obsługę anulowania procesu wraz z jego dziećmi. Stan anulowany lub timeout nie może przejść w sukces tylko dlatego, że na dysku pozostał stary plik wynikowy. Natywne budowanie Python i .NET korzysta z katalogu `BASE/runs/UUID`; raport zachowuje plan pierwotny i plan wykonania po zmianie ścieżek. PYZ jest tworzony w katalogu tymczasowym i atomowo instalowany jako `BASE/nazwa.pyz`. Android wykonuje `:app:clean` przed zadaniem debug, a potem kopiuje wyniki modułu do `BASE/artifacts`.

Każde zadanie zapisuje własny `build.log` i `build-report.json` w `BASE/.maxkompilator/UUID`. Plik `BASE/build-report.json` wskazuje raport ostatniego zadania. Blokada katalogu wyjściowego wyklucza jednoczesny zapis konkurencyjnych zadań. Artefakty mają sumy SHA-256; kontrola formatu nie polega wyłącznie na rozszerzeniu. W ścieżce APK dochodzi wywołanie `apksigner verify`, które musi się powieść. Test tego przepływu na prawdziwym Android SDK pozostaje otwarty.

Wykrywanie i tworzenie planu nie importuje źródeł aplikacji ani nie uruchamia jej konfiguracji. Budowanie może wykonywać kod projektu: hooki Python, skrypty Gradle/MSBuild i narzędzia zależności. Lokalny podproces ma uprawnienia użytkownika i nie jest piaskownicą systemową. Izolację dla niezaufanych projektów musi zapewnić osobny kontener, maszyna wirtualna lub inny wykonawca o ograniczonych uprawnieniach.

Zadania zdalne w przyszłym protokole będą identyfikowane jednoznacznie. Wykonawca ma deklarować system, architekturę i dostępne narzędzia; serwer nie może przyjąć dowolnej ścieżki hosta jako artefaktu. Przesyłanie źródeł, uwierzytelnienie i pobieranie wyników muszą respektować ograniczenia danego środowiska. Klucze podpisywania pozostają w magazynie wykonawcy lub profilu podpisów, poza zwykłą konfiguracją, logami i archiwum źródeł.

## Stany i dowody

Aktualny raport rozdziela stan zadania (`running`, `built`, `failed`, `cancelled`) od poziomu sprawdzenia artefaktu i pola `smoke_test`. Limit czasu kończy zadanie jako `failed` z konkretnym opisem błędu; anulowanie daje `cancelled`. Pole testu uruchomienia przyjmuje `not_run`, `passed`, `failed` albo `cancelled`. Pozytywna budowa wymaga pomyślnego wykonania i oczekiwanego wyniku; nadal nie oznacza automatycznie udanego testu instalacji czy uruchomienia.

CLI zwraca kod `0` po udanej operacji lub budowie, `1` po błędzie budowania, `2` przy błędnym wejściu lub planie, `3` po negatywnej diagnostyce środowiska i `130` po anulowaniu budowania. Błąd zleconego testu uruchomienia powoduje błąd całego zadania. W trybie JSON logi budowy trafiają na stderr, a końcowy raport jest pojedynczym obiektem na stdout.

Każdy test zapisuje swój zakres: planowanie, budowa, struktura artefaktu, podpis, instalacja albo uruchomienie. Test z podstawionym procesem może potwierdzić obsługę błędów, ale nie jest dowodem kompilacji rzeczywistym SDK.

Wagi i dowody realizacji produktu znajdują się w [progress.json](progress.json). Skrypt `scripts/update_progress.py` waliduje dane i generuje widoki w README/ROADMAP. Nie stanowi automatycznego audytora prawdziwości dowodów; ich ocenę opieramy na wskazanym kodzie, testach i wynikach konkretnego zadania.

## Dalsze rozszerzanie

Nowy adapter powinien zadeklarować obsługiwane wejścia i cele, wymagania narzędzi, plan oraz weryfikację wyników. Powinien zawierać mały projekt testowy z oczekiwanym zachowaniem. Obsługa kolejnego systemu lub architektury otrzymuje osobny dowód budowy i uruchomienia, bez dziedziczenia statusu z innej platformy.

Podstawowa konfiguracja `maxkompilator.toml` zapisuje typ projektu, punkt startowy, format, cel i dane Python. Jej rozszerzenie o pełne profile, menedżer zależności, kolejka i API/MCP są dalszymi elementami architektury. Ich dodanie ma zachować jeden silnik używany przez wszystkie interfejsy.
