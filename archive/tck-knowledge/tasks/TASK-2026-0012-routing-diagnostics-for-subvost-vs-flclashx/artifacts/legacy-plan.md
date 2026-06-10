# Диагностика policy-маршрутизации для `subvost` против `FlClashX`

- Дата: 2026-03-28
- Статус: done
- Источник: пользовательский отчёт о проблемах `Strawberry`, `Яндекс Музыка`, `PortProton/Battle.net` и недоступности `chatgpt.com/backend-api/codex/responses`

## Цель

Подготовить отдельный сценарий диагностики, который помогает воспроизводимо снять состояние системы в режиме `subvost`, и по фактам из дампов привести policy-маршрутизацию к явно подтверждённой пользовательской модели:

- весь трафик любых приложений идёт через VPN по умолчанию;
- пользовательские `direct`-исключения задаются только явно;
- на этом шаге нужно сохранить только доменные `direct`-исключения для `.ru`, `.su`, `.xn--p1ai`;
- служебные исключения для самого VPN-стека допустимы только чтобы не допустить routing loop.

Ожидаемый результат: один запуск создаёт лог с достаточным набором фактов для сравнения поведения `subvost` с рабочим сценарием через `FlClashX`, а итоговый `sing-box` policy соответствует модели `default -> proxy` с единственным пользовательским `direct` по `.ru/.su/.xn--p1ai`.

## Изменения

- Добавить новый публичный скрипт диагностики маршрутизации в корень репозитория и вынести реализацию в `libexec/`.
- Исправить новый диагностический сценарий так, чтобы он работал не только через публичный wrapper, но и при прямом запуске из `libexec/`.
- Зафиксировать в диагностике:
  - текущие rule/config-фрагменты `sing-box` и `xray`;
  - состояние процессов `xray`, `sing-box`, `FlClashX`, `PortProton`, `wine-preloader`, `wineserver`, `strawberry`, `yandexmusic`;
  - DNS-резолв и plain-vs-SOCKS доступность для `chatgpt.com`, `openai.com`, `api.openai.com`, `battle.net`, `music.yandex.ru` и связанных доменов;
  - сетевые соединения и недавние релевантные строки из логов `sing-box` и `xray`.
- Проанализировать дампы `subvost-routing-diagnostics-20260328-134923.log` и `subvost-routing-diagnostics-20260328-134956.log`, подтвердить рабочее состояние `tun0`, локального `xray -> sing-box` стека и фактическое поведение DNS/HTTP через plain-vs-SOCKS путь.
- Зафиксировать изменение требований: отказаться от process-level `direct` для `Strawberry`, `Яндекс Музыки` и `PortProton`, потому что итоговая целевая модель уточнена пользователем как `default -> proxy` для всех приложений.
- Переписать `singbox-tun-subvost.json`:
  - убрать `exclude_uid: [0]`, чтобы root-процессы не обходили VPN автоматически;
  - убрать пользовательские process-level `direct`-исключения и точечные доменные `direct`/`proxy`-правила, не относящиеся к `.ru/.su/.xn--p1ai`;
  - оставить только служебный `direct` для `xray` и `sing-box`;
  - перевести DNS на схему `dns-proxy` по умолчанию с отдельным `dns-direct` только для `.ru/.su/.xn--p1ai`.

## Проверки

- Ручной запуск нового диагностического скрипта после старта `subvost`
- Проверка, что скрипт создаёт отдельный лог в `logs/` и не ломает существующий `capture-xray-tun-state.sh`
- Анализ дампов `logs/subvost-routing-diagnostics-20260328-134923.log` и `logs/subvost-routing-diagnostics-20260328-134956.log`
- `sing-box check -c singbox-tun-subvost.json`
- Ручной smoke после обновления `sing-box` policy: пользователь подтвердил, что после применения конфига ожидаемая модель маршрутизации работает

## Допущения

- Для наиболее полезной диагностики пользователь запускает проблемные приложения до или во время съёма дампа, чтобы они попали в `ss`, `ps` и runtime-логи.
- Проверки HTTP без пользовательских токенов считаются тестом сетевой достижимости, а не бизнес-валидности ответа; `401/403` допустимы как признак того, что соединение дошло до сервиса.
- `FlClashX` остаётся внешним эталоном поведения, но на этом шаге сценарий фокусируется на повторяемом сборе фактов в режиме `subvost`.
- Служебный `direct` для `xray` и `sing-box` обязателен: без него TUN-стек зацикливается сам в себя и теряет работоспособность.

## Итог

Добавлен и использован отдельный сценарий диагностики маршрутизации, который снимает процессы, policy-фрагменты, матрицу DNS-резолва, plain-vs-SOCKS HTTP-проверки, сетевые соединения и хвосты логов `sing-box`/`xray`. По двум целевым дампам подтверждено, что транспорт `xray -> sing-box` и `tun0` поднимаются штатно, а расхождения проявлялись на уровне policy/DNS-пути, а не из-за падения самого стека.

После уточнения требований от process-level `direct` для `Strawberry`, `Яндекс Музыки` и `PortProton` отказались. `singbox-tun-subvost.json` переписан под модель `default -> proxy`: убран `exclude_uid: [0]`, убраны пользовательские process-level и доменные `direct`-исключения кроме `.ru/.su/.xn--p1ai`, DNS по умолчанию направлен через `proxy`, а `direct` оставлен только для доменов `.ru/.su/.xn--p1ai` и служебных процессов `xray`/`sing-box`. Конфиг проверен через `sing-box check`, пользователь применил его вручную и подтвердил, что итоговое поведение соответствует ожидаемому.

Текст рабочего конфига, который был применён и подтвердил ожидаемое поведение:

```json
{
  "log": {
    "level": "debug",
    "timestamp": true
  },
  "dns": {
    "strategy": "ipv4_only",
    "servers": [
      {
        "type": "udp",
        "tag": "dns-proxy",
        "server": "8.8.8.8",
        "server_port": 53,
        "detour": "proxy"
      },
      {
        "type": "udp",
        "tag": "dns-direct",
        "server": "8.8.8.8",
        "server_port": 53,
        "detour": "direct"
      }
    ],
    "rules": [
      {
        "action": "route",
        "domain_suffix": [
          ".ru",
          ".su",
          ".xn--p1ai"
        ],
        "server": "dns-direct"
      }
    ],
    "final": "dns-proxy"
  },
  "inbounds": [
    {
      "type": "mixed",
      "tag": "mixed-in",
      "listen": "127.0.0.1",
      "listen_port": 7897
    },
    {
      "type": "tun",
      "tag": "tun-in",
      "address": [
        "172.19.0.1/30"
      ],
      "mtu": 1500,
      "auto_route": true,
      "auto_redirect": true,
      "strict_route": true,
      "stack": "mixed"
    }
  ],
  "outbounds": [
    {
      "type": "socks",
      "tag": "proxy",
      "server": "127.0.0.1",
      "server_port": 10808,
      "udp_fragment": true
    },
    {
      "type": "direct",
      "tag": "direct",
      "domain_resolver": {
        "server": "dns-direct",
        "strategy": "prefer_ipv4"
      }
    }
  ],
  "route": {
    "auto_detect_interface": true,
    "final": "proxy",
    "rules": [
      {
        "action": "sniff"
      },
      {
        "action": "hijack-dns",
        "protocol": "dns"
      },
      {
        "action": "route",
        "process_name": [
          "xray",
          "sing-box"
        ],
        "outbound": "direct"
      },
      {
        "action": "route",
        "domain_suffix": [
          ".ru",
          ".su",
          ".xn--p1ai"
        ],
        "outbound": "direct"
      }
    ]
  }
}
```

Остаточный риск: любые новые `direct`-исключения для конкретных приложений или внешних доменов нужно добавлять только осознанно, потому что они будут ослаблять утверждённую модель `всё через VPN по умолчанию`.
