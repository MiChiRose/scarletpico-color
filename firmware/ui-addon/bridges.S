.syntax unified
.cpu cortex-m0plus
.thumb
.section .text.ui_input_bridge,"ax",%progbits
.global ui_input_bridge
.type ui_input_bridge,%function
.thumb_func
ui_input_bridge:
    push {r0-r3,r6,lr}
    mov r0,r5
    bl ui_menu_input
    mov r5,r0
    pop {r0-r3,r6}
    movs r4,#2
    tst r4,r5
    pop {pc}
.size ui_input_bridge,.-ui_input_bridge

.section .text.ui_boot_bridge,"ax",%progbits
.global ui_boot_bridge
.type ui_boot_bridge,%function
.thumb_func
ui_boot_bridge:
    push {r0-r3,r6,lr}
    mov r0,r7
    bl ui_boot_display
    mov r7,r0
    pop {r0-r3,r6,pc}
.size ui_boot_bridge,.-ui_boot_bridge

.section .text.ui_volume_bridge,"ax",%progbits
.global ui_volume_bridge
.type ui_volume_bridge,%function
.thumb_func
ui_volume_bridge:
    ldr r3,=ui_volume
    ldrb r3,[r3]
    movs r4,r0
    bx lr
.size ui_volume_bridge,.-ui_volume_bridge
