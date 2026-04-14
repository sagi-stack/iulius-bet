"""
מודול חיזוי קרנות ושערים מדויקים
מבוסס על סטטיסטיקות היסטוריות + מומנטום
"""
import math

# ממוצעי ליגה לקרנות
LEAGUE_CORNERS_AVG = {
    39:  10.8,  # Premier League
    140: 10.2,  # La Liga
    78:  10.5,  # Bundesliga
    135: 10.1,  # Serie A
    61:  10.3,  # Ligue 1
    2:   10.6,  # UCL
    3:   10.4,  # UEL
    40:  11.2,  # Championship
    271: 9.8,   # ליגת העל
    71:  10.0,  # Brasileirao
    253: 9.9,   # MLS
}

def poisson_prob(lam, k):
    """הסתברות פואסון — כמה שערים/קרנות"""
    if lam <= 0: return 0
    return (lam**k * math.exp(-lam)) / math.factorial(k)

def predict_goals(home_form, away_form, h_pos=10, a_pos=10, league_id=39):
    """
    חיזוי שערים מדויק:
    - מחשב xG משוער מהפורמה
    - מחזיר הסתברות לכל תוצאה אפשרית
    """
    # חשב ממוצע שערים מהפורמה
    def avg_goals_scored(form, is_home):
        matches = [m for m in (form or []) if m.get("is_home")==is_home]
        if not matches: matches = form or []
        if not matches: return 1.4
        total = sum(m.get("home_score",0) if m.get("is_home") else m.get("away_score",0) for m in matches[-10:])
        return max(0.3, total / min(len(matches), 10))

    def avg_goals_conceded(form, is_home):
        matches = [m for m in (form or []) if m.get("is_home")==is_home]
        if not matches: matches = form or []
        if not matches: return 1.3
        total = sum(m.get("away_score",0) if m.get("is_home") else m.get("home_score",0) for m in matches[-10:])
        return max(0.3, total / min(len(matches), 10))

    # Lambda = ממוצע שערים צפויים
    home_att = avg_goals_scored(home_form, True)
    home_def = avg_goals_conceded(home_form, True)
    away_att = avg_goals_scored(away_form, False)
    away_def = avg_goals_conceded(away_form, False)

    # יתרון בית: +8%
    lambda_home = (home_att + away_def) / 2 * 1.08
    lambda_away = (away_att + home_def) / 2 * 0.95

    # כיוונון לפי מיקום בטבלה
    table_factor_h = 1.0 + (10 - h_pos) * 0.01
    table_factor_a = 1.0 + (10 - a_pos) * 0.01
    lambda_home = max(0.3, lambda_home * table_factor_h)
    lambda_away = max(0.3, lambda_away * table_factor_a)

    # חשב הסתברויות לכל תוצאה
    max_goals = 6
    scores = {}
    home_win = draw = away_win = 0

    for h in range(max_goals+1):
        for a in range(max_goals+1):
            prob = poisson_prob(lambda_home, h) * poisson_prob(lambda_away, a)
            scores[f"{h}-{a}"] = round(prob * 100, 1)
            if h > a: home_win += prob
            elif h == a: draw += prob
            else: away_win += prob

    # Top 6 results
    top_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:8]

    # Over/Under goals
    total_lambda = lambda_home + lambda_away
    over_15 = 1 - sum(poisson_prob(total_lambda, k) for k in range(2))
    over_25 = 1 - sum(poisson_prob(total_lambda, k) for k in range(3))
    over_35 = 1 - sum(poisson_prob(total_lambda, k) for k in range(4))
    over_45 = 1 - sum(poisson_prob(total_lambda, k) for k in range(5))

    # BTTS
    btts = (1 - poisson_prob(lambda_home, 0)) * (1 - poisson_prob(lambda_away, 0))

    return {
        "lambda_home":    round(lambda_home, 2),
        "lambda_away":    round(lambda_away, 2),
        "expected_total": round(total_lambda, 2),
        "top_scores":     top_scores,
        "home_win_pct":   round(home_win * 100, 1),
        "draw_pct":       round(draw * 100, 1),
        "away_win_pct":   round(away_win * 100, 1),
        "over_15":        round(over_15 * 100, 1),
        "over_25":        round(over_25 * 100, 1),
        "over_35":        round(over_35 * 100, 1),
        "over_45":        round(over_45 * 100, 1),
        "btts":           round(btts * 100, 1),
        "most_likely":    top_scores[0][0] if top_scores else "1-1",
        "most_likely_pct":top_scores[0][1] if top_scores else 0,
    }


def predict_corners(home_form, away_form, league_id=39):
    """
    חיזוי קרנות:
    - מבוסס על פורמה + ממוצע הליגה
    """
    def avg_corners(form, is_home_key="corners_home"):
        # אם אין נתוני קרנות ישירות — משתמשים ב-proxy מפורמה
        if not form: return None
        # בדוק אם יש נתוני קרנות
        has_corners = any("corners" in str(m) for m in form[:3])
        if has_corners:
            vals = [m.get("corners_for", 0) for m in form[-10:] if m.get("corners_for")]
            return sum(vals)/len(vals) if vals else None
        return None

    league_avg = LEAGUE_CORNERS_AVG.get(league_id, 10.5)

    # ניסיון לחשב מהפורמה
    h_corners = avg_corners(home_form)
    a_corners = avg_corners(away_form)

    if h_corners and a_corners:
        expected = h_corners + a_corners
    else:
        # proxy: קבוצות עם יותר נצחונות = יותר קרנות
        def win_rate(form):
            if not form: return 0.5
            pts = sum(m.get("points",0) for m in form[-10:])
            return pts / (len(form[-10:]) * 3)

        h_wr = win_rate(home_form)
        a_wr = win_rate(away_form)

        # קבוצה חזקה יוצרת יותר קרנות
        h_exp = league_avg * 0.5 * (0.8 + h_wr * 0.4)
        a_exp = league_avg * 0.5 * (0.8 + a_wr * 0.4)
        expected = h_exp + a_exp

    expected = max(7, min(15, expected))

    # Over/Under corners
    over_85  = 1 - sum(poisson_prob(expected, k) for k in range(9))
    over_95  = 1 - sum(poisson_prob(expected, k) for k in range(10))
    over_105 = 1 - sum(poisson_prob(expected, k) for k in range(11))
    over_115 = 1 - sum(poisson_prob(expected, k) for k in range(12))

    return {
        "expected_corners": round(expected, 1),
        "over_85":  round(over_85 * 100, 1),
        "over_95":  round(over_95 * 100, 1),
        "over_105": round(over_105 * 100, 1),
        "over_115": round(over_115 * 100, 1),
        "recommendation": (
            "Over 9.5" if expected >= 10.5 else
            "Under 9.5" if expected < 9.0 else
            "סביב 9.5 — לא ברור"
        )
    }
