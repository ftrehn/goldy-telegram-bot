# Checkout: address, recipient, phone, comment, confirmation, done.
#
# checkout-done references order-card-next-steps from orders.ftl. A message
# reference resolves in the caller's scope, so the { $phone } passed here is
# visible inside it — and the promise "a manager will call" is written once in
# the project rather than as two copies that drift apart.

checkout-address-prompt = Where should it go? Send the address as one line: city, street, building, flat.
checkout-address-last-button = Last address: { $address }
checkout-recipient-prompt = Who will receive the order? Send a name — a surname after a space is fine.
checkout-recipient-me-button = I am the recipient
checkout-phone-prompt = The recipient's phone. Any format will do.
checkout-phone-mine-button = My number: { $phone }
checkout-comment-prompt = A note for the order — a convenient delivery time, for instance. Or skip this step.
checkout-skip-button = Skip
checkout-confirm =
    <b>Check your order</b>

    Address: { $address }
    Recipient: { $recipient }
    Phone: { $phone }
    Note: { $has_comment ->
        [yes] { $comment }
       *[no] none
    }

    Lines: { $count }
    Total: { $total }
checkout-confirm-button = Place the order
checkout-placing = Placing your order…
checkout-repriced-notice = The price has changed — please check the order.
checkout-already-placed = This order has already been placed — it is under "My orders", /orders
checkout-done =
    Order { $number } accepted.

    { order-card-next-steps }
checkout-open-order-button = Open the order
checkout-to-catalog-button = To the catalog
