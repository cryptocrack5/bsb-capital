"""
BSB Capital - Team Quality Scoring Module
Quantifies founder/developer quality using objective metrics.

Methodology based on:
- Serial Entrepreneur Success Rate analysis
- GitHub Developer Activity metrics
- Management Team Risk Assessment frameworks
- Human Capital scoring for VC due diligence
"""

import logging
from typing import Optional

from config.settings import TEAM_WEIGHTS
from src.models.schemas import TeamAnalysis

logger = logging.getLogger(__name__)


# Tier classification for known founders/teams
KNOWN_SERIAL_ENTREPRENEURS = {
    "vitalik buterin": {"experience": 10, "exits": 1, "score": 95},
    "anatoly yakovenko": {"experience": 8, "exits": 1, "score": 85},
    "hayden adams": {"experience": 7, "exits": 1, "score": 85},
    "stani kulechov": {"experience": 8, "exits": 1, "score": 82},
    "changpeng zhao": {"experience": 10, "exits": 2, "score": 80},
    "sam bankman-fried": {"experience": 5, "exits": 1, "score": 10},  # Post-FTX
    "do kwon": {"experience": 5, "exits": 0, "score": 5},  # Post-LUNA
}


class TeamScorer:
    """
    Scores team quality on a 0-100 scale.

    Scoring formula:
        TeamScore = w1*EXP + w2*EXIT + w3*GH + w4*SIZE + w5*TRANS + w6*TRACK

    Where:
        EXP = Normalized experience years (0-10 scale)
        EXIT = Previous exits score (0-10)
        GH = GitHub activity score (0-10)
        SIZE = Team size adequacy (0-10)
        TRANS = Transparency/doxxing (0-10)
        TRACK = Track record score (0-10)
    """

    def analyze(
        self,
        community_data: dict,
        github_stats: Optional[dict] = None,
        known_founders: Optional[list[str]] = None,
    ) -> TeamAnalysis:
        """Run team quality analysis."""
        result = TeamAnalysis()

        dev_data = community_data.get("developer", {})
        links = community_data.get("links", {})

        # GitHub analysis
        if github_stats:
            result.github_commits_30d = github_stats.get("commits_4w", 0)
            result.github_contributors = github_stats.get("contributors", 0)
            result.github_commit_trend = github_stats.get("commits_trend", "unknown")
        elif dev_data:
            result.github_commits_30d = dev_data.get("commit_count_4_weeks", 0) or 0
            # CoinGecko provides code changes
            code_changes = dev_data.get("code_additions_deletions_4_weeks", {})
            additions = abs(code_changes.get("additions", 0) or 0)
            deletions = abs(code_changes.get("deletions", 0) or 0)
            if additions + deletions > 0:
                result.github_commit_trend = (
                    "active" if additions > deletions else "maintenance"
                )

        # Analyze known founders
        if known_founders:
            result.founders_identified = True
            result.founders_doxxed = True
            for founder in known_founders:
                key = founder.lower().strip()
                if key in KNOWN_SERIAL_ENTREPRENEURS:
                    data = KNOWN_SERIAL_ENTREPRENEURS[key]
                    result.avg_experience_years = max(
                        result.avg_experience_years, data["experience"]
                    )
                    result.previous_exits += data["exits"]

        # Infer team info from available data
        if links:
            repos = links.get("repos_url", {})
            github_repos = repos.get("github", []) if isinstance(repos, dict) else []
            if github_repos:
                result.founders_identified = True  # At least has public repos

        # Calculate component scores
        result.development_activity_score = self._score_dev_activity(result)
        result.transparency_score = self._score_transparency(result, links)
        result.track_record_score = self._score_track_record(result, known_founders)

        # Composite team score
        result.team_score = self._compute_team_score(result)

        return result

    def _score_dev_activity(self, team: TeamAnalysis) -> float:
        """Score development activity (0-100)."""
        score = 0.0

        # Commits (max 40 points)
        commits = team.github_commits_30d
        if commits > 200:
            score += 40
        elif commits > 100:
            score += 30
        elif commits > 50:
            score += 20
        elif commits > 10:
            score += 10
        elif commits > 0:
            score += 5

        # Contributors (max 30 points)
        contributors = team.github_contributors
        if contributors > 50:
            score += 30
        elif contributors > 20:
            score += 25
        elif contributors > 10:
            score += 15
        elif contributors > 5:
            score += 10
        elif contributors > 0:
            score += 5

        # Commit trend (max 30 points)
        trend = team.github_commit_trend
        if trend in ("increasing", "active"):
            score += 30
        elif trend == "stable":
            score += 20
        elif trend in ("decreasing", "maintenance"):
            score += 10
        elif trend == "inactive":
            score += 0

        return min(100, score)

    def _score_transparency(self, team: TeamAnalysis, links: dict) -> float:
        """Score team transparency (0-100)."""
        score = 0.0

        if team.founders_identified:
            score += 30
        if team.founders_doxxed:
            score += 30

        # Check for public presence
        if links:
            if links.get("homepage", []):
                score += 10
            if links.get("twitter_screen_name"):
                score += 10
            if links.get("subreddit_url"):
                score += 5
            if links.get("telegram_channel_identifier"):
                score += 5
            repos = links.get("repos_url", {})
            github_repos = repos.get("github", []) if isinstance(repos, dict) else []
            if github_repos:
                score += 10

        return min(100, score)

    def _score_track_record(
        self, team: TeamAnalysis, known_founders: Optional[list[str]]
    ) -> float:
        """Score track record based on experience and exits."""
        score = 0.0

        # Experience scoring (max 40)
        exp = team.avg_experience_years
        if exp >= 10:
            score += 40
        elif exp >= 7:
            score += 30
        elif exp >= 5:
            score += 20
        elif exp >= 3:
            score += 10

        # Previous exits (max 30)
        exits = team.previous_exits
        if exits >= 3:
            score += 30
        elif exits >= 2:
            score += 25
        elif exits >= 1:
            score += 15

        # Known founder bonus (max 30)
        if known_founders:
            for founder in known_founders:
                key = founder.lower().strip()
                if key in KNOWN_SERIAL_ENTREPRENEURS:
                    founder_score = KNOWN_SERIAL_ENTREPRENEURS[key]["score"]
                    score += min(30, founder_score * 0.3)
                    break

        return min(100, score)

    def _compute_team_score(self, team: TeamAnalysis) -> float:
        """Compute weighted composite team score."""
        w = TEAM_WEIGHTS

        # Normalize component scores to 0-10 scale
        exp_score = min(10, team.avg_experience_years)
        exit_score = min(10, team.previous_exits * 3)
        gh_score = team.development_activity_score / 10
        size_score = min(10, team.team_size * 0.5) if team.team_size > 0 else 5
        trans_score = team.transparency_score / 10
        track_score = team.track_record_score / 10

        weighted = (
            w["experience_years"] * exp_score
            + w["previous_exits"] * exit_score
            + w["github_activity"] * gh_score
            + w["team_size"] * size_score
            + w["transparency"] * trans_score
            + w["track_record"] * track_score
        )

        # Scale to 0-100
        return round(min(100, max(0, weighted * 10)), 1)
