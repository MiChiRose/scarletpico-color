.syntax unified
.cpu cortex-m0plus
.thumb

/* Private ABI at the verified main call site, not a general C function.
 * Original main SP+48 holds next_frame's low word. R7 is frame_waiting.
 * All other callee-saved registers and the stack remain intact. */
.section .text.video_pace_entry,"ax",%progbits
.global video_pace_entry
.thumb_func
video_pace_entry:
    ldr r2, [sp, #48]
    push {r4, lr}
    bl video_pace_frame
    lsrs r7, r0, #1
    movs r1, #1
    ands r0, r1
    pop {r4, pc}

/* Original compiler assumed success always implied frame_waiting. The new
 * no-pixel case invalidates that optimization; restore the missing test. */
.section .text.video_pace_ready,"ax",%progbits
.global video_pace_ready
.thumb_func
video_pace_ready:
    cmp r7, #0
    beq 1f
    ldr r3, =original_video_ready
    bx r3
1:  movs r0, #0
    bx lr
.ltorg
