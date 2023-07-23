from contextvars import ContextVar
from typing import Any

# TODO remove the unused file
ctx_request_id: ContextVar = ContextVar("request_id")


def set_request_id(value: Any) -> None:
    ctx_request_id.set(value)


def get_request_id() -> Any:
    try:
        return ctx_request_id.get()
    except Exception:
        return "0"
