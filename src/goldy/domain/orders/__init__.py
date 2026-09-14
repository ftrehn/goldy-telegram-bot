"""The order: what a cart becomes once the customer commits to it.

Lines are snapshots, the total is derived from them, and the lifecycle is five
statuses with no payment state in it — :class:`Order` and
``status_transitions`` say why.
"""
