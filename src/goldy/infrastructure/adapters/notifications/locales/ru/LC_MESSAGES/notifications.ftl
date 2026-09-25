# Тексты, которые воркер шлёт сам, без запроса от человека.
#
# Отдельный файл, а не общий с диалогами: их читает другой процесс, который не
# импортирует presentation и не должен начинать.
#
# Плейсхолдер без аргумента здесь не превращается в текст — fluent.runtime
# возвращает ошибку, рендерер поднимает NotificationRenderError, и сообщение не
# уходит вовсе. Поэтому у «есть причина» и «нет причины» два разных ключа, а не
# один селектор: селектор всё равно обязали бы передавать { $reason } всегда.
#
# notification-order-status — вспомогательное сообщение, его не отправляют
# отдельно; на него ссылаются два других и передают ему тот же { $status }.
# Ветка *[other] печатает сырое значение: новый статус из 1С покажется как есть,
# а не соврёт «новый».

notification-order-status =
    { $status ->
        [new] новый
        [confirmed] подтверждён
        [shipped] отгружен
        [completed] выполнен
        [cancelled] отменён
       *[other] { $status }
    }

notification-order-placed =
    Новый заказ { $number }

    Получатель: { $customer }, { $phone }
    Адрес: { $address }
    Позиций: { $lines }
    Итого: { $total }

notification-order-status-changed =
    Заказ { $number } — { notification-order-status }.

notification-order-status-changed-reason =
    Заказ { $number } — { notification-order-status }.
    Причина: { $reason }

notification-order-address-changed =
    Адрес доставки заказа { $number } изменён.

    Было: { $old_address }
    Стало: { $new_address }

notification-order-handover-rejected =
    Заказ { $number } не передан на сайт: { $code ->
        [prices_changed] цены изменились с момента оформления
        [item_unavailable] позиции нет в продаже на сайте
        [quantity_not_multiple] количество не кратно упаковке
        [credit_limit_exceeded] не хватает кредитного лимита компании
        [customer_not_linked] покупатель отвязал аккаунт сайта
        [external_id_reused] на сайте уже есть заказ с этим номером
        [rate_limited] сайт ограничил приём заказов
       *[other] сайт ответил «{ $code }»
    }.
    Заказ остаётся в боте — оформите его на сайте или в 1С вручную.
