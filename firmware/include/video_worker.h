#pragma once
#include "display_st7796.h"

/* Core 0 produces frames; core 1 owns LCD/SPI only while a job is pending.
 * Caller must wait_idle before every SD access or GUI draw, and stop before
 * clock changes or flash erase/program. stop parks/resets core 1 safely.
 * After submit, the new draw buffer is free even while the transfer is busy;
 * keep a prepared frame immutable until the next successful submit. */
bool video_start(display_scale_t scale);
bool video_ready(void);
/* Core 0 only; lack of completion for two seconds is unhealthy. */
bool video_healthy(void);
bool video_submit(unsigned emulated_fps);
void video_wait_idle(void);
void video_stop(void);
unsigned video_frames_completed(void);
unsigned video_last_transfer_us(void);
