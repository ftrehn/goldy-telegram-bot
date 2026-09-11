# The customer's own orders: list, card, address edit, cancellation.
#
# order-status is one message with a selector, referenced by the card, the list
# and the staff queue alike. A parameterised term -order-status(status:
# $status) does not work here: term arguments have to be literals and the
# parser answers E0014. The *[other] branch prints the raw value, so a status
# 1C grows later shows up as itself instead of claiming the order is new.

orders-title = <b>My orders</b> — page { $page } of { $pages }, { $total } in total
orders-empty = No orders yet. The catalog is at /catalog
orders-list-item = { $number } · { $date } · { $total } · { $status }
order-status =
    { $status ->
        [new] new
        [confirmed] confirmed
        [shipped] shipped
        [completed] completed
        [cancelled] cancelled
       *[other] { $status }
    }
order-number = #{ $number }
order-card =
    <b>Order { $number }</b> of { $date }

    Status: { order-status }
    Address: { $address }
    Recipient: { $recipient }, { $phone }
    Note: { $has_comment ->
        [yes] { $comment }
       *[no] none
    }

    { $lines }

    Total: { $total }
order-card-next-steps = A manager will call you on { $phone }. Settlement and delivery are agreed when the order is confirmed, and the delivery charge is quoted separately.
order-line = { $position }. { $name } — { $quantity } × { $price } = { $total }
order-lines-truncated = … and { $count } more items in this order. A manager can read out the rest.
order-cancelled-by =
    Cancelled by { $by ->
        [manager] the shop
       *[customer] you
    }
order-cancellation-reason = Reason: { $reason }
order-cancel-button = Cancel the order
order-cancel-confirm = Cancel order { $number }? It cannot be brought back — place a new one if you need to.
order-cancel-yes-button = Yes, cancel it
order-cancelled-toast = Order cancelled.
order-edit-address-button = Change the address
order-address-prompt = Send the new delivery address as one line.
order-address-changed-toast = Delivery address updated.
