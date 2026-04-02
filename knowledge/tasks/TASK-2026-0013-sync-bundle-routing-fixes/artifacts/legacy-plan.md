# Синхронизировать routing-правки из рабочего bundle

- Дата: 2026-03-28
- Статус: done
- Источник: синхронизация проверенных изменений из `/opt/subvost-xray-tun/`

## Цель

Перенести в репозиторий актуальную policy-модель `default -> proxy` без общего `direct` для `.ru/.su/.xn--p1ai` и с точечным исключением для `public-service.example.com`.

## Изменения

- Обновить `singbox-tun-subvost.json`:
  - убрать общее DNS-правило `dns-direct` для `.ru/.su/.xn--p1ai`;
  - убрать общее route-правило `direct` для `.ru/.su/.xn--p1ai`;
  - добавить точечные DNS и route-исключения для `public-service.example.com` и `.public-service.example.com`;
  - сохранить служебный `direct` только для процессов `xray` и `sing-box`.

## Проверки

- Проверить валидность JSON через `python3 -m json.tool`.
- Выполнить `sing-box check` для обновлённого конфига.
- Сверить, что diff с рабочим bundle по `singbox-tun-subvost.json` исчез.

## Допущения

- В репозиторий переносится только уже проверенная рабочая policy; live smoke с реальным перезапуском VPN остаётся ручной проверкой вне этой синхронизации.

## Итог

- `singbox-tun-subvost.json` синхронизирован с рабочим bundle из `/opt/subvost-xray-tun/`.
- В репозитории удалено общее `direct`-исключение для `.ru/.su/.xn--p1ai` и добавлен точечный allowlist для `public-service.example.com` и `.public-service.example.com`.
- Проверки пройдены: `python3 -m json.tool`, `sing-box check`, `diff -u` с рабочим bundle не показывает расхождений.
