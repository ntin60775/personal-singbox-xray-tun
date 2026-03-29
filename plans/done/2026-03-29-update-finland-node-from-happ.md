# Обновление Finland-узла из Happ для desktop bundle

- Дата: 2026-03-29
- Статус: done
- Источник: запрос пользователя восстановить VPN в bundle после обновления локаций у провайдера

## Цель

Обновить параметры рабочего узла Finland (Helsinki) в desktop bundle так, чтобы локальная operator-managed копия `xray-tun-subvost.json` снова соответствовала актуальной конфигурации из Happ VPN и проходила хотя бы локальную сетевую проверку рукопожатия REALITY.

Ожидаемый результат: локальный runtime bundle использует новый адрес сервера и новый `PublicKey`, а временный тестовый `xray`-запуск с локальным SOCKS больше не падает на старом REALITY-ключе.

## Изменения

- Обновить локальную operator-managed копию `xray-tun-subvost.json` по данным рабочего узла из Happ VPN.
- Сохранить совместимость текущей схемы `xray + sing-box TUN`, не меняя `singbox-tun-subvost.json`.
- Убрать путаницу с launcher'ами: оставить только актуальный ярлык bundle в пользовательском меню.

## Проверки

- `xray run -test -c локальная operator-managed копия xray-tun-subvost.json`
- `sing-box check -c singbox-tun-subvost.json`
- Временный smoke: отдельный `xray` на тестовом локальном SOCKS-порту и запрос через `curl --socks5-hostname`

## Допущения

- Источником истины для параметров узла считаются данные из рабочего профиля Happ VPN на телефоне.
- Подписка `https://sub.subvost.fun/...` для этого аккаунта отдает заглушку для неподдерживаемых клиентов, поэтому raw-узел берётся не из subscription response, а из параметров активного узла в Happ.
- Repo-managed копия `xray-tun-subvost.json` может позже храниться в Git только в санитизированном виде с placeholders вместо реальных `id`, `PublicKey` и `shortId`; это не отменяет факт локальной runtime-проверки на operator-managed копии.
- Полный TUN-smoke через `run-xray-tun-subvost.sh` и GUI требует отдельной ручной проверки на целевой машине с `sudo`/`pkexec`.

## Итог

В локальной operator-managed копии `xray-tun-subvost.json` обновлены два поля рабочего Finland-узла из Happ VPN: адрес сервера изменён с устаревшего `152.53.39.18` на `45.137.69.71`, а `PublicKey` REALITY заменён на актуальный ключ из мобильного клиента.

Статические проверки прошли на локальной operator-managed копии: `xray run -test -c xray-tun-subvost.json` завершился `Configuration OK`, `sing-box check -c singbox-tun-subvost.json` завершился без ошибок. Дополнительно выполнен сетевой smoke через временный локальный SOCKS-порт: запрос `curl --socks5-hostname 127.0.0.1:10809 https://clients3.google.com/generate_204` вернул `HTTP/2 204`, а лог `xray` подтвердил успешный `tunneling request` через `45.137.69.71:443`.

Старый пользовательский ярлык `personal-singbox-xray-tun.desktop` удалён из `~/.local/share/applications`, чтобы в меню остался только актуальный launcher bundle. Остаточный риск: repo-managed копия `xray-tun-subvost.json` может быть санитизирована перед commit и тогда перестаёт быть готовым runtime-конфигом; полный TUN/GUI smoke с `run-xray-tun-subvost.sh`, `tun0` и `pkexec` не выполнялся в этой сессии и должен быть подтверждён отдельно на целевой машине.
