/* Optional pixel work yields to the original emulation/audio cadence.
 * Pinned SHADOW image only. No game ticks, samples, clocks or pixels invented.
 * Core 0 owns all state; the existing core-1 worker remains unchanged. */
#include <stdbool.h>
#include <stdint.h>

extern bool original_features_frame(uint8_t, bool);
extern uint64_t time_us_64(void);
extern unsigned clock_get_hz(unsigned);
extern void sleep_us(uint64_t);
extern void original_audio_submit(const int16_t *, unsigned);
extern int previous_perf(const char *, const char *, unsigned, unsigned, unsigned, unsigned);
extern int original_printf(const char *, ...);

#define WORD(a) (*(volatile uint32_t *)(a))
#define BYTE(a) (*(volatile uint8_t *)(a))
enum { FRAME_US = 16743, DEBT_LIMIT_US = 8000, MAX_DEBT_US = 100000 };
static struct {
    unsigned draws, skips, busy, render_sum, render_count, skip_sum, skip_count, peak_lag;
    unsigned audio_wait_us, audio_timeouts;
    unsigned debt_us, since_draw, render_work_us;
} pace;

/* Return bit 0 = success, bit 1 = a prepared framebuffer is waiting.
 * A false offered argument means an EARLIER frame is still waiting: preserve
 * it. A frame deliberately not drawn here must NOT be submitted by main. */
unsigned video_pace_frame(uint8_t keys, bool offered, uint32_t due) {
    bool first = !BYTE(0x2001f2bc); /* original sound wrapper initialized */
    bool pausing = BYTE(0x2001f923); /* original pause_pending */
    if (first) {
        pace.draws = pace.skips = pace.busy = 0;
        pace.render_sum = pace.render_count = pace.skip_sum = pace.skip_count = pace.peak_lag = 0;
        pace.audio_wait_us = pace.audio_timeouts = 0;
        pace.debt_us = pace.since_draw = 0;
        pace.render_work_us = 0;
    }
    uint32_t start = (uint32_t)time_us_64();
    int32_t behind = (int32_t)(start - due); /* timer-low wrap is intentional */
    unsigned lag = behind > 0 ? (unsigned)behind : 0;
    bool draw = offered;
    if (offered && !first && !pausing) {
        /* Let a rendered frame borrow a small amount of time, then repay it
         * with cheaper no-pixel ticks. No fixed divisor or predicted-cost
         * gate that could permanently starve a costly scene of pictures. */
        unsigned queued = WORD(0x2001ee80) - WORD(0x2001ee84);
        /* The chained DMA has a following 128-sample block (8 ms). Keep
         * another 1 ms margin. This is a conservative estimate, not a
         * hardware timing guarantee; the counter in PERF verifies it. */
        unsigned needed = pace.render_work_us > 7000u ?
            ((pace.render_work_us - 7000u) * 16u + 999u) / 1000u : 0;
        bool audio_low = BYTE(0x2001e26e) && BYTE(0x2001e26d) && queued < needed;
        if ((pace.debt_us > DEBT_LIMIT_US || audio_low) && pace.since_draw < 12u) draw = false;
    }
    unsigned wait_before = pace.audio_wait_us;
    bool ok = original_features_frame(keys, draw);
    unsigned elapsed = (uint32_t)time_us_64() - start;
    /* The original pause code recreates both video buffers and forces a draw,
     * including when offered was false. Do not measure time spent in menus. */
    if (pausing) {
        draw = true;
        pace.debt_us = 0;
        pace.render_work_us = 0;
    } else if (ok && elapsed < 100000u) {
        /* Backpressure is useful pacing, not expensive emulation work.
         * Counting it as CPU overload can trap the screen in permanent skip
         * after startup/underrun has shifted the audio buffer's phase. */
        unsigned wait = pace.audio_wait_us - wait_before;
        unsigned work = elapsed > wait ? elapsed - wait : 0;
        unsigned debt = pace.debt_us + work;
        pace.debt_us = debt > FRAME_US ? debt - FRAME_US : 0;
        if (pace.debt_us > MAX_DEBT_US) pace.debt_us = MAX_DEBT_US;
        if (draw) {
            pace.render_work_us = pace.render_work_us ?
                (pace.render_work_us * 7u + work + 4u) / 8u : work;
            pace.render_sum += elapsed;
            ++pace.render_count;
        } else {
            pace.skip_sum += elapsed;
            ++pace.skip_count;
        }
        if (lag > pace.peak_lag) pace.peak_lag = lag;
    }
    if (!ok) return 0;
    if (draw) { ++pace.draws; pace.since_draw = 0; }
    else {
        if (offered) ++pace.skips; else ++pace.busy;
        if (pace.since_draw < 12u) ++pace.since_draw;
    }
    return 1u | ((draw || !offered) ? 2u : 0u);
}

/* A fast catch-up tick can arrive while the small audio queue is still full.
 * Preserve the existing PCM instead of immediately discarding its tail.
 * The original DMA IRQ runs throughout the wait; bounded to 24 ms even if
 * the device stops consuming. Initial prefill/inactive output never wait.
 * Hook ONLY the game wrapper, not the original driver or startup chime. */
void video_pace_audio_submit(const int16_t *pcm, unsigned frames) {
    if (frames <= 512u && BYTE(0x2001e26e) && BYTE(0x2001e26d)) {
        uint32_t start = (uint32_t)time_us_64();
        while (WORD(0x2001ee80) - WORD(0x2001ee84) > 512u - frames) {
            if ((uint32_t)time_us_64() - start >= 24000u) {
                ++pace.audio_timeouts;
                break;
            }
            sleep_us(50);
        }
        pace.audio_wait_us += (uint32_t)time_us_64() - start;
    }
    original_audio_submit(pcm, frames);
}

int video_pace_perf(const char *fmt, const char *scale, unsigned emu,
                    unsigned lcd, unsigned cpu, unsigned video) {
    int result = previous_perf(fmt, scale, emu, lcd, cpu, video);
    original_printf("PACE cpu=%u draw=%u skip=%u busy=%u draw_us=%u skip_us=%u "
                    "lag_us=%u queue=%u underrun=%u dropped=%u wait_us=%u timeout=%u debt_us=%u\n",
        clock_get_hz(5), pace.draws, pace.skips, pace.busy,
        pace.render_count ? pace.render_sum / pace.render_count : 0,
        pace.skip_count ? pace.skip_sum / pace.skip_count : 0, pace.peak_lag,
        WORD(0x2001ee80) - WORD(0x2001ee84),
        WORD(0x2001e268), WORD(0x2001e264), pace.audio_wait_us, pace.audio_timeouts, pace.debt_us);
    pace.draws = pace.skips = pace.busy = 0;
    pace.render_sum = pace.render_count = pace.skip_sum = pace.skip_count = pace.peak_lag = 0;
    pace.audio_wait_us = pace.audio_timeouts = 0;
    return result;
}
