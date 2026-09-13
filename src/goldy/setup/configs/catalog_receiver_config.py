from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CatalogReceiverConfig:
    """What the catalog receiver needs in order to listen to 1C.

    Its own config rather than fields on :class:`CatalogConfig`, because the
    two answer different questions. ``CatalogConfig`` holds our decisions
    about a catalog every process reads — the price list a customer without a
    binding is shown. This one describes a network listener that exactly one
    process opens: where it binds, what it accepts, and the secret 1C has to
    present. The bot and the worker have no port to listen on and nothing to
    check a bearer token against, so handing them these settings would only
    give them a secret they cannot use.

    That is also why the token is not in ``configs_provider``. A config there
    reaches every container, and a container is a statement about what a
    process may do. The receiver's process loads this object itself and puts
    it into its own context, the way the bot does with ``TelegramConfig`` and
    the worker with ``NotificationConfig``; nobody else can resolve it, so
    nobody else can accidentally depend on it.

    Attributes:
        host: The interface to bind. Loopback by default, because the process
            holds a token that lets whoever reaches the port rewrite the
            catalog, and a receiver started on a workstation with nothing set
            must not open that port to the network. The compose file sets
            ``0.0.0.0`` for the container explicitly, since 1C reaches it
            through a published port; a deployment on a host with a public
            interface names the interface it means.
        port: The TCP port to listen on. ``8090`` is a free default in the
            local environment, where ``8080`` is taken.
        token: The bearer token 1C sends in ``Authorization``. Required, with
            no default: a receiver that accepted a well-known value would let
            anyone who can reach the port rewrite the catalog.
        max_body_mib: The largest request body accepted, in mebibytes. 1C
            sends products a thousand rows to a batch and prices two thousand,
            which is a few megabytes; the ceiling exists so that a runaway
            export cannot make the receiver buffer gigabytes before refusing.
    """

    token: str
    host: str = "127.0.0.1"
    port: int = 8090
    max_body_mib: int = 64
