# Каталог: категории, список, карточка, описание, поиск и его пустая выдача.
#
# Бейдж наличия и «Цена по запросу» лежат в common.ftl: их рисует и каталог, и
# корзина, а один ключ нельзя определить в двух файлах — бандл молча оставит
# первое определение, и второе место начнёт показывать чужой текст.

catalog-title = <b>Каталог</b>
catalog-category-title = <b>{ $name }</b>
catalog-pick-category = Выберите раздел или откройте список товаров.
catalog-no-categories = Внутри разделов нет — откройте список товаров.
catalog-all-products = Весь каталог
catalog-show-products-button = Показать товары
catalog-up-button = ↑ Уровень выше
catalog-search-button = Поиск
catalog-list-title = <b>{ $category }</b> — страница { $page } из { $pages }, всего { $total }
catalog-list-empty = Здесь пока нет товаров.
catalog-list-item = { $name } — { $price }
catalog-sort-button =
    Сортировка: { $sort ->
        [price] по цене
       *[name] по названию
    }
catalog-sku =
    Артикул: { $has_sku ->
        [yes] { $sku }
       *[no] не указан
    }
catalog-card =
    <b>{ $name }</b>

    { catalog-sku }
    { $has_price ->
        [yes] Цена: { $price } за { $unit }
       *[no] { price-on-request }
    }
    { stock-badge }

    { $excerpt }
catalog-description-button = Описание
catalog-description =
    <b>{ $name }</b>

    { $description }
catalog-add-button = В корзину
catalog-added-toast = Добавили в корзину: { $name }
catalog-open-cart-button = Корзина
catalog-search-prompt = Что ищем? Отправьте название или артикул — искать будем по всему каталогу.
catalog-search-title = Найдено { $total } по запросу «{ $term }» во всём каталоге — страница { $page } из { $pages }
catalog-search-empty = По запросу «{ $term }» ничего не нашлось. Проверьте артикул или попробуйте другое слово.
catalog-search-again-button = Искать снова
catalog-to-catalog-button = В каталог
