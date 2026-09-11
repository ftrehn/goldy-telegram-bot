# Корзина и подтверждение очистки.
#
# cart-screen-empty — это не cart-empty из common.ftl. Первое рассказывает про
# обычное состояние пустой корзины и зовёт в каталог, второе объясняет отказ:
# оформление запустили, а оформлять нечего.

cart-title =
    <b>Корзина</b> — { $count ->
        [one] { $count } позиция
        [few] { $count } позиции
        [many] { $count } позиций
       *[other] { $count } позиции
    } на { $total }
cart-screen-empty = Корзина пуста. Товары — в каталоге, /catalog
cart-line = { $position }. { $name } — { $quantity } × { $price } = { $total } { $mark }
cart-line-unavailable-mark = ⚠ нет в каталоге
cart-unavailable-notice = Отмеченные позиции пропали из каталога. Уберите их — тогда заказ можно будет оформить.
cart-unpriced-notice = На позиции с пометкой «Цена по запросу» сейчас нет цены для вашего прайс-листа. Уберите их или напишите менеджеру — тогда заказ можно будет оформить.
cart-remove-unavailable-button = Убрать недоступные
cart-checkout-button = Оформить заказ
cart-clear-button = Очистить корзину
cart-clear-confirm = Очистить корзину целиком? Состав потом не восстановить.
cart-cleared-toast = Корзина очищена.
cart-plus-button = +
cart-minus-button = −
cart-remove-button = Убрать
cart-quantity-button = Количество
cart-quantity-prompt = Отправьте количество числом — от 1 до { $max }.
cart-continue-button = В каталог
