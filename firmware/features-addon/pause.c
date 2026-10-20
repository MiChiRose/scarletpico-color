#include "features.h"
#include <string.h>
#ifdef SCARLET_RP2040_NATIVE
#include "../imported/scarletpico-rp2040-source/console_power.h"
#endif

#ifdef SCARLET_PAUSE_SETTINGS
/* Append-only UI build: retain the pinned input/snapshot state and addresses.
 * The historical build (without this flag) remains byte-identical. */
extern bool chord_active,chord_latched;
extern uint32_t chord_since;
extern uint8_t slot_status[5];
#define PAUSE_ROWS 5
#define PAUSE_EXIT_ROW 4
#else
bool pause_pending,exit_requested;
static bool chord_active,chord_latched;
static uint32_t chord_since;
static uint8_t slot_status[5];
#define PAUSE_ROWS 4
#define PAUSE_EXIT_ROW 3
#endif

unsigned features_buttons(unsigned pressed) {
 if(exit_requested){exit_requested=false;return 256;}
 uint32_t now=(uint32_t)time_us_64();
 if((pressed&12)==12) {
  if(!chord_active){chord_since=now;chord_active=true;}
  if(!chord_latched && (uint32_t)(now-chord_since)>=1500000) {
   pause_pending=true;chord_latched=true;
  }
  return pressed&~12u;
 }
 chord_active=false;
 if(chord_latched) {
  if(!(pressed&12))chord_latched=false;
  return pressed&~12u;
 }
 return pressed;
}
static const char *status_name(unsigned status) {
 switch(status) {
 case STATE_EMPTY:return feature_tr("EMPTY","ПУСТО");
 case STATE_SAVED:return feature_tr("SAVED","ЕСТЬ");
 case STATE_INVALID:return feature_tr("INVALID","ОШИБКА");
 default:return feature_tr("CARD ERROR","СБОЙ SD");
 }
}
static void pause_row(unsigned i,unsigned selected) {
 const char *en[]={"RESUME","SAVE STATE","LOAD STATE",
#ifdef SCARLET_PAUSE_SETTINGS
 "SETTINGS",
#endif
 "RETURN TO LIBRARY"};
 const char *ru[]={"ПРОДОЛЖИТЬ","СОХРАНИТЬ СНИМОК","ЗАГРУЗИТЬ СНИМОК",
#ifdef SCARLET_PAUSE_SETTINGS
 "НАСТРОЙКИ",
#endif
 "К СПИСКУ ИГР"};
 feature_row(i,selected,ui_settings.language?ru[i]:en[i],NULL);
}
static void pause_draw(unsigned selected) {
 feature_page(feature_tr("PAUSED","ПАУЗА"));
 for(unsigned i=0;i<PAUSE_ROWS;i++)pause_row(i,selected);
 feature_message("SNAPSHOTS ARE SEPARATE FROM IN-GAME SAVES","СНИМКИ ХРАНЯТСЯ ОТДЕЛЬНО ОТ СОХРАНЕНИЙ ИГРЫ");
 feature_footer(feature_tr("UP/DN: CHOOSE   A: SELECT","ВВЕРХ/ВНИЗ: ВЫБОР   A: ОТКРЫТЬ"),feature_tr("B: RESUME","B: ПРОДОЛЖИТЬ"));
}
static void slot_row(unsigned i,unsigned selected) {
 char label[24];
 const char *prefix=feature_tr("SLOT ","СЛОТ ");
 unsigned j=0;while(prefix[j]){label[j]=prefix[j];j++;}
 label[j++]='1'+i;label[j]=0;
 feature_row(i,selected,label,status_name(slot_status[i]));
}
static void slots_draw(bool save,unsigned selected) {
 feature_page(save?feature_tr("SAVE STATE","СОХРАНИТЬ СНИМОК"):feature_tr("LOAD STATE","ЗАГРУЗИТЬ СНИМОК"));
 for(unsigned i=0;i<5;i++)slot_row(i,selected);
 feature_footer(feature_tr("UP/DN: SLOT   A: SELECT   B: BACK","ВВЕРХ/ВНИЗ: СЛОТ   A: ВЫБОР   B: НАЗАД"),feature_tr("5 SLOTS PER GAME - INCLUDES ALL SAVE PROFILES","5 СЛОТОВ НА ИГРУ - СНИМОК ВКЛЮЧАЕТ ВСЕ ПРОФИЛИ"));
}
static uint8_t menu_edge(uint8_t *last) {
#ifdef SCARLET_RP2040_NATIVE
 console_power_ui_tick();
#endif
 uint8_t k=feature_keys();
 if(k!=*last){sleep_ms(25);if(feature_keys()!=k)return 0;}
 uint8_t edge=k&~*last;*last=k;sleep_ms(5);return edge;
}
static bool confirm(bool load) {
 /* Explicit A confirmation after release; never overwrite from a held key. */
 feature_footer(load?feature_tr("LOAD SNAPSHOT? CURRENT UNSAVED POSITION WILL BE LOST.","ЗАГРУЗИТЬ СНИМОК? ТЕКУЩАЯ НЕСОХРАНЕННАЯ ПОЗИЦИЯ ПРОПАДЕТ."):
                       feature_tr("REPLACE THIS SLOT? THE PREVIOUS SNAPSHOT IS KEPT AS BACKUP.","ПЕРЕЗАПИСАТЬ СЛОТ? ПРЕДЫДУЩИЙ СНИМОК ОСТАНЕТСЯ РЕЗЕРВНЫМ."),
                feature_tr("A: CONFIRM   B: CANCEL","A: ПОДТВЕРДИТЬ   B: ОТМЕНА"));
 feature_release();uint8_t last=0;
 for(;;){uint8_t k=menu_edge(&last);if(k&UI_B)return false;if(k&UI_A)return true;}
}
static bool confirm_exit(void) {
 feature_footer(feature_tr("RETURN TO LIBRARY? SAVE A STATE TO RESUME FROM HERE.","ВЫЙТИ К СПИСКУ ИГР? ДЛЯ ПРОДОЛЖЕНИЯ НУЖЕН СНИМОК."),
                feature_tr("A: EXIT   B: STAY PAUSED","A: ВЫЙТИ   B: ОСТАТЬСЯ В ПАУЗЕ"));
 feature_release();uint8_t last=0;
 for(;;){uint8_t k=menu_edge(&last);if(k&UI_B)return false;if(k&UI_A)return true;}
}
static bool slots(bool save) {
 unsigned selected=0;
 for(unsigned i=0;i<5;i++)slot_status[i]=state_status(i);
 slots_draw(save,selected);feature_release();uint8_t last=0;
 for(;;) {
  uint8_t key=menu_edge(&last);unsigned old=selected;
  if(key&UI_B){feature_release();return false;}
  if(key&UI_UP)selected=selected?selected-1:4;
  else if(key&(UI_DOWN|UI_SELECT))selected=(selected+1)%5;
  if(old!=selected){slot_row(old,selected);slot_row(selected,selected);continue;}
  if(!(key&(UI_A|UI_START)))continue;
  if(!save && slot_status[selected]==STATE_EMPTY){feature_message("THIS SLOT IS EMPTY","ЭТОТ СЛОТ ПУСТ");continue;}
  if((!save || slot_status[selected]!=STATE_EMPTY) && !confirm(!save)) {
   slots_draw(save,selected);feature_release();last=0;continue;
  }
  feature_message(save?"SAVING... DO NOT SWITCH OFF":"LOADING...",save?"СОХРАНЕНИЕ... НЕ ВЫКЛЮЧАЙТЕ ПИТАНИЕ":"ЗАГРУЗКА...");
  unsigned result=save?state_save(selected):state_load(selected);
  if(result==STATE_SAVED && !save){feature_release();return true;}
  slot_status[selected]=state_status(selected);slots_draw(save,selected);
  if(result==STATE_SAVED)feature_message("STATE SAVED","СНИМОК СОХРАНЕН");
  else if(result==STATE_NO_MEMORY)feature_message("NOT ENOUGH MEMORY - CURRENT GAME IS UNCHANGED","НЕ ХВАТАЕТ ПАМЯТИ - ТЕКУЩАЯ ИГРА НЕ ИЗМЕНЕНА");
  else if(result==STATE_INVALID)feature_message("INVALID STATE - CURRENT GAME IS UNCHANGED","СНИМОК ПОВРЕЖДЕН - ТЕКУЩАЯ ИГРА НЕ ИЗМЕНЕНА");
  else feature_message("CARD ERROR - CURRENT GAME IS UNCHANGED","ОШИБКА КАРТЫ - ТЕКУЩАЯ ИГРА НЕ ИЗМЕНЕНА");
  feature_release();last=0;
 }
}
static void pause_menu(void) {
 unsigned selected=0;pause_draw(selected);feature_release();uint8_t last=0;
 for(;;) {
  uint8_t key=menu_edge(&last);unsigned old=selected;
  if(key&UI_B)break;
  if(key&UI_UP)selected=selected?selected-1:PAUSE_ROWS-1;
  else if(key&(UI_DOWN|UI_SELECT))selected=(selected+1)%PAUSE_ROWS;
  if(old!=selected){pause_row(old,selected);pause_row(selected,selected);continue;}
  if(!(key&(UI_A|UI_START)))continue;
  if(selected==0)break;
  if(selected==PAUSE_EXIT_ROW){
   if(confirm_exit()){exit_requested=true;break;}
   feature_release();pause_draw(selected);last=0;continue;
  }
#ifdef SCARLET_PAUSE_SETTINGS
  if(selected==3) {
   /* features_frame has stopped core 1 and I2S and paused the watchdog.
    * Existing settings can therefore persist safely to flash. The core/APU
    * stay loaded; CPU profile changes still apply only on next game launch.
    * feature_settings consumes the release of B before returning here. */
   feature_settings();pause_draw(selected);last=0;continue;
  }
#endif
  if(slots(selected==1))break;
  pause_draw(selected);last=0;
 }
 feature_release();
}
bool features_frame(uint8_t joypad,bool render) {
 if(pause_pending) {
  pause_pending=false;
  /* Stop DMA/I2S, not addon_stop: APU and fractional sample state survive. */
  original_video_wait_idle();bool guard=original_guard_pause();
  original_audio_stop();original_video_stop();
  pause_menu();
  chord_active=chord_latched=false;
  if(exit_requested){original_guard_resume(guard);return true;}
  ui_rect(0,0,480,320,0);
  if(!original_video_start(5) || !original_audio_start()) {
   feature_error("RESUME FAILED - NOT ENOUGH MEMORY");
   original_guard_resume(guard);return false;
  }
  /* Recreated video buffers need a first full frame, even if a previous job
   * was waiting in the original main loop. Next frame resumes normal policy. */
  render=true;joypad=255;original_guard_resume(guard);
 }
 return original_addon_frame(joypad,render);
}
