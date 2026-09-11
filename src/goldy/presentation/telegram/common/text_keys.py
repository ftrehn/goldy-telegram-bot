"""Every Fluent message key the bot asks for, in one place.

Constants rather than literals at the call site for two reasons. A key is a
contract with the ``.ftl`` files, and the same one is often needed in two
places — ``auth-registration-required`` is used by both the gate and the
``/start`` handler, and two literals spelled slightly differently is how one of
them starts pointing at a message nobody wrote. And renaming a message becomes
one edit here instead of a grep across the presentation layer.

Names mirror the keys, so the mapping stays obvious in both directions.
"""

from typing import Final

# Registration and the gate in front of it.
AUTH_REGISTRATION_REQUIRED: Final[str] = "auth-registration-required"
AUTH_SHARE_PHONE_BUTTON: Final[str] = "auth-share-phone-button"
AUTH_CONTACT_NOT_YOURS: Final[str] = "auth-contact-not-yours"
AUTH_CONTACT_WITHOUT_NUMBER: Final[str] = "auth-contact-without-number"

# Refusals, one per rule the domain can raise.
ERROR_FORBIDDEN: Final[str] = "error-forbidden"
ERROR_BLOCKED: Final[str] = "error-blocked"
ERROR_NOT_FOUND: Final[str] = "error-not-found"
ERROR_ALREADY_EXISTS: Final[str] = "error-already-exists"
ERROR_LAST_ACCOUNT: Final[str] = "error-last-account"
ERROR_ACCOUNT_NOT_LINKED: Final[str] = "error-account-not-linked"
ERROR_ALREADY_BLOCKED: Final[str] = "error-already-blocked"
ERROR_NOT_BLOCKED: Final[str] = "error-not-blocked"
"""Three refusals the profile and admin dialogs could already produce.

They had no entry, so unlinking a messenger twice or blocking an already
blocked person answered "something went wrong, we are looking into it" and
filed the click as an outage. Nothing about them is new — only the table was
incomplete, and the test that walks the error classes now walks ``users`` too.
"""

ERROR_UNKNOWN: Final[str] = "error-unknown"
"""Shown when nothing more specific fits. Used by the gate and the error
handler alike, which is exactly the duplication this module exists to stop."""

# Greetings.
START_WELCOME: Final[str] = "start-welcome"
START_WELCOME_BACK: Final[str] = "start-welcome-back"

# The commands anyone can reach.
HELP_CUSTOMER: Final[str] = "help-customer"
HELP_STAFF: Final[str] = "help-staff"
"""Two messages rather than one with a conditional.

Fluent can branch on a variable, but a customer must not even be told that
``/admin`` exists — and a selector that hides a line is one edit away from
showing it.
"""

ME_PROFILE: Final[str] = "me-profile"
UNKNOWN_COMMAND: Final[str] = "unknown-command"
CANCELLED: Final[str] = "cancelled"

# One line each for the menu Telegram draws beside the text box.
COMMAND_CATALOG: Final[str] = "command-catalog"
COMMAND_SEARCH: Final[str] = "command-search"
COMMAND_CART: Final[str] = "command-cart"
COMMAND_ORDERS: Final[str] = "command-orders"
COMMAND_ME: Final[str] = "command-me"
COMMAND_HELP: Final[str] = "command-help"
"""Descriptions for the published command menu, one per customer command.

Separate keys rather than the lines of ``help-customer`` cut up, because the
two have different limits and different jobs: Telegram allows a command
description 256 characters and shows it in a list with no formatting, while the
help message is one screen of marked-up text. Splitting one into the other
would mean a change to the help screen silently reshaping the menu.

There is deliberately no ``command-manage-orders``. ``help-staff`` exists so a
customer is never told that staff commands exist, and a published menu listing
one would walk straight around that — which is why the menu is set with
``BotCommandScopeAllPrivateChats`` and the staff command is left out of it
rather than filtered somewhere later.
"""

# The profile dialog.
PROFILE_RENAME_BUTTON: Final[str] = "profile-rename-button"
PROFILE_LOCALE_BUTTON: Final[str] = "profile-locale-button"
PROFILE_NOTIFICATIONS_BUTTON: Final[str] = "profile-notifications-button"
PROFILE_ACCOUNTS_BUTTON: Final[str] = "profile-accounts-button"
PROFILE_MARKETING_BUTTON: Final[str] = "profile-marketing-button"
PROFILE_CLOSE_BUTTON: Final[str] = "profile-close-button"
PROFILE_BACK_BUTTON: Final[str] = "profile-back-button"
PROFILE_RENAME_PROMPT: Final[str] = "profile-rename-prompt"
PROFILE_LOCALE_PROMPT: Final[str] = "profile-locale-prompt"
PROFILE_NOTIFICATIONS_PROMPT: Final[str] = "profile-notifications-prompt"
PROFILE_ACCOUNTS_PROMPT: Final[str] = "profile-accounts-prompt"

# The admin dialog.
ADMIN_USERS_TITLE: Final[str] = "admin-users-title"
ADMIN_USER_CARD: Final[str] = "admin-user-card"
ADMIN_EMPTY: Final[str] = "admin-empty"
ADMIN_BLOCK_BUTTON: Final[str] = "admin-block-button"
ADMIN_UNBLOCK_BUTTON: Final[str] = "admin-unblock-button"
ADMIN_ROLE_BUTTON: Final[str] = "admin-role-button"
ADMIN_BACK_BUTTON: Final[str] = "admin-back-button"
ADMIN_CLOSE_BUTTON: Final[str] = "admin-close-button"
ADMIN_PREV_BUTTON: Final[str] = "admin-prev-button"
ADMIN_NEXT_BUTTON: Final[str] = "admin-next-button"
ADMIN_BLOCK_REASON_PROMPT: Final[str] = "admin-block-reason-prompt"
ADMIN_ROLE_PROMPT: Final[str] = "admin-role-prompt"

# Buttons every dialog needs, so five dialogs do not spell them five ways.
COMMON_BACK_BUTTON: Final[str] = "common-back-button"
COMMON_CLOSE_BUTTON: Final[str] = "common-close-button"
COMMON_CANCEL_BUTTON: Final[str] = "common-cancel-button"
COMMON_CONFIRM_BUTTON: Final[str] = "common-confirm-button"
PAGING_PREV_BUTTON: Final[str] = "paging-prev-button"
PAGING_NEXT_BUTTON: Final[str] = "paging-next-button"

# Badges the storefront, the cart and the staff card all draw.
STOCK_BADGE: Final[str] = "stock-badge"
"""Selector over ``$in_stock``: "in stock: N pcs" or "made to order".

Never a reason to hide a button. Stock is a projection of 1C with no
reservation behind it, so a product at zero is sold to order and the screen
says exactly that.
"""

PRICE_ON_REQUEST: Final[str] = "price-on-request"
"""What a listing prints where a price would go when there is none.

Drawing a zero would read as "free", which is worse than an error, and hiding
the product would hide goods the shop is perfectly able to sell.
"""

# Refusals of the buying flow. Every one of these is reached through
# ``ERROR_TEXTS``, which renders it with ``i18n.get(key)`` and no arguments —
# so none of these messages may carry a placeholder.
ERROR_CHECK_VALUE: Final[str] = "error-check-value"
"""The tail entry for ``DomainFieldError``.

Last by construction rather than by dictionary order: the MRO walk in the error
handler picks the nearest match, so a specific error still wins. What it buys is
that a typo in an address, a name or a block reason stops being reported as
"something went wrong, we are looking into it".
"""

CART_EMPTY: Final[str] = "cart-empty"
CART_LINE_NOT_FOUND: Final[str] = "cart-line-not-found"
CART_FULL: Final[str] = "cart-full"
CART_NOT_FOUND: Final[str] = "cart-not-found"
CART_REPRICED: Final[str] = "cart-repriced"
CART_LINE_UNAVAILABLE: Final[str] = "cart-line-unavailable"
QUANTITY_TOO_SMALL: Final[str] = "quantity-too-small"
QUANTITY_TOO_LARGE: Final[str] = "quantity-too-large"
MONEY_CURRENCY_MISMATCH: Final[str] = "money-currency-mismatch"
ORDER_EMPTY: Final[str] = "order-empty"
ORDER_TRANSITION_REFUSED: Final[str] = "order-transition-refused"
ORDER_CANNOT_CANCEL: Final[str] = "order-cannot-cancel"
ORDER_REASON_REQUIRED: Final[str] = "order-reason-required"
ORDER_NOT_EDITABLE: Final[str] = "order-not-editable"
ORDER_NOT_FOUND: Final[str] = "order-not-found"
CATALOG_PRODUCT_GONE: Final[str] = "catalog-product-gone"
CATALOG_PRICE_MISSING: Final[str] = "catalog-price-missing"
CATALOG_PRICE_UNSUPPORTED: Final[str] = "catalog-price-unsupported"
SEARCH_TERM_TOO_SHORT: Final[str] = "search-term-too-short"

# The catalog dialog: categories, listing, card, description, search.
CATALOG_TITLE: Final[str] = "catalog-title"
CATALOG_CATEGORY_TITLE: Final[str] = "catalog-category-title"
CATALOG_PICK_CATEGORY: Final[str] = "catalog-pick-category"
CATALOG_NO_CATEGORIES: Final[str] = "catalog-no-categories"
CATALOG_ALL_PRODUCTS: Final[str] = "catalog-all-products"
"""The name a listing of the whole catalog is titled with.

A message rather than an empty ``$category``, because the heading is one
message and Fluent renders a missing argument as the word for nothing.
"""

CATALOG_SHOW_PRODUCTS_BUTTON: Final[str] = "catalog-show-products-button"
CATALOG_UP_BUTTON: Final[str] = "catalog-up-button"
CATALOG_SEARCH_BUTTON: Final[str] = "catalog-search-button"
CATALOG_LIST_TITLE: Final[str] = "catalog-list-title"
CATALOG_LIST_EMPTY: Final[str] = "catalog-list-empty"
CATALOG_LIST_ITEM: Final[str] = "catalog-list-item"
"""One row of a listing, rendered by the getter into a button label."""

CATALOG_SORT_BUTTON: Final[str] = "catalog-sort-button"
CATALOG_SKU: Final[str] = "catalog-sku"
CATALOG_CARD: Final[str] = "catalog-card"
"""Needs ``name price unit excerpt has_sku sku in_stock stock``.

Longer than its own text suggests, because the card embeds ``catalog-sku`` and
``stock-badge`` and **a referenced message is rendered in the caller's scope** —
it has no arguments of its own and reads the ones passed here. So the window
that draws this key owes the arguments of all three messages.

Getting that wrong is not cosmetic. ``FluentRuntimeCore.get`` raises
``FluentMessageError`` on an unknown external rather than leaving ``{ $sku }``
in the text, so one forgotten argument is a screen that does not render at all.
Use :func:`~goldy.presentation.telegram.common.formatting.flag` for the two
selector flags, whose branches are spelled ``yes`` and ``no``.
"""
CATALOG_DESCRIPTION_BUTTON: Final[str] = "catalog-description-button"
CATALOG_DESCRIPTION: Final[str] = "catalog-description"
CATALOG_ADD_BUTTON: Final[str] = "catalog-add-button"
"""Hidden by a missing price, never by a missing stock. The two are not alike.

Stock says nothing about whether the shop can sell: it is a projection of 1C
with no reservation behind it, so a product at zero is one brought in to order
and the badge says exactly that. Hiding the button there would be a block by
stock, and an inconsistent one — a line already in the cart could still be
ordered while the same product could not be added — biting precisely the case
the shop values.

A missing price is the opposite. There is no row under this customer's price
type, so there is no amount to put in a cart line; the listing prints "price on
request" and the button goes away, because the same absence is the only thing
that raises ``ProductNotPricedError`` at checkout. Offering a button that
cannot succeed is worse than not offering one.
"""

CATALOG_ADDED_TOAST: Final[str] = "catalog-added-toast"
CATALOG_OPEN_CART_BUTTON: Final[str] = "catalog-open-cart-button"
CATALOG_SEARCH_PROMPT: Final[str] = "catalog-search-prompt"
CATALOG_SEARCH_TITLE: Final[str] = "catalog-search-title"
CATALOG_SEARCH_EMPTY: Final[str] = "catalog-search-empty"
CATALOG_SEARCH_AGAIN_BUTTON: Final[str] = "catalog-search-again-button"
CATALOG_TO_CATALOG_BUTTON: Final[str] = "catalog-to-catalog-button"

# The cart dialog: the cart itself and the confirmation before clearing it.
CART_TITLE: Final[str] = "cart-title"
CART_SCREEN_EMPTY: Final[str] = "cart-screen-empty"
"""Not the same message as ``cart-empty``.

``cart-empty`` is a refusal — checkout ran against nothing. This one is the
ordinary state of a cart nobody has filled yet, and it invites rather than
apologises.
"""

CART_LINE: Final[str] = "cart-line"
CART_LINE_UNAVAILABLE_MARK: Final[str] = "cart-line-unavailable-mark"
CART_UNAVAILABLE_NOTICE: Final[str] = "cart-unavailable-notice"
CART_UNPRICED_NOTICE: Final[str] = "cart-unpriced-notice"
"""The other reason "checkout" is hidden, and not the same reason at all.

``cart-unavailable-notice`` says the marked products are gone from the catalog,
and "remove unavailable" sweeps away exactly those. A product with no row under
this customer's price type is still in the catalog — it is the price that is
missing — so that button would not touch it and that wording would not describe
it. Two notices rather than one hedged sentence, because each one names what to
do about the fault it is about.
"""

CART_REMOVE_UNAVAILABLE_BUTTON: Final[str] = "cart-remove-unavailable-button"
CART_CHECKOUT_BUTTON: Final[str] = "cart-checkout-button"
CART_CLEAR_BUTTON: Final[str] = "cart-clear-button"
CART_CLEAR_CONFIRM: Final[str] = "cart-clear-confirm"
CART_CLEARED_TOAST: Final[str] = "cart-cleared-toast"
CART_PLUS_BUTTON: Final[str] = "cart-plus-button"
CART_MINUS_BUTTON: Final[str] = "cart-minus-button"
CART_REMOVE_BUTTON: Final[str] = "cart-remove-button"
CART_QUANTITY_BUTTON: Final[str] = "cart-quantity-button"
CART_QUANTITY_PROMPT: Final[str] = "cart-quantity-prompt"
CART_CONTINUE_BUTTON: Final[str] = "cart-continue-button"

# The checkout dialog: address, recipient, phone, comment, confirm, done.
CHECKOUT_ADDRESS_PROMPT: Final[str] = "checkout-address-prompt"
CHECKOUT_ADDRESS_LAST_BUTTON: Final[str] = "checkout-address-last-button"
CHECKOUT_RECIPIENT_PROMPT: Final[str] = "checkout-recipient-prompt"
CHECKOUT_RECIPIENT_ME_BUTTON: Final[str] = "checkout-recipient-me-button"
CHECKOUT_PHONE_PROMPT: Final[str] = "checkout-phone-prompt"
CHECKOUT_PHONE_MINE_BUTTON: Final[str] = "checkout-phone-mine-button"
CHECKOUT_COMMENT_PROMPT: Final[str] = "checkout-comment-prompt"
CHECKOUT_SKIP_BUTTON: Final[str] = "checkout-skip-button"
CHECKOUT_CONFIRM: Final[str] = "checkout-confirm"
CHECKOUT_CONFIRM_BUTTON: Final[str] = "checkout-confirm-button"
CHECKOUT_PLACING: Final[str] = "checkout-placing"
"""Drawn before the command is awaited, so the button is physically gone.

The first of three layers against a double tap, and the weakest: it loses to a
tap that arrives while the first command is still inside its transaction. The
one that actually holds is that checkout clears the cart in that transaction,
so the second attempt meets an empty cart.
"""

CHECKOUT_REPRICED_NOTICE: Final[str] = "checkout-repriced-notice"
CHECKOUT_ALREADY_PLACED: Final[str] = "checkout-already-placed"
"""The one domain error a dialog catches locally.

A second tap that got past the redrawn window lands on a cart checkout has
already emptied, and ``EmptyCartError`` is what comes back. Rendering the
generic "your cart is empty" there would be true and useless; the person wants
to know their order went through.
"""

CHECKOUT_DONE: Final[str] = "checkout-done"
"""Needs ``number phone`` — ``phone`` because it embeds the next-steps line.

The promise that a manager will call is written once, in ``order-card-next-
steps``, and referenced from here rather than restated. The reference costs
this screen the recipient's phone number as an argument, which is the trade
that keeps the "done" screen and the order card from drifting apart.
"""

CHECKOUT_OPEN_ORDER_BUTTON: Final[str] = "checkout-open-order-button"
CHECKOUT_TO_CATALOG_BUTTON: Final[str] = "checkout-to-catalog-button"

# The customer's own orders: list, card, address edit, cancellation.
ORDERS_TITLE: Final[str] = "orders-title"
ORDERS_EMPTY: Final[str] = "orders-empty"
ORDERS_LIST_ITEM: Final[str] = "orders-list-item"
ORDER_STATUS: Final[str] = "order-status"
"""The one status dictionary, referenced from four screens.

A message with a selector rather than a parameterised term: term arguments have
to be literals, so ``-order-status(status: $status)`` is refused by the parser
with E0014. A message reference resolves in the caller's scope, which is what
makes ``$status`` visible inside it.

The ``*[other]`` branch prints the raw value, so a status 1C grows later shows
up as itself instead of claiming the order is new.
"""

ORDER_NUMBER: Final[str] = "order-number"
"""How a number is decorated — decoration being presentation's job.

A message rather than a Python f-string because the number sign is not the same
character in both languages.
"""

ORDER_CARD: Final[str] = "order-card"
"""Needs ``number date status address recipient phone has_comment comment
lines total``.

``status`` is there because the card embeds ``order-status``, which resolves in
this scope and finds the variable here. ``lines`` arrives already rendered: the
getter formats each ``order-line`` and joins them, because Fluent has no loop
and a message per line count is not a translation, it is a cartesian product.
"""

ORDER_CARD_NEXT_STEPS: Final[str] = "order-card-next-steps"
"""What happens after "confirm", for ``NEW`` and ``CONFIRMED`` orders.

Somebody walked through five screens, saw a total and pressed a button — and in
an interface where money was expected, no money happened. This is the one place
that can say why: a manager will call the recipient, settlement and delivery
are agreed then, and the delivery charge is quoted separately. The "done"
screen of checkout references this very message rather than restating it.
"""

ORDER_LINE: Final[str] = "order-line"
ORDER_LINES_TRUNCATED: Final[str] = "order-lines-truncated"
"""What a card says in place of the positions it had no room for.

Both cards join their lines into one Fluent argument, and Fluent refuses a
placeable over 2500 characters by failing the whole message rather than by
shortening it. A cart is allowed a hundred positions and a product name 255
characters, so an ordinary wholesale order reaches that ceiling — without this,
the card of such an order does not render at all, for the buyer or for the
manager.

Deliberately free of a plural selector. The notice is reserved for before the
lines are counted, and that reservation is only an upper bound while the
wording's length follows nothing but the digits of the count.
"""
ORDER_CANCELLED_BY: Final[str] = "order-cancelled-by"
ORDER_CANCELLATION_REASON: Final[str] = "order-cancellation-reason"
"""Drawn only when there is one, which is only when staff cancelled.

Somebody withdrawing their own order owes nobody an explanation; somebody
cancelling another person's does, and the aggregate refuses a manager without
one. A second message rather than a branch inside ``order-cancelled-by``,
because the customer's card would otherwise print an empty "reason:" line under
every order they cancelled themselves.
"""
ORDER_CANCEL_BUTTON: Final[str] = "order-cancel-button"
ORDER_CANCEL_CONFIRM: Final[str] = "order-cancel-confirm"
ORDER_CANCEL_YES_BUTTON: Final[str] = "order-cancel-yes-button"
ORDER_CANCELLED_TOAST: Final[str] = "order-cancelled-toast"
ORDER_EDIT_ADDRESS_BUTTON: Final[str] = "order-edit-address-button"
ORDER_ADDRESS_PROMPT: Final[str] = "order-address-prompt"
ORDER_ADDRESS_CHANGED_TOAST: Final[str] = "order-address-changed-toast"

# The staff queue: a command and a dialog of its own, not a branch of /admin.
MANAGE_ORDERS_TITLE: Final[str] = "manage-orders-title"
MANAGE_ORDERS_EMPTY: Final[str] = "manage-orders-empty"
MANAGE_ORDERS_ITEM: Final[str] = "manage-orders-item"
MANAGE_ORDERS_FILTER_BUTTON: Final[str] = "manage-orders-filter-button"
MANAGE_ORDERS_FILTER_PROMPT: Final[str] = "manage-orders-filter-prompt"
MANAGE_ORDERS_FILTER_ANY: Final[str] = "manage-orders-filter-any"
MANAGE_ORDERS_FILTER_ANY_BUTTON: Final[str] = "manage-orders-filter-any-button"
MANAGE_ORDERS_CARD: Final[str] = "manage-orders-card"
"""Needs ``number date status customer blocked_mark address recipient phone
has_comment comment lines total``.

The customer's card plus the two things only staff are shown: who ordered, and
whether that person is blocked. ``blocked_mark`` is a rendered string rather
than a flag — empty when there is nothing to warn about — because a selector
would have put the wording in the card, and it belongs with the warning.
"""

MANAGE_ORDERS_LINE: Final[str] = "manage-orders-line"
"""A queue line carries the current stock beside the quantity ordered.

That join is what makes ``CONFIRMED`` mean anything: a manager deciding whether
to accept an order sees what is on the shelf next to what was asked for. The
customer's own card leaves it unset.
"""

MANAGE_ORDERS_CUSTOMER_BLOCKED: Final[str] = "manage-orders-customer-blocked"
MANAGE_ORDERS_STATUS_BUTTON: Final[str] = "manage-orders-status-button"
MANAGE_ORDERS_STATUS_PROMPT: Final[str] = "manage-orders-status-prompt"
MANAGE_ORDERS_REASON_PROMPT: Final[str] = "manage-orders-reason-prompt"
MANAGE_ORDERS_STATUS_CHANGED_TOAST: Final[str] = "manage-orders-status-changed-toast"
