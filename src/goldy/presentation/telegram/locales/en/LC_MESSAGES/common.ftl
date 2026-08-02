auth-registration-required = To use the bot, share your phone number — tap the button below.
auth-share-phone-button = Share my number
auth-contact-not-yours = That is someone else's contact. Tap the button to send your own number.
auth-contact-without-number = That contact carries no phone number. Please try again.

error-forbidden = You are not allowed to do that.
error-blocked = Your access has been restricted. Please contact support.
error-not-found = Not found.
error-already-exists = That number or account is already taken. Please try again.
error-last-account = You cannot unlink your only messenger — we would have no way to reach you.
error-unknown = Something went wrong. We are looking into it.

start-welcome = Hello, { $name }! You are registered.
start-welcome-back = Welcome back, { $name }!

help-customer =
    <b>What I can do</b>

    /me — my profile
    /help — this help
help-staff =
    <b>What I can do</b>

    /me — my profile
    /help — this help

    <b>For staff</b>
    /admin — manage users

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
