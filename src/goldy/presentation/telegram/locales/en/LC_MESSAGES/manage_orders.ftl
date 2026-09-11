# The staff order queue: queue, card, filter, status change.
#
# A dialog of its own rather than a branch of /admin: the admin side is about
# people and this is about orders, and a shared "back" button in a stitched
# dialog would have to remember which hub it came from — state that exists only
# to serve the stitching.

manage-orders-title = <b>Order queue</b> — page { $page } of { $pages }, { $total } in total
manage-orders-empty = No orders.
manage-orders-item = { $number } · { $date } · { $customer } · { $total } · { $status }
manage-orders-filter-button = Filter: { $filter }
manage-orders-filter-prompt = Show orders in status:
manage-orders-filter-any = any
manage-orders-filter-any-button = All statuses
manage-orders-card =
    <b>Order { $number }</b> of { $date }

    Status: { order-status }
    Customer: { $customer } { $blocked_mark }
    Address: { $address }
    Recipient: { $recipient }, { $phone }
    Note: { $has_comment ->
        [yes] { $comment }
       *[no] none
    }

    { $lines }

    Total: { $total }
manage-orders-line = { $position }. { $name } — { $quantity } × { $price } = { $total } · { $stock }
manage-orders-customer-blocked = ⚠ customer is blocked
manage-orders-status-button = Change status
manage-orders-status-prompt = Which status should this order move to?
manage-orders-reason-prompt = Send the reason for cancelling — the customer will read it.
manage-orders-status-changed-toast = Order status updated.
