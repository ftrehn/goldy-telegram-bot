"""Stand-in for the finance port (ADR-0004), kept apart from ``stubs/site.py``.

A new file rather than an addition to that one: it already carries the linking
and pricing stubs the order-handover tests build on, and ``SiteFinance`` has
nothing to do with either.
"""

from datetime import UTC, datetime
from typing import final, override

from goldy.application.common.ports.site import SiteFinance
from goldy.application.common.views.money import MoneyView
from goldy.application.common.views.site import SiteFinanceSummaryView


def site_finance_summary_view(
    *,
    erp_linked: bool = True,
    is_stale: bool = False,
    is_partial: bool = False,
) -> SiteFinanceSummaryView:
    """A company in good standing with 1C, as the site would summarise it."""
    return SiteFinanceSummaryView(
        company_name="Ромашка",
        erp_linked=erp_linked,
        debt=MoneyView.zero(),
        advance=None,
        overdue=None,
        max_days_overdue=None,
        credit_limit=None,
        credit_available=None,
        as_of=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
        is_stale=is_stale,
        is_partial=is_partial,
    )


@final
class ScriptedSiteFinance(SiteFinance):
    """Answers with the summary a test put in, or the queued error."""

    def __init__(self) -> None:
        self.answer: SiteFinanceSummaryView = site_finance_summary_view()
        self.errors: list[Exception] = []
        self.calls: list[str] = []

    @override
    async def summary(self, subject: str) -> SiteFinanceSummaryView:
        self.calls.append(subject)

        if self.errors:
            raise self.errors.pop(0)

        return self.answer
