# Оформление: адрес, получатель, телефон, комментарий, подтверждение, готово.
#
# checkout-done ссылается на order-card-next-steps из orders.ftl. Ссылка на
# сообщение резолвится в области видимости вызывающего, поэтому { $phone },
# переданный сюда, внутри виден — и обещание «менеджер свяжется» записано в
# проекте ровно один раз, а не двумя разошедшимися копиями.

checkout-address-prompt = Куда доставить? Отправьте адрес одной строкой: город, улицу, дом и квартиру.
checkout-address-last-button = Прошлый адрес: { $address }
checkout-recipient-prompt = Кто получит заказ? Отправьте имя — можно с фамилией через пробел.
checkout-recipient-me-button = Получатель — я
checkout-phone-prompt = Телефон получателя. Формат любой: 8 916 123-45-67 тоже подойдёт.
checkout-phone-mine-button = Мой номер: { $phone }
checkout-comment-prompt = Комментарий к заказу — например, удобное время доставки. Или пропустите шаг.
checkout-skip-button = Пропустить
checkout-confirm =
    <b>Проверьте заказ</b>

    Адрес: { $address }
    Получатель: { $recipient }
    Телефон: { $phone }
    Комментарий: { $has_comment ->
        [yes] { $comment }
       *[no] нет
    }

    Позиций: { $count }
    Итого: { $total }
checkout-confirm-button = Подтвердить заказ
checkout-placing = Оформляем заказ…
checkout-repriced-notice = Цена изменилась, проверьте заказ.
checkout-already-placed = Заказ уже оформлен — он в разделе «Мои заказы», /orders
checkout-done =
    Заказ { $number } принят.

    { order-card-next-steps }
checkout-open-order-button = Открыть заказ
checkout-to-catalog-button = В каталог
