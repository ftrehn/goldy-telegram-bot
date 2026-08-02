from typing import Final

AUTHZ_NOT_AUTHORIZED: Final[str] = "Not authorized."
"""Deliberately says nothing about why.

A refusal that explains itself tells whoever is probing which roles exist and
who holds them.
"""
