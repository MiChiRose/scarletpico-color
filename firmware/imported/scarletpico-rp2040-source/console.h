#pragma once
#include "../../ui-addon/ui.h"
#include "pico/stdlib.h"

#define FEATURES_VERSION "2.2.5-RP2040"
#define SETTINGS_FLASH_OFFSET 0x7f000u
extern bool pause_pending, exit_requested, chord_active, chord_latched;
extern uint32_t chord_since;
extern uint8_t slot_status[5];
uint8_t feature_keys(void);
void feature_release(void);
const char *feature_tr(const char *, const char *);
void feature_page(const char *);
void feature_row(unsigned, unsigned, const char *, const char *);
void feature_footer(const char *, const char *);
void feature_message(const char *, const char *);
void feature_error(const char *);
void feature_settings(void);
void features_ui_init(const uint8_t *);
void features_boot_ui_init(const uint8_t *);
unsigned features_buttons(unsigned);
bool features_frame(uint8_t, bool);
unsigned console_menu(unsigned);
void console_message(const char *, const char *);
void console_card_error(void);
void console_input_reset(void);

/* These adapters refer to native objects, never fixed binary addresses. */
unsigned native_game_count(void);
const char *native_game_label(unsigned);
bool native_game_color(unsigned);
bool native_game_folder(unsigned);
void native_video_stop(void);
void native_video_start(void);
void *native_staging(unsigned *);
unsigned native_core_size(void);
void native_core_copy(void *);
void native_core_restore(const void *);
const uint8_t *native_rom(unsigned *);
uint8_t *native_save_ram(unsigned *);
void native_mark_save_dirty(void);
bool original_video_start(unsigned);
void original_video_stop(void);
void original_video_wait_idle(void);
bool original_guard_pause(void);
void original_guard_resume(bool);
bool original_addon_frame(uint8_t, bool);
bool original_audio_start(void);
void original_audio_stop(void);
void original_audio_submit(const int16_t *,size_t);
extern int16_t original_audio_pcm[536];
extern volatile uint32_t original_audio_queue[514];
void console_apu_init(void);
void console_audio_frame(void);
unsigned console_apu_size(void);
void console_apu_snapshot(uint8_t *);
void console_apu_restore(const uint8_t *);
enum {STATE_EMPTY,STATE_SAVED,STATE_INVALID,STATE_IO_ERROR,STATE_NO_MEMORY};
unsigned state_status(unsigned);
unsigned state_save(unsigned);
unsigned state_load(unsigned);
void console_state_bind(void);
