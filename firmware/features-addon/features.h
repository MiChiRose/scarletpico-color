#pragma once
#ifdef SCARLET_RP2040_NATIVE
#include "../imported/scarletpico-rp2040-source/console.h"
#elif defined(SCARLET_NATIVE_SOURCE)
#include "../imported/scarletpico-rp2350-source/console.h"
#else
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "ui.h"
#include "ff.h"

#define FEATURES_VERSION "2.2.2"

#define RESIDENT_SIZE 0x17f000u
#define CORE_SIZE 0xc324u
#define APU_SIZE 312u
#define CORE ((uint8_t *)0x20003600u)
#define APU ((uint8_t *)0x2001f2c0u)
#define SAMPLE_REMAINDER (*(uint32_t *)0x2001f2b8u)
#define SAVE_DATA (*(uint8_t **)0x2001db8cu)
#define SAVE_SIZE (*(uint32_t *)0x2001dcb0u)
#define ROM_SIZE (*(uint32_t *)0x2001db88u)
#define ROM_DATA (*(const uint8_t **)0x2001db84u)
#define DIRTY (*(uint8_t *)0x2001e252u)

extern void *original_malloc(size_t);
extern void original_free(void *);
extern void original_sd_bus(void);
extern void original_display_select_bus(void);
extern void original_video_stop(void);
extern void original_video_wait_idle(void);
extern bool original_video_start(unsigned);
extern bool original_guard_pause(void);
extern void original_guard_resume(bool);
extern bool original_addon_frame(uint8_t, bool);
extern void original_addon_stop(void);
extern void original_audio_stop(void);
extern bool original_audio_start(void);
extern void original_flash_erase(uint32_t, size_t);
extern void original_flash_program(uint32_t, const uint8_t *, size_t);
extern void original_ui_init(const uint8_t *);
extern bool original_loader_prepare(const char *, const uint8_t **, size_t *);
extern bool original_emulator_load(const uint8_t *, size_t, void *);
extern void original_core_error(void *, unsigned, uint16_t) __attribute__((noreturn));
extern uint64_t time_us_64(void);
extern void sleep_ms(uint32_t);

extern uint8_t cpu_profile;
extern bool pause_pending, exit_requested;
uint8_t feature_keys(void);
void feature_release(void);
const char *feature_tr(const char *, const char *);
void feature_page(const char *);
void feature_row(unsigned, unsigned, const char *, const char *);
void feature_footer(const char *, const char *);
void feature_message(const char *, const char *);
void feature_error(const char *);
void feature_settings(void);
void feature_about(void);
void features_draw_fps(unsigned lcd_fps, unsigned emulated_fps, unsigned scale);
void features_ui_init(const uint8_t *);
void features_boot_ui_init(const uint8_t *);
void features_game_clock(uint32_t, uint32_t, uint32_t);
void features_menu_clock(uint32_t, uint32_t, uint32_t);
bool features_prepare(const char *, const uint8_t **, size_t *);
bool features_load(const uint8_t *, size_t, void *);
uint8_t features_rom_read(void *, uint32_t);
void features_stop(void);
void features_stream_close(void);
unsigned features_buttons(unsigned);
bool features_frame(uint8_t, bool);

enum { STATE_EMPTY, STATE_SAVED, STATE_INVALID, STATE_IO_ERROR, STATE_NO_MEMORY };
unsigned state_status(unsigned slot);
unsigned state_save(unsigned slot);
unsigned state_load(unsigned slot);
uint32_t state_crc(uint32_t, const void *, size_t);

static inline uint32_t features_irq_off(void) {
 uint32_t value;
 __asm volatile("mrs %0, primask\ncpsid i" : "=r"(value) :: "memory");
 return value;
}
static inline void features_irq_restore(uint32_t value) {
 __asm volatile("msr primask, %0" :: "r"(value) : "memory");
}
#endif
