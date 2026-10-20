MEMORY {
 FLASH (rx) : ORIGIN = 0x10032400, LENGTH = 0x4cc00
 RAM (rw) : ORIGIN = 0x2001f7d8, LENGTH = 0x28c
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > FLASH
 .data : { *(.data*) } > RAM
 .bss (NOLOAD) : {
  __loader_bss_start = .;
  *(.bss*) *(COMMON)
  . = ALIGN(8);
  __loader_bss_end = .;
 } > RAM
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
ASSERT(SIZEOF(.data)==0,"Loader must have no initialized data")
ASSERT(__loader_bss_end<=0x2001fa64,"Loader permanent RAM budget exceeded")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"Loader overlaps settings sector")
