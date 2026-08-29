"""Zet het overzicht om naar platte tekst / markdown om in de podcastnotities te plakken."""

from __future__ import annotations

from . import ploeg
from .merk import app_naam as _app_naam


def _score(v) -> str:
    return f"{v:.2f}" if isinstance(v, (int, float)) else "–"


def _delta(v) -> str:
    if v is None or v == 0:
        return ""
    return f" (+{v})" if v > 0 else f" ({v})"


def _opstelling_regels(zijde: dict) -> list[str]:
    if not zijde or not zijde.get("basis"):
        return ["_geen opstelling beschikbaar_"]
    regels = []
    basis = ", ".join(
        f"{p['kort']}"
        + (f" ({p['rating']:.1f})" if p.get("rating") is not None else "")
        for p in zijde["basis"]
    )
    regels.append(f"**Basis ({zijde.get('formatie') or '?'}):** {basis}")
    bank = zijde.get("bank") or []
    if bank:
        inv = [p for p in bank if p.get("minuten")]
        rest = [p for p in bank if not p.get("minuten")]
        if inv:
            regels.append("**Ingevallen:** " + ", ".join(f"{p['kort']} ({p['minuten']}′)" for p in inv))
        if rest:
            regels.append("**Bank:** " + ", ".join(p["kort"] for p in rest))
    return regels


def naar_markdown(o: dict) -> str:
    r: list[str] = []
    so = o.get("sofascore") or {}
    vorige = so.get("vorige") or {}
    volgende = so.get("volgende") or {}
    vb = so.get("voorbeschouwing") or {}

    _titel = ploeg.actieve().get("naam") if ploeg.is_gekozen() else _app_naam()
    r.append(f"# {_titel} — voorbereiding\n")

    # 1. Vorige wedstrijd
    if vorige:
        t, u = vorige["thuis"], vorige["uit"]
        r.append(f"## 1. Vorige wedstrijd — {vorige.get('competitie','')}"
                 + (f" (speeldag {vorige['ronde']})" if vorige.get("ronde") else ""))
        r.append(f"\n**{t['naam']} {t.get('score','?')} – {u.get('score','?')} {u['naam']}**  ")
        r.append(f"{vorige.get('datum','')} · formatie {vorige.get('formatie','?')}  ")
        if vorige.get("url"):
            r.append(f"[Match op Sofascore]({vorige['url']})")

        thuis_naam = vorige["thuis"]["naam"]
        uit_naam = vorige["uit"]["naam"]
        ant_thuis = vorige.get("antwerp_thuis")
        opst = o.get("opstellingen") or {}
        r.append(f"\n**Opstelling {thuis_naam if ant_thuis else uit_naam}:** (via {opst.get('bron', 'Sofascore')})")
        r.extend("- " + regel for regel in _opstelling_regels(opst.get("vorige_antwerp") or {}))
        r.append(f"\n**Opstelling {uit_naam if ant_thuis else thuis_naam}:**")
        r.extend("- " + regel for regel in _opstelling_regels(opst.get("vorige_tegenstander") or {}))

        if vorige.get("tijdlijn"):
            r.append("\n**Wedstrijdverloop:**\n")
            r.append(f"| {thuis_naam} | ' | {uit_naam} |")
            r.append("|---|:-:|---|")
            for e in vorige["tijdlijn"]:
                stand = f" `{e['stand']}`" if e.get("stand") else ""
                links = f"{e['tekst']}{stand}" if e.get("thuis") else ""
                rechts = "" if e.get("thuis") else f"{e['tekst']}{stand}"
                r.append(f"| {links} | {e['minuut']}' | {rechts} |")
        if vorige.get("statistiek"):
            r.append("\n**Teamstatistieken:**\n")
            r.append(f"| {thuis_naam} | | {uit_naam} |")
            r.append("|--:|:-:|:--|")
            for grp in vorige["statistiek"]:
                for rij in grp["rijen"]:
                    r.append(f"| {rij['thuis']} | {rij['naam']} | {rij['uit']} |")

        if vorige.get("ontbrekend"):
            namen = ", ".join(f"{m['naam']} ({m['reden']})" for m in vorige["ontbrekend"] if m.get("naam"))
            if namen:
                r.append(f"\n_Afwezig: {namen}_")

        # spelerscores horen bij de vorige wedstrijd
        if o.get("scoretabel"):
            links = o.get("score_links") or {}
            bronnen = " · ".join(
                f"[{naam}]({links[key]})"
                for naam, key in (("Sofascore", "sofascore"), ("FotMob", "fotmob"), ("WhoScored", "whoscored"))
                if links.get(key)
            )
            r.append(f"\n**Spelerscores** (open de match: {bronnen})\n")
            r.append("| Speler | Min | Sofascore | FotMob | WhoScored | Gemiddelde |")
            r.append("|---|---:|---:|---:|---:|---:|")
            for rij in o["scoretabel"]:
                naam = rij["speler"] + (" (in)" if rij["invaller"] else "")
                r.append(f"| {naam} | {rij['minuten'] or ''} | {_score(rij['sofascore'])} | "
                         f"{_score(rij['fotmob'])} | {_score(rij['whoscored'])} | {_score(rij['gemiddelde'])} |")

    # 2. Voorbeschouwing
    if volgende:
        teg = (volgende.get("tegenstander") or {}).get("naam", "?")
        thuisuit = "thuis" if volgende.get("antwerp_thuis") else "uit"
        r.append(f"\n## 2. Voorbeschouwing — {teg} ({thuisuit})")
        r.append(f"\n{volgende.get('datum','')} · {volgende.get('competitie','')}  ")
        if volgende.get("url"):
            r.append(f"[Match op Sofascore]({volgende['url']})")

        ref = vb.get("scheidsrechter")
        if ref:
            r.append(f"\n**Scheidsrechter:** {ref['naam']}"
                     + (f" ({ref['land']})" if ref.get("land") else "")
                     + f" — {ref['matchen']} matchen, {ref['geel_per_match']} geel & "
                     f"{ref['rood_per_match']} rood per match.")

        rk = vb.get("reeksen") or {}
        if rk.get("algemeen") or rk.get("onderling"):
            r.append("\n**Reeksen & mijlpalen:**")
            for x in rk.get("algemeen", []):
                r.append(f"- {x['wie']}: {x['tekst']} — {x['waarde']}")
            for x in rk.get("onderling", []):
                r.append(f"- (onderling) {x['wie']}: {x['tekst']} — {x['waarde']}")

        opp_lineup = (o.get("opstellingen") or {}).get("volgende_tegenstander")
        if opp_lineup:
            detail = opp_lineup.get("herkomst_detail", "")
            r.append(f"\n**Opstelling {teg}** — {opp_lineup.get('herkomst', '')}"
                     + (f" ({detail})" if detail else "") + ":")
            r.extend("- " + regel for regel in _opstelling_regels(opp_lineup))

        vd = vb.get("vorm_detail") or {}
        if vd:
            for wie, blk in (("Antwerp", vd.get("antwerp", {})), (teg, vd.get("tegenstander", {}))):
                l5 = blk.get("laatste5") or {}
                r.append(f"\n- Vorm {wie}: {l5.get('vorm', '?')} ({l5.get('gf', '?')}–{l5.get('ga', '?')}, "
                         f"{l5.get('clean_sheets', 0)} clean sheets) · {blk.get('ongeslagen', 0)}x ongeslagen · "
                         f"{blk.get('scoren_op_rij', 0)}x op rij gescoord")

        h = vb.get("h2h") or {}
        if h.get("aantal"):
            r.append(f"\n**Onderlinge duels (alle {h['aantal']}):** "
                     f"{h['antwerp_winst']}× Antwerp · {h['gelijk']}× gelijk · {h['tegenstander_winst']}× {teg}")
            if h.get("grootste_zege"):
                gz = h["grootste_zege"]
                r.append(f"- Grootste zege: {gz['tekst']} ({(gz.get('datum') or '')[:10]}, {gz.get('competitie','')})")
            if h.get("grootste_nederlaag"):
                gn = h["grootste_nederlaag"]
                r.append(f"- Grootste nederlaag: {gn['tekst']} ({(gn.get('datum') or '')[:10]}, {gn.get('competitie','')})")

        if vb.get("klassement"):
            r.append("\n**Klassement:**\n")
            r.append("| # | Ploeg | Gesp. | W | G | V | DP+ | DP− | Saldo | Ptn |")
            r.append("|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|")
            for rij in vb["klassement"]:
                merk = " **(ANT)**" if rij["antwerp"] else f" **({teg})**" if rij["tegenstander"] else ""
                r.append(f"| {rij['positie']} | {rij['team']}{merk} | {rij['gespeeld']} | {rij['gewonnen']} | "
                         f"{rij['gelijk']} | {rij['verloren']} | {rij['dp_voor']} | {rij['dp_tegen']} | "
                         f"{rij['saldo']} | {rij['punten']} |")

        if vb.get("tegenstander_vorm_matches"):
            r.append(f"\n**Laatste resultaten {teg}:**")
            for m in vb["tegenstander_vorm_matches"]:
                r.append(f"- {(m.get('datum') or '')[:10]} {m['tekst']} ({m.get('competitie','')})")

        sh = vb.get("tegenstander_sterkhouders") or {}
        if sh:
            r.append(f"\n**Sterkhouders {teg}:**")
            for kat, titel in (("rating", "Beste rating"), ("goals", "Meeste goals"), ("assists", "Meeste assists")):
                spelers = ", ".join(f"{s['naam']} ({s['waarde']})" for s in sh.get(kat, []))
                if spelers:
                    r.append(f"- {titel}: {spelers}")

        ts = vb.get("topschutters") or {}
        for kat, titel in (("goals", "Pro League topschutters"), ("assists", "Pro League assists")):
            lijst = ts.get(kat) or []
            if lijst:
                tekst = ", ".join(
                    f"{s['naam']} ({s['waarde']})" + (" [ANT]" if s.get("antwerp") else "")
                    for s in lijst[:8]
                )
                r.append(f"\n**{titel}:** {tekst}")

        ve = o.get("voorbeschouwing_extra") or {}
        ou = ve.get("uitval") or {}
        if ou.get("geschorst"):
            r.append(f"\n🚫 **{teg} geschorst:** "
                     + " · ".join(f"{p['speler']}" + (f" ({p['reden']})" if p.get('reden') else "")
                                  for p in ou["geschorst"]))
        if ou.get("geblesseerd"):
            r.append(f"🤕 **{teg} geblesseerd:** "
                     + " · ".join(f"{p['speler']}" + (f" ({p['reden']})" if p.get('reden') else "")
                                  for p in ou["geblesseerd"]))
        con = ve.get("connecties") or {}
        if con.get("ex_antwerp_bij_tegenstander"):
            r.append("\n**Ex-Antwerp, nu bij " + teg + ":** "
                     + ", ".join(f"{c['speler']}" for c in con["ex_antwerp_bij_tegenstander"]))
        if con.get("ex_tegenstander_bij_antwerp"):
            r.append("**Ex-" + teg + ", nu bij Antwerp:** "
                     + ", ".join(f"{c['speler']}" for c in con["ex_tegenstander_bij_antwerp"]))

    # 3. Statistieken
    if o.get("stattabel"):
        tm = o.get("transfermarkt") or {}
        seizoen = tm.get("seizoen", "")
        r.append(f"\n## 3. Statistieken seizoen {seizoen}\n")
        uitval = tm.get("uitval") or {}
        if uitval.get("geschorst"):
            namen = " · ".join(
                f"{p['speler']}" + (f" ({p['reden']})" if p.get("reden") else "")
                for p in uitval["geschorst"]
            )
            r.append(f"🚫 **Geschorst voor de volgende wedstrijd:** {namen}")
        if uitval.get("geblesseerd"):
            namen = " · ".join(
                f"{p['speler']}" + (f" ({p['reden']})" if p.get("reden") else "")
                for p in uitval["geblesseerd"]
            )
            r.append(f"🤕 **Geblesseerd:** {namen}")
        r.append("\n| Speler | Gem. rating | Wedstrijden | Goals | Assists | Geel | Rood | Minuten |")
        r.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for rij in o["stattabel"]:
            gr = f"{rij['gem_rating']:.2f}" if rij.get("gem_rating") is not None else "–"
            merk = " ⚠️geschorst" if rij.get("geschorst") else (" 🤕" if rij.get("geblesseerd") else "")
            r.append(f"| {rij['speler']}{merk} | {gr} | {rij['wedstrijden']}{_delta(rij['d_wedstrijden'])} | "
                     f"{rij['goals']}{_delta(rij['d_goals'])} | {rij['assists']}{_delta(rij['d_assists'])} | "
                     f"{rij['geel']}{_delta(rij['d_geel'])} | {rij['rood']}{_delta(rij['d_rood'])} | "
                     f"{rij['minuten']}{_delta(rij['d_minuten'])} |")

    t = o.get("tijdstippen") or {}
    r.append(f"\n---\n_Sofascore: {t.get('sofascore') or '–'} · FotMob: {t.get('fotmob') or '–'} · "
             f"Transfermarkt: {t.get('transfermarkt') or '–'}_")
    return "\n".join(r)
