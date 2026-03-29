# Добавить direct-исключения для `ssdemordp` и локальной сети

- Дата: 2026-03-29
- Статус: done
- Источник: пользовательский запрос на обход VPN для `ssdemordp.oooaab.ru`, его IP, `localhost` и локальной сети

## Цель

Добавить точечные исключения из VPN для удалённого RDP-хоста `ssdemordp.oooaab.ru` и обеспечить, чтобы обращения к `localhost` и адресам локальных/private-сетей не уходили через VPN.

## Изменения

- Обновить `singbox-tun-subvost.json`:
  - добавить DNS-правило `dns-direct` для `ssdemordp.oooaab.ru`;
  - добавить route-правила `direct` для `ssdemordp.oooaab.ru` и его текущего IPv4;
  - добавить route-правила `direct` для loopback, link-local и private-сетей.

## Проверки

- Проверить валидность JSON.
- Выполнить `sing-box check` для обновлённого конфига.

## Допущения

- Под «вся локальная сеть» на этом шаге понимаются loopback-адреса, link-local и стандартные private-подсети IPv4/IPv6, которые не должны идти через внешний VPN-туннель.

## Итог

- В `singbox-tun-subvost.json` добавлены точечные `dns-direct` и `direct`-исключения для `ssdemordp.oooaab.ru`.
- Для обхода VPN по прямому IP добавлено route-правило `direct` для текущего IPv4 `81.29.134.113/32`, полученного по DNS lookup на момент изменения.
- Для локального трафика добавлены route-исключения `direct` для loopback, link-local и стандартных private-подсетей IPv4/IPv6.
- Проверки пройдены: `python3 -m json.tool singbox-tun-subvost.json` и `sing-box check -c singbox-tun-subvost.json`.
