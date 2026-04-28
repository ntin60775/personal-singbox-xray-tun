# Реестр governed modules

`knowledge/modules/registry.md` — навигационный cache по governed modules.
Источником истины по модулю остаётся `knowledge/modules/<MODULE-ID>-<slug>/module.md`,
а readiness/evidence truth остаётся в `verification.md`.

## Как вести

- одна строка на один governed module;
- `MODULE-ID` и `Slug` должны быть глобально уникальными;
- `Паспорт`, `Верификация`, `File Policy`, `Каталог` и `Краткое назначение`
  должны совпадать с каноническим `module.md`;
- `Source State` и `Readiness` являются кэшом read-model и не подменяют
  канонический contract паспорта и verification;
- registry не хранит длинные списки `governed_files`,
  relation-строки,
  вычисляемый `used_by`,
  evidence, сценарии и private helper churn.

## Таблица

| MODULE-ID | Slug | Source State | Readiness | Паспорт | Верификация | File Policy | Каталог | Краткое назначение |
|-----------|------|--------------|-----------|---------|-------------|-------------|---------|--------------------|
| `M-XXX` | `example` | `passport_ready` | `partial` | `knowledge/modules/M-XXX-example/module.md` | `knowledge/modules/M-XXX-example/verification.md` | `—` | `knowledge/modules/M-XXX-example/` | Короткая модульная сводка для read-only навигации. |
