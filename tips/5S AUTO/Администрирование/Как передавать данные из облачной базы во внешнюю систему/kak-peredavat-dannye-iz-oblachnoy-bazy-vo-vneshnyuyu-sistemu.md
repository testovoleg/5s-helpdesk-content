# Как передавать данные из облачной базы во внешнюю систему

<table><tr><td><b>Создано:</b> 27.10.2026</td></tr></table>

## Вопрос

Нужно регулярно передавать данные из облачной базы 5S AUTO во внешнюю систему – на сайт, в B2B-витрину или систему аналитики: номенклатуру, цены, остатки, заказы. Можно ли получить доступ к базе на чтение – например, через веб-публикацию и стандартный интерфейс OData?

## Ответ

В облачной версии 5S AUTO данные для внешних систем передаются через API-шлюзы и встроенные выгрузки. Доступ к базе через OData предоставляется только индивидуально: внешние запросы создают неконтролируемую нагрузку на серверы и могут нарушить их работу. Публикацию большого перечня объектов, например для MCP-коннектора или внешней системы аналитики, не открываем.

> [!NOTE]
> Программа работает только в толстом клиенте 1С. Веб-клиент и тонкий клиент не поддерживаются, поэтому через веб-публикацию базы работать с программой нельзя.

Выберите подходящий способ:

**1. Выгрузка прайс-листов.** Цены и остатки товаров выгружаются в файл, на FTP или по e-mail по расписанию – см. статью «[Выгрузка прайс-листов](https://kb.5systems.ru/articles/5s-auto/sklad-i-zapchasti/vygruzka-prays-listov)».

**2. Выгрузка для Авито.** Расширенная выгрузка товаров в формате Авито – см. статью «[Автоматическая публикация объявлений на Авито](https://kb.5systems.ru/articles/5s-auto/sklad-i-zapchasti/avtomaticheskaya-publikaciya-obyavleniy-na-avito)».

**3. API 5S AUTO.** Для авторизации используется метод входа шлюза [Auth API](https://api.5systems.ru/auth/v1/doc#tag/OpenID-Connect/paths/~1oidc~1login/post), логин и пароль пользователя 5S Cloud создаются самостоятельно – см. статью «[Создание и редактирование пользователей 5S Cloud](https://kb.5systems.ru/articles/5s-auto/administrirovanie-i-nastroyka-sistemy/sozdanie-i-redaktirovanie-polzovateley-5s-cloud)». Часть данных можно получить через шлюзы [Dataset API](https://api.5systems.ru/dataset/v1/doc) и [TSD API](https://api.5systems.ru/tsd/v1/doc). Подробнее – в статье «[API 5S AUTO](https://kb.5systems.ru/articles/5s-auto/administrirovanie-i-nastroyka-sistemy/api-5s-auto)».

**4. Своя обработка по расписанию.** Данные можно выгружать внешней обработкой, которая запускается регламентным заданием – см. статью «[Запуск произвольных обработок в регламентном задании](https://kb.5systems.ru/articles/5s-auto/administrirovanie-i-nastroyka-sistemy/zapusk-proizvolnykh-obrabotok-v-reglamentnom-zadanii)».

**5. Версия «на своем сервере».** В коробочной версии программа работает на собственных ресурсах компании, и в OData можно публиковать любые объекты.

## Материалы для изучения

- «[API 5S AUTO](https://kb.5systems.ru/articles/5s-auto/administrirovanie-i-nastroyka-sistemy/api-5s-auto)» – шлюзы API и настройка интеграции.
- «[Создание и редактирование пользователей 5S Cloud](https://kb.5systems.ru/articles/5s-auto/administrirovanie-i-nastroyka-sistemy/sozdanie-i-redaktirovanie-polzovateley-5s-cloud)» – учетные записи для авторизации в API.
- «[Выгрузка прайс-листов](https://kb.5systems.ru/articles/5s-auto/sklad-i-zapchasti/vygruzka-prays-listov)» – выгрузка цен и остатков по расписанию.
- «[Автоматическая публикация объявлений на Авито](https://kb.5systems.ru/articles/5s-auto/sklad-i-zapchasti/avtomaticheskaya-publikaciya-obyavleniy-na-avito)» – выгрузка товаров в формате Авито.
- «[Запуск произвольных обработок в регламентном задании](https://kb.5systems.ru/articles/5s-auto/administrirovanie-i-nastroyka-sistemy/zapusk-proizvolnykh-obrabotok-v-reglamentnom-zadanii)» – выгрузка данных своей обработкой по расписанию.

## Похожие вопросы

- Как передавать данные из облачной базы во внешнюю систему
- read-only доступ к базе 1С / 5S AUTO
- Нужен доступ к базе на чтение через OData
- Как выгрузить номенклатуру, цены и остатки на сайт
- Веб-клиент опубликованной базы не запускается
- Где документация по API 5S AUTO

## Теги

OData, API, API 5S AUTO, интеграция, внешняя система, сайт, выгрузка данных, прайс-лист, веб-публикация, веб-клиент, 5S Cloud, облачная версия
