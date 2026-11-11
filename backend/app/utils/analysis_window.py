"""Validation for the stable Stage 1 -> Stage 3 analysis time window."""

from datetime import datetime, timedelta, timezone


class AnalysisWindowError(ValueError):
    pass


def resolve_analysis_window(start_date: str | None, end_date: str | None, default_days: int = 120) -> tuple[str, str]:
    """Return ISO calendar dates and reject ambiguous, future, or oversized queries."""
    today = datetime.now(timezone.utc).date()
    try:
        end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else today
        start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else end - timedelta(days=default_days)
    except ValueError as exc:
        raise AnalysisWindowError("Dates must use ISO format YYYY-MM-DD") from exc
    if end > today:
        raise AnalysisWindowError("end_date cannot be in the future")
    if start >= end:
        raise AnalysisWindowError("start_date must be before end_date")
    if (end - start).days > 366:
        raise AnalysisWindowError("analysis period cannot exceed 366 days")
    return start.isoformat(), end.isoformat()
