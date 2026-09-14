from dataclasses import dataclass

from goldy.domain.users.values.locale import DEFAULT_LOCALE


@dataclass(slots=True, frozen=True)
class TelegramConfig:
    """How the Telegram side of the bot is wired.

    Separate from :class:`RedisConfig` for the usual reason: that one says where
    Redis is, this one says whether we use it. The storage flags exist so a
    developer can run the bot with nothing but a token — memory storage loses
    every dialogue on restart, which is fine locally and unacceptable in
    production.

    Attributes:
        bot_token: The token from BotFather.
        use_redis_storage: Whether dialogue state survives a restart.
        use_redis_event_isolation: Whether two replicas can process updates from
            the same chat at once. Memory isolation only covers one process, so
            with more than one replica this must be on.
        use_i18n_isolation: Whether each request gets its own locale context,
            rather than sharing one that a concurrent update could change.
        default_locale: Language used before we know the person's own.
        drop_pending_updates: Whether to discard updates that queued up while
            the bot was down. On by default — an order placed twenty minutes ago
            and answered now is worse than one silently lost.
        fsm_ttl_seconds: How long an abandoned dialogue and everything it kept
            — a half-typed address, a deep link waiting for a registration —
            stay in Redis. Seven days by default: long enough for somebody to
            come back to a cart they started on Friday, short enough that the
            store does not fill with conversations nobody will resume. Redis
            storage only; memory storage dies with the process anyway.
        proxy_url: Where the Bot API traffic leaves through, if not directly.
            ``None`` means the process talks to ``api.telegram.org`` itself,
            which is the right answer wherever Telegram is reachable. A
            ``socks5://``, ``socks4://`` or ``http://`` URL — credentials
            inside it if the proxy wants any — sends every request through
            that host instead, for a data centre whose own route to Telegram
            cannot be relied on. The loader checks the shape at startup, so a
            typo stops the process rather than the first update; the value
            carries a password, so it is masked in error output and never
            logged whole.
    """

    bot_token: str
    proxy_url: str | None = None
    use_redis_storage: bool = True
    use_redis_event_isolation: bool = True
    use_i18n_isolation: bool = True
    default_locale: str = DEFAULT_LOCALE
    drop_pending_updates: bool = True
    fsm_ttl_seconds: int = 7 * 24 * 60 * 60
