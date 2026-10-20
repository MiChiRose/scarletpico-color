# ScarletPico Color

Самодельная GB/GBC-консоль: **RP2040-Zero**, дисплей ST7796 480×320,
microSD, физические кнопки, I2S-звук и Li-ion аккумулятор.
Приватный репозиторий: https://github.com/MiChiRose/scarletpico-color.

## Актуальная прошивка — 2.2.7

- [UF2 для RP2040](firmware/releases/2026-10-20-rp2040-ui-polish/ScarletPico-v2_2_7-RP2040-UI-POLISH.uf2).
- [Установка и изменения](firmware/releases/2026-10-20-rp2040-ui-polish/README-RU.md),
  [проверки](firmware/releases/2026-10-20-rp2040-ui-polish/VALIDATION.md),
  [SHA и аудит](firmware/releases/2026-10-20-rp2040-ui-polish/build-audit.json).
- [Откат на рабочую 2.2.6 с батарейкой](firmware/releases/2026-10-20-rp2040-legacy222-battery/ScarletPico-v2_2_6-RP2040-LEGACY222-GP29.uf2).
- [Откат на проверенную пользователем 2.2.2](firmware/releases/2026-10-07-rp2040-native-menu/01-ScarletPico-v2_2_2-RP2040-ROLLBACK.uf2).

2.2.7 улучшает оформление и сокращает перерисовку меню, сохраняя LCD,
игровые частоты, звук и GP29-батарейку рабочей 2.2.6. ARM-тесты пройдены;
полная физическая приёмка 2.2.7 ещё нужна. Старые native-сборки 2.2.5
на этой приставке не заработали; не выбирать прошивку просто по дате папки.

**Происхождение кода:** текущая RP2040-версия — дополнения на C/ASM поверх
точного исторического образа 2.2.2, а не полная пересборка старого эмулятора.
База, исходники дополнений, сборщики и необходимые тестовые ELF сохранены.
Общий CMake-проект `firmware/` и `firmware/src/` — предыдущий этап, не 2.2.7.

## Продолжить на другом компьютере

После авторизации в GitHub под MiChiRose:

```sh
git clone https://github.com/MiChiRose/scarletpico-color.git
cd scarletpico-color
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-firmware-test.txt
```

На Windows вместо `source` активировать `.venv\Scripts\Activate.ps1`.
Установить Arm GNU Toolchain **14.3.Rel1 arm-none-eabi** и указать его bin:

```sh
python firmware/tools/build_ui_polish_release.py --arm-bin /path/to/arm-none-eabi/bin
python firmware/tests/test_ui_polish_arm.py
```

Pico SDK для 2.2.7 не нужен. Сборщик не прошивает устройство.
Подробнее: [DEVELOPMENT.md](DEVELOPMENT.md).

## Корпус и детали для 3D-печати

**Актуальный перечень — [hardware/case/LATEST.md](hardware/case/LATEST.md).**
Там последняя передняя часть со стойками LCD 3 мм, три отдельные задние
секции, кнопки, пружинная пластина, прижимы LCD/динамика и USB-C.
STL, параметры, исходный OBJ и Python-генераторы сохранены вместе.
Промежуточные STL, нужные генераторам как входы, не удалены.

R3 — примерочная ревизия. У общей пластины есть известные оговорки по
размеру окон D-pad и длине пружин A: см. LATEST.md. Загрузка в Git не
означает окончательную физическую приёмку. Отдельного проекта электронной
PCB нет — здесь макетные платы и печатные детали корпуса.

## Схемы и следующий этап

- [Питание и батарейка](docs/HARDWARE-BATTERY.md),
  [рисунок делителя GP29](hardware/battery-monitor/divider-472-wiring.png).
- Зарядные статусы TP4056 к GPIO не подключены; молния не имитируется.
- [Исходники экспериментального порта RP2350](firmware/imported/scarletpico-rp2350-source/README-RP2350.md).
  Это отдельный тестовый порт, не готовая замена 2.2.7: после замены платы
  потребуются адаптация, сверка распиновки и физические тесты.
- `app/`, `server.mjs`, `package.json` — прежний браузерный прототип (`npm start`).

ROM-ы, сохранения, личные файлы, SDK и кеши не публикуются. Лицензии
стороннего кода сохранены рядом с ним. Историческое описание проекта —
[в архиве](docs/archive/project-overview-before-2.2.7.md).
