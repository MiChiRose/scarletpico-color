/**
 * minigb_apu is released under the terms listed within the LICENSE file.
 *
 * minigb_apu emulates the audio processing unit (APU) of the Game Boy. This
 * project is based on MiniGBS by Alex Baines: https://github.com/baines/MiniGBS
 */

#pragma once

#include <stdint.h>

#ifndef AUDIO_SAMPLE_RATE
#define AUDIO_SAMPLE_RATE 16000
#endif

#define DMG_CLOCK_FREQ		4194304.0
#define SCREEN_REFRESH_CYCLES	70224.0
#define VERTICAL_SYNC		(DMG_CLOCK_FREQ/SCREEN_REFRESH_CYCLES)

#define AUDIO_SAMPLES		((unsigned)(AUDIO_SAMPLE_RATE / VERTICAL_SYNC))

/**
 * Fill exactly len bytes with signed 16-bit interleaved stereo PCM.
 * len must be a multiple of four; no fixed video-frame buffer size is assumed.
 */
void audio_callback(void *ptr, uint8_t *data, int len);

/**
 * Read audio register at given address "addr".
 */
uint8_t audio_read(const uint16_t addr);

/**
 * Write "val" to audio register at given address "addr".
 */
void audio_write(const uint16_t addr, const uint8_t val);

/**
 * Initialise audio driver.
 */
void audio_init(void);
