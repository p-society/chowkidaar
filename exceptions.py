class ChowkidaarBotError(Exception):
    """Base class for all custom exceptions in the CP bot."""

    pass


class RegistrationError(ChowkidaarBotError):
    """Raised when user registration fails or is malformed."""

    def __init__(self, message="Registration failed."):
        super().__init__(message)


class SubmissionFormatError(ChowkidaarBotError):
    """Raised when the user's daily log message is not in a valid format."""

    def __init__(self, message="Invalid submission format."):
        super().__init__(message)


class UserNotRegisteredError(ChowkidaarBotError):
    """Raised when a user tries to log without being registered."""

    def __init__(self, user_id: str):
        message = f"User with ID {user_id} is not registered."
        super().__init__(message)


class DatabaseConnectionError(ChowkidaarBotError):
    """Raised when there is a failure to connect or query the database."""

    def __init__(self, message="Could not connect to the database."):
        super().__init__(message)


class PlatformAPIError(ChowkidaarBotError):
    """Raised when there is an error fetching data from LC/CF."""

    def __init__(self, platform: str, message="API error"):
        full_msg = f"{platform} API error: {message}"
        super().__init__(full_msg)
