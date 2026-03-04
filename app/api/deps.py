from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bootstrap import AppContainer

_container: AppContainer | None = None


def set_container(container: AppContainer) -> None:
    global _container
    _container = container


def get_container() -> AppContainer:
    if _container is None:
        raise RuntimeError("Application container has not been initialized")
    return _container
