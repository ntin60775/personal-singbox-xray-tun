# Взять DNS-часть из Happ routing profile

- Дата: 2026-03-30
- Статус: done
- Источник: запрос пользователя применить только DNS-часть нового Happ routing profile без `blocksites`

## Цель

Перенести в desktop bundle только DNS-настройки из экспортированного Happ routing profile так, чтобы текущая модель маршрутизации `default -> proxy` сохранилась без возврата к широким `direct`-категориям и без DNS-blocklist.

## Изменения

- Обновить `singbox-tun-subvost.json`:
  - заменить текущие UDP DNS-серверы на DoH-серверы по данным профиля;
  - сохранить разделение `dns-proxy` и `dns-direct`;
  - добавить статические DNS-host overrides для доменов `host-a.example.com` и `host-b.example.com`;
  - не добавлять `blocksites`, `directsites`, `proxysites` и другие routing-политики из Happ.

## Проверки

- Проверить JSON на валидность.
- Выполнить `sing-box check -c singbox-tun-subvost.json`.
- Убедиться, что route policy в конфиге не изменилась за пределами DNS-секции.

## Допущения

- DNS-часть профиля переносится отдельно от routing-части, потому что широкие `direct`-исключения из Happ уже конфликтовали с целевой моделью bundle.
- Статические `dnshosts` применяются только на уровне резолва; фактическая маршрутизация к этим адресам остаётся под контролем существующих route-правил bundle.

## Итог

- В `singbox-tun-subvost.json` UDP DNS заменён на DoH по данным Happ-профиля: `dns-proxy` оставлен через `proxy` на `8.8.8.8/dns-query`, а `dns-direct` переведён на `77.88.8.8/dns-query` через `direct`.
- Добавлен отдельный `dns-hosts` с предопределёнными ответами для `host-a.example.com` и `host-b.example.com`, который применяется только в DNS-слое.
- Route policy bundle не менялась: `blocksites`, `directsites`, `proxysites` и другие routing-политики из Happ в конфиг не переносились.
- Проверки пройдены: `python3 -m json.tool singbox-tun-subvost.json`, `sing-box check -c singbox-tun-subvost.json`, `markdown-localization-guard` для итогового плана.
