MEMORY {
 FLASH (rx) : ORIGIN = 0x10038900, LENGTH = 0x46700
 RAM (rw) : ORIGIN = 0x2001f9b8, LENGTH = 0xac
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > FLASH
 .data : { *(.data*) } > RAM
 .bss (NOLOAD) : {
  __polish_bss_start = .;
  *(.bss*) *(COMMON)
  . = ALIGN(8);
  __polish_bss_end = .;
 } > RAM
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
ui_rect = 0x10031265;
ui_text = 0x100300c5;
ui_settings = 0x2001f7d5;
ui_game_count = 0x100311d9;
ui_game_selected = 0x100311e5;
ui_library_error = 0x100311f1;
ui_game_label = 0x100311fd;
ui_game_color = 0x10031225;
ui_game_status = 0x10031245;
old_card_error = 0x100309c1;
old_features_ui_init = 0x10032a61;
old_boot_draw = 0x10033001;
old_boot_chime = 0x10033239;
old_keys = 0x1003264d;
old_release = 0x1003267d;
legacy_battery_header = 0x10038681;
time_us_64 = 0x10009e3d;
sleep_ms = 0x10009c21;
memcpy = 0x1000b955;
__aeabi_uidiv = 0x1000aab1;
__aeabi_uidivmod = 0x1000aab1;
ASSERT(SIZEOF(.data)==0,"No initialised RAM load image")
ASSERT(__polish_bss_end<=0x2001fa64,"Pinned RAM budget exceeded")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"Settings sector overlap")
