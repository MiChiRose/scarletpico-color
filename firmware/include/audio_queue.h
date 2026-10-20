#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdatomic.h>

/* Core-0 foreground producer / core-0 IRQ consumer. Neither waits for the
 * other; publication follows the samples, reclamation follows the reads.
 * 32 ms capacity at 16 kHz. Unsigned counters intentionally wrap. */
#define AUDIO_QUEUE_CAPACITY 512u
typedef struct {
    uint32_t data[AUDIO_QUEUE_CAPACITY];
    volatile uint32_t write, read;
} audio_queue_t;
static inline void audio_queue_reset(audio_queue_t *q) { q->write = q->read = 0; }
static inline unsigned audio_queue_count(const audio_queue_t *q) {
    return q->write - q->read;
}
static inline size_t audio_queue_push(audio_queue_t *q, const int16_t *pcm,
                                      size_t frames, unsigned volume) {
    uint32_t write = q->write;
    unsigned room = AUDIO_QUEUE_CAPACITY - (write - q->read);
    if (frames > room) frames = room;
    if (volume > 100) volume = 100;
    for (size_t i = 0; i < frames; ++i) {
        /* One mono amplifier: mix BOTH GB channels and send identical I2S
         * slots, independent of the breakout's SD_MODE channel selection. */
        int32_t mono = ((int32_t)pcm[2*i] + pcm[2*i+1]) * (int32_t)volume / 200;
        uint32_t sample = (uint16_t)(int16_t)mono;
        q->data[(write + i) & (AUDIO_QUEUE_CAPACITY - 1u)] = (sample << 16) | sample;
    }
    atomic_signal_fence(memory_order_release);
    q->write = write + (uint32_t)frames;
    return frames;
}
static inline size_t audio_queue_pop(audio_queue_t *q, uint32_t *out, size_t frames) {
    uint32_t read = q->read;
    unsigned available = q->write - read;
    if (frames > available) frames = available;
    atomic_signal_fence(memory_order_acquire);
    for (size_t i = 0; i < frames; ++i)
        out[i] = q->data[(read + i) & (AUDIO_QUEUE_CAPACITY - 1u)];
    atomic_signal_fence(memory_order_release);
    q->read = read + (uint32_t)frames;
    return frames;
}
