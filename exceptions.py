from fastapi import HTTPException


class DetailedHTTPException(HTTPException):
    """
    Расширение стандартного HTTPException для добавления кастомных полей в ответ.
    """
    def __init__(self, status_code: int, detail: str, error_code: str, **kwargs):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.extra_info = kwargs