# Актуальные файлы корпуса

Список после уборки 19 октября 2026. R3 SPLIT — примерочная ревизия, не полностью принятая физическим тестом. Пути актуальных файлов сохранены; копии комплектов и новые ZIP не создавались.

## Известная проблема кнопочной пластины

Последняя общая пластина — [SYMMETRIC-DPAD](button-bench-R3/split-spring-test/00-RECTANGULAR-SYMMETRIC-DPAD-RETAINER.stl). Четыре окна симметричны, но **исходный размер цельной R2 не восстановлен**: 84,51 мм² вместо примерно 100,5 мм², то есть на 16% меньше по площади. При уборке геометрия не менялась. У A прямые пружины короче исходных (8,3 вместо 10,3 мм), усилие требует проверки. Этот STL не является окончательно утверждённой конструкцией.

Пластина замкнутая и цельная, 89 × 50 × 3 мм; шесть прежних M2×6. Корпус, D-pad и накладки пружинного теста не менялись. [Подробности](button-bench-R3/split-spring-test/README-full-outline.md), [последний рендер](button-bench-R3/split-spring-test/preview-symmetric-dpad.png), [проверки](button-bench-R3/split-spring-test/checks-symmetric-dpad.json).

## Основные детали

| Деталь | Файл |
|---|---|
| Передняя часть, LCD-стойки 3 мм | [01-front-R3-LCD-3mm.stl](rev3-split/output/01-front-R3-LCD-3mm.stl) |
| Верх задней крышки | [02a-rear-upper-R3.stl](rev3-split/output/02a-rear-upper-R3.stl) |
| Изогнутый переход | [02b-rear-transition-R3.stl](rev3-split/output/02b-rear-transition-R3.stl) |
| Низ задней крышки | [02c-rear-lower-R3.stl](rev3-split/output/02c-rear-lower-R3.stl) |
| Крестовина | [04-dpad-R2.stl](rev3-split/output/04-dpad-R2.stl) |
| Четыре совместимые накладки | [04-four-matching-caps-SPRING-TEST.stl](button-bench-R3/split-spring-test/04-four-matching-caps-SPRING-TEST.stl) |
| Общая кнопочная пластина — оговорка выше | [00-RECTANGULAR-SYMMETRIC-DPAD-RETAINER.stl](button-bench-R3/split-spring-test/00-RECTANGULAR-SYMMETRIC-DPAD-RETAINER.stl) |
| Прижим динамика | [06-speaker-retainer-R2.stl](rev3-split/output/06-speaker-retainer-R2.stl) |
| Четыре прижима LCD | [07-four-LCD-clips-R2.stl](rev3-split/output/07-four-LCD-clips-R2.stl) |
| Внутренняя опора USB-C | [usb-c-carrier-DRAFT.stl](rev3-split/output/usb-c-carrier-DRAFT.stl) |
| Вкладыши USB-C — две копии | [usb-c-slider-PRINT-TWO.stl](rev3-split/output/usb-c-slider-PRINT-TWO.stl) |

Если деталь уже напечатана и подошла, перепечатывать из-за уборки не требуется. Положение деталей в STL и масштаб 100% сохранены. Задний переход печатается на поперечном торце, не большой изогнутой поверхностью на поддержках. Для кнопочной пластины: без Raft, локальные поддержки только под центральной опорой/рёбрами D-pad, не под тонкими пружинами.

[Инструкция по корпусу и крепежу](rev3-split/README.md). При расхождении со старыми перечнями STL использовать именно этот список. [Схема крепления LCD](rev3-split/output/lcd-mount-guide-R3.png) показывает принцип крепления; высота стоек на старой картинке историческая, актуальная — 3 мм над внутренней плоскостью.

## Необязательные детали и запасной вариант

- [Подкладки под носики LCD-прижимов](rev3-split/output/08-LCD-pad-set-OPTIONAL.stl) — по необходимости, не шайбы под стойки.
- [Пробник стыка задних секций и крепежа](rev3-split/output/10-seam-fastener-FIT-TEST-OPTIONAL.stl).
- [Отдельная передняя панель стенда](button-bench-R3/output/01-all-buttons-front-TEST.stl) — запасной исходный стенд; если облегчённая панель уже есть, новую печатать не нужно.
- Три раздельных держателя V2 для сравнения/возврата: [D-pad](button-bench-R3/split-spring-test/01-DPAD-retainer-SPRING-V2.stl), [A/B](button-bench-R3/split-spring-test/02-AB-retainer-SPRING-V2.stl), [Start/Select](button-bench-R3/split-spring-test/03-START-SELECT-retainer-SPRING-V2.stl). Вместе с общей пластиной не устанавливаются.

## Технические входы сборки — не печатать вместо актуальных деталей

14 старых STL в папках output, variable-depth/output, usb-c-top/output, rev2/output и старый rev3-split/output/01-front-R3.stl нужны адаптерам и проверкам сборки. Это не дополнительные рекомендуемые варианты. Их нельзя удалять без изменения цепочки сборки. Все Python-исходники, параметры, OBJ/MTL и текущие отчёты сохранены.

## Уборка

62 устаревших сгенерированных файла, включая 30 STL, 18 PNG, три старых ZIP, старые отчёты экспериментов и Finder-кеши, перенесены в отдельную папку Корзины ScarletPico-CAD-cleanup-2026-10-19. Их можно восстановить с прежними относительными путями. Корзина не очищалась. Прошивки, игры, сохранения и исходники не затрагивались.

[Журнал уборки и пути восстановления](cleanup-generated-2026-10-19.json). Исторические README сохранены как документация этапов и могут упоминать уже убранные файлы; их старые списки не являются текущим набором печати.
