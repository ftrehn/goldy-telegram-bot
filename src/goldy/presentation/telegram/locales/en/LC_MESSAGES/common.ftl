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
