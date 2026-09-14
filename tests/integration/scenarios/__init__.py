"""The buyer's path end to end, one story per test.

The other integration packages each hold one layer still: ``persistence`` asks
what the SQL does, ``telegram`` asks what a dialog draws, ``worker`` asks what a
task relays. Nothing asked what happens when a person walks the whole way — from
a catalog arriving out of 1C to an order sitting in a manager's queue — and that
is the path where the interesting failures live, because every one of them is a
disagreement between two layers that each pass their own tests.

Telegram is not in it. A scenario sends the same commands and queries the
dialogs send, in the same order, through the same mediator; what a screen prints
is already covered next door and asserting it again here would make these tests
fail on a wording change. What is still real is everything below that: the
production containers, a real Postgres, the real mappers, the real pipelines.
"""
