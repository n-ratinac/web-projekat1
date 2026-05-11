## Timovi

| Tim A     | Tim B    |
| --------- | -------- |
| Sibinović | Sava |
| Mirković  | Simić    |
| Pavle     | Matija  |
| Ristić      | Luka |

## Podešavanje projekta

U powershell-u, otići u neki direktorijum gde imate pune permisije i izvršiti sledeće.

```sh
git clone https://github.com/n-ratinac/web-projekat1.git
code web-projekat1
```

## Instalacija python paketa

```sh
pip install -r requirements.txt
```

## Problemi

Ako kljentska aplikacija ne prima podatke sa servera onda:

1. Proveri da li je pokrenut `python server.py`
2. Proveri da li klijentska aplikacija gadja adekvatan server (ws://localhost:8765)
3. U direktorijumu koji sadzri `index.html` fajl, pokrenuti `python -m http.server 8080`, pa pristupiti lokaciji `localhost:8080`

## Podela posla

U fajlu [ISSUES.md](ISSUES.md) nalazi se opis stvari koje treba da se urade. Timovi treba da podele posao između sebe i reše što više zadataka.
