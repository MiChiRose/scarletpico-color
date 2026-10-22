# Архитектура и сборка

[← О проекте](README.md) · [Установка UF2](docs/FLASHING.md) · [Схема](docs/PINOUT.md)

## Актуальная цепочка RP2040

1. Точный образ 2.2.2:
   `firmware/releases/2026-10-07-rp2040-native-menu/01-ScarletPico-v2_2_2-RP2040-ROLLBACK.uf2`.
   SHA256 `98b80f2827d626e697b83034d426b77e5fe028e1792f30edaec50a80ab963089`.
2. Батарейка: `firmware/battery-legacy-addon/`,
   `firmware/imported/scarletpico-rp2040-source/battery_model.[ch]`,
   `firmware/tools/build_legacy_battery_release.py` → 2.2.6.
3. UI: `firmware/ui-polish-addon/`,
   `firmware/tools/build_ui_polish_release.py` → 2.2.7.
4. Полный каталог: `firmware/library-paging-addon/`,
   `firmware/tools/build_library_paging_release.py` → 2.2.8.
   Это отдельная добавка к точной 2.2.7, без пересборки старого эмулятора.

Актуальная сборка/проверка каталога:

```sh
python3 firmware/tools/build_library_paging_release.py --arm-bin /path/to/arm-none-eabi/bin
python3 firmware/tests/test_library_paging_arm.py
SCARLET_HEAP_IMAGE=firmware/build-library-paging-addon/patched.bin python3 firmware/tests/test_video_heap_arm.py
```

См. [примечания 2.2.8](firmware/releases/2026-10-22-rp2040-library-paging/README-RU.md).
`GAME_LIBRARY_MAX=32` в историческом заголовке сохраняет ABI старого массива;
это больше не общий предел каталога в 2.2.8. Новый сканер держит 28 записей,
общий счётчик и смещение; на границах перечитывает следующий отсортированный
блок. На очень больших каталогах обмен RAM на повторное чтение SD заметен
по задержке, но не отнимает память у эмулятора или сохранений.

Сборщики проверяют SHA входа и старые байты перед патчами. Не подставлять
похожий UF2. С Arm GNU Toolchain 14.3.Rel1 ожидается SHA256 прошивки 2.2.7:
`2be5dd4d37001167a77501174ce02ba3d59a21e555b4ff6b87a2620b8c6f34c0`.
ZIP может отличаться временными метками; эталон — UF2 и аудит.

В Git намеренно включены небольшие бинарные входы ARM-тестов внутри firmware:
`build-battery-legacy-addon/battery.elf` и `patched.bin`,
`build-features-v2_2_2-addon/features.elf`, `build-pause-ui-addon/pause-ui.elf`.
Остальные build-каталоги игнорируются. `build-ui-polish-addon/` создаётся
сборщиком 2.2.7. Основная инструкция сборки — в корневом README.

Батарейку можно отдельно пересобрать и проверить:

```sh
python firmware/tools/build_legacy_battery_release.py --arm-bin /path/to/arm-none-eabi/bin
python firmware/tests/test_legacy_battery_arm.py
```

Дополнительная регрессия памяти после сборки 2.2.7 (macOS/Linux):

```sh
SCARLET_HEAP_IMAGE=firmware/build-ui-polish-addon/patched.bin python firmware/tests/test_video_heap_arm.py
```

Архивные сборщики/тесты прошлых этапов сохранены для истории. Некоторые
требуют старых build-фикстур вне актуального набора. Они не являются другой
инструкцией сборки 2.2.7. Первый Git-коммит — снимок 20 октября 2026;
истории коммитов до него не существовало.

## RP2350 и SDK

Полный экспериментальный CMake-порт:
`firmware/imported/scarletpico-rp2350-source/`. Он использует также соседние
`ui-addon/`, `features-addon/`, `src/`, `vendor/Peanut-GB-CGB/`.
Версия 3.0-test — отдельная, ещё не аппаратно принятая линия; поздние
изменения 2.2.6/2.2.7 туда автоматически не перенесены.

Рабочая копия SDK (~746 МБ) не включена. Сохранённая база: Pico SDK **2.3.1**,
commit `079c6f39023649b154152db30f1d781e884879bc`.

```sh
git clone https://github.com/raspberrypi/pico-sdk.git firmware/vendor/pico-sdk
git -C firmware/vendor/pico-sdk checkout 079c6f39023649b154152db30f1d781e884879bc
git -C firmware/vendor/pico-sdk submodule update --init --recursive
cmake -S firmware/imported/scarletpico-rp2350-source -B firmware/build-rp2350-source -DPICO_SDK_PATH=/absolute/path/to/pico-sdk -DPICO_BOARD=waveshare_rp2350_zero -DPICO_PLATFORM=rp2350-arm-s
cmake --build firmware/build-rp2350-source -j
```

Нужны CMake, Arm GNU Toolchain и инструменты SDK (picotool — по его штатной
инструкции). Это подготовка порта, не заявление о его проверенной работе
на ещё не полученной плате. Сначала сверить разводку, затем перенести
актуальные UI/батарейку и проверить LCD, SD, звук, игры и сохранения.
UF2 RP2040 на RP2350 не прошивать.

Остальные сторонние рабочие исходники включены обычными файлами, не пустыми
gitlinks. Исходные upstream-базы:

- Peanut-GB: `d0bcca771c83a2638c93a9ae61f3d51f226dc905`.
- Peanut-GB-CGB: `33f053b9e70297ff0bab53da527c19126384d911`;
  локальные изменения включены, см. `firmware/vendor/Peanut-GB-CGB-PROVENANCE.md`.
- pico-fatfs-sd: `995777133afe98a2917bf45ffc7b488d10d62650`.

Лицензии/уведомления остаются в исходниках и third_party/notices.

## Корпус

Начать с `hardware/case/LATEST.md`. STL уже готовы. Генераторы используют
Python, numpy, manifold3d, trimesh, Pillow; дополнительные зависимости см.
в imports выбранного скрипта. OBJ/MTL и промежуточные STL сохранены как входы.
У старых генераторов встречаются абсолютные macOS-пути к шрифтам/входам —
на другом устройстве потребуется адаптация. Не запускать всю историческую
цепочку поверх текущих моделей: скрипты перезаписывают STL. Сначала зафиксировать
текущий комплект в Git, чтобы изменения можно было сравнить и отменить.

## Сохранение будущих изменений

```sh
git pull --ff-only
git switch main
# изменить файлы, выполнить нужные проверки
git add <конкретные-файлы>
git diff --cached
git commit -m "Describe the change"
git push origin main
```

Локальные изменения не отправляются автоматически. Не добавлять ROM-ы,
сохранения или секреты даже в приватный репозиторий.
