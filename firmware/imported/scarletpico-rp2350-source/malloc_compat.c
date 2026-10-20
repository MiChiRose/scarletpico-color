// The locally installed Arduino ARM toolchain builds newlib with retargetable
// malloc locks. Standard ARM toolchains do not need these hooks. Pico SDK
// initialises the mutex before main through its normal auto-init mechanism.
#include <newlib.h>
#if defined(_RETARGETABLE_LOCKING)
#include "pico/mutex.h"
auto_init_recursive_mutex(newlib_malloc_mutex);
extern recursive_mutex_t __lock___malloc_recursive_mutex
  __attribute__((alias("newlib_malloc_mutex")));
void __retarget_lock_acquire_recursive(void *lock) {
  recursive_mutex_enter_blocking((recursive_mutex_t *)lock);
}
void __retarget_lock_release_recursive(void *lock) {
  recursive_mutex_exit((recursive_mutex_t *)lock);
}
#endif
