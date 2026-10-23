"""
Typed Exceptions for Taskflow Python SDK.
"""

class TaskflowAPIError(Exception):
    """Base exception for all Taskflow API communication errors."""
    def __init__(self, message: str, status_code: int = 500, response_data: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class AuthenticationError(TaskflowAPIError):
    """Raised when authentication credentials fail or session expires."""
    def __init__(self, message: str = "Invalid email or password.", response_data: dict = None):
        super().__init__(message, status_code=401, response_data=response_data)


class PermissionDeniedError(TaskflowAPIError):
    """Raised when user role lacks required privilege."""
    def __init__(self, message: str = "Administrative privileges required.", response_data: dict = None):
        super().__init__(message, status_code=403, response_data=response_data)


class NotFoundError(TaskflowAPIError):
    """Raised when target task, user, or team does not exist."""
    def __init__(self, message: str = "Resource not found.", response_data: dict = None):
        super().__init__(message, status_code=404, response_data=response_data)


class ValidationError(TaskflowAPIError):
    """Raised when request payload fails schema validation."""
    def __init__(self, message: str = "Payload validation error.", response_data: dict = None):
        super().__init__(message, status_code=400, response_data=response_data)
