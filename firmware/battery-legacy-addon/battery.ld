MEMORY {
 FLASH (rx) : ORIGIN = 0x10038400, LENGTH = 0x46c00
 RAM (rw) : ORIGIN = 0x2001f998, LENGTH = 0xcc
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > FLASH
 .data : { *(.data*) } > RAM
 .bss (NOLOAD) : {
  __battery_bss_start = .;
  *(.bss*) *(COMMON)
  . = ALIGN(8);
  __battery_bss_end = .;
 } > RAM
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
time_us_64 = 0x10009e3d;
old_rect = 0x100013e1;
old_text = 0x10000a55;
old_menu_input = 0x100313ed;
old_pace_frame = 0x10036501;
old_hud = 0x10032f39;
__aeabi_uidiv = 0x1000aab1;
__aeabi_uidivmod = 0x1000aab1;
memcpy = 0x1000b955;
ASSERT(SIZEOF(.data)==0,"No uninitialised load image for RAM")
ASSERT(__battery_bss_end<=0x2001fa64,"Pinned permanent RAM budget exceeded")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"Settings sector overlap")
