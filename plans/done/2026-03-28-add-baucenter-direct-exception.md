# Добавить direct-исключение для baucenter.ru

- Дата: 2026-03-28
- Статус: done
- Источник: пользовательский запрос на точечный обход VPN для `https://baucenter.ru`

## Цель

Добавить allowlist для `baucenter.ru` без возврата общего `direct` для национальных доменов.

## Изменения

- Обновить `singbox-tun-subvost.json`:
  - добавить DNS-правило `dns-direct` для `baucenter.ru`;
  - добавить route-правило `direct` для `baucenter.ru`;
  - охватить как точный домен, так и поддомены.

## Проверки

- Проверить валидность JSON.
- Выполнить `sing-box check` для обновлённого конфига.

## Допущения

- Под `https://baucenter.ru` подразумевается и точный хост `baucenter.ru`, и его поддомены, если сайт использует редиректы или внешние поддомены внутри своей зоны.

## Итог

- В `singbox-tun-subvost.json` добавлены точечные правила `dns-direct` и `direct` для `baucenter.ru` и `.baucenter.ru`.
- Общая модель `default -> proxy` сохранена; обход VPN расширен только на целевой домен.
- Проверки пройдены: `python3 -m json.tool` и `sing-box check -c /home/prog7/MyWorkspace/40-Tools-and-Apps/Apps/subvost-xray-tun/singbox-tun-subvost.json`.
