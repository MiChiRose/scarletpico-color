/* Loading-only extension to the SHA-pinned UI v1 image.
 * The original flash writer still consumes 256-byte pages in exactly the
 * same order. Only its sequential data-read call site uses read-ahead.
 * No emulator, renderer, sound, interrupt or frequency changes. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* FatFs FRESULT uses -fshort-enums in the base; expose the exact uint8 ABI.
 * FIL remains opaque: no reliance on private FatFs field offsets. */
typedef uint8_t result_t;
enum { OK=0, INTERNAL_ERROR=2, READ_AHEAD=4096, PAGE_SIZE=256 };
extern result_t original_f_read(void *, void *, unsigned, unsigned *);
extern bool original_ui_prepare(const char *, const uint8_t **, size_t *);
extern void *original_malloc(size_t);
extern void original_free(void *);
extern uint64_t time_us_64(void);
extern void original_ui_spinner_tick(uint32_t);
extern void original_sd_bus(void);
extern bool original_ui_loading;
extern uint32_t original_spinner_time;

static struct {
    uint8_t *bytes;
    unsigned next, valid;
    bool active, allocation_attempted;
} cache;

static void progress(void) {
    uint32_t now=(uint32_t)time_us_64();
    /* Only the launcher calls this, with the game/video worker stopped.
     * Use the identical eligibility test as the untouched UI v1 spinner.
     * If it did not draw, the SPI bus is still configured for the card. */
    if (original_ui_loading && (uint32_t)(now-original_spinner_time)>=100000u) {
        original_ui_spinner_tick(now);
        original_sd_bus();
    }
}

result_t loader_header_read(void *file, void *dst, unsigned n, unsigned *got) {
    /* Header reads are not read ahead: the original loader seeks after them. */
    cache.next=cache.valid=0;
    result_t result=original_f_read(file,dst,n,got);
    progress();
    return result;
}

result_t loader_page_read(void *file, void *dst, unsigned n, unsigned *got) {
    *got=0;
    /* This hook is ONLY at the pinned loader's <=256-byte sequential call.
     * It is not a general-purpose replacement for f_read or save-file I/O. */
    if (n>PAGE_SIZE) return INTERNAL_ERROR;
    if (!n) return OK;
    if (cache.active && !cache.allocation_attempted) {
        cache.allocation_attempted=true;
        cache.bytes=original_malloc(READ_AHEAD);
    }
    if (!cache.active || !cache.bytes) {
        result_t result=original_f_read(file,dst,n,got);
        progress();
        return result;
    }
    if (cache.next==cache.valid) {
        cache.next=cache.valid=0;
        unsigned read=0;
        result_t result=original_f_read(file,cache.bytes,READ_AHEAD,&read);
        if (result!=OK || read>READ_AHEAD) {
            progress();
            return result!=OK ? result : INTERNAL_ERROR;
        }
        cache.valid=read;
    }
    unsigned available=cache.valid-cache.next;
    if (n>available) n=available;
    uint8_t *out=dst;
    for (unsigned i=0;i<n;i++) out[i]=cache.bytes[cache.next+i];
    cache.next+=n;
    *got=n;
    /* Short read/EOF is reported, never padded into a successful ROM.
     * The original writer rejects it and does not commit a cache marker. */
    progress();
    return OK;
}

bool loader_prepare(const char *path, const uint8_t **rom, size_t *size) {
    /* No recursive loads are allowed; this runs in the stopped-core menu. */
    if (cache.active) return false;
    cache.bytes=NULL;
    cache.next=cache.valid=0;
    cache.allocation_attempted=false;
    cache.active=true;
    bool ok=original_ui_prepare(path,rom,size);
    if (cache.bytes) original_free(cache.bytes);
    cache.bytes=NULL;
    cache.next=cache.valid=0;
    cache.allocation_attempted=false;
    cache.active=false;
    return ok;
}
