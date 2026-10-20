cmake_minimum_required(VERSION 3.13...3.28)

set(PICO_SDK_PATH "${CMAKE_CURRENT_LIST_DIR}/vendor/pico-sdk" CACHE PATH "Pico SDK path")
include(${PICO_SDK_PATH}/pico_sdk_init.cmake)

project(scarletpico_firmware C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(SCARLET_GAME_CLOCK_KHZ "125000" CACHE STRING "Game CPU clock: 125000 baseline, 200000 at 1.15V, 250000 experimental")
if(NOT SCARLET_GAME_CLOCK_KHZ MATCHES "^(125000|200000|250000)$")
    message(FATAL_ERROR "SCARLET_GAME_CLOCK_KHZ must be 125000, 200000 or 250000")
endif()

pico_sdk_init()
add_subdirectory(vendor/pico-fatfs-sd/src build-fatfs)

add_executable(scarletpico
    src/display_st7796.c
    src/hw_config.c
    src/game_library.c
    src/emulator.c
    src/partition_map.c
    src/main.c
    src/storage.c
    src/video_worker.c
    src/freeze_guard.c
)

target_include_directories(scarletpico PRIVATE
    include
    vendor/Peanut-GB-CGB
)

target_compile_options(scarletpico PRIVATE -O3 -ffast-math -fstack-usage)
target_compile_definitions(scarletpico PRIVATE
    PICO_FLASH_SIZE_BYTES=2097152
    PICO_STACK_SIZE=4096u
    PICO_CORE1_STACK_SIZE=4096u
    GAME_CLOCK_KHZ=${SCARLET_GAME_CLOCK_KHZ}u
    PICO_MALLOC_PANIC=0
    PICO_STDIO_USB_STDOUT_TIMEOUT_US=2000
    PICO_STDIO_DEADLOCK_TIMEOUT_MS=10
    PARAM_ASSERTIONS_DISABLE_ALL=1
)

target_link_libraries(scarletpico PRIVATE
    pico_stdlib
    pico_multicore
    pico-fatfs-sd
    hardware_clocks
    hardware_flash
    hardware_gpio
    hardware_spi
    hardware_sync
    hardware_vreg
    hardware_watchdog
)

pico_enable_stdio_usb(scarletpico 1)
pico_enable_stdio_uart(scarletpico 0)
pico_set_program_name(scarletpico "ScarletPico Color GB/GBC Menu")
pico_set_program_version(scarletpico "0.10-${SCARLET_GAME_CLOCK_KHZ}kHz")
pico_add_extra_outputs(scarletpico)

add_executable(scarletpico_diag
    src/diagnostic_fs_main.c
    src/display_st7796.c
    src/hw_config.c
    src/partition_map.c
)

target_include_directories(scarletpico_diag PRIVATE include)
target_compile_options(scarletpico_diag PRIVATE -O2)
target_compile_definitions(scarletpico_diag PRIVATE
    PICO_FLASH_SIZE_BYTES=2097152
    PICO_STACK_SIZE=4096u
    PARAM_ASSERTIONS_DISABLE_ALL=1
    SD_SPI_BAUD_HZ=1000000u
    LCD_SPI_BAUD_HZ=12500000u
)
target_link_libraries(scarletpico_diag PRIVATE
    pico_stdlib
    pico-fatfs-sd
    hardware_gpio
    hardware_spi
)
pico_enable_stdio_usb(scarletpico_diag 1)
pico_enable_stdio_uart(scarletpico_diag 0)
pico_add_extra_outputs(scarletpico_diag)
