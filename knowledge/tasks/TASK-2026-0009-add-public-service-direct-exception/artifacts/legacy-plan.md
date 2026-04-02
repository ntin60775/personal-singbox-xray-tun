# Добавить direct-исключение для public-service.example.com

- Дата: 2026-03-28
- Статус: done
- Источник: пользовательский запрос на точечный обход VPN для `https://public-service.example.com`

## Цель

Добавить allowlist для `public-service.example.com` без возврата общего `direct` для национальных доменов.

## Изменения

- Обновить `singbox-tun-subvost.json`:
  - добавить DNS-правило `dns-direct` для `public-service.example.com`;
  - добавить route-правило `direct` для `public-service.example.com`;
  - охватить как точный домен, так и поддомены.

## Проверки

- Проверить валидность JSON.
- Выполнить `sing-box check` для обновлённого конфига.

## Допущения

- Под `https://public-service.example.com` подразумевается и точный хост `public-service.example.com`, и его поддомены, если сайт использует редиректы или внешние поддомены внутри своей зоны.

## Итог

- В `singbox-tun-subvost.json` добавлены точечные правила `dns-direct` и `direct` для `public-service.example.com` и `.public-service.example.com`.
- Общая модель `default -> proxy` сохранена; обход VPN расширен только на целевой домен.
- Проверки пройдены: `python3 -m json.tool` и `sing-box check -c /opt/subvost-xray-tun/singbox-tun-subvost.json`.
