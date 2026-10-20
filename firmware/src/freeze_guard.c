#include "freeze_guard.h"
#include "config.h"
#include "hardware/watchdog.h"

#define GUARD_MAGIC 0x53475038u
static bool active;

bool freeze_guard_boot_report(freeze_report_t *report) {
    bool valid = watchdog_enable_caused_reboot() && watchdog_hw->scratch[0] == GUARD_MAGIC;
    if (valid && report) {
        report->stage = watchdog_hw->scratch[1];
        report->pc = watchdog_hw->scratch[2];
        report->clock_khz = watchdog_hw->scratch[3];
    }
    watchdog_disable();
    watchdog_hw->scratch[0] = 0;
    active = false;
    return valid;
}
const char *freeze_stage_name(unsigned stage) {
    switch (stage) {
        case FREEZE_INPUT: return "INPUT";
        case FREEZE_CLOCK: return "CLOCK";
        case FREEZE_VIDEO_START: return "VIDEO START";
        case FREEZE_FRAME: return "EMULATOR FRAME";
        case FREEZE_VIDEO_WAIT: return "VIDEO WAIT";
        case FREEZE_VIDEO_STOP: return "VIDEO STOP";
        case FREEZE_SD_SAVE: return "SD SAVE";
        default: return "UNKNOWN";
    }
}
void freeze_guard_start(void) {
    watchdog_hw->scratch[0] = GUARD_MAGIC;
    watchdog_hw->scratch[1] = FREEZE_CLOCK;
    watchdog_hw->scratch[2] = 0;
    watchdog_hw->scratch[3] = GAME_CLOCK_KHZ;
    watchdog_enable(8000, true);
    active = true;
}
void freeze_guard_mark(freeze_stage_t stage, uint16_t pc) {
    if (!active) return;
    watchdog_hw->scratch[1] = stage;
    watchdog_hw->scratch[2] = pc;
}
void freeze_guard_feed(bool video_healthy) {
    if (active && video_healthy) watchdog_update();
}
void freeze_guard_stop(void) {
    watchdog_disable();
    active = false;
    watchdog_hw->scratch[0] = 0;
}
bool freeze_guard_pause(void) {
    bool was_active = active;
    watchdog_disable();
    active = false;
    return was_active;
}
void freeze_guard_resume(bool was_active) {
    if (!was_active) return;
    watchdog_enable(8000, true);
    active = true;
}
