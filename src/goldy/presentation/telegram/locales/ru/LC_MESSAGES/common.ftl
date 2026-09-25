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
address-outside-russia = Доставляем только по России: напишите адрес кириллицей.
address-without-building = В адресе нет номера дома. Укажите улицу и дом, иначе курьеру некуда ехать.
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
command-finance = Финансы компании

start-welcome = Здравствуйте, { $name }! Вы зарегистрированы.
start-welcome-back = С возвращением, { $name }!

help-customer =
    <b>Что я умею</b>

    /catalog — каталог товаров
    /search — поиск по названию и артикулу
    /cart — корзина
    /orders — мои заказы
    /finance — финансы компании (после привязки сайта)
    /me — мой профиль
    /help — эта справка
help-staff =
    <b>Что я умею</b>

    /catalog — каталог товаров
    /search — поиск по названию и артикулу
    /cart — корзина
    /orders — мои заказы
    /finance — финансы компании (после привязки сайта)
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

# Привязка к аккаунту сайта (ADR-0004). Отказы идут через ERROR_TEXTS и не
# несут плейсхолдеров — по той же причине, что отказы сценария покупки.
site-unavailable = Сайт сейчас не отвечает. Попробуйте через несколько минут.
site-not-linked =
    Аккаунт сайта не привязан. Откройте на tkgoldy.ru «Личный кабинет → Мессенджеры»
    и нажмите «Привязать Telegram» — бот откроется сам.
site-link-code-invalid = Ссылка для привязки устарела или уже использована. Получите новую в личном кабинете на сайте.
site-link-forbidden = Этот аккаунт сайта нельзя привязать к боту. Напишите менеджеру.
site-customer-not-linked = Сайт больше не узнаёт вашу привязку — её сняли в личном кабинете. Привяжите аккаунт заново.
site-finance-denied = Финансы компании вам недоступны: нужна подтверждённая организация и права руководителя или бухгалтера.
site-order-rejected = Сайт не принял действие с заказом. Напишите менеджеру.
site-order-not-cancellable = Заказ уже взят в работу — отменить его можно только через менеджера.

site-link-preview =
    <b>Привязать аккаунт сайта?</b>

    { $who }

    После привязки в боте будут ваши оптовые цены, заказы и финансы компании.
    Если это не вы — нажмите «Отмена».
site-link-confirm-button = Да, это я
site-link-cancel-button = Отмена
site-link-done =
    Готово: бот привязан к аккаунту { $who }. Цены в каталоге и корзине теперь ваши.
site-link-cancelled = Привязка отменена.
site-link-after-registration = Осталось подтвердить привязку аккаунта сайта.

profile-site-linked =
    Сайт: { $who }
profile-site-not-linked = Сайт: не привязан. Оптовые цены и финансы — после привязки в личном кабинете на tkgoldy.ru.
profile-site-unlink-button = Отвязать аккаунт сайта
profile-site-unlink-prompt = Отвязать аккаунт сайта? Бот вернётся к розничным ценам, финансы станут недоступны.
profile-site-unlinked-toast = Аккаунт сайта отвязан.

finance-title = <b>Финансы — { $company }</b>
finance-no-erp = Компания пока не связана с учётной системой — цифр нет. Их покажет менеджер.
finance-debt = Задолженность: { $amount }
finance-advance = Аванс: { $amount }
finance-overdue = Просрочено: { $amount }, до { $days } дн.
finance-credit-limit = Кредитный лимит: { $limit }, доступно { $available }
finance-credit-untracked = Кредитный лимит в учёте не ведётся.
finance-stale = ⚠ Учётная система не ответила — цифры на { $as_of }.
finance-partial = ⚠ Ответили не все партнёры компании — сумма неполная.
finance-footer = Отгрузки, оплаты и акт сверки — в личном кабинете на сайте.
