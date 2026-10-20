#include "video_worker.h"
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pico/multicore.h"
#include "pico/stdlib.h"

#ifndef VIDEO_ALLOC
#define VIDEO_ALLOC malloc
#endif

static uint16_t *buffers[2];
/* Owned by core 1 only after launch; separate from both producer buffers. */
static uint16_t *last_presented;
static unsigned write_index;
static uint64_t submitted_at;
static bool running;
static display_scale_t selected_scale;
static atomic_bool pending, stop_requested, parked;
static atomic_uint completed, last_transfer_us;
/* Published by pending's release-store, immutable until the worker releases it. */
static struct { const uint16_t *pixels; unsigned emulated_fps; } job;

static void worker(void) {
    uint64_t stats_start = time_us_64();
    unsigned stats_frames = 0;
    bool previous_valid = false;
    while (!atomic_load_explicit(&stop_requested, memory_order_acquire)) {
        if (!atomic_load_explicit(&pending, memory_order_acquire)) {
            __wfe();
            continue;
        }
        uint64_t start = time_us_64();
        bool transmitted = true;
        if (previous_valid && last_presented) {
            transmitted = display_present_changed(job.pixels, last_presented, selected_scale) != 0;
        } else {
            display_present_frame(job.pixels, selected_scale);
            if (last_presented)
                memcpy(last_presented, job.pixels, GB_WIDTH * GB_HEIGHT * sizeof(uint16_t));
            previous_valid = true;
        }
        unsigned elapsed = (unsigned)(time_us_64() - start);
        atomic_store_explicit(&last_transfer_us, elapsed, memory_order_relaxed);
        if (transmitted) {
            atomic_fetch_add_explicit(&completed, 1u, memory_order_relaxed);
            ++stats_frames;
        }
        uint64_t now = time_us_64();
        if (now - stats_start >= 1000000u) {
            unsigned fps = (unsigned)((uint64_t)stats_frames * 1000000u / (now - stats_start));
            display_draw_fps(fps, job.emulated_fps, selected_scale);
            stats_start = now;
            stats_frames = 0;
        }
        atomic_store_explicit(&pending, false, memory_order_release);
        __sev();
    }
    atomic_store_explicit(&parked, true, memory_order_release);
    __sev();
    /* No SDK locks or flash work after acknowledging park. */
    while (true) __wfe();
}

bool video_start(display_scale_t scale) {
    video_stop();
    buffers[0] = display_default_framebuffer();
    buffers[1] = VIDEO_ALLOC(GB_WIDTH * GB_HEIGHT * sizeof(uint16_t));
    if (!buffers[1]) return false;
    /* Optional optimization: memory-heavy games can still use full redraws. */
    last_presented = VIDEO_ALLOC(GB_WIDTH * GB_HEIGHT * sizeof(uint16_t));
    memset(buffers[0], 0, GB_WIDTH * GB_HEIGHT * sizeof(uint16_t));
    memset(buffers[1], 0, GB_WIDTH * GB_HEIGHT * sizeof(uint16_t));
    write_index = 0;
    display_set_draw_buffer(buffers[0]);
    selected_scale = scale;
    atomic_store(&pending, false);
    atomic_store(&stop_requested, false);
    atomic_store(&parked, false);
    atomic_store(&completed, 0);
    atomic_store(&last_transfer_us, 0);
    running = true;
    multicore_launch_core1(worker);
    return true;
}

bool video_ready(void) {
    return running && !atomic_load_explicit(&pending, memory_order_acquire);
}
bool video_healthy(void) {
    return !running || !atomic_load_explicit(&pending, memory_order_acquire) ||
           time_us_64() - submitted_at < 2000000u;
}
bool video_submit(unsigned emulated_fps) {
    if (!video_ready()) return false;
    job.pixels = buffers[write_index];
    job.emulated_fps = emulated_fps;
    write_index ^= 1u;
    display_set_draw_buffer(buffers[write_index]);
    submitted_at = time_us_64();
    atomic_store_explicit(&pending, true, memory_order_release);
    __sev();
    return true;
}
void video_wait_idle(void) {
    while (running && atomic_load_explicit(&pending, memory_order_acquire)) sleep_us(50);
}
void video_stop(void) {
    if (!running) return;
    video_wait_idle();
    atomic_store_explicit(&stop_requested, true, memory_order_release);
    __sev();
    while (!atomic_load_explicit(&parked, memory_order_acquire)) sleep_us(50);
    multicore_reset_core1();
    display_set_draw_buffer(NULL);
    free(buffers[1]);
    free(last_presented);
    buffers[1] = NULL;
    last_presented = NULL;
    running = false;
}
unsigned video_frames_completed(void) { return atomic_load_explicit(&completed, memory_order_relaxed); }
unsigned video_last_transfer_us(void) { return atomic_load_explicit(&last_transfer_us, memory_order_relaxed); }
