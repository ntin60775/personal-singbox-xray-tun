# Синхронизировать routing-правки из рабочего bundle

- Дата: 2026-03-28
- Статус: done
- Источник: синхронизация проверенных изменений из `/home/prog7/MyWorkspace/40-Tools-and-Apps/Apps/subvost-xray-tun/`

## Цель

Перенести в репозиторий актуальную policy-модель `default -> proxy` без общего `direct` для `.ru/.su/.xn--p1ai` и с точечным исключением для `baucenter.ru`.

## Изменения

- Обновить `singbox-tun-subvost.json`:
  - убрать общее DNS-правило `dns-direct` для `.ru/.su/.xn--p1ai`;
  - убрать общее route-правило `direct` для `.ru/.su/.xn--p1ai`;
  - добавить точечные DNS и route-исключения для `baucenter.ru` и `.baucenter.ru`;
  - сохранить служебный `direct` только для процессов `xray` и `sing-box`.

## Проверки

- Проверить валидность JSON через `python3 -m json.tool`.
- Выполнить `sing-box check` для обновлённого конфига.
- Сверить, что diff с рабочим bundle по `singbox-tun-subvost.json` исчез.

## Допущения

- В репозиторий переносится только уже проверенная рабочая policy; live smoke с реальным перезапуском VPN остаётся ручной проверкой вне этой синхронизации.

## Итог

- `singbox-tun-subvost.json` синхронизирован с рабочим bundle из `/home/prog7/MyWorkspace/40-Tools-and-Apps/Apps/subvost-xray-tun/`.
- В репозитории удалено общее `direct`-исключение для `.ru/.su/.xn--p1ai` и добавлен точечный allowlist для `baucenter.ru` и `.baucenter.ru`.
- Проверки пройдены: `python3 -m json.tool`, `sing-box check`, `diff -u` с рабочим bundle не показывает расхождений.
