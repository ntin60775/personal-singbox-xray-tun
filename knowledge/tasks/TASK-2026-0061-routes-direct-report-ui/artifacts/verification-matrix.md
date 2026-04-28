# Матрица проверки TASK-2026-0061

| Инвариант | Сценарий нарушения | Проверка / команда | Статус покрытия |
|-----------|--------------------|--------------------|-----------------|
| Runtime behavior не меняется | report builder меняет `routing.rules` или порядок catch-all | unit tests на `render_runtime_config` до/после report; `tests.test_subvost_runtime` | planned |
| UI не парсит Xray JSON напрямую | web/GTK самостоятельно читают config и получают разные списки | review + tests на service payload; grep/audit UI-файлов | planned |
| `template` и `profile` не смешиваются | пользователь видит общий список без источника | unit tests report shape + Playwright screenshot | planned |
| Видно победившее runtime-правило | конфликт template/profile не объяснён | conflict fixture + unit test + UI smoke | planned |
| `Подписки` не содержит основной report | вкладка подписок снова перегружена routing-report | Playwright screenshot + DOM/assertions | planned |
| `Настройки` доступны как верхняя вкладка | настройки остались только header-кнопкой | native/web UI tests + screenshot | planned |
| Все новые строки на русском | owned UI text содержит английские заголовки | `owned-text-localization-guard` по UI-файлам | planned |
| Длинные `geosite:*`/`geoip:*` не ломают layout | chips/rows переполняют контейнер | Playwright desktop/mobile-ish viewport screenshots | planned |
| Kimi CLI review выполнен | финальный макет не получил внешнюю консультацию | artifact с командой и выводом Kimi | planned |
| Playwright/live smoke выполнен | вкладка не проверена в браузере | `playwright-interactive` screenshot и функциональные assertions | planned |
