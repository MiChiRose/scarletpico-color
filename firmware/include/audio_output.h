#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define SCARLET_AUDIO_RATE 16000u
/* Called on core 0, with the final game clock already selected. */
bool audio_output_start(void);
/* Stop before clock changes, flash programming, or returning to the menu. */
void audio_output_stop(void);
void audio_output_submit(const int16_t *stereo, size_t frames);
unsigned audio_output_underruns(void);
unsigned audio_output_dropped(void);
/* Fixed at the requested 50%; no new menu or button combinations. */
unsigned audio_output_volume(void);
