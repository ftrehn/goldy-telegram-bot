auth-registration-required = To use the bot, share your phone number — tap the button below.
auth-share-phone-button = Share my number
auth-contact-not-yours = That is someone else's contact. Tap the button to send your own number.
auth-contact-without-number = That contact carries no phone number. Please try again.

error-forbidden = You are not allowed to do that.
error-blocked = Your access has been restricted. Please contact support.
error-not-found = Not found.
error-already-exists = That number or account is already taken. Please try again.
error-last-account = You cannot unlink your only messenger — we would have no way to reach you.
error-account-not-linked = That messenger is not linked in the first place.
error-already-blocked = This user is already blocked.
error-not-blocked = This user is not blocked.
error-unknown = Something went wrong. We are looking into it.

# Refusals of the buying flow. None of these may carry a placeholder:
# handle_app_error calls i18n.get(key) with no arguments, and Fluent does not
# degrade a missing argument into visible text — it raises FluentMessageError.
# That is not an AppError, so the error handler itself dies and the person gets
# nothing at all instead of the refusal this message was written for.
error-check-value = Please check what you entered — that value will not do.
cart-empty = Your cart is empty — add something before placing an order.
cart-line-not-found = That line is no longer in your cart. Open the cart again.
cart-full = There are too many lines in the cart. Remove some, or order in parts.
cart-not-found = There is no cart yet — add the first product to it.
cart-repriced = The price changed while you were checking out. Check the total and confirm again.
cart-line-unavailable = The contents of your cart have changed — please review it.
quantity-too-small = The quantity has to be at least one.
quantity-too-large = That many cannot be ordered at once. Lower the quantity or contact a manager.
money-currency-mismatch = One order cannot mix currencies. Please contact a manager.
order-empty = The order has no lines at all.
order-transition-refused = The order is already in another status — that move is not possible.
order-cannot-cancel = The order has shipped and cannot be cancelled through the bot. Write to a manager.
order-reason-required = Please give a reason for the cancellation.
order-not-editable = This order can no longer be edited.
order-not-found = No such order.
catalog-product-gone = That product has left the catalog.
catalog-price-missing = Prices are unavailable right now. We are looking into it — please try later.
catalog-price-unsupported = Your price list is not supported at the moment. Please contact a manager.
search-term-too-short = The search term is too short or too long — try another one.

# Buttons five dialogs need at once.
common-back-button = Back
common-close-button = Close
common-cancel-button = Cancel
common-confirm-button = Confirm
paging-prev-button = ← Previous
paging-next-button = Next →

# Badges drawn by the storefront, the cart and the order card alike.
stock-badge =
    { $in_stock ->
        [yes] In stock: { $stock } { $unit }
       *[no] Made to order
    }
price-on-request = Price on request

# Descriptions for the command menu Telegram draws beside the text box. Keys of
# their own rather than the lines of help-customer cut up: a command
# description is capped at 256 characters and carries no markup. /manage_orders
# is deliberately absent — help-staff exists so a customer is never told that
# staff commands are there.
command-catalog = Product catalog
command-search = Search by name or article
command-cart = Your cart
command-orders = Your orders
command-me = Your profile
command-help = What this bot can do

start-welcome = Hello, { $name }! You are registered.
start-welcome-back = Welcome back, { $name }!

help-customer =
    <b>What I can do</b>

    /catalog — browse the catalog
    /search — search by name or article
    /cart — your cart
    /orders — your orders
    /me — my profile
    /help — this help
help-staff =
    <b>What I can do</b>

    /catalog — browse the catalog
    /search — search by name or article
    /cart — your cart
    /orders — your orders
    /me — my profile
    /help — this help

    <b>For staff</b>
    /admin — manage users
    /manage_orders — the order queue

me-profile =
    <b>{ $name }</b>

    Phone: { $phone }
    Role: { $role ->
        [manager] manager
        [admin] administrator
       *[customer] customer
    }
    Language: { $locale ->
        [ru] Русский
       *[en] English
    }
    Notifications: { $notify }

unknown-command = I do not understand. Send /help to see what I can do.
cancelled = Cancelled. Send /help if you need a reminder.

profile-rename-button = Change name
profile-locale-button = Language
profile-notifications-button = Notifications
profile-accounts-button = Unlink a messenger
profile-marketing-button = Toggle marketing
profile-close-button = Close
profile-back-button = Back
profile-rename-prompt = Send your new name. A surname after a space is fine.
profile-locale-prompt = Pick a language.
profile-notifications-prompt = Notifications currently go to { $notify }. Where to?
profile-accounts-prompt = Which messenger should I unlink?

admin-users-title = <b>Users</b> — page { $page } of { $pages }, { $total } in total
admin-empty = Nobody here yet.
admin-user-card =
    <b>{ $name }</b>

    Phone: { $phone }
    Role: { $role ->
        [manager] manager
        [admin] administrator
       *[customer] customer
    }
    Status: { $status ->
        [blocked] blocked
       *[active] active
    }
    Language: { $locale }
    Block reason: { $reason }
admin-block-button = Block
admin-unblock-button = Unblock
admin-role-button = Change role
admin-back-button = Back
admin-close-button = Close
admin-prev-button = ← Previous
admin-next-button = Next →
admin-block-reason-prompt = Send the reason. Whoever lifts the block will read it.
admin-role-prompt = Pick a role. Administrator cannot be granted through the bot.
