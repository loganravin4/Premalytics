package com.neutralground.service;

import com.neutralground.domain.Match;

/** Outcome codes: H home win, D draw, A away win. */
public final class Outcomes {

    public static final String HOME = "H";
    public static final String DRAW = "D";
    public static final String AWAY = "A";

    private Outcomes() {
    }

    /** By goals after extra time. A match decided on penalties is a draw here. Null if unplayed. */
    public static String byGoals(Match match) {
        if (!match.isPlayed()) {
            return null;
        }
        int diff = Integer.compare(match.getHomeGoals(), match.getAwayGoals());
        return diff > 0 ? HOME : diff < 0 ? AWAY : DRAW;
    }

    /** Shootout-credited: a level knockout match counts for the team that advanced. Null if unplayed. */
    public static String credited(Match match) {
        String byGoals = byGoals(match);
        if (DRAW.equals(byGoals) && match.getWinnerCode() != null) {
            return match.getWinnerCode().equals(match.getHomeTeam().getCode()) ? HOME : AWAY;
        }
        return byGoals;
    }

    /** The most likely outcome. Ties go home, then away, then draw. */
    public static String pick(double pHome, double pDraw, double pAway) {
        if (pHome >= pAway && pHome >= pDraw) {
            return HOME;
        }
        return pAway >= pDraw ? AWAY : DRAW;
    }
}
