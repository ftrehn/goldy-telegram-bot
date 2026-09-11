auth-registration-required = Чтобы пользоваться ботом, поделитесь номером телефона — нажмите кнопку ниже.
auth-share-phone-button = Поделиться номером
auth-contact-not-yours = Это чужой контакт. Нажмите кнопку и отправьте свой номер.
auth-contact-without-number = В контакте нет номера телефона. Попробуйте ещё раз.

error-forbidden = Недостаточно прав для этого действия.
error-blocked = Ваш доступ ограничен. Обратитесь в поддержку.
error-not-found = Не найдено.
error-already-exists = Этот номер или аккаунт уже занят. Попробуйте ещё раз.
error-last-account = Нельзя отвязать единственный мессенджер — иначе мы не сможем с вами связаться.
error-account-not-linked = Этот мессенджер и так не привязан.
error-already-blocked = Пользователь уже заблокирован.
error-not-blocked = Пользователь не заблокирован.
error-unknown = Что-то пошло не так. Мы уже разбираемся.

# Отказы сценария покупки. Ни одно из этих сообщений не имеет права нести
# плейсхолдер: handle_app_error зовёт i18n.get(key) без аргументов, а Fluent на
# недостающий аргумент не подставляет ничего — он поднимает FluentMessageError.
# Это не AppError, поэтому падает сам обработчик ошибок, и человек не получает
# вообще ничего вместо отказа, который для него и написали.
error-check-value = Проверьте, что вы ввели: значение не подходит.
cart-empty = Корзина пуста — добавьте товары, прежде чем оформлять заказ.
cart-line-not-found = Этой позиции в корзине уже нет. Откройте корзину заново.
cart-full = В корзине слишком много позиций. Уберите лишнее или оформите заказ частями.
cart-not-found = Корзины пока нет — добавьте в неё первый товар.
cart-repriced = Цена изменилась, пока вы оформляли заказ. Проверьте сумму и подтвердите ещё раз.
cart-line-unavailable = Состав корзины изменился, проверьте её.
quantity-too-small = Количество должно быть не меньше одного.
quantity-too-large = Столько за раз заказать нельзя. Уменьшите количество или свяжитесь с менеджером.
money-currency-mismatch = В одном заказе не может быть разных валют. Свяжитесь с менеджером.
order-empty = В заказе нет ни одной позиции.
order-transition-refused = Заказ уже в другом статусе — этот переход невозможен.
order-cannot-cancel = Заказ уже отгружен, отменить его через бота нельзя. Напишите менеджеру.
order-reason-required = Укажите причину отмены.
order-not-editable = Этот заказ уже нельзя править.
order-not-found = Такого заказа нет.
catalog-product-gone = Товара больше нет в каталоге.
catalog-price-missing = Цены сейчас недоступны. Мы уже разбираемся, попробуйте позже.
catalog-price-unsupported = Ваш прайс-лист сейчас не поддерживается. Свяжитесь с менеджером.
search-term-too-short = Запрос слишком короткий или слишком длинный — попробуйте иначе.

# Кнопки, которые нужны сразу пяти диалогам.
common-back-button = Назад
common-close-button = Закрыть
common-cancel-button = Отмена
common-confirm-button = Подтвердить
paging-prev-button = ← Назад
paging-next-button = Вперёд →

# Бейджи, которые рисуют и витрина, и корзина, и карточка заказа.
stock-badge =
    { $in_stock ->
        [yes] В наличии: { $stock } { $unit }
       *[no] Под заказ
    }
price-on-request = Цена по запросу

# Описания для меню команд, которое Telegram рисует у поля ввода. Отдельные
# ключи, а не разрезанная help-customer: у описания команды свой предел в 256
# символов и никакой разметки. /manage_orders здесь нет намеренно — help-staff
# существует ровно затем, чтобы покупателю не сообщали о командах персонала.
command-catalog = Каталог товаров
command-search = Поиск по названию и артикулу
command-cart = Корзина
command-orders = Мои заказы
command-me = Мой профиль
command-help = Что умеет бот

start-welcome = Здравствуйте, { $name }! Вы зарегистрированы.
start-welcome-back = С возвращением, { $name }!

help-customer =
    <b>Что я умею</b>

    /catalog — каталог товаров
    /search — поиск по названию и артикулу
    /cart — корзина
    /orders — мои заказы
    /me — мой профиль
    /help — эта справка
help-staff =
    <b>Что я умею</b>

    /catalog — каталог товаров
    /search — поиск по названию и артикулу
    /cart — корзина
    /orders — мои заказы
    /me — мой профиль
    /help — эта справка

    <b>Для персонала</b>
    /admin — управление пользователями
    /manage_orders — очередь заказов

me-profile =
    <b>{ $name }</b>

    Телефон: { $phone }
    Роль: { $role ->
        [manager] менеджер
        [admin] администратор
       *[customer] покупатель
    }
    Язык: { $locale ->
        [en] English
       *[ru] Русский
    }
    Уведомления: { $notify }

unknown-command = Не понимаю. Наберите /help, чтобы увидеть список команд.
cancelled = Отменил. Наберите /help, если нужна подсказка.

profile-rename-button = Изменить имя
profile-locale-button = Язык
profile-notifications-button = Уведомления
profile-accounts-button = Отвязать мессенджер
profile-marketing-button = Переключить рассылку
profile-close-button = Закрыть
profile-back-button = Назад
profile-rename-prompt = Отправьте новое имя. Можно с фамилией через пробел.
profile-locale-prompt = Выберите язык.
profile-notifications-prompt = Сейчас уведомления приходят в { $notify }. Куда слать?
profile-accounts-prompt = Какой мессенджер отвязать?

admin-users-title = <b>Пользователи</b> — страница { $page } из { $pages }, всего { $total }
admin-empty = Пока никого нет.
admin-user-card =
    <b>{ $name }</b>

    Телефон: { $phone }
    Роль: { $role ->
        [manager] менеджер
        [admin] администратор
       *[customer] покупатель
    }
    Статус: { $status ->
        [blocked] заблокирован
       *[active] активен
    }
    Язык: { $locale }
    Причина блокировки: { $reason }
admin-block-button = Заблокировать
admin-unblock-button = Разблокировать
admin-role-button = Изменить роль
admin-back-button = Назад
admin-close-button = Закрыть
admin-prev-button = ← Назад
admin-next-button = Вперёд →
admin-block-reason-prompt = Отправьте причину блокировки. Её увидит тот, кто будет разблокировать.
admin-role-prompt = Выберите роль. Администратора через бота выдать нельзя.
