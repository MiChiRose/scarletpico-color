MEMORY {
 FLASH (rx) : ORIGIN = 0x1002ff00, LENGTH = 0x4f100
 RAM (rw) : ORIGIN = 0x2001f3f8, LENGTH = 0x66c
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > FLASH
 .data : { *(.data*) } > RAM
 .bss (NOLOAD) : {
  __ui_bss_start = .;
  *(.bss*) *(COMMON)
  . = ALIGN(8);
  __ui_bss_end = .;
 } > RAM
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
ASSERT(SIZEOF(.data)==0,"UI must have no initialized RAM data")
ASSERT(__ui_bss_end<=0x2001fa64,"UI RAM budget exceeded")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"UI overlaps settings sector")
