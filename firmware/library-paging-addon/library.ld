MEMORY {
 FLASH (rx) : ORIGIN = 0x10039500, LENGTH = 0x45a00
 RAM (rw) : ORIGIN = 0x2001f9d0, LENGTH = 0x94
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > FLASH
 .data : { *(.data*) } > RAM
 .bss (NOLOAD) : {
  __library_bss_start = .;
  *(.bss*) *(COMMON)
  . = ALIGN(8);
  __library_bss_end = .;
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
legacy_battery_header = 0x10038681;
original_storage_mount = 0x100083ad;
original_sd_bus = 0x10031191;
/* Keep the working GP29 poll/indicator wrapper in the menu input chain. */
old_menu_input = 0x100386c5;
legacy_input_bridge = 0x100314bb;
f_opendir = 0x10015d81;
f_readdir = 0x10015ee9;
f_closedir = 0x10015e71;
f_open = 0x100146e5;
f_read = 0x10014f35;
f_close = 0x10015771;
memset = 0x1000b949;
memcpy = 0x1000b955;
__aeabi_uidiv = 0x1000aab1;
__aeabi_uidivmod = 0x1000aab1;
ASSERT(SIZEOF(.data)==0,"No initialized RAM image")
ASSERT(__library_bss_end<=0x2001fa64,"Legacy heap budget exceeded")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"Settings sector overlap")
