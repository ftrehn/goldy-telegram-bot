"""The cart: a draft order that belongs to a person, not to a messenger.

The aggregate records no domain events at all, and that is a decision rather
than an omission — :class:`Cart` says why.
"""
