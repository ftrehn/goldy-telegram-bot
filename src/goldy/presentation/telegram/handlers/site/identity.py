from goldy.presentation.telegram.common.formatting import for_message_text


def describe_site_customer(
    name: str,
    *,
    email: str | None = None,
    company: str | None = None,
) -> str:
    """Who a site account belongs to, as one line safe to put in a message.

    Joined here rather than in Fluent: the parts are optional, and a selector
    per optional part is three nested branches that each have to agree on
    what "absent" is. Every part comes from the site and was typed by a person
    there, so each is quoted.
    """
    parts = [name, email, company]
    return ", ".join(for_message_text(part) for part in parts if part)
