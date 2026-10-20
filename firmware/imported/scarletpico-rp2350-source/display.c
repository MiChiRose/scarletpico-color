#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "hardware/dma.h"
#include "hardware/regs/spi.h"
#include "config.h"
#include "display.h"
#include "video_math.h"

static int dma_tx;
static dma_channel_config dma_cfg;
static uint16_t row_buffers[2][480] __attribute__((aligned(4)));
static unsigned width, height, origin_x, origin_y;
static uint16_t xmap[480], ymap[320];

static void bus_idle(void) {
  dma_channel_wait_for_finish_blocking(dma_tx);
  while (spi_is_busy(LCD_SPI)) tight_loop_contents();
  while (spi_is_readable(LCD_SPI)) (void)spi_get_hw(LCD_SPI)->dr;
  spi_get_hw(LCD_SPI)->icr = SPI_SSPICR_RORIC_BITS;
}
static void write_command(uint8_t cmd, const uint8_t *data, size_t len) {
  gpio_put(PIN_LCD_CS, 0);
  gpio_put(PIN_LCD_DC, 0);
  spi_write_blocking(LCD_SPI, &cmd, 1);
  gpio_put(PIN_LCD_DC, 1);
  if (len) spi_write_blocking(LCD_SPI, data, len);
  gpio_put(PIN_LCD_CS, 1);
}
static void window(unsigned x, unsigned y, unsigned w, unsigned h) {
  bus_idle();
  spi_set_format(LCD_SPI, 8, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);
  uint16_t ex=x+w-1, ey=y+h-1;
  uint8_t col[] = {x>>8,x,ex>>8,ex};
  uint8_t line[] = {y>>8,y,ey>>8,ey};
  write_command(0x2a,col,4); write_command(0x2b,line,4);
  write_command(0x2c,NULL,0);
  spi_set_format(LCD_SPI,16,SPI_CPOL_0,SPI_CPHA_0,SPI_MSB_FIRST);
  gpio_put(PIN_LCD_CS,0); gpio_put(PIN_LCD_DC,1);
}
static void send_row(const uint16_t *row, unsigned count) {
  dma_channel_configure(dma_tx,&dma_cfg,&spi_get_hw(LCD_SPI)->dr,row,count,true);
}
static void finish_window(void) { bus_idle(); gpio_put(PIN_LCD_CS,1); }
uint32_t display_game_speed(void) {
  gpio_put(PIN_LCD_CS,1); gpio_put(PIN_SD_CS,1);
  return spi_set_baudrate(LCD_SPI,SCARLET_LCD_HZ);
}
void display_sd_speed(void) {
  bus_idle(); gpio_put(PIN_LCD_CS,1); gpio_put(PIN_SD_CS,1);
  spi_set_format(LCD_SPI,8,SPI_CPOL_0,SPI_CPHA_0,SPI_MSB_FIRST);
  spi_set_baudrate(LCD_SPI,SD_HZ);
}
unsigned display_width(void) {return width;}
unsigned display_height(void) {return height;}

void display_init(void) {
  const uint8_t outputs[]={PIN_LCD_CS,PIN_SD_CS,PIN_LCD_DC,PIN_LCD_RST,PIN_LCD_BL};
  for(unsigned i=0;i<sizeof(outputs);i++) {gpio_init(outputs[i]);gpio_put(outputs[i],1);gpio_set_dir(outputs[i],GPIO_OUT);}
  gpio_put(PIN_LCD_BL,0);
  spi_init(LCD_SPI,12000000);
  gpio_set_function(PIN_SCK,GPIO_FUNC_SPI);
  gpio_set_function(PIN_MOSI,GPIO_FUNC_SPI);
  gpio_set_function(PIN_MISO,GPIO_FUNC_SPI);gpio_pull_up(PIN_MISO);
  // Moderate pad drive; high-rate variants still depend on wiring/module.
  gpio_set_drive_strength(PIN_SCK,GPIO_DRIVE_STRENGTH_4MA);
  gpio_set_drive_strength(PIN_MOSI,GPIO_DRIVE_STRENGTH_4MA);
  gpio_set_slew_rate(PIN_SCK,GPIO_SLEW_RATE_FAST);
  gpio_set_slew_rate(PIN_MOSI,GPIO_SLEW_RATE_FAST);
  dma_tx=dma_claim_unused_channel(true);
  dma_cfg=dma_channel_get_default_config(dma_tx);
  channel_config_set_transfer_data_size(&dma_cfg,DMA_SIZE_16);
  channel_config_set_read_increment(&dma_cfg,true);
  channel_config_set_write_increment(&dma_cfg,false);
  channel_config_set_dreq(&dma_cfg,spi_get_dreq(LCD_SPI,true));
  gpio_put(PIN_LCD_RST,1);sleep_ms(10);
  gpio_put(PIN_LCD_RST,0);sleep_ms(20);
  gpio_put(PIN_LCD_RST,1);sleep_ms(120);
  write_command(0x01,NULL,0);sleep_ms(120);
  write_command(0x11,NULL,0);sleep_ms(120);
  #define CMD(c,...) do {const uint8_t d[]={__VA_ARGS__};write_command(c,d,sizeof(d));} while(0)
  CMD(0xf0,0xc3);CMD(0xf0,0x96);
  CMD(0x36,0x28);CMD(0x3a,0x55); // landscape, BGR, RGB565
  CMD(0xb4,0x01);CMD(0xb7,0xc6);CMD(0xb6,0x80,0x02,0x3b);
  CMD(0xc1,0x06);CMD(0xc2,0xa7);CMD(0xc5,0x18);
  CMD(0xe0,0xf0,0x09,0x0b,0x06,0x04,0x15,0x2f,0x54,0x42,0x3c,0x17,0x14,0x18,0x1b);
  CMD(0xe1,0xe0,0x09,0x0b,0x06,0x04,0x03,0x2b,0x43,0x42,0x3b,0x16,0x14,0x17,0x1b);
  CMD(0xf0,0x3c);CMD(0xf0,0x69);
  write_command(0x29,NULL,0);sleep_ms(50);
  #undef CMD
  width=SCARLET_SCALE==1?160:SCARLET_SCALE==3?240:SCARLET_SCALE==4?356:320;
  height=SCARLET_SCALE==1?144:SCARLET_SCALE==3?216:SCARLET_SCALE==4?320:288;
  origin_x=(480-width)/2;origin_y=(320-height)/2;
  for(unsigned x=0;x<width;x++) xmap[x]=scaled_source(x,160,width);
  for(unsigned y=0;y<height;y++) ymap[y]=scaled_source(y,144,height);
  display_clear(0);
  gpio_put(PIN_LCD_BL,1);
}
void display_clear(uint16_t color) {
  for(unsigned x=0;x<480;x++) row_buffers[0][x]=color;
  window(0,0,480,320);
  for(unsigned y=0;y<320;y++) {bus_idle();send_row(row_buffers[0],480);}
  finish_window();
}
void display_frame(const uint16_t *pixels) {
  window(origin_x,origin_y,width,height);
  unsigned current=0;
  for(unsigned y=0;y<height;y++) {
    uint16_t *dest=row_buffers[current];
    const uint16_t *src=pixels+ymap[y]*160;
    // CPU prepares the next row while DMA shifts the preceding row.
    for(unsigned x=0;x<width;x++) dest[x]=src[xmap[x]];
    bus_idle();send_row(dest,width);current^=1;
  }
  finish_window();
}

// 5x7 uppercase font, column bitmaps; lowercase folds to uppercase.
static const uint8_t letters[26][5]={
 {0x7e,9,9,9,0x7e},{0x7f,0x49,0x49,0x49,0x36},{0x3e,0x41,0x41,0x41,0x22},
 {0x7f,0x41,0x41,0x22,0x1c},{0x7f,0x49,0x49,0x49,0x41},{0x7f,9,9,9,1},
 {0x3e,0x41,0x49,0x49,0x7a},{0x7f,8,8,8,0x7f},{0,0x41,0x7f,0x41,0},
 {0x20,0x40,0x41,0x3f,1},{0x7f,8,0x14,0x22,0x41},{0x7f,0x40,0x40,0x40,0x40},
 {0x7f,2,0x0c,2,0x7f},{0x7f,4,8,0x10,0x7f},{0x3e,0x41,0x41,0x41,0x3e},
 {0x7f,9,9,9,6},{0x3e,0x41,0x51,0x21,0x5e},{0x7f,9,0x19,0x29,0x46},
 {0x26,0x49,0x49,0x49,0x32},{1,1,0x7f,1,1},{0x3f,0x40,0x40,0x40,0x3f},
 {0x1f,0x20,0x40,0x20,0x1f},{0x3f,0x40,0x38,0x40,0x3f},{0x63,0x14,8,0x14,0x63},
 {7,8,0x70,8,7},{0x61,0x51,0x49,0x45,0x43}};
static const uint8_t numbers[10][5]={
 {0x3e,0x51,0x49,0x45,0x3e},{0,0x42,0x7f,0x40,0},{0x62,0x51,0x49,0x49,0x46},
 {0x22,0x41,0x49,0x49,0x36},{0x18,0x14,0x12,0x7f,0x10},{0x2f,0x49,0x49,0x49,0x31},
 {0x3e,0x49,0x49,0x49,0x32},{1,0x71,9,5,3},{0x36,0x49,0x49,0x49,0x36},
 {0x26,0x49,0x49,0x49,0x3e}};
static uint8_t glyph(char c, unsigned col) {
  if(c>='a'&&c<='z')c-=32;
  if(c>='A'&&c<='Z')return letters[c-'A'][col];
  if(c>='0'&&c<='9')return numbers[c-'0'][col];
  if(c=='-')return 8;
  if(c=='_')return 0x40;
  if(c==':')return col==2?0x24:0;
  if(c=='.')return col==2?0x40:0;
  if(c=='/')return 0x40>>col;
  if(c=='>')return col==2?0x14:col==3?8:0;
  if(c=='+')return col==2?0x3e:8;
  return 0;
}
void display_text(int x,int y,const char *text,uint16_t color,uint16_t bg) {
  if(x<0||x>=480||y<0||y>312)return;
  unsigned length=strlen(text);if(length>(480-x)/6)length=(480-x)/6;
  if(!length)return;
  window(x,y,length*6,8);
  for(unsigned r=0;r<8;r++) {
    unsigned current=r&1;
    uint16_t *dest=row_buffers[current];
    for(unsigned n=0;n<length;n++)for(unsigned c=0;c<6;c++)
      dest[n*6+c]=(c<5&&(glyph(text[n],c)&(1u<<r)))?color:bg;
    bus_idle();send_row(dest,length*6);
  }
  finish_window();
}
void display_status(unsigned lcd,unsigned emu,unsigned drops) {
  (void)emu;(void)drops;
  char text[16];snprintf(text,sizeof(text),"%u FPS   ",lcd);
  display_text(4,308,text,0xffff,0);
}

void display_ui_begin(unsigned x,unsigned y,unsigned w,unsigned h) {
  display_game_speed();window(x,y,w,h);
}
void display_ui_row(const uint8_t *bytes,unsigned size) {
  bus_idle();
  for(unsigned i=0;i<size/2;i++)row_buffers[0][i]=((unsigned)bytes[2*i]<<8)|bytes[2*i+1];
  send_row(row_buffers[0],size/2);
}
void display_ui_end(void) {finish_window();}
void display_rect(unsigned x,unsigned y,unsigned w,unsigned h,uint16_t c) {
  if(!w||!h||x>=480||y>=320)return;
  if(w>480-x)w=480-x;
  if(h>320-y)h=320-y;
  display_game_speed();window(x,y,w,h);
  for(unsigned i=0;i<w;i++)row_buffers[0][i]=c;
  for(unsigned row=0;row<h;row++){bus_idle();send_row(row_buffers[0],w);}
  finish_window();
}
