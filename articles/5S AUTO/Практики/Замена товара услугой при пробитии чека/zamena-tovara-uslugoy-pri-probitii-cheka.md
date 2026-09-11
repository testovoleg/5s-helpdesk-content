# Замена товара услугой при пробитии чека

<table><tr><td><b>Время чтения:</b> 6 мин.</td><td><b>Обновлено:</b> 24.06.2022</td></tr></table>

<sub>Источник: https://www.5systems.ru/help/zamena-tovara-uslugoy-pri-probitii-cheka</sub>

Открыть *План видов характеристик* ***«Свойства объектов»*** (Сервис → Все операции → План видов характеристик).

[ ![Замена товара услугой - Свойства](attachments/01-zamena-tovara-uslugoy-svoystva.jpg)](https://wiki.5-systems.ru/w/index.php/%D0%A4%D0%B0%D0%B9%D0%BB:%D0%97%D0%B0%D0%BC%D0%B5%D0%BD%D0%B0_%D1%82%D0%BE%D0%B2%D0%B0%D1%80%D0%B0_%D1%83%D1%81%D0%BB%D1%83%D0%B3%D0%BE%D0%B9_1-%D0%A1%D0%B2%D0%BE%D0%B9%D1%81%D1%82%D0%B2%D0%B0_%D0%BE%D0%B1%D1%8A%D0%B5%D0%BA%D1%82%D0%BE%D0%B2.jpg)

Сюда требуется добавить [ ![Кнопка Добавить](attachments/02-knopka-dobavit.png)](https://wiki.5-systems.ru/w/index.php/%D0%A4%D0%B0%D0%B9%D0%BB:%D0%98%D0%BA%D0%BE%D0%BD%D0%BA%D0%B0_%D0%94%D0%BE%D0%B1%D0%B0%D0%B2%D0%B8%D1%82%D1%8C.jpg) новое *свойство* с именем ***«НаименованиеДляЗамены»*** и с указанием *типа значений* ***«Номенклатура»***.

[ ![Замена товара услугой - Наименование для замены](attachments/03-zamena-tovara-uslugoy-naimenovanie-dlya-zameny.jpg)](https://wiki.5-systems.ru/w/index.php/%D0%A4%D0%B0%D0%B9%D0%BB:%D0%97%D0%B0%D0%BC%D0%B5%D0%BD%D0%B0_%D1%82%D0%BE%D0%B2%D0%B0%D1%80%D0%B0_%D1%83%D1%81%D0%BB%D1%83%D0%B3%D0%BE%D0%B9_2-%D0%9D%D0%B0%D0%B8%D0%BC%D0%B5%D0%BD%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5_%D0%B4%D0%BB%D1%8F_%D0%B7%D0%B0%D0%BC%D0%B5%D0%BD%D1%8B.jpg)

В *Регистре сведений* ***«Разыменование ссылок»*** нужно добавить [ ![Кнопка Добавить](attachments/04-knopka-dobavit.png)](https://wiki.5-systems.ru/w/index.php/%D0%A4%D0%B0%D0%B9%D0%BB:%D0%98%D0%BA%D0%BE%D0%BD%D0%BA%D0%B0_%D0%94%D0%BE%D0%B1%D0%B0%D0%B2%D0%B8%D1%82%D1%8C.jpg) новую запись:

*Ключ* = ***«ФК_ВариантЗаменыТовара»***

*Ссылка* = ***1*** *(Выбор типа данных = Число)*

[ ![Замена товара услугой - Разыменование ссылок](attachments/05-zamena-tovara-uslugoy-razymenovanie-ssylok.jpg)](https://wiki.5-systems.ru/w/index.php/%D0%A4%D0%B0%D0%B9%D0%BB:%D0%97%D0%B0%D0%BC%D0%B5%D0%BD%D0%B0_%D1%82%D0%BE%D0%B2%D0%B0%D1%80%D0%B0_%D1%83%D1%81%D0%BB%D1%83%D0%B3%D0%BE%D0%B9_3-%D0%A0%D0%B0%D0%B7%D1%8B%D0%BC%D0%B5%D0%BD%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5_%D1%81%D1%81%D1%8B%D0%BB%D0%BE%D0%BA.jpg)

В справочнике *«Типы номенклатуры»* либо в самом справочнике *«Номенклатура»* открыть ***Список свойств*** и добавить [ ![Кнопка Добавить](attachments/06-knopka-dobavit.png)](https://wiki.5-systems.ru/w/index.php/%D0%A4%D0%B0%D0%B9%D0%BB:%D0%98%D0%BA%D0%BE%D0%BD%D0%BA%D0%B0_%D0%94%D0%BE%D0%B1%D0%B0%D0%B2%D0%B8%D1%82%D1%8C.jpg) ранее созданное *свойство* ***НаименованиеДляЗамены***. В *значении* необходимо указать *номенклатуру, на которую будет производиться замена*.

[ ![Замена товара услугой - Номенклатура](attachments/07-zamena-tovara-uslugoy-nomenklatura.jpg)](https://wiki.5-systems.ru/w/index.php/%D0%A4%D0%B0%D0%B9%D0%BB:%D0%97%D0%B0%D0%BC%D0%B5%D0%BD%D0%B0_%D1%82%D0%BE%D0%B2%D0%B0%D1%80%D0%B0_%D1%83%D1%81%D0%BB%D1%83%D0%B3%D0%BE%D0%B9_4-%D0%9D%D0%BE%D0%BC%D0%B5%D0%BD%D0%BA%D0%BB%D0%B0%D1%82%D1%83%D1%80%D0%B0.jpg)

---

**Теги:** практики, чек, товар, услуга, касса
