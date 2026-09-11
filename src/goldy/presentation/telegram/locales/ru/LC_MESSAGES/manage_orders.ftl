# Очередь заказов персонала: очередь, карточка, фильтр, смена статуса.
#
# Отдельный диалог, а не ветка внутри /admin: админка про людей, а это про
# заказы, и общая кнопка «Назад» в сшитом диалоге обязана была бы помнить, из
# какого хаба пришли, — состояние, существующее только ради сшивки.

manage-orders-title = <b>Очередь заказов</b> — страница { $page } из { $pages }, всего { $total }
manage-orders-empty = Заказов нет.
manage-orders-item = { $number } · { $date } · { $customer } · { $total } · { $status }
manage-orders-filter-button = Фильтр: { $filter }
manage-orders-filter-prompt = Показывать заказы в статусе:
manage-orders-filter-any = любой
manage-orders-filter-any-button = Все статусы
manage-orders-card =
    <b>Заказ { $number }</b> от { $date }

    Статус: { order-status }
    Покупатель: { $customer } { $blocked_mark }
    Адрес: { $address }
    Получатель: { $recipient }, { $phone }
    Комментарий: { $has_comment ->
        [yes] { $comment }
       *[no] нет
    }

    { $lines }

    Итого: { $total }
manage-orders-line = { $position }. { $name } — { $quantity } × { $price } = { $total } · { $stock }
manage-orders-customer-blocked = ⚠ покупатель заблокирован
manage-orders-status-button = Сменить статус
manage-orders-status-prompt = В какой статус перевести заказ?
manage-orders-reason-prompt = Отправьте причину отмены — её увидит покупатель.
manage-orders-status-changed-toast = Статус заказа обновлён.
