# Редизайн review-экрана по референсам proxy-клиентов

- Дата: 2026-04-02
- Статус: done
- Источник: уточнение пользователя уйти от абстрактных концептов и взять стандартные интерфейсы Happ, Clash Verge Rev и Koala Clash

## Цель

Пересобрать страницу сравнения дизайнов так, чтобы она опиралась не на свободные визуальные концепции, а на узнаваемые паттерны реальных proxy/VPN-клиентов: desktop-dashboard семейства Clash и list-driven UX Happ.

## Изменения

- Зафиксировать паттерны референсов:
  - `Clash Verge Rev`: тёмный desktop-shell, левая навигация, dashboard из плотных operational-панелей;
  - `Koala Clash`: тот же desktop-shell, но мягче визуально, с более заметным glass/slate treatment и акцентом на selector/main page;
  - `Happ`: list-driven, подписки и сервера как основной сценарий, быстрые действия по строкам, ping и current connection.
- Переписать `gui/design_review.html` под три прямых reference-style варианта вместо авторских концептов.
- Сохранить работу страницы на живых данных из `/api/store`.
- Обновить тесты так, чтобы они проверяли новые reference-style секции.

## Проверки

- `python3 -m py_compile gui/gui_server.py`
- `python3 -m unittest tests.test_gui_server`
- Локальный HTTP smoke:
  - открыть `/design-review`;
  - убедиться, что рендерятся секции `happ`, `clash-verge`, `koala`;
  - убедиться, что `/api/store` продолжает использоваться как источник данных.

## Допущения

- На этой итерации меняется именно review-экран вариантов, а не основной production UI.
- `Clash Verge Rev` и `Koala Clash` достаточно близки по архитектуре, поэтому различие между ними в review делается через плотность, обработку поверхностей и presentation main page.
- Для `Happ` допустимо адаптировать mobile-first логику в desktop web preview, сохранив главное: списочный сценарий, ping, быстрые действия и акцент на подписках/текущем соединении.

## Итог

- Страница `gui/design_review.html` полностью пересобрана под прямые референсы вместо абстрактных концептов:
  - `Happ-style Main List`;
  - `Clash Verge Rev-style Desktop`;
  - `Koala Clash-style Glass Main Page`.
- Все три варианта продолжают читать живые данные из `/api/store`, а не из статического mock JSON.
- Текущий production-маршрут GUI не изменён: review-экран остаётся отдельным маршрутом `/design-review`.
- Обновлён unit-тест на наличие новых reference-style секций.
- Подтверждено:
  - `python3 -m py_compile gui/gui_server.py`;
  - `python3 -m unittest tests.test_gui_server`;
  - локальный HTTP smoke на `/design-review` с проверкой секций `happ`, `clash-verge`, `koala`.
- Остаточный риск: browser-level сравнение через реальный графический браузер в этой сессии не выполнялось; подтверждены HTML-отдача, backend API и локальные Python-проверки.
