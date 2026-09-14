# The cart, and the confirmation before emptying it.
#
# cart-screen-empty is not cart-empty from common.ftl. This one describes the
# ordinary state of a cart nobody has filled and invites; that one explains a
# refusal — checkout ran, and there was nothing to check out.

cart-title =
    <b>Cart</b> — { $count ->
        [one] { $count } item
       *[other] { $count } items
    } for { $total }
cart-screen-empty = Your cart is empty. The goods are in the catalog, /catalog
cart-line = { $position }. { $name } — { $quantity } × { $price } = { $total } { $mark }
cart-line-unavailable-mark = ⚠ gone from the catalog
cart-unavailable-notice = The marked lines have left the catalog. Remove them and the order can be placed.
cart-unpriced-notice = The lines reading "price on request" have no price under your price list. Remove them or write to a manager, and the order can be placed.
cart-remove-unavailable-button = Remove unavailable
cart-checkout-button = Place the order
cart-clear-button = Empty the cart
cart-clear-confirm = Empty the whole cart? The contents cannot be brought back.
cart-cleared-toast = Cart emptied.
cart-plus-button = +
cart-minus-button = −
cart-remove-button = Remove
cart-quantity-button = Quantity
cart-quantity-prompt = Send the quantity as a number — from 1 to { $max }.
cart-continue-button = To the catalog
