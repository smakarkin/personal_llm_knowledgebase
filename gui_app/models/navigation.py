"""Модель навигации GUI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    key: str
    title: str
