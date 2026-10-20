/* Production launcher with simulated GPIO/time/storage, no physical I/O. */
#define main device_main
#include "../src/main.c"
#undef main
#include <assert.h>
#include <setjmp.h>

spi_inst_t test_spi;
static uint64_t fake_time;
static unsigned scenario, launches;
static jmp_buf done;
static char launched_path[GAME_PATH_SIZE];
static bool worker_running, save_dirty;
static uint64_t video_busy_until;
static unsigned rendered, skipped, saves_written, idle_waits;
static bool guarded;
static uint32_t test_clock = 125000;
static unsigned test_voltage = VREG_VOLTAGE_1_10;
static unsigned test_lcd_rate = LCD_SPI_BAUD_HZ;
bool freeze_guard_boot_report(freeze_report_t *r) { (void)r; return false; }
const char *freeze_stage_name(unsigned stage) { (void)stage; return "TEST"; }
void freeze_guard_start(void) { guarded = true; }
void freeze_guard_mark(freeze_stage_t stage, uint16_t pc) { (void)stage; (void)pc; }
void freeze_guard_feed(bool healthy) { (void)healthy; }
void freeze_guard_stop(void) { guarded = false; }
bool freeze_guard_pause(void) { bool was_active = guarded; guarded = false; return was_active; }
void freeze_guard_resume(bool was_active) { guarded = was_active; }

static uint8_t simulated_buttons(void) {
    if (scenario == 1) {
        if (fake_time >= 260000 && fake_time < 340000) return BUTTON_DOWN;
        if (fake_time >= 400000 && fake_time < 460000) return BUTTON_START;
    }
    if (scenario == 2 && fake_time < 3000000) return BUTTON_START | BUTTON_SELECT;
    if (scenario == 3 && fake_time < 900000) return BUTTON_A;
    if (scenario == 5) {
        if (fake_time >= 260000 && fake_time < 340000) return BUTTON_RIGHT;
        if (fake_time >= 400000 && fake_time < 460000) return BUTTON_START;
    }
    if ((scenario == 6 || scenario == 7) && fake_time >= 300000 && fake_time < 2200000)
        return BUTTON_START | BUTTON_SELECT;
    return 0;
}
void gpio_init(unsigned pin) { (void)pin; }
void gpio_pull_up(unsigned pin) { (void)pin; }
void gpio_set_dir(unsigned pin, bool out) { (void)pin; (void)out; }
bool gpio_get(unsigned pin) {
    for (unsigned i = 0; i < 8; ++i)
        if (button_pins[i] == pin) return !(simulated_buttons() & (1u << i));
    return true;
}
uint64_t time_us_64(void) { return fake_time; }
void sleep_us(uint64_t us) {
    fake_time += us;
    if ((scenario < 2 || scenario == 5) && fake_time > 1000000) longjmp(done, 1);
}
void sleep_ms(uint32_t ms) { sleep_us(ms * 1000ull); }
void stdio_init_all(void) {}
bool set_sys_clock_khz(uint32_t khz, bool required) {
    (void)required; assert(!worker_running);
    if (khz == 200000) assert(test_voltage == VREG_VOLTAGE_1_15);
    if (khz == 250000) assert(test_voltage == VREG_VOLTAGE_1_20);
    test_clock = khz;
    return true;
}
void vreg_set_voltage(unsigned voltage) {
    assert(!worker_running);
    if (voltage == VREG_VOLTAGE_1_10) assert(test_clock == 125000);
    test_voltage = voltage;
}
void clock_configure_undivided(unsigned clock, uint32_t src, uint32_t aux, uint32_t frequency) {
    assert(!worker_running && test_clock == 200000 && test_voltage == VREG_VOLTAGE_1_15);
    assert(clock == clk_peri && src == 0 && aux == CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLK_SYS);
    assert(frequency == 200000000u);
}
unsigned spi_get_baudrate(const spi_inst_t *spi) { (void)spi; return 12000000; }
void display_bus_init(void) {}
void display_init(void) {}
void display_select_bus(void) {}
bool display_set_spi_baudrate(unsigned baud) {
    assert(!worker_running);
    test_lcd_rate = baud;
    return true;
}
void display_clear(uint16_t color) { (void)color; }
void display_test_pattern(void) {}
void display_present(void) {}
const char *display_scale_name(display_scale_t scale) { (void)scale; return "TEST"; }
bool video_start(display_scale_t scale) {
    assert(scale == DISPLAY_FIT_HEIGHT && test_lcd_rate == lcd_rates[lcd_profile]);
    worker_running = true;
    video_busy_until = fake_time; /* a freshly started worker is idle */
    return true;
}
bool video_ready(void) { return worker_running && fake_time >= video_busy_until; }
bool video_healthy(void) { return true; }
bool video_submit(unsigned fps) {
    (void)fps; assert(video_ready());
    video_busy_until = fake_time + (scenario == 7 ? 1000 : 31000); return true;
}
void video_wait_idle(void) {
    ++idle_waits;
    if (worker_running && fake_time < video_busy_until) fake_time = video_busy_until;
}
void video_stop(void) { video_wait_idle(); worker_running = false; }
unsigned video_frames_completed(void) { return 0; }
unsigned video_last_transfer_us(void) { return 0; }
void display_store_rgb_line(const uint16_t *data, uint8_t row) { (void)data; (void)row; }
void display_fill_rect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t c) {
    (void)x; (void)y; (void)w; (void)h; (void)c;
}
void display_draw_text(uint16_t x, uint16_t y, const char *s, uint16_t f, uint16_t b, uint8_t scale) {
    (void)x; (void)y; (void)s; (void)f; (void)b; (void)scale;
}
bool storage_mount(void) { return true; }
FRESULT storage_scan_games(game_entry_t *list, size_t capacity, size_t *count, bool *limited) {
    assert(capacity >= 2);
    memset(list, 0, 2 * sizeof *list);
    snprintf(list[0].filename, sizeof list[0].filename, "Aladdin.gbc");
    snprintf(list[1].filename, sizeof list[1].filename, "Zelda.gb");
    list[0].color = true;
    *count = 2; *limited = false;
    return FR_OK;
}
bool storage_prepare_rom(const char *path, const uint8_t **rom, size_t *size) {
    assert(!worker_running); /* Flash cache requires the second core stopped. */
    assert(test_clock == 125000 && test_voltage == VREG_VOLTAGE_1_10);
    assert(test_lcd_rate == LCD_SPI_BAUD_HZ);
    assert(!guarded);
    ++launches;
    snprintf(launched_path, sizeof launched_path, "%s", path);
    if (scenario == 6 || scenario == 7) {
        static const uint8_t dummy_rom[16] = {0};
        *rom = dummy_rom; *size = sizeof dummy_rom;
        return true;
    }
    longjmp(done, 2);
}
bool game_rom_path(const game_entry_t *game, char *path, size_t n) {
    return snprintf(path, n, "0:/roms/%s", game->filename) > 0;
}
bool game_save_path(const game_entry_t *game, char *path, size_t n) {
    (void)game; snprintf(path, n, "0:/saves/test.sav"); return true;
}
const char *game_status_message(game_status_t status) { (void)status; return "READY"; }
bool storage_load_save(const char *p, uint8_t *data, size_t n) { (void)p; (void)data; (void)n; return true; }
bool storage_write_save(const char *p, const uint8_t *data, size_t n) {
    (void)p; (void)data; (void)n;
    assert(fake_time >= video_busy_until); /* Never SD while LCD is active. */
    assert(!guarded); /* Watchdog cannot reset a non-transactional SD write. */
    ++saves_written;
    return true;
}
bool emulator_load(const uint8_t *rom, size_t n, emulator_line_fn draw) { (void)rom; (void)n; (void)draw; return true; }
bool emulator_frame(uint8_t keys) { (void)keys; return true; }
bool emulator_frame_render(uint8_t keys, bool render) {
    assert(guarded);
    assert(test_clock == GAME_CLOCK_KHZ);
    if (scenario == 7) assert(render); /* idle LCD must not impose a 30 FPS cap */
    if (simulated_buttons() == (BUTTON_START | BUTTON_SELECT))
        assert((keys & (BUTTON_START | BUTTON_SELECT)) == (BUTTON_START | BUTTON_SELECT));
    if (render) ++rendered; else ++skipped;
    fake_time += 10000; /* CPU still progresses while the 31ms LCD transfer runs. */
    save_dirty = true;
    return true;
}
bool emulator_is_color(void) { return true; }
const char *emulator_error(void) { return "TEST"; }
uint8_t *emulator_save_data(void) { return NULL; }
size_t emulator_save_size(void) { return scenario == 6 || scenario == 7 ? 8192 : 0; }
bool emulator_save_dirty(void) { return save_dirty; }
void emulator_save_clean(void) { save_dirty = false; }
size_t emulator_context_size(void) { return 0; }
uint16_t emulator_program_counter(void) { return 0x1234; }

int main(void) {
    int result = setjmp(done);
    if (!result) device_main();
    assert(result == 1 && launches == 0); /* idle boot remains in menu */
    scenario = 1; fake_time = 0; selected = 0;
    result = setjmp(done);
    if (!result) device_main();
    assert(result == 2 && launches == 1 && !strcmp(launched_path, "0:/roms/Zelda.gb"));
    scenario = 5; fake_time = 0; selected = 0; lcd_profile = 0;
    assert(game_scale == DISPLAY_FIT_HEIGHT);
    result = setjmp(done);
    if (!result) device_main();
    assert(result == 2 && game_scale == DISPLAY_FIT_HEIGHT && !strcmp(launched_path, "0:/roms/Aladdin.gbc"));
    assert(lcd_profile == 1 % LCD_PROFILE_COUNT);
    scenario = 2; fake_time = 0;
    release_buttons(2000);
    assert(fake_time >= 3030000 && buttons() == 0);
    scenario = 3; fake_time = 0;
    release_buttons(150);
    assert(fake_time >= 930000 && buttons() == 0);
    scenario = 4; fake_time = 0;
    release_buttons(2000);
    assert(fake_time >= 2000000);
    scenario = 6; fake_time = 0;
    run_game(&games[0]);
    assert(rendered > 10 && skipped > 10 && saves_written == 1 && !save_dirty);
    assert(!worker_running && idle_waits > 0);
    assert(!guarded);
    assert(test_clock == 125000 && test_voltage == VREG_VOLTAGE_1_10);
    assert(test_lcd_rate == LCD_SPI_BAUD_HZ);
    assert(fake_time >= 1800000 && fake_time < 2200000);
    scenario = 7; fake_time = 0; rendered = skipped = 0;
    run_game(&games[0]);
    assert(rendered > 80 && skipped == 0);
    assert(!worker_running && !guarded);
    assert(test_clock == 125000 && test_voltage == VREG_VOLTAGE_1_10);
    puts("PASS: no fixed render cap with idle LCD; safe voltage/clock order and menu restoration");
    puts("PASS: menu, selected ROM, full-height stays fixed, cooldown, nonblocking game loop, chord suppression, save/LCD exclusion, stopped core before flash/clocks");
}
