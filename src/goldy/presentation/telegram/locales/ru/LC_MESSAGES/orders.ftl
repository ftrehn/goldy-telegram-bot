# Заказы покупателя: список, карточка, правка адреса, отмена.
#
# order-status — одно сообщение с селектором, на которое ссылаются и карточка,
# и список, и очередь персонала. Параметризованный терм -order-status(status:
# $status) здесь не работает: аргументы терма обязаны быть литералами, и парсер
# отдаёт E0014. Ветка *[other] печатает сырое значение — новый статус из 1С
# покажется как есть, а не соврёт «новый».

orders-title = <b>Мои заказы</b> — страница { $page } из { $pages }, всего { $total }
orders-empty = Заказов пока нет. Каталог — /catalog
orders-list-item = { $number } · { $date } · { $total } · { $status }
order-status =
    { $status ->
        [new] новый
        [confirmed] подтверждён
        [shipped] отгружен
        [completed] выполнен
        [cancelled] отменён
       *[other] { $status }
    }
order-number = № { $number }
order-card =
    <b>Заказ { $number }</b> от { $date }

    Статус: { order-status }
    Адрес: { $address }
    Получатель: { $recipient }, { $phone }
    Комментарий: { $has_comment ->
        [yes] { $comment }
       *[no] нет
    }

    { $lines }

    Итого: { $total }
order-card-next-steps = Менеджер свяжется с вами по телефону { $phone }. Расчёт и доставку обсудите при подтверждении заказа, стоимость доставки менеджер назовёт отдельно.
order-line = { $position }. { $name } — { $quantity } × { $price } = { $total }
order-lines-truncated = … и ещё позиций в заказе: { $count }. Полный состав подскажет менеджер.
order-cancelled-by =
    Заказ отменён { $by ->
        [manager] магазином
       *[customer] вами
    }
order-cancellation-reason = Причина: { $reason }
order-cancel-button = Отменить заказ
order-cancel-confirm = Отменить заказ { $number }? Вернуть его не получится — при необходимости оформите новый.
order-cancel-yes-button = Да, отменить
order-cancelled-toast = Заказ отменён.
order-edit-address-button = Изменить адрес
order-address-prompt = Отправьте новый адрес доставки одной строкой.
order-address-changed-toast = Адрес доставки обновлён.
