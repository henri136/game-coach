#!/usr/bin/env python3
"""Berechnet die Waffen-Meta aus den offenen stat.ink-Rohdaten (CC BY 4.0).

Läuft wöchentlich als GitHub Action und schreibt waffen-meta.json –
die Splatoon-Coach-App lädt diese Datei beim Start und zeigt so immer
aktuelle Zahlen, ganz ohne fremde Hilfe.
"""
import csv, io, json, ssl, sys, urllib.request
from datetime import date, timedelta

TAGE = 14
MIN_WAFFE = 300
MIN_KARTE = 100
BASIS = "https://dl-stats.stats.ink/splatoon-3/battle-results-csv"

STAGE_MAP = {"yunohana": "Sengkluft", "gonzui": "Streifenaal-Straße", "kinmedai": "Pinakoithek", "mategai": "Schwertmuschel-Reservoir", "namero": "Aalstahl-Metallwerk", "yagara": "Schnapperchen-Basar", "masaba": "Makrelenbrücke", "mahimahi": "Mahi-Mahi-Resort", "zatou": "Cetacea-Markt", "chozame": "Störwerft", "amabi": "Perlmutt-Akademie", "sumeshi": "Flunder-Funpark", "hirame": "Schollensiedlung", "kusaya": "Kusaya-Quellen", "manta": "Manta Maria", "nampla": "Um'ami-Ruinen", "taraport": "Talerfisch & Pock", "kombu": "Buckelwal-Piste", "takaashi": "Seespinnen-Skyline", "ohyo": "Frachtschiff Schwerfisch", "negitoro": "Blauflossen-Depot", "baigai": "ROM & RAMen", "kajiki": "La Ola Airport", "ryugu": "Bahnhof Lemuria", "grand_arena": "Splatsville Grand Arena", "decaline": "Dekabahnstation"}

def hole(url):
    req = urllib.request.Request(url, headers={"User-Agent": "henri-splatoon-coach-meta/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def waffen_namen():
    liste = json.loads(hole("https://stat.ink/api/v3/weapon?full=1"))
    m = {}
    for w in liste:
        de = (w.get("name") or {}).get("de_DE") or (w.get("name") or {}).get("en_US")
        if not de: continue
        m[w["key"]] = de
        for a in (w.get("aliases") or []):
            m.setdefault(a, de)
    return m

def main():
    key2de = waffen_namen()
    heute = date.today()
    tage = [heute - timedelta(days=i) for i in range(1, TAGE + 1)]
    W, SW, SD = {}, {}, {}
    battles = 0
    geladen = []
    for t in tage:
        url = f"{BASIS}/{t.year}/{t.month:02d}/{t.isoformat()}.csv"
        try:
            roh = hole(url)
        except Exception as e:
            print(f"überspringe {t}: {e}", file=sys.stderr)
            continue
        geladen.append(t)
        for row in csv.reader(io.StringIO(roh.decode("utf-8", "replace"))):
            if not row or row[0].startswith("#") or len(row) < 90: continue
            win = row[7]
            if win not in ("alpha", "bravo"): continue
            battles += 1
            stage = STAGE_MAP.get(row[5])
            for i, team in [(21, "alpha"), (29, "alpha"), (37, "alpha"), (45, "alpha"),
                            (53, "bravo"), (61, "bravo"), (69, "bravo"), (77, "bravo")]:
                de = key2de.get(row[i])
                if not de: continue
                try: kill, assist, death = int(row[i+2] or 0), int(row[i+3] or 0), int(row[i+4] or 0)
                except ValueError: continue
                sieg = 1 if team == win else 0
                s = W.setdefault(de, [0, 0, 0, 0, 0])
                s[0] += 1; s[1] += sieg; s[2] += kill; s[3] += death; s[4] += assist
                if stage:
                    sw = SW.setdefault(stage, {}).setdefault(de, [0, 0])
                    sw[0] += 1; sw[1] += sieg
                    sd = SD.setdefault(stage, [0, 0])
                    sd[0] += 1; sd[1] += death
    if battles < 1000:
        print(f"Nur {battles} Battles geladen – behalte alte Datei.", file=sys.stderr)
        sys.exit(0)
    waffen = {de: {"n": n, "wr": round(w / n, 3), "k": round(k / n, 1), "d": round(d / n, 1), "a": round(a / n, 1)}
              for de, (n, w, k, d, a) in W.items() if n >= MIN_WAFFE}
    karten = {}
    for stage, ws in SW.items():
        top = sorted(((de, v[1] / v[0]) for de, v in ws.items() if v[0] >= MIN_KARTE), key=lambda x: -x[1])[:3]
        sp, dth = SD[stage]
        karten[stage] = {"top": [{"w": de, "wr": round(wr, 3)} for de, wr in top], "d": round(dth / sp, 1)}
    fmt = lambda d: f"{d.day}.{d.month}."
    meta = {"erzeugt": heute.isoformat(),
            "stand": f"{fmt(min(geladen))} – {fmt(max(geladen))}{max(geladen).year}",
            "battles": battles, "spieler": sum(v[0] for v in W.values()),
            "waffen": waffen, "karten": karten}
    with open("waffen-meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    print(f"OK: {battles} Battles, {len(waffen)} Waffen, {len(karten)} Karten, Stand {meta['stand']}")

if __name__ == "__main__":
    main()
