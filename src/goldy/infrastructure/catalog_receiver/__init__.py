"""The HTTP receiver 1C posts the catalog to.

Infrastructure rather than presentation, and the difference is who is on the
other end. ``presentation/`` is where a person writes to the bot and is
answered in their language, behind an identity and an authorization gate.
Nobody is on the other end of this package: a scheduled job in an accounting
system posts JSON bodies and reads status codes, exactly as the RabbitMQ
subscribers in ``task_manager/consumers/`` take messages off a broker. Both
are adapters at the edge of the process that turn a transport's envelope into
a command and hand it to the ``Sender``; both belong beside the transport
they speak, not beside the dialogs.

The handling is synchronous — the command runs inside the request and the
response carries its outcome — although a receiver could just as well drop
the body onto a queue and answer ``202``. It does not, because the order of
the calls is the correctness of the import. A finalisation sweeps whatever
its batch did not mention, so it must not run until every batch of its scope
is committed; with the commands run inside the request, 1C learns that a
batch is committed from the ``200`` it waits for and sends the finalisation
only after the last of them. A queue would buy throughput the exchange does
not need and cost the one guarantee it cannot do without.

One request is one dishka ``REQUEST`` scope — a session, a transaction, the
pipelines — opened by the middleware ``dishka.integrations.aiohttp`` installs,
so a batch that fails is rolled back by the same pipeline that rolls back a
failed Telegram update. The receiver adds nothing to that.
"""
