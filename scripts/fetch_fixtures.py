"""
Iulius Bet - Full Data Fetch
5 שנות היסטוריה (2021-2025) + משחקים 7 ימים קדימה
"""
import requests, json, time
from pathlib import Path
from datetime import datetime, timedelta

API_KEY = "4a87b9fa556109b4d09c7e351496ba30"
BASE    = "https://v3.football.api-sports.io"
HDR     = {"x-apisports-key": API_KEY}
DATA    = Path(__file__).parent.parent / "data"
DATA.mkdir(exist_ok=True)

LEAGUES = {
    39:  "Premier League",
    140: "La Liga",
    78:  "Bundesliga",
    135: "Serie A",
    61:  "Ligue 1",
    2:   "Champions League",
    3:   "Europa League",
    40:  "Championship",
    271: "Liga Haal",
    71:  "Brasileirao",
    253: "MLS",
}

HISTORY_SEASONS = [2021, 2022, 2023, 2024, 2025]
CURRENT_SEASON  = 2025
req_count = 0

def get(ep, params={}):
    global req_count
    try:
        r = requests.get(f"{BASE}/{ep}", headers=HDR, params=params, timeout=15)
        req_count += 1
        time.sleep(0.35)
        if r.status_code == 200:
            rem = r.headers.get("x-ratelimit-requests-remaining","?")
            if req_count % 30 == 0:
                print(f"    [API: {req_count} בוצעו | {rem} נותרו]")
            return r.json().get("response", [])
        if r.status_code == 429:
            print("  ⏳ Rate limit — ממתין 60 שניות...")
            time.sleep(60)
            return get(ep, params)
        print(f"  ERR {r.status_code} — {ep}")
        return []
    except Exception as e:
        print(f"  EXC: {e}")
        return []

def save(name, data):
    with open(DATA / f"{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load(name):
    p = DATA / f"{name}.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None

def ex(name):
    return (DATA / f"{name}.json").exists()

def sep(title):
    print("\n" + "="*55)
    print(f"  {title}")
    print("="*55)

# ── שלב 1: טבלאות 5 עונות ────────────────────────────────────
def fetch_standings():
    sep("📊 שלב 1: טבלאות — 5 עונות × 11 ליגות")
    for lid, name in LEAGUES.items():
        for season in HISTORY_SEASONS:
            fname = f"standings_{lid}_{season}"
            if ex(fname):
                continue
            data = get("standings", {"league": lid, "season": season})
            if not data:
                continue
            out = []
            try:
                for row in data[0]["league"]["standings"][0]:
                    t = row.get("team", {})
                    out.append({
                        "position": row.get("rank"),
                        "team_id":  t.get("id"),
                        "team":     t.get("name", ""),
                        "points":   row.get("points", 0),
                        "won":      row.get("all", {}).get("win", 0),
                        "draw":     row.get("all", {}).get("draw", 0),
                        "lost":     row.get("all", {}).get("lose", 0),
                        "gf":       row.get("all", {}).get("goals", {}).get("for", 0),
                        "ga":       row.get("all", {}).get("goals", {}).get("against", 0),
                        "gd":       row.get("goalsDiff", 0),
                        "form":     row.get("form", ""),
                    })
            except Exception:
                continue
            save(fname, out)
            print(f"  ✅ {name} {season}: {len(out)} קבוצות")

# ── שלב 2: משחקים עתידיים — 7 ימים קדימה ────────────────────
def fetch_upcoming():
    sep("⚽ שלב 2: משחקים עתידיים — 7 ימים קדימה")
    today = datetime.now().strftime("%Y-%m-%d")
    end   = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    print(f"  מ-{today} עד {end}")

    all_fx = []
    for lid, name in LEAGUES.items():
        data = get("fixtures", {
            "league":  lid,
            "season":  CURRENT_SEASON,
            "from":    today,
            "to":      end,
            "status":  "NS",
        })
        for m in data:
            fix   = m.get("fixture", {})
            teams = m.get("teams", {})
            all_fx.append({
                "id":        fix.get("id"),
                "league_id": lid,
                "league":    name,
                "home_id":   teams.get("home", {}).get("id"),
                "home_name": teams.get("home", {}).get("name", ""),
                "away_id":   teams.get("away", {}).get("id"),
                "away_name": teams.get("away", {}).get("name", ""),
                "date":      fix.get("date", ""),
                "timestamp": fix.get("timestamp", 0),
            })
        if data:
            print(f"  ✅ {name}: {len(data)} משחקים")
        else:
            print(f"  — {name}: אין משחקים השבוע")

    all_fx.sort(key=lambda x: x.get("timestamp", 0))
    save("upcoming_fixtures", all_fx)
    print(f"\n  סהכ: {len(all_fx)} משחקים עתידיים")
    return all_fx

# ── שלב 3: היסטוריה מלאה לכל קבוצה — 5 עונות ───────────────
def fetch_team_history(all_fx):
    sep("📈 שלב 3: היסטוריה מלאה — 5 עונות לכל קבוצה")

    # אסוף כל team_id מהמשחקים העתידיים
    team_ids = set()
    for fx in all_fx:
        if fx.get("home_id"): team_ids.add(fx["home_id"])
        if fx.get("away_id"): team_ids.add(fx["away_id"])
    print(f"  {len(team_ids)} קבוצות לשאוב")

    for tid in team_ids:
        # בדוק אם כבר יש קובץ מאוחד
        if ex(f"form_{tid}_all"):
            continue

        all_results = []
        for season in HISTORY_SEASONS:
            fname = f"form_{tid}_{season}"
            if ex(fname):
                cached = load(fname)
                if cached:
                    all_results.extend(cached)
                continue

            data = get("fixtures", {
                "team":   tid,
                "season": season,
                "status": "FT",
            })

            season_res = []
            for m in data:
                fix   = m.get("fixture", {})
                teams = m.get("teams", {})
                goals = m.get("goals", {})
                stats = m.get("statistics", [])

                is_home = teams.get("home", {}).get("id") == tid
                hg = goals.get("home", 0) or 0
                ag = goals.get("away", 0) or 0
                pts = 3 if (is_home and hg>ag) or (not is_home and ag>hg) else (1 if hg==ag else 0)

                # קרנות
                corners_for = corners_ag = 0
                for ts in stats:
                    t_id = ts.get("team", {}).get("id")
                    sv   = {s["type"]: s["value"] for s in ts.get("statistics", [])}
                    corn = int(sv.get("Corner Kicks", 0) or 0)
                    if t_id == tid: corners_for = corn
                    else:           corners_ag  = corn

                season_res.append({
                    "date":        fix.get("date", ""),
                    "season":      season,
                    "home":        teams.get("home", {}).get("name", ""),
                    "away":        teams.get("away", {}).get("name", ""),
                    "home_id":     teams.get("home", {}).get("id"),
                    "away_id":     teams.get("away", {}).get("id"),
                    "home_score":  hg,
                    "away_score":  ag,
                    "points":      pts,
                    "is_home":     is_home,
                    "corners_for": corners_for,
                    "corners_ag":  corners_ag,
                })

            save(fname, season_res)
            all_results.extend(season_res)

        # שמור קובץ מאוחד מכל 5 עונות
        all_results.sort(key=lambda x: x.get("date", ""))
        save(f"form_{tid}_all", all_results)

    print(f"  ✅ היסטוריה נשמרה לכל הקבוצות")

# ── שלב 4: H2H ────────────────────────────────────────────────
def fetch_h2h(all_fx):
    sep("🆚 שלב 4: עימותים ישירים H2H")
    pairs = {}
    for fx in all_fx:
        hid = fx.get("home_id")
        aid = fx.get("away_id")
        if hid and aid:
            key = tuple(sorted([hid, aid]))
            pairs[key] = (hid, aid)

    print(f"  {len(pairs)} זוגות")
    for (a, b), (home_id, away_id) in pairs.items():
        fname = f"h2h_{home_id}_{away_id}"
        if ex(fname): continue
        data = get("fixtures/headtohead", {"h2h": f"{a}-{b}", "last": 20})
        results = []
        for m in data:
            fix   = m.get("fixture", {})
            teams = m.get("teams", {})
            goals = m.get("goals", {})
            results.append({
                "date":       fix.get("date", ""),
                "home":       teams.get("home", {}).get("name", ""),
                "away":       teams.get("away", {}).get("name", ""),
                "home_id":    teams.get("home", {}).get("id"),
                "away_id":    teams.get("away", {}).get("id"),
                "home_score": goals.get("home", 0),
                "away_score": goals.get("away", 0),
            })
        save(fname, results)
    print(f"  ✅ H2H נשמר")

# ── שלב 5: פציעות ─────────────────────────────────────────────
def fetch_injuries(all_fx):
    sep("🚑 שלב 5: פציעות עדכניות")
    team_ids = set()
    for fx in all_fx:
        if fx.get("home_id"): team_ids.add(fx["home_id"])
        if fx.get("away_id"): team_ids.add(fx["away_id"])

    for tid in team_ids:
        data = get("injuries", {"team": tid, "season": CURRENT_SEASON})
        injured = []
        for p in data:
            player = p.get("player", {})
            injured.append({
                "name":     player.get("name", ""),
                "position": player.get("type", ""),
                "reason":   p.get("fixture", {}).get("status", {}).get("long", ""),
            })
        save(f"injuries_{tid}", injured)
    print(f"  ✅ פציעות ל-{len(team_ids)} קבוצות")

# ── שלב 6: מלכי שערים ────────────────────────────────────────
def fetch_scorers():
    sep("🥅 שלב 6: מלכי שערים")
    for lid, name in LEAGUES.items():
        fname = f"scorers_{lid}_{CURRENT_SEASON}"
        if ex(fname): continue
        data = get("players/topscorers", {"league": lid, "season": CURRENT_SEASON})
        out  = []
        for item in data:
            p    = item.get("player", {})
            stat = item.get("statistics", [{}])[0]
            team = stat.get("team", {})
            out.append({
                "name":    p.get("name", ""),
                "team":    team.get("name", ""),
                "team_id": team.get("id"),
                "goals":   stat.get("goals", {}).get("total", 0) or 0,
                "assists": stat.get("goals", {}).get("assists", 0) or 0,
                "played":  stat.get("games", {}).get("appearences", 0) or 0,
            })
        save(fname, out)
        print(f"  ✅ {name}: {len(out)} שחקנים")

# ── MAIN ──────────────────────────────────────────────────────
def main():
    print("\n" + "★"*25)
    print("  IULIUS BET — Full Data Fetch")
    print(f"  תאריך היום: {datetime.now().strftime('%d/%m/%Y')}")
    print(f"  עונה נוכחית: {CURRENT_SEASON}")
    print(f"  היסטוריה: {HISTORY_SEASONS}")
    print("★"*25)

    # בדוק חיבור
    test = get("status")
    if not test:
        print("בעיה בחיבור")
        return
    acc  = test[0] if isinstance(test, list) and len(test) > 0 else {}
    reqs = acc.get("requests", {}) if acc else {}
    print(f"\n✅ מחובר! נותרו היום: {reqs.get('current','?')} / {reqs.get('limit_day','?')}")

    start = datetime.now()

    fetch_standings()
    all_fx = fetch_upcoming()
    fetch_team_history(all_fx)
    fetch_h2h(all_fx)
    fetch_injuries(all_fx)
    fetch_scorers()

    elapsed = (datetime.now() - start).seconds // 60
    files   = len(list(DATA.glob("*.json")))

    print("\n" + "★"*25)
    print(f"  הכל מוכן! ⚽")
    print(f"  זמן: {elapsed} דקות")
    print(f"  קבצים: {files}")
    print(f"  בקשות API: {req_count}")
    print("★"*25)
    print("\n💡 רענן את הדפדפן — המשחקים יופיעו!")

if __name__ == "__main__":
    main()
