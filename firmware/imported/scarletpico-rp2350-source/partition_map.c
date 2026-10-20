#include "ff.h"
_Static_assert(FF_MULTI_PARTITION==1,"Explicit partition mapping required");
/* Preserve the fix for this console's card: stale FAT16 metadata at LBA 0
 * must not hide the actual FAT partition in the MBR. No fixed starting LBA. */
PARTITION VolToPart[FF_VOLUMES]={{0,1}};
