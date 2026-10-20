cmake_minimum_required(VERSION 3.13)
set(PICO_BOARD waveshare_rp2040_zero CACHE STRING "RP2040 target")
set(PICO_PLATFORM rp2040 CACHE STRING "Cortex-M0+ platform")
include(${PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(scarlet2040 C CXX ASM)
set(CMAKE_C_STANDARD 11)
if(SCARLET_PICOTOOL)
  add_executable(picotool IMPORTED GLOBAL)
  set_property(TARGET picotool PROPERTY IMPORTED_LOCATION ${SCARLET_PICOTOOL})
endif()
pico_sdk_init()
set(SCARLET_CPU_KHZ 200000 CACHE STRING "CPU/peripheral clock")
set(SCARLET_LCD_HZ 100000000 CACHE STRING "Requested LCD SPI clock")
set(SCARLET_SCALE 2 CACHE STRING "Integer x2")
set(NATIVE ${CMAKE_CURRENT_LIST_DIR}/../scarletpico-rp2350-source)
set(SD ${NATIVE}/third_party/sd)
set(SHARED ${CMAKE_CURRENT_LIST_DIR}/../..)
add_executable(scarlet2040 main.c console_ui.c console_audio.c console_power.c battery_model.c
  ${NATIVE}/display.c ${NATIVE}/hw_config.c ${NATIVE}/partition_map.c ${NATIVE}/console_state.c
  ${SHARED}/ui-addon/ui.c ${SHARED}/features-addon/boot.c ${SHARED}/features-addon/pause.c
  ${SD}/ff15/source/ff.c ${SD}/ff15/source/ffunicode.c ${SD}/ff15/source/ffsystem.c
  ${SD}/src/glue.c ${SD}/src/my_debug.c
  ${SD}/sd_driver/spi.c ${SD}/sd_driver/sd_spi.c ${SD}/sd_driver/sd_card.c
  ${SD}/sd_driver/crc.c ${SD}/sd_driver/demo_logging.c)
target_include_directories(scarlet2040 PRIVATE . ${NATIVE} ${NATIVE}/third_party/peanut
  ${SHARED}/ui-addon ${SD}/ff15/source ${SD}/include ${SD}/sd_driver)
target_compile_definitions(scarlet2040 PRIVATE
  SCARLET_CPU_KHZ=${SCARLET_CPU_KHZ} SCARLET_LCD_HZ=${SCARLET_LCD_HZ}
  SCARLET_SCALE=${SCARLET_SCALE} PEANUT_FULL_GBC_SUPPORT=1 ENABLE_SOUND=1
  SCARLET_NATIVE_SOURCE=1 SCARLET_RP2040_NATIVE=1 SCARLET_PAUSE_SETTINGS=1
  PICO_STDIO_USB_STDOUT_TIMEOUT_US=0)
target_compile_options(scarlet2040 PRIVATE -O3 -fno-strict-aliasing -Wall -Wextra
  -Wno-unused-parameter -Wno-sign-compare)
target_link_libraries(scarlet2040 pico_stdlib pico_multicore hardware_spi hardware_dma
  hardware_flash hardware_sync hardware_clocks hardware_vreg hardware_pio hardware_pwm hardware_adc)
pico_generate_pio_header(scarlet2040 ${SHARED}/src/audio_i2s.pio)
pico_enable_stdio_uart(scarlet2040 0)
pico_enable_stdio_usb(scarlet2040 1)
pico_set_program_name(scarlet2040 "ScarletPico Color RP2040 native test")
pico_set_program_version(scarlet2040 "2.2.5-RP2040-gp29-test")
pico_add_extra_outputs(scarlet2040)
