#include "freeze_guard.h"
#include "config.h"
#include "hardware/watchdog.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
watchdog_hw_t test_watchdog;
static bool enabled, rebooted;
static unsigned feeds;
void watchdog_enable(uint32_t ms, bool debug) { assert(ms == 8000 && debug); enabled = true; }
void watchdog_disable(void) { enabled = false; }
void watchdog_update(void) { assert(enabled); ++feeds; }
bool watchdog_enable_caused_reboot(void) { return rebooted; }
int main(void) {
    freeze_report_t report;
    assert(!freeze_guard_boot_report(&report));
    freeze_guard_start();
    assert(enabled);
    freeze_guard_mark(FREEZE_FRAME, 0x1234);
    freeze_guard_feed(true);
    freeze_guard_feed(false);
    assert(feeds == 1);
    rebooted = true;
    assert(freeze_guard_boot_report(&report));
    assert(report.stage == FREEZE_FRAME && report.pc == 0x1234 && report.clock_khz == GAME_CLOCK_KHZ);
    assert(!enabled && !freeze_guard_boot_report(&report));
    freeze_guard_start();
    freeze_guard_mark(FREEZE_SD_SAVE, 0x4567);
    bool was_active = freeze_guard_pause();
    assert(was_active && !enabled);
    freeze_guard_feed(true);
    assert(feeds == 1);
    freeze_guard_resume(was_active);
    assert(enabled);
    freeze_guard_feed(true);
    assert(feeds == 2);
    freeze_guard_stop();
    assert(!enabled && !freeze_guard_boot_report(&report));
    freeze_guard_start();
    rebooted = false; /* manual restart is not reported as a freeze */
    assert(!freeze_guard_boot_report(&report));
    assert(!strcmp(freeze_stage_name(FREEZE_VIDEO_WAIT), "VIDEO WAIT"));
    puts("PASS: watchdog breadcrumbs, one-shot boot report, healthy-only feeding, pause for SD writes, manual-reset exclusion");
}
