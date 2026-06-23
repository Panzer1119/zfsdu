class ZFSDUError(Exception):
    """Base application error."""


class ZFSUnavailableError(ZFSDUError):
    """Raised when zfs command is unavailable."""


class ZFSCommandError(ZFSDUError):
    """Raised when a zfs command exits with a non-zero status."""


class InvalidDatasetError(ZFSDUError):
    """Raised when the dataset root argument is invalid."""

