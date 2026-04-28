# Матрица проверки TASK-2026-0061

| Инвариант | Сценарий нарушения | Проверка / команда | Статус покрытия |
|-----------|--------------------|--------------------|-----------------|
| Runtime behavior не меняется | report builder меняет `routing.rules` или порядок catch-all | `python3 -m unittest tests.test_subvost_routing tests.test_subvost_app_service tests.test_gui_server tests.test_native_shell_app tests.test_native_shell_shared tests.test_windows_core_helper_contract` | covered |
| UI не парсит Xray JSON напрямую | web/GTK самостоятельно читают config и получают разные списки | service/status payload tests + audit `gui/main_gui.html`, `gui/native_shell_app.py` | covered |
| `template` и `profile` не смешиваются | пользователь видит общий список без источника | `tests.test_subvost_routing` report shape + Playwright smoke | covered |
| Видно победившее runtime-правило | конфликт template/profile не объяснён | conflict fixture в `tests.test_subvost_routing` + UI smoke | covered |
| `Подписки` не содержит основной report | вкладка подписок снова перегружена routing-report | Playwright assertion `#view-connection #panel-routing == false` | covered |
| `Настройки` доступны как верхняя вкладка | настройки остались только header-кнопкой | `tests.test_gui_server`, `tests.test_native_shell_app`, Playwright settings assertion | covered |
| Все новые строки на русском | owned UI text содержит английские заголовки | `owned-text-localization-guard` по task docs/native UI; web HTML отдельно просмотрен, потому guard считает машинные HTML/CSS/JS литералы пользовательским текстом | covered |
| Длинные `geosite:*`/`geoip:*` не ломают layout | chips/rows переполняют контейнер | Playwright screenshots `1366x900` и `820x900`, overflowX=`false` | covered |
| Kimi CLI review выполнен | финальный макет не получил внешнюю консультацию | `artifacts/kimi-design-review.md` | covered |
| Playwright/live smoke выполнен | вкладка не проверена в браузере | `artifacts/playwright-smoke.md`, screenshots `playwright-routes-tab*.png` | covered |
