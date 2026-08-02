auth-registration-required = Чтобы пользоваться ботом, поделитесь номером телефона — нажмите кнопку ниже.
auth-share-phone-button = Поделиться номером
auth-contact-not-yours = Это чужой контакт. Нажмите кнопку и отправьте свой номер.
auth-contact-without-number = В контакте нет номера телефона. Попробуйте ещё раз.

error-forbidden = Недостаточно прав для этого действия.
error-blocked = Ваш доступ ограничен. Обратитесь в поддержку.
error-not-found = Не найдено.
error-already-exists = Этот номер или аккаунт уже занят. Попробуйте ещё раз.
error-last-account = Нельзя отвязать единственный мессенджер — иначе мы не сможем с вами связаться.
error-unknown = Что-то пошло не так. Мы уже разбираемся.

start-welcome = Здравствуйте, { $name }! Вы зарегистрированы.
start-welcome-back = С возвращением, { $name }!

help-customer =
    <b>Что я умею</b>

    /me — мой профиль
    /help — эта справка
help-staff =
    <b>Что я умею</b>

    /me — мой профиль
    /help — эта справка

    <b>Для персонала</b>
    /admin — управление пользователями

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
