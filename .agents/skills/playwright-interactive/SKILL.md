---
name: "playwright-interactive"
description: "Постоянная работа с браузером и Electron через `js_repl` для быстрого итеративного UI-debugging."
---

# Навык Playwright Interactive

Используй этот навык, когда нужна интерактивная работа с браузером или Electron в постоянной сессии `js_repl`. Держи Playwright-хендлы живыми между правками кода, перезагрузками и повторными проверками, чтобы цикл итерации оставался быстрым.

## Предусловия

- Для этого навыка должен быть включён `js_repl`.
- Если `js_repl` недоступен, включи его в `~/.codex/config.toml`:

```toml
[features]
js_repl = true
```

- Новую сессию можно также запустить с `--enable js_repl` (эквивалент `-c features.js_repl=true`).
- После включения `js_repl` перезапусти сессию Codex, чтобы список инструментов обновился.
- Пока что этот workflow нужно запускать без sandbox-ограничений: стартуй Codex с `--sandbox danger-full-access` или с эквивалентной настройкой `sandbox_mode=danger-full-access`. Это временное требование, пока поддержка `js_repl` + Playwright внутри sandbox не доведена до рабочего состояния.
- Если режим sandbox или сетевых/файловых прав менялся уже после старта `js_repl`, обязательно выполни `js_repl_reset` перед новым browser launch. Ядро `js_repl` живёт отдельно и может сохранить старые ограничения даже после смены режима всей сессии.
- Выполняй setup из того каталога проекта, который реально собираешься отлаживать.
- Относись к `js_repl_reset` как к инструменту восстановления, а не как к штатной очистке. Reset уничтожает все живые Playwright-хендлы.

## Разовая подготовка

```bash
test -f package.json || npm init -y
npm install playwright
# Только для web-сценариев, headed Chromium или mobile emulation:
# npx playwright install chromium
# Только для Electron, и только если текущий workspace — это само приложение:
# npm install --save-dev electron
node -e "import('playwright').then(() => console.log('playwright import ok')).catch((error) => { console.error(error); process.exit(1); })"
```

Если позже переключишься на другой workspace, повтори setup уже там.

## Основной workflow

1. Перед тестированием составь краткий QA-инвентарь:
   - собери его из трёх источников: требований пользователя, реально реализованных user-visible фич и поведения, а также утверждений, которые собираешься написать в финальном ответе;
   - всё, что появилось хотя бы в одном из этих трёх источников, должно быть покрыто минимум одной QA-проверкой до signoff;
   - перечисли user-visible утверждения, за которые собираешься подписаться;
   - перечисли все значимые user-facing контролы, переключатели режимов и реализованные интерактивные поведения;
   - перечисли изменения состояния и представления, которые может вызвать каждый контрол или поведение;
   - используй этот список как общую карту покрытия и для функционального QA, и для визуального QA;
   - для каждой пары claim/control-state зафиксируй ожидаемую функциональную проверку, конкретное состояние для визуальной проверки и артефакт, который собираешься получить;
   - если требование визуально центральное, но звучит субъективно, переведи его в наблюдаемую QA-проверку, а не оставляй неявным;
   - добавь минимум 2 exploratory/off-happy-path сценария, которые могут вскрыть хрупкое поведение.
2. Один раз выполни bootstrap-cell.
3. Запусти или подтверди нужный dev server в постоянной TTY-сессии.
4. Запусти нужный runtime и дальше переиспользуй те же Playwright-хендлы.
5. После каждой правки кода делай reload для renderer-only изменений или relaunch для main-process/startup изменений.
6. Прогони функциональный QA реальным пользовательским вводом.
7. Отдельно прогони визуальный QA.
8. Проверь viewport fit и сними скриншоты, которые реально подтверждают твои утверждения.
9. Закрывай Playwright-сессию только тогда, когда задача действительно завершена.

## Bootstrap (запускается один раз)

```javascript
var chromium;
var electronLauncher;
var browser;
var context;
var page;
var mobileContext;
var mobilePage;
var electronApp;
var appWindow;

try {
  ({ chromium, _electron: electronLauncher } = await import("playwright"));
  console.log("Playwright загружен");
} catch (error) {
  throw new Error(
    `Не удалось загрузить playwright из текущего js_repl cwd. Сначала выполни setup-команды в этом workspace. Исходная ошибка: ${error}`
  );
}
```

## Запуск или переиспользование web-сессии

Задай `TARGET_URL` как адрес приложения, которое отлаживаешь. Для локальных серверов предпочитай `127.0.0.1`, а не `localhost`.

```javascript
const TARGET_URL = "http://127.0.0.1:3000";

if (!browser) {
  browser = await chromium.launch({ headless: false });
}

if (!context) {
  context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
  });
}

if (!page) {
  page = await context.newPage();
}

await page.goto(TARGET_URL, { waitUntil: "domcontentloaded" });
console.log("Загружено:", await page.title());
```

## Запуск или переиспользование Electron-сессии

Задай `ELECTRON_ENTRY = "."`, если текущий workspace и есть Electron-приложение, а `package.json` указывает `main` на правильный entry point. Если нужно стартовать конкретный main-process файл напрямую, используй путь вроде `./main.js`.

В `js_repl` опирайся на `codex.cwd`, а не на `process.cwd()`: глобальный `process` может быть недоступен.

```javascript
const ELECTRON_ENTRY = ".";

if (electronApp) {
  await electronApp.close().catch(() => {});
}

electronApp = await electronLauncher.launch({
  args: [ELECTRON_ENTRY],
  cwd: codex.cwd,
});

appWindow = await electronApp.firstWindow();

console.log("Загружено окно Electron:", await appWindow.title());
```

## Переиспользование сессий во время итерации

Старайся держать одну и ту же сессию живой, если только нет прямой причины её пересоздавать.

Перезагрузка web-renderer:

```javascript
for (const p of context.pages()) {
  await p.reload({ waitUntil: "domcontentloaded" });
}
console.log("Существующие вкладки перезагружены");
```

Перезагрузка только Electron-renderer:

```javascript
await appWindow.reload({ waitUntil: "domcontentloaded" });
console.log("Окно Electron перезагружено");
```

Перезапуск Electron после изменений в main-process, preload или startup:

```javascript
await electronApp.close().catch(() => {});

electronApp = await electronLauncher.launch({
  args: ["."],
  cwd: codex.cwd,
});

appWindow = await electronApp.firstWindow();
console.log("Окно Electron перезапущено:", await appWindow.title());
```

Базовая рабочая дисциплина:

- держи каждый `js_repl`-cell коротким и сфокусированным на одном интерактивном шаге;
- переиспользуй существующие top-level bindings (`browser`, `context`, `page`, `electronApp`, `appWindow`), а не объявляй их заново;
- если нужна изоляция, создай новую страницу или новый context внутри того же браузера;
- для Electron используй `electronApp.evaluate(...)` только для main-process inspection или целевой диагностики;
- исправляй ошибки прямо в текущих bindings; не сбрасывай REPL, пока ядро действительно не сломано или не унаследовало неверные ограничения.

## Чек-листы

### Цикл Сессии

- Один раз bootstrap `js_repl`, затем держи те же Playwright-хендлы живыми между итерациями.
- Запусти нужный runtime из текущего workspace.
- Внеси изменение в код.
- Сделай reload или relaunch в зависимости от типа изменения.
- Обнови общий QA-инвентарь, если exploratory-проверка открыла новый контрол, state или visible claim.
- Повтори функциональный QA.
- Повтори визуальный QA.
- Снимай финальные артефакты только после того, как интерфейс находится именно в том состоянии, которое ты оцениваешь.
- Перед завершением задачи выполни cleanup.

### Выбор Между Reload И Relaunch

- Renderer-only change: reload существующей страницы или окна Electron.
- Main-process, preload или startup change: relaunch Electron.
- Если есть новая неопределённость относительно process ownership или startup-кода, перезапускай приложение вместо догадок.

### Функциональный QA

- Для signoff используй реальные пользовательские действия: клавиатуру, мышь, клики, touch или эквивалентные Playwright input APIs.
- Проверь хотя бы один критический end-to-end сценарий.
- Подтверди видимый результат этого сценария, а не только внутреннее состояние.
- Для realtime- и animation-heavy интерфейсов проверяй поведение под реальным темпом взаимодействия.
- Иди по общему QA-инвентарю, а не по случайным spot-check.
- До signoff покрой хотя бы по одному разу все очевидные visible controls, а не только главный happy path.
- Для обратимых контролов и stateful toggles из инвентаря проверь полный цикл: исходное состояние, изменённое состояние и возврат обратно.
- После scripted-проверок сделай короткий exploratory-pass на 30-90 секунд с нормальным пользовательским вводом вместо следования только ожидаемому сценарию.
- Если exploratory-pass открыл новый state, control или claim, добавь его в общий QA-инвентарь и покрой до signoff.
- `page.evaluate(...)` и `electronApp.evaluate(...)` можно использовать для инспекции и диагностики, но это не считается signoff-вводом.

### Визуальный QA

- Визуальный QA — отдельная дисциплина, не приложение к функциональному QA.
- Используй тот же общий QA-инвентарь, который был определён перед тестированием и обновлялся по ходу проверки; не начинай визуальное покрытие с другого неявного списка.
- Повтори user-visible claims и проверь каждый явно; не считай, что функциональный проход автоматически доказывает визуальные утверждения.
- User-visible claim не считается подтверждённым, пока ты не посмотрел именно то состояние, в котором этот claim должен восприниматься.
- Осмотри initial viewport до любого скролла.
- Подтверди, что initial view визуально поддерживает основные обещания интерфейса; если ключевой обещанный элемент там не воспринимается явно, считай это багом.
- Осмотри все обязательные видимые регионы, а не только основную интерактивную область.
- Осмотри состояния и режимы, уже перечисленные в общем QA-инвентаре, включая хотя бы одно значимое post-interaction состояние, если продукт интерактивный.
- Если motion и transitions — часть опыта, проверь не только конечные состояния, но и хотя бы одно состояние в движении.
- Если labels, overlays, annotations, guides или highlights должны следовать за изменяющимся контентом, проверь это соответствие после нужного state change.
- Для dynamic и interaction-dependent визуалов смотри на интерфейс достаточно долго, чтобы оценить стабильность, слои и читаемость; одного скриншота для signoff недостаточно.
- Для интерфейсов, которые становятся плотнее после загрузки или взаимодействия, проверяй максимально реалистичное плотное состояние, а не только пустой, loading или collapsed вариант.
- Если у продукта есть заявленный минимально поддерживаемый viewport или размер окна, сделай отдельный visual QA-pass там; если нет, выбери меньший, но реалистичный размер и проверь его явно.
- Различай наличие и качество реализации: если affordance технически есть, но его плохо видно из-за слабого контраста, перекрытия, обрезки или нестабильности, считай это визуальным дефектом.
- Если обязательный видимый регион обрезан, скрыт, перекрыт или вытолкнут за пределы viewport в проверяемом состоянии, это баг, даже если page-level scroll metrics выглядят нормально.
- Ищи clipping, overflow, distortion, layout imbalance, inconsistent spacing, alignment problems, illegible text, weak contrast, broken layering и awkward motion states.
- Оценивай не только корректность, но и визуальное качество. Интерфейс должен выглядеть намеренно собранным, цельным и уместным для задачи.
- Для signoff предпочитай viewport screenshots. Full-page captures используй как вторичные отладочные артефакты.
- Если full-window screenshot недостаточно, чтобы уверенно оценить регион, сделай отдельный focused screenshot.
- Если motion делает скриншот двусмысленным, дождись стабилизации интерфейса и снимай именно то состояние, которое оцениваешь.
- Перед signoff явно спроси себя: какую видимую часть интерфейса я ещё не рассмотрел внимательно?
- Перед signoff явно спроси себя: какой видимый дефект сильнее всего смутил бы пользователя при внимательном просмотре?

### Критерии Signoff

- Функциональный сценарий прошёл с нормальным пользовательским вводом.
- Покрытие явно сопоставлено с общим QA-инвентарём: зафиксировано, какие требования, фичи, контролы, состояния и claims были проверены, и отдельно названы осознанные исключения.
- Визуальный QA покрыл весь релевантный интерфейс.
- У каждого user-visible claim есть соответствующая визуальная проверка и артефакт из того состояния, где этот claim действительно важен.
- Viewport-fit проверки прошли для intended initial view и для любого обязательного минимального viewport или размера окна.
- Если продукт стартует в отдельном окне, проверены стартовый размер, положение и initial layout до ручного resize или repositioning.
- Скриншоты прямо подтверждают утверждения, которые ты делаешь.
- Обязательные скриншоты реально просмотрены для тех состояний и размеров viewport/окна, которые использовались при QA.
- UI не просто функционален; он визуально собран и не выглядит эстетически слабым для своей задачи.
- Функциональная корректность, viewport fit и визуальное качество проходят независимо; одно не доказывает другое.
- Для интерактивного продукта выполнен короткий exploratory-pass, и в ответе явно сказано, что именно он покрыл.
- Если в какой-то момент screenshot review и numeric checks расходились, расхождение было расследовано до signoff; видимый clipping на скриншоте нельзя списывать только на хорошие метрики.
- В ответ включено короткое отрицательное подтверждение по основным классам дефектов, которые проверялись и не были найдены.
- Cleanup выполнен, либо сессия осознанно оставлена живой для дальнейшей работы.

## Примеры скриншотов

Предпочитай JPEG с `quality: 85` для артефактов через `view_image`, если только не нужна именно lossless-проверка.

Пример для desktop:

```javascript
const { unlink } = await import("node:fs/promises");
const desktopPath = `${codex.tmpDir}/desktop.jpg`;

await page.screenshot({ path: desktopPath, type: "jpeg", quality: 85 });
await codex.tool("view_image", { path: desktopPath });
await unlink(desktopPath).catch(() => {});
```

Пример для Electron:

```javascript
const { unlink } = await import("node:fs/promises");
const electronPath = `${codex.tmpDir}/electron-window.jpg`;

await appWindow.screenshot({ path: electronPath, type: "jpeg", quality: 85 });
await codex.tool("view_image", { path: electronPath });
await unlink(electronPath).catch(() => {});
```

Пример для мобильного viewport:

```javascript
const { unlink } = await import("node:fs/promises");

if (!mobileContext) {
  mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  mobilePage = await mobileContext.newPage();
}

await mobilePage.goto(TARGET_URL, { waitUntil: "domcontentloaded" });
const mobilePath = `${codex.tmpDir}/mobile.jpg`;
await mobilePage.screenshot({ path: mobilePath, type: "jpeg", quality: 85 });
await codex.tool("view_image", { path: mobilePath });
await unlink(mobilePath).catch(() => {});
```

## Проверки viewport fit (обязательно)

Не считай скриншот приемлемым только потому, что на нём виден основной виджет. Перед signoff явно проверь, что intended initial view соответствует требованиям продукта, и опирайся одновременно на screenshot review и numeric checks.

- Сначала зафиксируй, что именно считается intended initial view. Для скроллящихся страниц это above-the-fold опыт. Для shell-like интерфейсов, игр, редакторов, dashboard и инструментов это вся основная интерактивная поверхность плюс контролы и статус, необходимые для старта работы.
- Скриншоты — главное доказательство viewport fit. Численные проверки поддерживают их, но не могут переопределить видимый clipping.
- Signoff провален, если обязательный видимый регион обрезан, скрыт, перекрыт или вытолкнут за пределы viewport в intended initial view, даже если page-level scroll metrics выглядят хорошо.
- Скролл допустим только тогда, когда продукт изначально так задуман, а initial view всё равно показывает основной опыт и основной call to action либо обязательный стартовый контекст.
- Для fixed-shell интерфейсов скролл не считается приемлемым workaround, если он нужен, чтобы дотянуться до части основной интерактивной поверхности или essential controls.
- Не полагайся только на document scroll metrics. Fixed-height shell, внутренние панели и hidden-overflow контейнеры могут обрезать обязательный UI, даже когда page-level метрики выглядят чисто.
- Проверяй bounds конкретных регионов, а не только границы документа. Убедись, что каждый обязательный видимый регион помещается во viewport в startup state.
- Для Electron и desktop app проверяй и стартовый размер/положение окна, и initial visible layout renderer-части до любого ручного resize или repositioning.
- Успешная viewport-fit проверка доказывает только видимость intended initial view без нежелательного clipping или scrolling. Она не доказывает визуальную корректность и эстетическое качество интерфейса.

Web или renderer check:

```javascript
console.log(await page.evaluate(() => ({
  innerWidth: window.innerWidth,
  innerHeight: window.innerHeight,
  clientWidth: document.documentElement.clientWidth,
  clientHeight: document.documentElement.clientHeight,
  scrollWidth: document.documentElement.scrollWidth,
  scrollHeight: document.documentElement.scrollHeight,
  canScrollX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  canScrollY: document.documentElement.scrollHeight > document.documentElement.clientHeight,
})));
```

Проверка для Electron:

```javascript
console.log(await appWindow.evaluate(() => ({
  innerWidth: window.innerWidth,
  innerHeight: window.innerHeight,
  clientWidth: document.documentElement.clientWidth,
  clientHeight: document.documentElement.clientHeight,
  scrollWidth: document.documentElement.scrollWidth,
  scrollHeight: document.documentElement.scrollHeight,
  canScrollX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  canScrollY: document.documentElement.scrollHeight > document.documentElement.clientHeight,
})));
```

При реальном риске clipping дополни numeric check проверками `getBoundingClientRect()` по конкретным обязательным регионам интерфейса; document-level метрик недостаточно для fixed-shell сценариев.

## Dev Server

Для локальной web-отладки держи приложение запущенным в постоянной TTY-сессии. Не рассчитывай на one-shot background-команды из краткоживущего shell.

Используй штатную команду старта проекта, например:

```bash
npm start
```

Перед `page.goto(...)` убедись, что нужный порт слушает и приложение отвечает.

Для Electron-отладки запускай приложение из `js_repl` через `_electron.launch(...)`, чтобы процесс принадлежал той же сессии. Если Electron-renderer зависит от отдельного dev server, например Vite или Next, держи этот сервер в постоянной TTY-сессии и потом делай relaunch или reload Electron-приложения из `js_repl`.

## Cleanup

Выполняй cleanup только тогда, когда задача действительно завершена.

- Это ручная очистка. Выход из Codex, закрытие терминала или потеря `js_repl`-сессии не вызывают автоматически `electronApp.close()`, `context.close()` или `browser.close()`.
- Для Electron по умолчанию считай, что приложение продолжит жить, если ты покинешь сессию, не выполнив cleanup-cell.

```javascript
if (electronApp) {
  await electronApp.close().catch(() => {});
}

if (mobileContext) {
  await mobileContext.close().catch(() => {});
}

if (context) {
  await context.close().catch(() => {});
}

if (browser) {
  await browser.close().catch(() => {});
}

browser = undefined;
context = undefined;
page = undefined;
mobileContext = undefined;
mobilePage = undefined;
electronApp = undefined;
appWindow = undefined;

console.log("Сессия Playwright закрыта");
```

Если собираешься сразу выйти из Codex после отладки, сначала выполни cleanup-cell и дождись лога `"Сессия Playwright закрыта"`.

## Типовые сбои

- `Cannot find module 'playwright'`: выполни разовый setup в текущем workspace и проверь import до начала работы с `js_repl`.
- Пакет Playwright установлен, но не хватает браузерного бинаря: выполни `npx playwright install chromium`.
- `page.goto: net::ERR_CONNECTION_REFUSED`: убедись, что dev server жив, снова проверь порт и предпочитай `http://127.0.0.1:<port>`.
- `electron.launch` зависает, таймаутится или завершается сразу: проверь локальную зависимость `electron`, корректность `args` и то, что renderer dev server уже поднят до запуска.
- `Identifier has already been declared`: переиспользуй существующие top-level bindings, выбери новое имя или локально оберни код в `{ ... }`. `js_repl_reset` используй только если kernel действительно застрял или унаследовал неверные ограничения.
- `js_repl` timed out или был reset: повторно выполни bootstrap-cell и восстанови сессию короткими, сфокусированными cell.
- Browser launch или сетевые операции падают сразу после смены sandbox/access режима: сначала выполни `js_repl_reset`, потому что старый kernel может всё ещё жить со старыми ограничениями, и только потом повторяй запуск.
- Browser launch или сетевые операции падают сразу и без смены режима: проверь, что сама сессия Codex действительно стартовала с `--sandbox danger-full-access`, и при необходимости перезапусти её так.
