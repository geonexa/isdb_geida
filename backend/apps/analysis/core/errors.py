"""Errors an analysis can raise. Their message is shown to the user as the reason a run failed."""


class AnalysisError(Exception):
    """A clear, user-facing failure (missing data, area too large, nothing to measure, ...)."""


# Name used by the first modules; same class.
ModuleError = AnalysisError
