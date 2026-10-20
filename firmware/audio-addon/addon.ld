/* Original heap/BSS boundary is extended by the verified patcher. */
MEMORY {
    FLASH (rx) : ORIGIN = 0x1002e800, LENGTH = 0x51800
    RAM (rw) : ORIGIN = 0x2001e264, LENGTH = 0x1800
}
SECTIONS {
    .text : { *(.text*) *(.rodata*) } > FLASH
    .data : { *(.data*) } > RAM
    .bss (NOLOAD) : {
        __addon_bss_start = .;
        *(.bss*) *(COMMON)
        . = ALIGN(8);
        __addon_bss_end = .;
    } > RAM
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
ASSERT(SIZEOF(.data) == 0, "Addon must not have initialized RAM data")
ASSERT(__addon_bss_end <= 0x2001fa64, "Audio RAM budget exceeded")
