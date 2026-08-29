# Tests

Beschermen tegen stille breuk: als Sofascore, FotMob of Transfermarkt hun API of
HTML wijzigt, faalt hier een test i.p.v. dat een redactielid met een lege pagina zit.

## Draaien

```bash
py -m unittest discover -s tests
```

Nodig: `beautifulsoup4` en `jinja2` in je Python. Geen internet nodig — de scrapers
draaien tegen **opgenomen responses** in `fixtures/`.

## Fixtures vernieuwen

Draai dit als een test faalt door een sitewijziging (heeft wél internet + `curl_cffi` nodig):

```bash
py tests/opnemen.py            # alle scenario's (antwerp + arsenal)
py tests/opnemen.py antwerp    # één scenario
```

Commit daarna de gewijzigde `fixtures/`-map.

## Wat er getest wordt

| Bestand | |
|---|---|
| `test_scrapers.py` | `sofascore/fotmob/transfermarkt/preview.fetch()` + `aggregate.bouw_overzicht()` tegen fixtures, voor Antwerp (Jupiler Pro League) en Arsenal (Premier League) |
| `test_tm_kolommen.py` | Transfermarkt-kolommen op kop lezen én de positionele fallback geven hetzelfde |
| `test_status.py` | elke bron zet een `status`; `app.BronLeegError`; `aggregate._bron_status` |
| `test_eenheden.py` | naam-matching, merk-config, ploegenlijst, FotMob-zoektermen (zonder net) |
