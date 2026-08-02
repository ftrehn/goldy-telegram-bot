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
    """

    bot_token: str
    use_redis_storage: bool = True
    use_redis_event_isolation: bool = True
    use_i18n_isolation: bool = True
    default_locale: str = DEFAULT_LOCALE
    drop_pending_updates: bool = True
