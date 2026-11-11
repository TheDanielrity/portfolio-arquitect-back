class AuthenticationError(Exception):
    """Credentials or the backing administrator session are not valid."""


class AdministratorAlreadyExists(Exception):
    """Local provisioning cannot replace an existing administrator."""


class ResourceNotFound(Exception):
    """The requested resource does not exist."""


class ResourceConflict(Exception):
    """An existing resource or reference prevents the requested operation."""


class InvalidOperation(Exception):
    """The requested domain operation does not satisfy its business conditions."""
