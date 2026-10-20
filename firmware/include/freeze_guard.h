#pragma once
#include <stdbool.h>
#include <stdint.h>
typedef enum {
    FREEZE_INPUT = 1, FREEZE_CLOCK, FREEZE_VIDEO_START, FREEZE_FRAME,
    FREEZE_VIDEO_WAIT, FREEZE_VIDEO_STOP, FREEZE_SD_SAVE
} freeze_stage_t;
typedef struct { unsigned stage, pc, clock_khz; } freeze_report_t;
bool freeze_guard_boot_report(freeze_report_t *report);
const char *freeze_stage_name(unsigned stage);
void freeze_guard_start(void);
void freeze_guard_mark(freeze_stage_t stage, uint16_t pc);
void freeze_guard_feed(bool video_healthy);
void freeze_guard_stop(void);
/* Never force a watchdog reset during a non-transactional SD save. */
bool freeze_guard_pause(void);
void freeze_guard_resume(bool was_active);
