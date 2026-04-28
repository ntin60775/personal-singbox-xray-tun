# Модульный companion-layer

`knowledge/modules/` — опциональный shared/public слой `Module Core`.
Он не заменяет `Task Core` и не становится источником истины по статусу задачи.

В managed-срезе этой поставки каталог вводит reusable модульную верификацию
и канонический storage для module passports:

- `registry.md` — навигационный cache по governed modules;
- `_templates/module.md` — шаблон shared/public паспорта модуля;
- `_templates/file-local-policy.md` — шаблон module-local policy для governed hot spots;
- `_templates/verification.md` — шаблон канонического verification-артефакта governed module;
- `module.md`, `file-local-policy.md` и `verification.md` живут рядом внутри `knowledge/modules/<MODULE-ID>-<slug>/`.

Этот каталог нужен для модульной инженерной памяти,
которая переживает несколько задач,
но не подменяет task-local `task.md`,
`plan.md`
и `artifacts/verification-matrix.md`.

Ownership жёстко разделён:

- `module.md` хранит shared/public truth,
  управляемую поверхность
  публичные контракты
  и исходящие relation rows `depends_on`;
- `file-local-policy.md` хранит только явный hot-spot scope,
  набор разрешённых markers
  и обязательные `BLOCK_*` якоря для `file show`;
- `verification.md` хранит readiness, evidence и handoff-контур;
- `registry.md` остаётся только навигационным cache.

Relation-layer в v1 intentionally lightweight:

- каноническая relation-truth живёт только в `module.md`;
- `registry.md` не кэширует relation rows и не хранит `used_by`;
- `used_by` вычисляется read-model из входящих `depends_on`;
- target связи обязан быть exact `MODULE-ID` другого governed module;
- внешние зависимости, path-level refs и full graph DSL в этот слой не входят.

File-local contract layer в v1 intentionally warning-first:

- hot-spot scope задаётся только явной таблицей `## Hot spots` внутри `file-local-policy.md`;
- `task-knowledge file show` остаётся главным read-only API для private/local truth;
- вне hot-spot scope `file show` возвращает owner/verification truth без hard errors;
- repo-wide mandatory markup, синтаксический граф импортов и auto-generated markup в этот слой не входят.
