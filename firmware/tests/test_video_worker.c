/* Run the production two-buffer protocol on real concurrent host threads. */
#define _POSIX_C_SOURCE 200809L
#include "video_worker.h"
#include "pico/stdlib.h"
#include <assert.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <stdlib.h>

static unsigned alloc_count, fail_allocation;
static void *test_video_alloc(size_t size) {
    return ++alloc_count == fail_allocation ? NULL : malloc(size);
}
#define VIDEO_ALLOC test_video_alloc
#include "../src/video_worker.c"

static uint16_t default_buffer[GB_WIDTH * GB_HEIGHT];
static uint16_t *draw_buffer = default_buffer;
static pthread_t worker_thread;
static void (*worker_entry)(void);
static atomic_bool reset_requested, transfer_entered, allow_transfer;
static atomic_uint transfers;
static atomic_uint_fast64_t time_offset;
static display_scale_t expected_scale;

uint64_t time_us_64(void) {
    struct timespec ts;
    assert(clock_gettime(CLOCK_MONOTONIC, &ts) == 0);
    return (uint64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000 + atomic_load(&time_offset);
}
void sleep_us(uint64_t us) {
    struct timespec ts = {.tv_sec = us / 1000000, .tv_nsec = (us % 1000000) * 1000};
    nanosleep(&ts, NULL);
}
void __wfe(void) {
    if (atomic_load(&reset_requested)) pthread_exit(NULL);
    sched_yield();
}
void __sev(void) {}
static void *thread_main(void *arg) { (void)arg; worker_entry(); return NULL; }
void multicore_launch_core1(void (*entry)(void)) {
    atomic_store(&reset_requested, false);
    worker_entry = entry;
    assert(pthread_create(&worker_thread, NULL, thread_main, NULL) == 0);
}
void multicore_reset_core1(void) {
    atomic_store(&reset_requested, true);
    assert(pthread_join(worker_thread, NULL) == 0);
}
uint16_t *display_default_framebuffer(void) { return default_buffer; }
void display_set_draw_buffer(uint16_t *p) { draw_buffer = p ? p : default_buffer; }
const char *display_scale_name(display_scale_t scale) { (void)scale; return "TEST"; }
void display_draw_text(uint16_t x, uint16_t y, const char *s, uint16_t fg, uint16_t bg, uint8_t scale) {
    (void)x; (void)y; (void)s; (void)fg; (void)bg; (void)scale;
}
void display_draw_fps(unsigned lcd, unsigned emulated, display_scale_t scale) {
    (void)lcd; (void)emulated; assert(scale == expected_scale);
}
void display_present_frame(const uint16_t *pixels, display_scale_t scale) {
    assert(scale == expected_scale);
    uint16_t value = pixels[0];
    atomic_store(&transfer_entered, true);
    while (!atomic_load(&allow_transfer)) sched_yield();
    for (unsigned i = 0; i < GB_WIDTH * GB_HEIGHT; ++i) assert(pixels[i] == value);
    atomic_fetch_add(&transfers, 1);
}
unsigned display_present_changed(const uint16_t *pixels, uint16_t *previous, display_scale_t scale) {
    assert(previous && previous != pixels);
    if (!memcmp(pixels, previous, GB_WIDTH * GB_HEIGHT * sizeof *pixels)) return 0;
    assert(previous[0] + 1 == pixels[0]);
    display_present_frame(pixels, scale);
    memcpy(previous, pixels, GB_WIDTH * GB_HEIGHT * sizeof *pixels);
    return GB_WIDTH * GB_HEIGHT;
}
static void fill(uint16_t value) {
    for (unsigned i = 0; i < GB_WIDTH * GB_HEIGHT; ++i) draw_buffer[i] = value;
}
int main(void) {
    assert(!video_ready() && !video_submit(60));
    video_stop();
    for (unsigned round = 0; round < 24; ++round) {
        expected_scale = DISPLAY_FAST + round % 4;
        atomic_store(&transfers, 0);
        assert(video_start(expected_scale));
        assert(video_ready() && video_frames_completed() == 0);
        uint16_t *first = draw_buffer;
        for (unsigned n = 0; n < 10; ++n) {
            atomic_store(&allow_transfer, false);
            atomic_store(&transfer_entered, false);
            fill((uint16_t)(n + 1));
            assert(video_submit(60));
            while (!atomic_load(&transfer_entered)) sched_yield();
            assert(!video_ready() && !video_submit(60));
            assert(video_healthy());
            atomic_store(&time_offset, 2100000);
            assert(!video_healthy());
            atomic_store(&time_offset, 0);
            /* Mutating the other buffer must not corrupt the in-flight frame. */
            fill(0xdead);
            atomic_store(&allow_transfer, true);
            video_wait_idle();
            assert(video_ready() && video_frames_completed() == n + 1);
        }
        assert(draw_buffer == first && atomic_load(&transfers) == 10);
        fill(10); /* unchanged frame must not inflate the LCD FPS counter */
        assert(video_submit(60));
        video_wait_idle();
        assert(video_frames_completed() == 10 && atomic_load(&transfers) == 10);
        video_stop();
        assert(draw_buffer == default_buffer && !video_ready());
    }
    fail_allocation = 1; alloc_count = 0;
    assert(!video_start(DISPLAY_FIT_HEIGHT) && !video_ready());
    fail_allocation = 2; alloc_count = 0;
    expected_scale = DISPLAY_FIT_HEIGHT;
    assert(video_start(expected_scale)); /* no diff cache: full redraw fallback */
    assert(last_presented == NULL);
    atomic_store(&allow_transfer, true);
    fill(123);
    assert(video_submit(60));
    video_wait_idle();
    fill(456);
    assert(video_submit(60));
    video_wait_idle();
    video_stop();
    puts("PASS: concurrent ownership, stuck-video health detection, 242 transfers, restart/cleanup, allocation failure and full-redraw fallback");
}
