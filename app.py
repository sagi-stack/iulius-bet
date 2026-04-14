import streamlit as st
import json, math
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="Iulius Bet", page_icon="⚽", layout="wide")

DATA = Path("data")
DATA.mkdir(exist_ok=True)

if "lang" not in st.session_state:
    st.session_state.lang = "he"

lang = st.session_state.lang
he = lang == "he"
def t(h, e): return h if he else e

def load(name):
    p = DATA / f"{name}.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None

def poisson(lam, k):
    if lam <= 0: return 0
    return (lam**k * math.exp(-lam)) / math.factorial(min(k, 20))

def over_prob(lam, line):
    k = int(line + 0.5)
    return 1 - sum(poisson(lam, i) for i in range(k + 1))

def momentum(form, n):
    if not form: return 50.0
    r = form[-n:] if len(form) >= n else form
    mp = len(r) * 3
    ac = sum(x.get("points", 0) for x in r)
    return min(100, max(0, ac / mp * 100)) if mp > 0 else 50.0

def avg_scored(form, is_home):
    if not form: return 1.3
    m = [x for x in form if x.get("is_home") == is_home] or form
    m = m[-15:]
    total = sum(x.get("home_score", 0) if x.get("is_home") else x.get("away_score", 0) for x in m)
    return max(0.3, total / len(m))

def avg_conceded(form, is_home):
    if not form: return 1.3
    m = [x for x in form if x.get("is_home") == is_home] or form
    m = m[-15:]
    total = sum(x.get("away_score", 0) if x.get("is_home") else x.get("home_score", 0) for x in m)
    return max(0.3, total / len(m))

def predict(hid, aid, lid, hname, aname):
    hf  = load(f"form_{hid}_all") or load(f"form_{hid}_2025") or load(f"form_{hid}_2024") or []
    af  = load(f"form_{aid}_all") or load(f"form_{aid}_2025") or load(f"form_{aid}_2024") or []
    h2h = load(f"h2h_{hid}_{aid}") or load(f"h2h_{aid}_{hid}") or []
    hi  = load(f"injuries_{hid}") or []
    ai  = load(f"injuries_{aid}") or []
    std = load(f"standings_{lid}_2025") or load(f"standings_{lid}_2024") or []
    sm  = {r["team"]: r for r in std}
    hr  = sm.get(hname, {}); ar = sm.get(aname, {})
    hp  = hr.get("position", 10); ap = ar.get("position", 10)
    hpts= hr.get("points", 40);   apts= ar.get("points", 40)

    mom_h = (momentum(hf,2)*0.15 + momentum(hf,5)*0.45 + momentum(hf,10)*0.25 + momentum(hf,20)*0.15)
    mom_a = (momentum(af,2)*0.15 + momentum(af,5)*0.45 + momentum(af,10)*0.25 + momentum(af,20)*0.15)

    lam_h = max(0.3, (avg_scored(hf, True)  + avg_conceded(af, False)) / 2 * 1.08)
    lam_a = max(0.3, (avg_scored(af, False) + avg_conceded(hf, True))  / 2 * 0.95)

    tbl_h = max(0, min(100, ((20 - hp) / 19) * 100))
    tbl_a = max(0, min(100, ((20 - ap) / 19) * 100))

    h2h_pts = 0
    for m in h2h[-10:]:
        hs = m.get("home_score", 0) or 0
        as_ = m.get("away_score", 0) or 0
        ih = m.get("home_id") == hid
        h2h_pts += 3 if (ih and hs > as_) or (not ih and as_ > hs) else (1 if hs == as_ else 0)
    h2h_s = min(100, max(0, h2h_pts / (max(len(h2h[-10:]), 1) * 3) * 100)) if h2h else 50

    inj_h = max(20, 100 - len(hi) * 12)
    inj_a = max(20, 100 - len(ai) * 12)

    sc_h = mom_h*0.40 + tbl_h*0.15 + h2h_s*0.10 + inj_h*0.10 + 65*0.15 + lam_h/2.5*100*0.10
    sc_a = mom_a*0.40 + tbl_a*0.15 + (100-h2h_s)*0.10 + inj_a*0.10 + 40*0.15 + lam_a/2.5*100*0.10
    diff = sc_h - sc_a

    if   diff >= 15:  cls, pred = "home", t("ניצחון ביתי", "Home Win")
    elif diff >= 6:   cls, pred = "home", t("יתרון לבית", "Home Fav")
    elif diff >= -5:  cls, pred = "draw", t("תיקו", "Draw")
    elif diff >= -14: cls, pred = "away", t("יתרון אורחים", "Away Fav")
    else:             cls, pred = "away", t("ניצחון אורחים", "Away Win")
    conf = min(95, abs(diff) * 2 + 35)

    probs = {}; hw = dw = aw = 0.0
    for h in range(6):
        for a in range(6):
            p = poisson(lam_h, h) * poisson(lam_a, a)
            probs[f"{h}-{a}"] = round(p * 100, 1)
            if h > a: hw += p
            elif h == a: dw += p
            else: aw += p
    top = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:5]

    lh2 = lam_h * 0.42; la2 = lam_a * 0.42
    ht = {}; htw = htd = hta = 0.0
    for h in range(4):
        for a in range(4):
            p = poisson(lh2, h) * poisson(la2, a)
            ht[f"{h}-{a}"] = round(p * 100, 1)
            if h > a: htw += p
            elif h == a: htd += p
            else: hta += p
    ht_top = sorted(ht.items(), key=lambda x: x[1], reverse=True)[:4]

    total = lam_h + lam_a
    return {
        "cls": cls, "pred": pred, "conf": round(conf, 0),
        "lam_h": round(lam_h, 2), "lam_a": round(lam_a, 2),
        "top": top, "hw": round(hw*100,1), "dw": round(dw*100,1), "aw": round(aw*100,1),
        "ht_top": ht_top, "htw": round(htw*100,1), "htd": round(htd*100,1), "hta": round(hta*100,1),
        "o15": round(over_prob(total,1.5)*100,1),
        "o25": round(over_prob(total,2.5)*100,1),
        "o35": round(over_prob(total,3.5)*100,1),
        "btts": round((1-poisson(lam_h,0))*(1-poisson(lam_a,0))*100,1),
        "exp_corners": round(max(7, min(15, 10.5)), 1),
        "o95":  round(over_prob(10.5, 9.5)*100,1),
        "o105": round(over_prob(10.5,10.5)*100,1),
        "hp": hp, "ap": ap, "hpts": hpts, "apts": apts,
        "hinj": len(hi), "ainj": len(ai), "h2h_n": len(h2h),
    }

LEAGUES = {
    39:"Premier League", 140:"La Liga", 78:"Bundesliga",
    135:"Serie A", 61:"Ligue 1", 2:"Champions League",
    3:"Europa League", 40:"Championship", 271:"Liga Haal",
    71:"Brasileirao", 253:"MLS",
}

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚽ Iulius Bet")
    st.caption("Smart Betting Analysis")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🇮🇱 עב", use_container_width=True):
            st.session_state.lang = "he"; st.rerun()
    with c2:
        if st.button("🇬🇧 EN", use_container_width=True):
            st.session_state.lang = "en"; st.rerun()
    st.divider()
    lg_names = list(LEAGUES.values())
    sel_lgs = st.multiselect(t("ליגות", "Leagues"), lg_names, default=lg_names[:6])
    search = st.text_input(t("חפש קבוצה", "Search team"), "")
    st.divider()
    if st.button("🔄 " + t("עדכן נתונים", "Update data"), use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("p_"): del st.session_state[k]
        st.rerun()

# ── MAIN ─────────────────────────────────────────────────────────────────────
st.title("⚽ " + t("חיזויים למחזור הקרוב", "Upcoming Round Predictions"))
st.caption(t(
    "חיזוי אוטומטי לכל משחק: תוצאה סופית + מחצית + קרנות + Over/Under",
    "Auto prediction: Final score + Half-time + Corners + Over/Under"
))

fixtures = load("upcoming_fixtures")
if not fixtures:
    st.error(t(
        "אין נתונים! הרץ: python3 scripts/fetch_fixtures.py",
        "No data! Run: python3 scripts/fetch_fixtures.py"
    ))
    st.stop()

by_league = {}
for fx in fixtures:
    lid = fx.get("league_id")
    lg  = LEAGUES.get(lid, fx.get("league", "?"))
    if sel_lgs and lg not in sel_lgs: continue
    if search and search.lower() not in fx.get("home_name","").lower() and search.lower() not in fx.get("away_name","").lower(): continue
    by_league.setdefault(lg, []).append(fx)

total_matches = sum(len(v) for v in by_league.values())
st.caption(f"{total_matches} {t('משחקים', 'matches')}")

for lg, matches in by_league.items():
    st.subheader(f"⚽ {lg} — {len(matches)} {t('משחקים', 'matches')}")

    for fx in matches:
        mid   = str(fx.get("id", ""))
        hname = fx.get("home_name", "")
        aname = fx.get("away_name", "")
        hid   = fx.get("home_id")
        aid   = fx.get("away_id")
        lid   = fx.get("league_id")

        try:
            dt = datetime.fromisoformat(fx.get("date","").replace("Z","+00:00"))
            date_str = dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            date_str = fx.get("date","")[:16]

        pkey = "p_" + mid
        if pkey not in st.session_state:
            st.session_state[pkey] = predict(hid, aid, lid, hname, aname)
        p = st.session_state[pkey]

        cls  = p["cls"]
        conf = int(p["conf"])
        icon = {"home": "🏠", "draw": "🤝", "away": "✈️"}.get(cls, "")

        with st.container(border=True):
            # שורה 1: תאריך + חיזוי + ביטחון
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                st.caption(f"📅 {date_str}")
            with c2:
                st.markdown(f"**{icon} {p['pred']}**")
            with c3:
                st.caption(f"{conf}% {t('ביטחון','conf')}")

            # שורה 2: קבוצות + xG
            c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 3])
            with c1:
                st.markdown(f"**{hname}**")
                st.caption(f"#{p['hp']} | {p['hpts']}pt | 🚑{p['hinj']}")
            with c2:
                st.metric("xG", p["lam_h"])
            with c3:
                st.markdown("### vs")
            with c4:
                st.metric("xG", p["lam_a"])
            with c5:
                st.markdown(f"**{aname}**")
                st.caption(f"#{p['ap']} | {p['apts']}pt | 🚑{p['ainj']}")

            st.progress(conf / 100)

            # טאבים
            tab1, tab2, tab3 = st.tabs([
                t("⚽ תוצאה סופית", "⚽ Final Score"),
                t("⏱️ מחצית", "⏱️ Half-time"),
                t("📊 סטטיסטיקות", "📊 Statistics"),
            ])

            with tab1:
                c1, c2, c3 = st.columns(3)
                with c1: st.metric(t("ניצחון בית","Home Win"), f"{p['hw']}%")
                with c2: st.metric(t("תיקו","Draw"), f"{p['dw']}%")
                with c3: st.metric(t("ניצחון אורחים","Away Win"), f"{p['aw']}%")
                st.caption(t("תוצאות הכי סבירות:","Most likely scores:"))
                cols = st.columns(5)
                for i, (sc, prob) in enumerate(p["top"]):
                    with cols[i]:
                        st.metric(sc, f"{prob}%")

            with tab2:
                c1, c2, c3 = st.columns(3)
                with c1: st.metric(t("בית מובילה","Home leads"), f"{p['htw']}%")
                with c2: st.metric(t("שוויון","Level"), f"{p['htd']}%")
                with c3: st.metric(t("אורחים מובילים","Away leads"), f"{p['hta']}%")
                st.caption(t("תוצאות מחצית:","HT scores:"))
                cols = st.columns(4)
                for i, (sc, prob) in enumerate(p["ht_top"]):
                    with cols[i]:
                        st.metric(sc, f"{prob}%")

            with tab3:
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("O1.5", f"{p['o15']}%")
                with c2: st.metric("O2.5", f"{p['o25']}%")
                with c3: st.metric("O3.5", f"{p['o35']}%")
                with c4: st.metric("BTTS", f"{p['btts']}%")
                c5, c6, c7 = st.columns(3)
                with c5: st.metric(t("קרנות צפויות","Exp corners"), p["exp_corners"])
                with c6: st.metric("O9.5", f"{p['o95']}%")
                with c7: st.metric("O10.5", f"{p['o105']}%")
