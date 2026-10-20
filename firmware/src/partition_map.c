#include "ff.h"

_Static_assert(FF_MULTI_PARTITION == 1, "Explicit MBR partition mapping is required");

/* The console uses volume 0: = first MBR partition of its only SD card.
 * Auto-detection can mistake stale FAT metadata in the MBR boot-code area for
 * a whole-disk filesystem. Do not hard-code the partition's starting LBA. */
PARTITION VolToPart[FF_VOLUMES] = {
    {0, 1}, {0, 2}, {0, 3}, {0, 4},
};
