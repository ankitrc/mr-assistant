"""Errors raised by tools. Agents should show `str(error)` to the user as-is."""


class ToolError(Exception):
    """A tool could not answer (bad input, nothing found, not permitted)."""


class NotFound(ToolError):
    """The requested record does not exist or is not visible to the current user."""


class UnknownEmployee(ToolError):
    """The employee id has no current assignment."""
