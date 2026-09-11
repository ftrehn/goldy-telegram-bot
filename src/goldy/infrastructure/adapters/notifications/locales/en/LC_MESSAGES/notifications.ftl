# What the worker says on its own, without anybody having asked.
#
# A separate file from the dialogues: another process reads these, one that does
# not import presentation and must not start.
#
# A placeholder without its argument does not degrade into text here —
# fluent.runtime reports an error, the renderer raises NotificationRenderError,
# and the message is not sent at all. Hence two keys for "with a reason" and
# "without one" rather than one selector: a selector would still oblige every
# render to carry { $reason }.
#
# notification-order-status is a helper, never sent on its own; the two messages
# below reference it and pass it the same { $status }. The *[other] branch
# prints the raw value, so a status invented in 1C shows as itself rather than
# claiming to be "new".

notification-order-status =
    { $status ->
        [new] new
        [confirmed] confirmed
        [shipped] shipped
        [completed] completed
        [cancelled] cancelled
       *[other] { $status }
    }

notification-order-placed =
    New order { $number }

    Recipient: { $customer }, { $phone }
    Address: { $address }
    Items: { $lines }
    Total: { $total }

notification-order-status-changed =
    Order { $number } is { notification-order-status }.

notification-order-status-changed-reason =
    Order { $number } is { notification-order-status }.
    Reason: { $reason }

notification-order-address-changed =
    The delivery address of order { $number } has changed.

    Was: { $old_address }
    Now: { $new_address }
