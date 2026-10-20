#include <stdio.h>
#include <string.h>
#include "config.h"
#include "display_st7796.h"
#include "emulator.h"
#include "game_library.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/spi.h"
#include "hardware/vreg.h"
#include "pico/stdlib.h"
#include "storage.h"
#include "video_worker.h"
#include "freeze_guard.h"

#define FRAME_TIME_US 16743u
#define MENU_BG 0xD7E9
#define MENU_INK 0x10C1
#define MENU_ROWS 7u

static game_entry_t games[GAME_LIBRARY_MAX];
static size_t game_count, selected;
static bool library_limited;
static FRESULT library_result;
static char save_path[GAME_PATH_SIZE];
static const display_scale_t game_scale = DISPLAY_FIT_HEIGHT;
static unsigned lcd_profile; /* volatile choice: reset always selects SAFE */
static const unsigned lcd_rates[] = {
    LCD_SPI_BAUD_HZ,
#if GAME_CLOCK_KHZ == 200000u
    25000000u, 50000000u,
#endif
};
#define LCD_PROFILE_COUNT (sizeof lcd_rates / sizeof lcd_rates[0])
static const unsigned button_pins[] = {
    PIN_BTN_A, PIN_BTN_B, PIN_BTN_SELECT, PIN_BTN_START,
    PIN_BTN_RIGHT, PIN_BTN_LEFT, PIN_BTN_UP, PIN_BTN_DOWN,
};

/* Only call with video core stopped. Raise DVDD before raising clk_sys, and
 * lower clk_sys before restoring the nominal 1.10V. Menu uses SDK clk_peri
 * 48 MHz; the 200 MHz test uses clk_sys for clk_peri to obtain 25/50 MHz SPI.
 * SD driver still configures 1 MHz before each SD transaction. */
static void menu_clock(void) {
    set_sys_clock_khz(125000, true);
#if GAME_CLOCK_KHZ > 125000u
    vreg_set_voltage(VREG_VOLTAGE_1_10);
#endif
    display_set_spi_baudrate(LCD_SPI_BAUD_HZ);
    display_select_bus();
}
static void game_clock(void) {
#if GAME_CLOCK_KHZ == 200000u
    /* RP2040 datasheet section 2.15.3: 200 MHz at DVDD 1.15V. */
    vreg_set_voltage(VREG_VOLTAGE_1_15);
    sleep_ms(10);
#elif GAME_CLOCK_KHZ > 200000u
    vreg_set_voltage(VREG_VOLTAGE_1_20);
    sleep_ms(10);
#endif
    set_sys_clock_khz(GAME_CLOCK_KHZ, true);
#if GAME_CLOCK_KHZ == 200000u
    clock_configure_undivided(clk_peri, 0,
        CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLK_SYS, GAME_CLOCK_KHZ * 1000u);
#endif
    display_set_spi_baudrate(lcd_rates[lcd_profile]);
    display_select_bus();
}

static void buttons_init(void) {
    for (size_t i = 0; i < sizeof button_pins / sizeof button_pins[0]; ++i) {
        gpio_init(button_pins[i]);
        gpio_set_dir(button_pins[i], GPIO_IN);
        gpio_pull_up(button_pins[i]);
    }
}
static uint8_t buttons(void) {
    uint8_t pressed = 0;
    for (unsigned i = 0; i < 8; ++i)
        if (!gpio_get(button_pins[i])) pressed |= (uint8_t)(1u << i);
    return pressed;
}

/* A transition needs both a cooldown and complete release. Held Start/Select
 * cannot leak from the game into menu selection or launch. */
static void release_buttons(unsigned minimum_ms) {
    uint64_t until = time_us_64() + minimum_ms * 1000ull;
    uint64_t released_since = 0;
    while (true) {
        freeze_guard_feed(true); /* intentional button-release wait, no SPI work */
        uint64_t now = time_us_64();
        if (buttons()) released_since = 0;
        else if (!released_since) released_since = now;
        if (now >= until && released_since && now - released_since >= 30000u) return;
        sleep_ms(5);
    }
}
static uint8_t wait_press(void) {
    release_buttons(100);
    while (true) {
        freeze_guard_feed(true);
        uint8_t pressed = buttons();
        if (pressed) {
            sleep_ms(25);
            if (buttons() == pressed) return pressed;
        }
        sleep_ms(5);
    }
}
static void message(const char *title, const char *detail, const char *hint) {
    freeze_guard_mark(FREEZE_VIDEO_WAIT, emulator_program_counter());
    video_wait_idle();
    display_clear(MENU_BG);
    display_draw_text(20, 24, title, MENU_INK, MENU_BG, 2);
    display_draw_text(20, 80, detail, MENU_INK, MENU_BG, 1);
    display_draw_text(20, 270, hint, MENU_INK, MENU_BG, 1);
    printf("%s: %s\n", title, detail);
}
static void scan_library(void) {
    message("SCARLETPICO COLOR", "READING MICROSD GAME LIST...", "GB AND GBC - V0.10");
    library_result = storage_scan_games(games, GAME_LIBRARY_MAX, &game_count, &library_limited);
    if (selected >= game_count) selected = 0;
}
static void draw_menu(void) {
    display_clear(MENU_BG);
    display_fill_rect(0, 0, 480, 45, MENU_INK);
    display_draw_text(18, 14, "SCARLETPICO COLOR", MENU_BG, MENU_INK, 2);
    display_draw_text(398, 17, "V0.10", MENU_BG, MENU_INK, 1);
    char clock_label[16];
    snprintf(clock_label, sizeof clock_label, "%uMHZ", GAME_CLOCK_KHZ / 1000u);
    display_draw_text(316, 17, clock_label, MENU_BG, MENU_INK, 1);
    if (library_result != FR_OK) {
        char error[48];
        snprintf(error, sizeof error, "CANNOT READ ROMS - FAT CODE %u", library_result);
        display_draw_text(18, 84, error, MENU_INK, MENU_BG, 1);
        display_draw_text(18, 106, "USE A ROMS FOLDER ON THE SD CARD", MENU_INK, MENU_BG, 1);
    } else if (!game_count) {
        display_draw_text(18, 84, "NO GAMES FOUND", MENU_INK, MENU_BG, 2);
        display_draw_text(18, 116, "PUT .GB AND .GBC FILES IN /ROMS", MENU_INK, MENU_BG, 1);
    } else {
        size_t first = selected / MENU_ROWS * MENU_ROWS;
        for (size_t row = 0; row < MENU_ROWS && first + row < game_count; ++row) {
            size_t index = first + row;
            uint16_t bg = index == selected ? MENU_INK : MENU_BG;
            uint16_t fg = index == selected ? MENU_BG : MENU_INK;
            uint16_t y = (uint16_t)(58 + row * 26);
            display_fill_rect(10, y - 4, 460, 24, bg);
            char label[31];
            snprintf(label, sizeof label, "%.30s", games[index].label);
            display_draw_text(20, y, label, fg, bg, 2);
            display_draw_text(424, y + 3, games[index].color ? "GBC" : "GB", fg, bg, 1);
        }
        char count[64];
        snprintf(count, sizeof count, "%u / %u%s", (unsigned)selected + 1,
                 (unsigned)game_count, library_limited ? " - LIST LIMITED TO 32" : "");
        display_draw_text(18, 249, count, MENU_INK, MENU_BG, 1);
        display_draw_text(18, 265, game_status_message(games[selected].status), MENU_INK, MENU_BG, 1);
    }
    char lcd_label[72];
    if (lcd_profile)
        snprintf(lcd_label, sizeof lcd_label, "LEFT RIGHT: LCD %u MHZ TEST - OUT OF SPEC", lcd_rates[lcd_profile] / 1000000u);
    else
        snprintf(lcd_label, sizeof lcd_label, "LEFT RIGHT: LCD 12 MHZ SAFE - FULL HEIGHT");
    display_draw_text(18, 277, lcd_label, MENU_INK, MENU_BG, 1);
    display_draw_text(18, 289, "UP DOWN OR SELECT: CHOOSE   A OR START: PLAY", MENU_INK, MENU_BG, 1);
    display_draw_text(18, 303, "B: REFRESH   HOLD START AND SELECT IN GAME FOR MENU", MENU_INK, MENU_BG, 1);
}
static bool flush_save(void) {
    if (!emulator_save_dirty() || !emulator_save_size()) return true;
    /* SD and LCD share SPI0. No new video job is submitted during this call. */
    freeze_guard_mark(FREEZE_VIDEO_WAIT, emulator_program_counter());
    video_wait_idle();
    freeze_guard_mark(FREEZE_SD_SAVE, emulator_program_counter());
    bool was_active = freeze_guard_pause();
    bool saved = storage_write_save(save_path, emulator_save_data(), emulator_save_size());
    freeze_guard_resume(was_active);
    freeze_guard_mark(FREEZE_INPUT, emulator_program_counter());
    if (!saved) return false;
    emulator_save_clean();
    return true;
}
static void save_before_menu(void) {
    while (!flush_save()) {
        message("SAVE FAILED", "A: RETRY SAVE   B: DISCARD UNSAVED CHANGES", "THE GAME WILL RETURN TO THE MENU");
        uint8_t pressed = wait_press();
        if (pressed & BUTTON_B) return;
    }
}
static void back_after_error(const char *title, const char *detail) {
    message(title, detail, "B: BACK");
    while (!(wait_press() & BUTTON_B)) {}
}
static void run_game(const game_entry_t *game) {
    if (game->status != GAME_READY) {
        back_after_error("CANNOT START GAME", game_status_message(game->status));
        return;
    }
    char rom_path[GAME_PATH_SIZE];
    if (!game_rom_path(game, rom_path, sizeof rom_path) ||
        !game_save_path(game, save_path, sizeof save_path)) return;
    release_buttons(150);
    /* Flash erase/program must never run while core 1 executes from XIP. */
    video_stop();
    menu_clock();
    message("LOADING GAME", game->label, "DO NOT UNPLUG - A NEW GAME MAY TAKE SEVERAL SECONDS");
    const uint8_t *rom;
    size_t size;
    if (!storage_prepare_rom(rom_path, &rom, &size)) {
        back_after_error("ROM LOAD FAILED", "CHECK THE SD CARD AND ROM SIZE");
        return;
    }
    if (!emulator_load(rom, size, display_store_rgb_line)) {
        back_after_error("CANNOT START GAME", emulator_error());
        return;
    }
    if (!storage_load_save(save_path, emulator_save_data(), emulator_save_size())) {
        back_after_error("SAVE READ FAILED", "EXISTING SAVE WAS NOT REPLACED");
        return;
    }
    emulator_save_clean();
    freeze_guard_start();
    game_clock();
    printf("Starting %s: mode=%s ROM=%lu RAM=%lu LCD_SPI=%u Hz\n", game->filename,
           emulator_is_color() ? "GBC" : "GB", (unsigned long)size,
           (unsigned long)emulator_save_size(), spi_get_baudrate(spi0));
    display_clear(0);
    freeze_guard_mark(FREEZE_VIDEO_START, emulator_program_counter());
    if (!video_start(game_scale)) {
        freeze_guard_stop();
        menu_clock();
        back_after_error("NOT ENOUGH MEMORY", "THIS GAME NEEDS MORE RAM THAN THE VIDEO MODE ALLOWS");
        return;
    }
    uint64_t next_frame = time_us_64();
    uint64_t last_save = next_frame, chord_started = 0, stats_start = next_frame;
    uint64_t compute_us = 0, render_us = 0, skip_us = 0;
    unsigned stats_frames = 0, emulated_fps = 0, last_video_count = 0;
    unsigned render_count = 0, skip_count = 0;
    bool frame_waiting = false;
    while (true) {
        bool healthy = video_healthy();
        freeze_guard_mark(healthy ? FREEZE_INPUT : FREEZE_VIDEO_WAIT, emulator_program_counter());
        freeze_guard_feed(healthy);
        if (!healthy) {
            /* Do not overwrite the diagnostic stage or feed a stuck worker. */
            sleep_ms(5);
            continue;
        }
        uint8_t pressed = buttons();
        uint64_t now = time_us_64();
        bool chord = (pressed & (BUTTON_START | BUTTON_SELECT)) == (BUTTON_START | BUTTON_SELECT);
        if (chord) {
            pressed &= (uint8_t)~(BUTTON_START | BUTTON_SELECT);
            if (!chord_started) chord_started = now;
            if (now - chord_started >= 1500000u) {
                save_before_menu();
                break;
            }
        } else chord_started = 0;
        /* Start the already-rendered next frame as soon as SPI is free, even
         * between emulation ticks. The other buffer is then safe to draw into. */
        if (frame_waiting && video_ready()) {
            video_submit(emulated_fps);
            frame_waiting = false;
        }
        if (now < next_frame) {
            sleep_us(500);
            continue;
        }
        /* No fixed 30 FPS cap: render whenever a producer buffer is free.
         * Busy video skips pixels, never game logic. */
        bool render = !frame_waiting;
        uint64_t frame_start = time_us_64();
        freeze_guard_mark(FREEZE_FRAME, emulator_program_counter());
        if (!emulator_frame_render((uint8_t)~pressed, render)) {
            freeze_guard_mark(FREEZE_VIDEO_STOP, emulator_program_counter());
            video_stop();
            freeze_guard_stop();
            back_after_error("EMULATOR STOPPED", emulator_error());
            save_before_menu();
            break;
        }
        uint64_t elapsed = time_us_64() - frame_start;
        compute_us += elapsed;
        if (render) { render_us += elapsed; ++render_count; }
        else { skip_us += elapsed; ++skip_count; }
        ++stats_frames;
        if (render) frame_waiting = true;
        if (frame_waiting && video_ready()) {
            video_submit(emulated_fps);
            frame_waiting = false;
        }
        next_frame += FRAME_TIME_US;
        now = time_us_64();
        if (now - stats_start >= 1000000u) {
            uint64_t interval = now - stats_start;
            emulated_fps = (unsigned)((uint64_t)stats_frames * 1000000u / interval);
            unsigned count = video_frames_completed();
            unsigned lcd_fps = (unsigned)((uint64_t)(count - last_video_count) * 1000000u / interval);
            printf("PERF %s: EMU=%u LCD=%u CPU/frame=%lu us LCD/last=%u us "
                   "CPU/render=%lu us CPU/skip=%lu us DRAW=%u SKIP=%u\n",
                   display_scale_name(game_scale), emulated_fps, lcd_fps,
                   (unsigned long)(compute_us / stats_frames), video_last_transfer_us(),
                   (unsigned long)(render_count ? render_us / render_count : 0),
                   (unsigned long)(skip_count ? skip_us / skip_count : 0), render_count, skip_count);
            last_video_count = count;
            stats_frames = 0;
            compute_us = 0;
            render_us = skip_us = 0;
            render_count = skip_count = 0;
            stats_start = now;
        }
        if (now > next_frame + 500000u) next_frame = now;
        if (now - last_save >= 10000000u) {
            if (!flush_save()) printf("Autosave failed; dirty RAM retained\n");
            last_save = now;
        }
    }
    freeze_guard_mark(FREEZE_VIDEO_STOP, emulator_program_counter());
    video_stop();
    freeze_guard_stop();
    menu_clock();
}

int main(void) {
    freeze_report_t crash;
    bool recovered = freeze_guard_boot_report(&crash);
    stdio_init_all();
    buttons_init();
    display_bus_init();
    sleep_ms(10);
    bool mounted = storage_mount();
    display_init();
    printf("\nScarletPico Color v0.10 - GB/GBC launcher - context %lu bytes\n",
           (unsigned long)emulator_context_size());
    if (recovered) {
        char details[128];
        snprintf(details, sizeof details, "LAST STAGE: %s\nLAST PC: %04X   CPU: %u MHZ\nUNSAVED PROGRESS MAY BE LOST",
                 freeze_stage_name(crash.stage), crash.pc, crash.clock_khz / 1000);
        message("RECOVERED FROM FREEZE", details, "TAKE A PHOTO OF THIS SCREEN - A: CONTINUE");
        while (!(wait_press() & BUTTON_A)) {}
    }
    /* Optional display check; no game auto-starts. */
    if (buttons() & BUTTON_B) {
        display_test_pattern();
        while (buttons() & BUTTON_B) sleep_ms(10);
        release_buttons(100);
    }
    while (!mounted) {
        message("MICROSD MOUNT FAILED", "USE SD DIAGNOSTIC V05 IF THIS PERSISTS", "A: RETRY");
        if (wait_press() & BUTTON_A) mounted = storage_mount();
    }
    scan_library();
    draw_menu();
    release_buttons(200);
    uint8_t previous = 0;
    uint64_t repeat_at = 0;
    while (true) {
        uint8_t pressed = buttons();
        if (pressed != previous) {
            sleep_ms(25);
            if (buttons() != pressed) continue;
        }
        uint8_t edge = pressed & (uint8_t)~previous;
        uint64_t now = time_us_64();
        if (edge & (BUTTON_UP | BUTTON_DOWN)) repeat_at = now + 400000u;
        else if ((pressed & (BUTTON_UP | BUTTON_DOWN)) && now >= repeat_at) {
            edge |= pressed & (BUTTON_UP | BUTTON_DOWN);
            repeat_at = now + 180000u;
        }
        previous = pressed;
        if (edge & BUTTON_B) {
            scan_library();
            draw_menu();
            release_buttons(100);
            previous = 0;
        } else if (game_count && library_result == FR_OK) {
            if (edge & BUTTON_RIGHT) {
                lcd_profile = (lcd_profile + 1u) % LCD_PROFILE_COUNT;
                draw_menu();
            } else if (edge & BUTTON_LEFT) {
                lcd_profile = (lcd_profile + LCD_PROFILE_COUNT - 1u) % LCD_PROFILE_COUNT;
                draw_menu();
            } else if (edge & BUTTON_UP) {
                selected = selected ? selected - 1 : game_count - 1;
                draw_menu();
            } else if (edge & (BUTTON_DOWN | BUTTON_SELECT)) {
                selected = (selected + 1) % game_count;
                draw_menu();
            } else if (edge & (BUTTON_A | BUTTON_START)) {
                run_game(&games[selected]);
                draw_menu();
                release_buttons(2000);
                previous = 0;
            }
        }
        sleep_ms(5);
    }
}
