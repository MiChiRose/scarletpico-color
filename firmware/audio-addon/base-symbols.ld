/* Recovered from the SHA-256-pinned v0.9-B image. Each SDK entry was uniquely
 * matched to our SDK 2.3.1 ELF; hooks/ABI additionally tested in Unicorn.
 * These addresses are INVALID for any other base image. */
original_emulator_frame = 0x10007071;
original_video_stop = 0x10008ce5;
__aeabi_idiv = 0x1000aa61;
__aeabi_uidiv = 0x1000aab1;
clock_get_hz = 0x1000a08d;
dma_claim_unused_channel = 0x1001b389;
gpio_init = 0x10008ed1;
gpio_set_function = 0x10008e31;
irq_add_shared_handler = 0x100091bd;
irq_set_enabled = 0x100090f5;
memset = 0x1000b949;
pio_add_program = 0x1001b48d;
pio_claim_unused_sm = 0x1001b451;
pio_sm_init = 0x1001b5f1;
pio_sm_set_consecutive_pindirs = 0x1001b53d;
