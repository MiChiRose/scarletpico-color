MEMORY {
 FLASH (rx) : ORIGIN = 0x10032600, LENGTH = 0x4ca00
 RAM (rw) : ORIGIN = 0x2001f7e8, LENGTH = 0x27c
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > FLASH
 .data : { *(.data*) } > RAM
 .bss (NOLOAD) : {
  __features_bss_start = .;
  *(.bss*) *(COMMON)
  . = ALIGN(8);
  __features_bss_end = .;
 } > RAM
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
ASSERT(SIZEOF(.data)==0,"Addon must have no initialized data")
ASSERT(__features_bss_end<=0x2001fa64,"Permanent RAM budget exceeded")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"Addon overlaps settings")
