# The catalog: categories, listing, card, description, search and its empty page.
#
# The stock badge and "price on request" live in common.ftl, because both the
# catalog and the cart draw them and one key cannot be defined in two files —
# the bundle silently keeps the first definition and the other screen starts
# showing somebody else's wording.

catalog-title = <b>Catalog</b>
catalog-category-title = <b>{ $name }</b>
catalog-pick-category = Pick a section, or open the product listing.
catalog-no-categories = No sections inside — open the product listing.
catalog-all-products = The whole catalog
catalog-show-products-button = Show products
catalog-up-button = ↑ One level up
catalog-search-button = Search
catalog-list-title = <b>{ $category }</b> — page { $page } of { $pages }, { $total } in total
catalog-list-empty = Nothing here yet.
catalog-list-item = { $name } — { $price }
catalog-sort-button =
    Sorted: { $sort ->
        [price] by price
       *[name] by name
    }
catalog-sku =
    Article: { $has_sku ->
        [yes] { $sku }
       *[no] not set
    }
catalog-card =
    <b>{ $name }</b>

    { catalog-sku }
    { $has_price ->
        [yes] Price: { $price } per { $unit }
       *[no] { price-on-request }
    }
    { stock-badge }

    { $excerpt }
catalog-description-button = Description
catalog-description =
    <b>{ $name }</b>

    { $description }
catalog-add-button = Add to cart
catalog-added-toast = Added to your cart: { $name }
catalog-open-cart-button = Cart
catalog-search-prompt = What are you looking for? Send a name or an article — we search the whole catalog.
catalog-search-title = Found { $total } for "{ $term }" across the whole catalog — page { $page } of { $pages }
catalog-search-empty = Nothing matched "{ $term }". Check the article, or try another word.
catalog-search-again-button = Search again
catalog-to-catalog-button = To the catalog

# Links from the website. No placeholders: the product is either withdrawn or
# was never real, so there is nothing to name it with — and Fluent refuses to
# render a message whose argument nobody can fill.
deeplink-product-gone = That link points at a product the catalog no longer has. Here is the catalog — have a look at something similar.
deeplink-category-gone = The section that link pointed at is no longer in the catalog. Here is the catalog from the first screen.
