/* Sound-only hooks for SHA-pinned v0.9-B. Original emulation/video/menu code
 * remains in place; these wrappers call its original entry points. */
#include "audio_output.h"
#include "minigb_apu.h"

static bool initialized;
static uint32_t sample_remainder;
static int16_t pcm[536]; /* ceil(16000 * 70224 / 4194304) stereo frames */

extern bool original_emulator_frame(uint8_t keys, bool render);
extern void original_video_stop(void);

bool addon_frame(uint8_t keys, bool render) {
    if (!initialized) {
        audio_init();
        sample_remainder = 0;
        audio_output_start();
        initialized = true;
    }
    bool ok = original_emulator_frame(keys, render);
    if (ok) {
        /* Fractional accounting: 267/268 samples, not a rounded fixed count.
         * Audio runs for every emulated frame, including skipped LCD frames. */
        sample_remainder += 16000u * 70224u;
        unsigned frames = sample_remainder >> 22;
        sample_remainder &= 4194303u;
        audio_callback(0, (uint8_t *)pcm, frames * 4u);
        audio_output_submit(pcm, frames);
    } else {
        audio_output_stop();
        initialized = false;
    }
    return ok;
}

void addon_stop(void) {
    audio_output_stop();
    initialized = false;
    original_video_stop();
}
