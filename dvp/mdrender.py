"""Piepklein Markdown -> HTML, enkel voor de subset die export.py produceert:
kopjes (#/##/###), **vet**, `code`, - lijsten, | tabellen |, [tekst](url), ---, alinea's.
"""

from __future__ import annotations

import html
import re

_DONKER = """
  body{margin:0;background:#0e1014;color:#e7e9ee;font:15px/1.6 system-ui,"Segoe UI",Roboto,sans-serif}
  main{max-width:820px;margin:0 auto;padding:28px 22px 60px}
  h1{font-size:22px;margin:0 0 6px} h2{font-size:16px;margin:26px 0 10px;color:#ff4d67}
  h3{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#8a93a3;margin:18px 0 6px}
  a{color:#ff4d67} code{background:#1e222b;padding:1px 5px;border-radius:4px;font-size:13px}
  table{border-collapse:collapse;width:100%;margin:8px 0;font-size:13.5px}
  th,td{border:1px solid #2a2f3a;padding:5px 8px;text-align:left}
  th{color:#8a93a3;font-size:12px;text-transform:uppercase}
  hr{border:0;border-top:1px solid #2a2f3a;margin:22px 0}
  ul{margin:6px 0;padding-left:20px} li{margin:2px 0}
  .balk{margin-bottom:16px;font-size:13px}
"""

_LICHT = """
  body{margin:0;background:#fff;color:#15181d;font:13px/1.5 Georgia,"Times New Roman",serif}
  main{max-width:820px;margin:0 auto;padding:20px 26px 60px}
  h1{font-size:21px;margin:0 0 4px} h2{font-size:15px;margin:20px 0 7px;border-bottom:1px solid #ccc;padding-bottom:3px}
  h3{font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:#555;margin:12px 0 4px}
  a{color:#15181d} code{font-family:inherit}
  table{border-collapse:collapse;width:100%;margin:6px 0;font-size:11.5px}
  th,td{border:1px solid #bbb;padding:3px 6px;text-align:left}
  thead th{background:#eee;font-size:10.5px;text-transform:uppercase}
  hr{border:0;border-top:1px solid #bbb;margin:16px 0}
  ul{margin:4px 0;padding-left:20px} li{margin:1px 0}
  .balk{margin-bottom:18px;display:flex;gap:14px;align-items:center}
  .balk button{font:inherit;font-weight:bold;padding:8px 16px;cursor:pointer;background:#d10f2f;color:#fff;border:0;border-radius:6px}
  @page{margin:14mm}
  @media print{
    .balk{display:none!important}
    h2,h3{break-after:avoid} tr,li,.kaart{break-inside:avoid}
    thead{display:table-header-group} a{text-decoration:none;color:#000}
  }
"""


def _inline(tekst: str) -> str:
    tekst = html.escape(tekst)
    tekst = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank">\1</a>', tekst)
    tekst = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", tekst)
    tekst = re.sub(r"`([^`]+)`", r"<code>\1</code>", tekst)
    return tekst


def _tabel(regels: list[str]) -> str:
    rijen = [[c.strip() for c in r.strip().strip("|").split("|")] for r in regels]
    rijen = [r for r in rijen if not all(set(c) <= {"-", ":"} for c in r)]
    if not rijen:
        return ""
    uit = ["<table>"]
    for i, r in enumerate(rijen):
        tag = "th" if i == 0 else "td"
        uit.append("<tr>" + "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in r) + "</tr>")
    uit.append("</table>")
    return "".join(uit)


def naar_html(md: str) -> str:
    out: list[str] = []
    lijst: list[str] = []
    tabel: list[str] = []

    def _sluit_lijst():
        if lijst:
            out.append("<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in lijst) + "</ul>")
            lijst.clear()

    def _sluit_tabel():
        if tabel:
            out.append(_tabel(tabel))
            tabel.clear()

    for regel in md.splitlines():
        s = regel.rstrip()
        if s.startswith("|") and "|" in s[1:]:
            _sluit_lijst()
            tabel.append(s)
            continue
        _sluit_tabel()
        if not s.strip():
            _sluit_lijst()
        elif s.startswith("### "):
            _sluit_lijst(); out.append(f"<h3>{_inline(s[4:])}</h3>")
        elif s.startswith("## "):
            _sluit_lijst(); out.append(f"<h2>{_inline(s[3:])}</h2>")
        elif s.startswith("# "):
            _sluit_lijst(); out.append(f"<h1>{_inline(s[2:])}</h1>")
        elif s.strip() == "---":
            _sluit_lijst(); out.append("<hr>")
        elif s.lstrip().startswith("- "):
            lijst.append(s.lstrip()[2:])
        else:
            _sluit_lijst(); out.append(f"<p>{_inline(s)}</p>")
    _sluit_lijst()
    _sluit_tabel()
    return "\n".join(out)


def pagina(titel: str, md: str, *, licht: bool = False, print_knop: bool = False) -> str:
    thema = _LICHT if licht else _DONKER
    kleur = "light" if licht else "dark"
    if print_knop:
        balk = ("<div class='balk'><button onclick='window.print()'>🖨 Afdrukken / Opslaan als PDF</button>"
                "<a href='/'>&larr; terug naar de tool</a></div>")
        # dialoog automatisch openen zodra de pagina (incl. logo) geladen is
        script = ("<script>addEventListener('load',function(){setTimeout(function(){"
                  "try{window.print()}catch(e){}},400)});</script>")
    else:
        balk = "<div class='balk'><a href='/'>&larr; terug naar de tool</a></div>"
        script = ""
    return (
        f"<!doctype html><html lang='nl'><head><meta charset='utf-8'>"
        f"<meta name='color-scheme' content='{kleur}'><link rel='icon' href='/static/logo.png'>"
        f"<title>{html.escape(titel)}</title><style>{thema}</style></head><body><main>"
        f"{balk}{naar_html(md)}</main>{script}</body></html>"
    )
