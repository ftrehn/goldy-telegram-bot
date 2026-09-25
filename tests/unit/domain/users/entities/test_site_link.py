"""``SiteLink.from_site`` trims what the site sends, and never refuses it.

The site's names are whatever a customer typed into its cabinet, and a person
whose link the site already made must still see it here — so a name that does
not fit is shortened, not rejected, and one that is blank becomes a
placeholder.
"""

from goldy.domain.users.entities.site_link import (
    MAX_SITE_COMPANY_NAME_LENGTH,
    MAX_SITE_CUSTOMER_NAME_LENGTH,
    SiteLink,
)


def test_the_answer_is_kept_as_is_when_it_already_fits() -> None:
    link = SiteLink.from_site(
        customer_name="Иван Иванов",
        company_name="Ромашка",
        is_wholesale=True,
    )

    assert link.customer_name == "Иван Иванов"
    assert link.company_name == "Ромашка"
    assert link.is_wholesale is True


def test_repeated_whitespace_in_the_customer_name_is_collapsed() -> None:
    link = SiteLink.from_site(
        customer_name="Иван   \n Иванов",
        company_name=None,
        is_wholesale=False,
    )

    assert link.customer_name == "Иван Иванов"


def test_repeated_whitespace_in_the_company_name_is_collapsed() -> None:
    link = SiteLink.from_site(
        customer_name="Иван Иванов",
        company_name="Ромашка   плюс  \n",
        is_wholesale=False,
    )

    assert link.company_name == "Ромашка плюс"


def test_a_customer_name_longer_than_the_column_is_shortened_to_fit() -> None:
    """Refusing it would leave a person the site already linked unable to see it."""
    link = SiteLink.from_site(
        customer_name="a" * (MAX_SITE_CUSTOMER_NAME_LENGTH + 50),
        company_name=None,
        is_wholesale=False,
    )

    assert link.customer_name == "a" * MAX_SITE_CUSTOMER_NAME_LENGTH


def test_a_company_name_longer_than_the_column_is_shortened_to_fit() -> None:
    link = SiteLink.from_site(
        customer_name="Иван Иванов",
        company_name="b" * (MAX_SITE_COMPANY_NAME_LENGTH + 50),
        is_wholesale=False,
    )

    assert link.company_name == "b" * MAX_SITE_COMPANY_NAME_LENGTH


def test_an_empty_customer_name_becomes_a_placeholder() -> None:
    link = SiteLink.from_site(customer_name="", company_name=None, is_wholesale=False)

    assert link.customer_name == "—"


def test_a_customer_name_of_only_whitespace_becomes_a_placeholder() -> None:
    link = SiteLink.from_site(
        customer_name="   \n\t",
        company_name=None,
        is_wholesale=False,
    )

    assert link.customer_name == "—"


def test_no_company_name_stays_absent() -> None:
    link = SiteLink.from_site(
        customer_name="Иван Иванов",
        company_name=None,
        is_wholesale=False,
    )

    assert link.company_name is None


def test_an_empty_company_name_is_treated_as_absent() -> None:
    link = SiteLink.from_site(
        customer_name="Иван Иванов", company_name="", is_wholesale=False
    )

    assert link.company_name is None


def test_a_company_name_of_only_whitespace_is_treated_as_absent() -> None:
    link = SiteLink.from_site(
        customer_name="Иван Иванов",
        company_name="   ",
        is_wholesale=False,
    )

    assert link.company_name is None
