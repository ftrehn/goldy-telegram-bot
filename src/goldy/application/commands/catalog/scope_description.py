from goldy.application.common.ports.catalog import CatalogScope


def describe_scope(scope: CatalogScope) -> str:
    """Renders a scope as one line of a log or of an import response.

    Qualifier included, because a sweep over prices is a sweep over *one*
    price list: a log line saying only "prices" would leave the reader unable
    to tell which exported list the numbers next to it belonged to.
    """
    qualifier = scope.price_type_id or scope.warehouse_id

    return scope.kind.value if qualifier is None else f"{scope.kind.value}:{qualifier}"
