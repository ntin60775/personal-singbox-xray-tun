# SDD TASK-2026-0061

## Проблема

Пользователь не видит в интерфейсе, какие адреса и сайты идут напрямую, минуя VPN. Сейчас источники direct-правил разнесены между:

- template-конфиг `xray-tun-subvost.json`;
- активным routing-профилем из store/subscription;
- generated/active runtime-конфиг.

Без UI-отчёта пользователь не может быстро понять, почему конкретный адрес обходит VPN и какой слой правил имеет приоритет.

## Цель

Добавить отдельную вкладку `Маршруты` с read-only отчётом `Прямые маршруты`, который:

- показывает прямые маршруты по источникам;
- показывает фактически применённый runtime;
- объясняет конфликты inline;
- сохраняет текущую runtime semantics неизменной.

## Не входит

- ручное редактирование маршрутов;
- сохранение пользовательских direct-исключений;
- изменение порядка Xray rules;
- изменение формата Happ/routing-профилей.

## Архитектура

### Источники данных

- `template`: `xray-tun-subvost.json`, rules до profile overlay;
- `profile`: поля активного routing-профиля `direct_sites`, `direct_ip`, `global_proxy`, `route_order`;
- `runtime`: generated или active runtime config после применения profile overlay;
- `state`: текущий routing status из store/service.

### Форма отчёта

Минимальный backend payload должен быть пригоден и для web UI, и для GTK UI:

```json
{
  "direct_report": {
    "summary": {
      "template_count": 0,
      "profile_count": 0,
      "runtime_count": 0,
      "conflict_count": 0,
      "runtime_available": false
    },
    "template": [],
    "profile": [],
    "runtime": [],
    "conflicts": []
  }
}
```

Каждая строка правила:

```json
{
  "id": "stable-rule-id",
  "source": "template",
  "kind": "domain",
  "value": "full:corp-rdp.example.com",
  "action": "direct",
  "label": "corp-rdp.example.com",
  "reason": "точечное встроенное правило",
  "priority": 10,
  "active": true,
  "overridden_by": null,
  "wins_over": []
}
```

### Модель приоритетов

Порядок принятия решения:

```text
template pre-catchall rules
  > routing profile rules by route_order
  > final catch-all from profile.global_proxy
```

UI обязан показывать этот порядок как объяснение, но не должен менять порядок runtime rules.

### UI-модель

Верхняя навигация:

- `Подключение`
- `Подписки`
- `Маршруты`
- `Диагностика`
- `Настройки`

Вкладка `Маршруты`:

- заголовок: `Маршруты`;
- основной блок: `Прямые маршруты`;
- подзаголовок: `Адреса и группы, которые идут напрямую, минуя VPN`;
- сводка: всего, template, профиль, runtime, conflicts;
- раскрываемые группы: `Итоговый runtime`, `Встроенные правила`, `Активный профиль`;
- conflicts inline в строках runtime и счётчик в summary;
- empty states для отсутствия runtime и отсутствия active profile.

## Инварианты

1. Runtime behavior не меняется: задача только отображает report.
2. UI не парсит Xray JSON напрямую; UI получает нормализованный report.
3. `template` и `profile` не смешиваются в один неразличимый список.
4. В отчёте явно видно, какое правило победило в runtime.
5. `Подписки` не содержит основной отчёт по прямым маршрутам.
6. `Настройки` доступны как верхняя вкладка, а не отдельная header-кнопка.
7. Все новые пользовательские строки на русском.
8. Длинные списки `geosite:*` и `geoip:*` не ломают layout.
9. Kimi CLI используется как консультационный review gate до финального UI signoff.
10. Playwright/live smoke подтверждает, что вкладка видима и не пустая.

## Критерии приёмки

- backend отдаёт `direct_report` в status/store payload;
- unit tests покрывают extraction из template/profile/runtime;
- unit tests покрывают conflict/priority explanations;
- web UI показывает верхние вкладки и вкладку `Маршруты`;
- GTK UI показывает вкладку `Маршруты` и вкладку `Настройки`;
- `Прямые маршруты` не содержит англоязычного owned UI-заголовка;
- direct action может отображаться как machine literal только в строке правила, если это нужно для технической точности;
- финальные проверки и screenshots сохранены в `artifacts/`.

## Проверочные gates

- unit-тесты;
- локализационный guard;
- дизайн-ревью через Kimi CLI;
- browser smoke через Playwright;
- `git diff --check`.
