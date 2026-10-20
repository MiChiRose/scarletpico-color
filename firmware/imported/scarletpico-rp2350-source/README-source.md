# Исходники ScarletPico RP2350 test1

Новая экспериментальная реализация по подключению из ScarletPico v0.9.
Это не восстановленные оригинальные исходники и не побайтовый порт старого UF2.
Подробности подключения и вечерней проверки — в README-RP2350.md пакета.

Сборка: Pico SDK 2.3.0 с подмодулем tinyusb, ARM GCC, CMake; плата
`waveshare_rp2350_zero`, платформа `rp2350-arm-s`. Указать `PICO_SDK_PATH`
и, при необходимости, `PICO_TOOLCHAIN_PATH`, затем выполнить `./build.sh B`.
Профили A/B/C/D соответствуют описанию пакета. `SCARLET_PICOTOOL` в CMake
позволяет передать путь к отдельно установленному picotool; иначе SDK находит
его или собирает стандартным способом. `malloc_compat.c` содержит только
дополнительные malloc-хуки для локального Arduino ARM toolchain с retargetable
newlib; на обычном newlib они не включаются.

Проверка логики на компьютере:

```sh
clang -std=c11 -O1 -g -fsanitize=address,undefined \
  -Ithird_party/peanut -I. test_host.c -o test-host
./test-host
```

Она не проверяет работу GPIO, flash и SD на микроконтроллере или аппаратный FPS.

Зависимости, зафиксированные при подготовке:

- Peanut-GB, `tvecera/Peanut-GB`, ветка `gbc-rtc-fix`, commit
  `a7919bb8be099f5a0a1f85daa6a33b73519eb666`. MIT, текст в начале заголовка.
  Локальные изменения: безопасное обновление индексов BG/OAM-палитры,
  явные скобки для ветки LCD timing, необязательный атрибут `PEANUT_GB_HOT`.
- `carlk3/no-OS-FatFS-SD-SPI-RPi-Pico`, commit
  `196016f525e5b9c161f2b965ddd3045a4ef87649`. Apache-2.0 для драйвера SD;
  собственная лицензия FatFs находится в его исходных файлах. Локальное
  изменение конфигурации: `FF_FS_NORTC=1`; код старого hardware_rtc не
  включается в сборку RP2350.
- Pico SDK 2.3.0, commit `98a542c1a62fb549ffb5d66a3e5892b06276b670`,
  tinyusb commit `86ad6e56c1700e85f1c5678607a762cfe3aa2f47`.
  SDK и компилятор не включены в архив исходников.

В этом пакете нет игровых ROM. Тестовая программа в `test_host.c` — короткий
оригинальный программный цикл, создаваемый в памяти для проверки ядра.
