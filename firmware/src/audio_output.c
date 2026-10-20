#include "audio_output.h"
#include "audio_queue.h"
#include "config.h"
#include "audio_i2s.pio.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/irq.h"
#include "hardware/pio.h"
#include "hardware/sync.h"
#include <string.h>

_Static_assert(PIN_AUDIO_LRCLK == PIN_AUDIO_BCLK + 1, "I2S clocks must be adjacent");
#define BLOCK_FRAMES 128u
static audio_queue_t queue;
static uint32_t blocks[2][BLOCK_FRAMES];
static PIO const audio_pio = pio0;
static int sm, channels[2];
static unsigned offset;
#define volume 50u
static bool allocated, active, playing, allocation_failed;
static volatile unsigned underruns;
static unsigned dropped;

static void fill_block(unsigned i) {
    size_t n = audio_queue_pop(&queue, blocks[i], BLOCK_FRAMES);
    if (n != BLOCK_FRAMES) {
        memset(blocks[i] + n, 0, (BLOCK_FRAMES - n) * sizeof(uint32_t));
        ++underruns; /* Silence, NEVER replay an old sound buffer. */
    }
}
static void audio_dma_irq(void) {
    for (unsigned i = 0; i < 2; ++i) {
        if (!dma_channel_get_irq1_status(channels[i])) continue;
        dma_channel_acknowledge_irq1(channels[i]);
        if (!active) continue;
        /* The other DMA is already running: update only the completed half. */
        fill_block(i);
        dma_channel_set_read_addr(channels[i], blocks[i], false);
        dma_channel_set_trans_count(channels[i], BLOCK_FRAMES, false);
    }
}
bool audio_output_start(void) {
    audio_output_stop();
    if (allocation_failed) return false;
    if (!allocated) {
        sm = pio_claim_unused_sm(audio_pio, false);
        if (sm < 0) { allocation_failed = true; return false; }
        channels[0] = dma_claim_unused_channel(false);
        channels[1] = dma_claim_unused_channel(false);
        if (channels[0] < 0 || channels[1] < 0) {
            /* This exact firmware uses two SPI DMA channels and no PIO SM.
             * Do not retry partial allocation indefinitely if that changes. */
            allocation_failed = true;
            return false;
        }
        offset = pio_add_program(audio_pio, &scarlet_i2s_program);
        if ((int)offset < 0) { allocation_failed = true; return false; }
        irq_add_shared_handler(DMA_IRQ_1, audio_dma_irq, PICO_SHARED_IRQ_HANDLER_DEFAULT_ORDER_PRIORITY);
        allocated = true;
    }
    audio_queue_reset(&queue);
    underruns = dropped = 0;
    for (unsigned pin = PIN_AUDIO_BCLK; pin <= PIN_AUDIO_DIN; ++pin)
        pio_gpio_init(audio_pio, pin);
    pio_sm_set_consecutive_pindirs(audio_pio, sm, PIN_AUDIO_BCLK, 3, true);
    pio_sm_config cfg = scarlet_i2s_program_get_default_config(offset);
    sm_config_set_out_pins(&cfg, PIN_AUDIO_DIN, 1);
    sm_config_set_sideset_pins(&cfg, PIN_AUDIO_BCLK);
    sm_config_set_out_shift(&cfg, false, true, 32);
    sm_config_set_fifo_join(&cfg, PIO_FIFO_JOIN_TX);
    /* Only the PIO divider changes. Never alter CPU/SPI/system clocks. */
    uint32_t div256 = clock_get_hz(clk_sys) / (SCARLET_AUDIO_RATE / 4u);
    sm_config_set_clkdiv_int_frac8(&cfg, div256 >> 8, div256 & 255u);
    pio_sm_init(audio_pio, sm, offset, &cfg);
    pio_sm_exec(audio_pio, sm, pio_encode_set(pio_x, 14));
    for (unsigned i = 0; i < 2; ++i) {
        dma_channel_config dc = dma_channel_get_default_config(channels[i]);
        channel_config_set_transfer_data_size(&dc, DMA_SIZE_32);
        channel_config_set_read_increment(&dc, true);
        channel_config_set_write_increment(&dc, false);
        channel_config_set_dreq(&dc, pio_get_dreq(audio_pio, sm, true));
        channel_config_set_chain_to(&dc, channels[1-i]);
        dma_channel_configure(channels[i], &dc, &audio_pio->txf[sm], blocks[i], BLOCK_FRAMES, false);
        dma_channel_acknowledge_irq1(channels[i]);
        dma_channel_set_irq1_enabled(channels[i], true);
    }
    active = true;
    irq_set_enabled(DMA_IRQ_1, true);
    return true; /* Start clocks only after two buffers of real PCM exist. */
}
void audio_output_submit(const int16_t *stereo, size_t frames) {
    if (!active) return;
    dropped += frames - audio_queue_push(&queue, stereo, frames, volume);
    if (!playing && audio_queue_count(&queue) >= 2u * BLOCK_FRAMES) {
        fill_block(0);
        fill_block(1);
        playing = true;
        dma_start_channel_mask(1u << channels[0]);
        pio_sm_set_enabled(audio_pio, sm, true);
    }
}
void audio_output_stop(void) {
    if (!allocated) return;
    uint32_t irq_state = save_and_disable_interrupts();
    active = playing = false;
    pio_sm_set_enabled(audio_pio, sm, false);
    /* Disable BOTH chains before aborting: neither can restart its peer.
     * Disable IRQs before abort (RP2040 DMA erratum E13). */
    for (unsigned i = 0; i < 2; ++i) {
        dma_channel_set_irq1_enabled(channels[i], false);
        hw_clear_bits(&dma_hw->ch[channels[i]].ctrl_trig, DMA_CH0_CTRL_TRIG_EN_BITS);
    }
    for (unsigned i = 0; i < 2; ++i) {
        dma_channel_abort(channels[i]);
        dma_channel_acknowledge_irq1(channels[i]);
    }
    pio_sm_clear_fifos(audio_pio, sm);
    audio_queue_reset(&queue);
    restore_interrupts(irq_state);
    /* Missing I2S clocks shuts down MAX98357A; DIN is held low. */
    for (unsigned pin = PIN_AUDIO_BCLK; pin <= PIN_AUDIO_DIN; ++pin) {
        gpio_init(pin); gpio_put(pin, 0); gpio_set_dir(pin, GPIO_OUT);
    }
}
unsigned audio_output_underruns(void) { return underruns; }
unsigned audio_output_dropped(void) { return dropped; }
unsigned audio_output_volume(void) { return volume; }
