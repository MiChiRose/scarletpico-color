.syntax unified
.cpu cortex-m0plus
.thumb
.section .text.features_input_bridge,"ax",%progbits
.global features_input_bridge
.type features_input_bridge,%function
.thumb_func
features_input_bridge:
    /* Replaces STR r4,[sp,#88]; BL time_us_64 in the ORIGINAL main loop.
       The original loop's callee-saved locals remain in r5/r6/r7. */
    push {r2,r3,r5,r6,r7,lr}
    mov r0,r4
    bl features_buttons
    mov r4,r0
    lsrs r0,r0,#8
    bne 1f
    str r4,[sp,#112]
    bl time_us_64
    pop {r2,r3,r5,r6,r7,pc}
1:
    pop {r2,r3,r5,r6,r7}
    pop {r0}
    ldr r3,=0x10008297
    bx r3
.size features_input_bridge,.-features_input_bridge
