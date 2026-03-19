#include <SparkFunAutoDriver.h>
#include <Adafruit_MCP4728.h>
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_MotorShield.h>
#include "utility/Adafruit_MS_PWMServoDriver.h"
#include "SoftwareSerial.h"
#include "Adafruit_TLC59711.h"
#include <SPI.h>
#define led_data   A0
#define led_clock  A1


Adafruit_TLC59711 tlc = Adafruit_TLC59711(1, led_clock, led_data);
Adafruit_MCP4728 mcp;

unsigned char motor_busy[8] = {0, 0, 0, 0, 0, 0};
// Software position tracking via delta accumulation from getPos()
// getPos() is buggy (16-bit truncation), but deltas between ~100ms reads are small and accurate
// Indices: 0=FocusA, 1=FocusB, 2=ObjA, 3=MicroC, 4=MicroA, 5=MicroB
long soft_pos[6] = {0, 0, 0, 0, 0, 0};
long prev_hw[6] = {0, 0, 0, 0, 0, 0};
bool hw_initialized = false;

#define MAX_BUF (16) // What is the longest message Arduino can store?

char buffer[MAX_BUF]; // where we store the message until we get a ';'
int sofar; // how much is in the buffer


#define NUM_BOARDS 6
AutoDriver *boardIndex[NUM_BOARDS];

const unsigned int motor_run_v[6] ={120, 120, 120, 75, 75, 75};
const unsigned int motor_acc_v[6] = {120, 120, 120, 75, 75, 75};
const unsigned int motor_dec_v[6] = {120, 120, 120, 75, 75, 75};  
const unsigned int motor_hold_v[6] = {30, 30, 30, 30, 75, 75};
const unsigned int motor_acc[6] = {400, 400, 400, 4, 4, 4};
const unsigned int motor_dec[6] = {400, 400, 400, 4, 4, 4};

// Numbering starts from the board farthest from the
//  controller and counts up from 0.
AutoDriver FocusA(0, 10, 6); //Slave
AutoDriver FocusB(1, 10, 6);
AutoDriver ObjA(2, 10, 6);
AutoDriver MicroC(3, 10, 6);
AutoDriver MicroA(4, 10, 6); //Slave
AutoDriver MicroB(5, 10, 6);

unsigned int temp;
unsigned long prev_time;
unsigned int pattern_mode;
long motor_speed = 1500;
long light = 0;
long prevlight = 0;
long lightnum = -1;
unsigned int image_mode = 0;
unsigned int image_type = 0;
unsigned long image_mode_time = 0;
unsigned long image_delay = 500;//2560;
unsigned int data_enabled = 1;
unsigned long pulse_length = 0;
unsigned long pulse_time;
unsigned int pulse_on = 0;

unsigned long times_test[32] = {0};
unsigned int times_test_ind = 0;
#define LED_BF 5
//#define LED_FA A2
#define LED_FA 3
#define LED_FB 6
#define LED_FC 9
 

unsigned long last_serial_time;

#ifdef __arm__
// should use uinstd.h to define sbrk but Due causes a conflict
extern "C" char* sbrk(int incr);
#else  // __ARM__
extern char *__brkval;
#endif  // __arm__

int freeMemory() {
  char top;
#ifdef __arm__
  return &top - reinterpret_cast<char*>(sbrk(0));
#elif defined(CORE_TEENSY) || (ARDUINO > 103 && ARDUINO != 151)
  return &top - __brkval;
#else  // __arm__
  return __brkval ? &top - __brkval : &top - __malloc_heap_start;
#endif  // __arm__
}
/*
#define SWITCHES_0 7
#define SWITCHES_1 8
#define SWITCHES_2 A3
#define SWITCHES_3 A0
#define SWITCHES_4 A1
*/
unsigned char button_state[5] = {0};
unsigned char last_button_state[5] = {0};
unsigned long bounce_time[3] = {0};  // the last time the output pin was toggled
unsigned long debounceDelay = 16000L;//32000L;    // the debounce time; increase if the output flickers
unsigned char limit_switch = 0;
/*
//Poll all limit switches
void pollButtons() {
  unsigned char button_state_tmp[5];
  button_state_tmp[0] = digitalRead(SWITCHES_0);
  button_state_tmp[1] = digitalRead(SWITCHES_1);
  button_state_tmp[2] = digitalRead(SWITCHES_2);
  button_state_tmp[3] = digitalRead(SWITCHES_3);
  button_state_tmp[4] = digitalRead(SWITCHES_4);

  //Debounce switches
  for (unsigned char i = 0; i < 5; i++) {
    if ((button_state_tmp[i] != button_state[i])) {
      if ((millis() - bounce_time[i]) > debounceDelay) {
        //Serial.println("SWITCH");
        bounce_time[i] = millis();
        button_state[i] = button_state_tmp[i];
        if (button_state[i] == 0) {
          limit_switch = 1;
          FocusA.run(0, 0);
          FocusB.run(0, 0);
          ObjA.run(0, 0);
          MicroC.run(0, 0);
          MicroA.run(0, 0);
          MicroB.run(0, 0);

        }
      } else {
        //Serial.println("BOUNCE");
      }
    }
  }
}
*/
//String packet = String();
char packet[512];
char temp_str[14];
int packet_pos = -1;
int serial_write_count = 0;

//Update loop
void updatePatterns() {
  unsigned int stepSize;
  long FlowAPos;
  long FlowBPos;
  unsigned int busy;
  unsigned char advancePattern = 0;
  unsigned long move = 0;

  //Poll limit switches
  //pollButtons();
 
  unsigned long now = millis();

  if (image_mode!=0) {
    if (image_type==1) {
      if (now > (image_mode_time + image_delay)) {
        //times_test[times_test_ind] = now-image_mode_time;
        //times_test_ind ++;
        image_mode_time = now;
       
        light = light + 2;//8;
        if (light>64) {//255) {
          light = 0;
          image_mode = 0;
          image_type = 0;
        }
        int light_tmp = 255 - light;
        analogWrite(LED_BF, light_tmp);
       
      }
    }
    if (image_type==2) {
      if (image_mode==1) {
        light = 0;
        int light_tmp = 255 - light;
        analogWrite(LED_BF, light_tmp);
        FocusA.run(0, 0);
        FocusA.setMaxSpeed(motor_speed);
        FocusA.move(1, 25600);
        FocusB.run(0, 0);
        FocusB.setMaxSpeed(motor_speed);
        FocusB.move(1, 25600);
        motor_busy[0] = motor_busy[0] + 1;
        motor_busy[1] = motor_busy[1] + 1;
        image_mode = 2;
      }
      else if (image_mode==2) {
        unsigned int busy_temp_a = FocusA.getStatus()&2;
        unsigned int busy_temp_b = FocusB.getStatus()&2;
        if ((busy_temp_a!=0) && (busy_temp_b!=0)) {
          light = prevlight;
          int light_tmp = 255 - light;
          analogWrite(LED_BF, light_tmp);
          FocusA.run(0, 0);
          FocusA.setMaxSpeed(motor_speed);
          FocusA.move(0, 51200);
          FocusB.run(0, 0);
          FocusB.setMaxSpeed(motor_speed);
          FocusB.move(0, 51200);
          image_mode = 3;
        }
      }
      else if (image_mode==3) {
        unsigned int busy_temp_a = FocusA.getStatus()&2;
        unsigned int busy_temp_b = FocusB.getStatus()&2;
        if ((busy_temp_a!=0) && (busy_temp_b!=0)) {
          light = 0;
          int light_tmp = 255 - light;
          analogWrite(LED_BF, light_tmp);
          FocusA.run(0, 0);
          FocusA.setMaxSpeed(motor_speed);
          FocusA.move(1, 51200);
          FocusB.run(0, 0);
          FocusB.setMaxSpeed(motor_speed);
          FocusB.move(1, 51200);
          image_mode = 4;
        }
      }
      else if (image_mode==4) {
        unsigned int busy_temp_a = FocusA.getStatus()&2;
        unsigned int busy_temp_b = FocusB.getStatus()&2;
        if ((busy_temp_a!=0) && (busy_temp_b!=0)) {
          light = prevlight;
          int light_tmp = 255 - light;
          analogWrite(LED_BF, light_tmp);
          image_mode = 0;
        }
      }
    }  
  }
 
  //Update serial data transmission
  if (data_enabled == 0) {
    serial_write_count = 0;
    packet_pos = -1;
  }
  if ((packet_pos >= 0) && (Serial.availableForWrite() > 16))  {
    if (1) {//(serial_write_count >= 10) {

      Serial.print(packet[packet_pos]);
      packet_pos ++;
       if (packet_pos >= strlen(packet)) {
        packet_pos = -1;
      }
      serial_write_count = 0;
    } else {
      serial_write_count ++;
    }

  }

  //Generate serial data packet
  if (((now - last_serial_time) >= (6400)) && (packet_pos == -1)) {
    //packet = "";
    long pos;
    byte checksum = 0;
   
    strcpy(packet, "M:");

    // Read current hardware positions (16-bit truncated by buggy getPos())
    long cur_hw[6];
    cur_hw[0] = FocusA.getPos();
    cur_hw[1] = FocusB.getPos();
    cur_hw[2] = ObjA.getPos();
    cur_hw[3] = MicroC.getPos();
    cur_hw[4] = MicroA.getPos();
    cur_hw[5] = MicroB.getPos();

    if (!hw_initialized) {
      for (int i = 0; i < 6; i++) prev_hw[i] = cur_hw[i];
      hw_initialized = true;
    }

    // Accumulate deltas into soft_pos (int16_t cast handles 16-bit wraparound)
    // Sign: Focus/Obj (0,1,2) use getPos() directly, Micro (3,4,5) use -getPos()
    for (int i = 0; i < 3; i++) {
      int16_t delta = (int16_t)(cur_hw[i] - prev_hw[i]);
      soft_pos[i] += delta;
    }
    for (int i = 3; i < 6; i++) {
      int16_t delta = (int16_t)(cur_hw[i] - prev_hw[i]);
      soft_pos[i] -= delta;  // negated for Micro motors
    }
    for (int i = 0; i < 6; i++) prev_hw[i] = cur_hw[i];

    temp = FocusA.getStatus();
    sprintf(temp_str,"%04x ",temp);
    strcat(packet, temp_str);
    sprintf(temp_str,"%ld ",soft_pos[0]);
    strcat(packet, temp_str);

    temp = FocusB.getStatus();
    sprintf(temp_str,"%04x ",temp);
    strcat(packet, temp_str);
    sprintf(temp_str,"%ld ",soft_pos[1]);
    strcat(packet, temp_str);

    temp = ObjA.getStatus();
    sprintf(temp_str,"%04x ",temp);
    strcat(packet, temp_str);
    sprintf(temp_str,"%ld ",soft_pos[2]);
    strcat(packet, temp_str);

    temp = MicroC.getStatus();
    sprintf(temp_str,"%04x ",temp);
    strcat(packet, temp_str);
    sprintf(temp_str,"%ld ",soft_pos[3]);
    strcat(packet, temp_str);

    temp = MicroA.getStatus();
    sprintf(temp_str,"%04x ",temp);
    strcat(packet, temp_str);
    sprintf(temp_str,"%ld ",soft_pos[4]);
    strcat(packet, temp_str);

    temp = MicroB.getStatus();
    sprintf(temp_str,"%04x ",temp);
    strcat(packet, temp_str);
    sprintf(temp_str,"%ld ",soft_pos[5]);
    strcat(packet, temp_str);

    sprintf(temp_str,"%d%d%d%d%d%d ",button_state[0],button_state[1],button_state[2],button_state[3],button_state[4],limit_switch);
    strcat(packet, temp_str);
   
    sprintf(temp_str,"%d ",lightnum);
    strcat(packet, temp_str);
    sprintf(temp_str,"%d ",light);
    strcat(packet, temp_str);
   
    for (int i = 0; i < 8; i++) {
      sprintf(temp_str,"%d",motor_busy[i]);
      strcat(packet, temp_str);
      if (i != 7) {
        strcat(packet, " ");
      }
    }

   
    checksum = 0;
    for (int i = 0; i < strlen(packet); i++) {
      checksum += packet[i];
    }
    sprintf(temp_str," %d\n",checksum);
    strcat(packet, temp_str);
    packet_pos = 0;
    last_serial_time = millis();
   
  }
}

void setup()
{
  Serial.begin(19200);
/*
  pinMode(SWITCHES_0, INPUT_PULLUP);
  pinMode(SWITCHES_1, INPUT_PULLUP);
  pinMode(SWITCHES_2, INPUT_PULLUP);
  pinMode(SWITCHES_3, INPUT_PULLUP);
  pinMode(SWITCHES_4, INPUT_PULLUP);
*/
  pinMode(MOSI, OUTPUT);
  pinMode(MISO, INPUT);
  pinMode(13, OUTPUT);
  pinMode(10, OUTPUT);

  TCCR0B = TCCR0B & B11111000 | B00000001;
  pinMode(LED_FA, OUTPUT);
  pinMode(LED_FB, OUTPUT);
  pinMode(LED_FC, OUTPUT);

  analogWrite(LED_BF, 255);
  pinMode(LED_BF, OUTPUT);
  analogWrite(LED_FA, 255);
  analogWrite(LED_FB, 255);
  analogWrite(LED_FC, 255);

  // Try to initialize!
  Serial.println("Init MCP4728?");
  if (!mcp.begin()) {
    Serial.println("Failed to find MCP4728 chip");
    for (int i=0; i<3; i++) {
      delay(10);
    }
  }
 
  mcp.setChannelValue(MCP4728_CHANNEL_A, 4095);
  mcp.setChannelValue(MCP4728_CHANNEL_B, 4095);
  mcp.setChannelValue(MCP4728_CHANNEL_C, 4095);
  mcp.setChannelValue(MCP4728_CHANNEL_D, 4095);

  /*
  mcp.setChannelValue(MCP4728_CHANNEL_A, 4095);
  mcp.setChannelValue(MCP4728_CHANNEL_B, 2048);
  mcp.setChannelValue(MCP4728_CHANNEL_C, 1024);
  mcp.setChannelValue(MCP4728_CHANNEL_D, 0);

   */
 
  SPI.begin();
  SPI.setDataMode(SPI_MODE3);

  // Set the pointers in our global AutoDriver array to
  //  the objects we've created.

  boardIndex[0] = &FocusA;
  boardIndex[1] = &FocusB;
  boardIndex[2] = &ObjA;
  boardIndex[3] = &MicroC;
  boardIndex[4] = &MicroA;
  boardIndex[5] = &MicroB;


  // Configure the boards to the settings we wish to use
  //  for them.

  Serial.print("INIT Z");
  Serial.print(" ");
  temp = FocusA.getParam(CONFIG);
 
  Serial.print(temp, HEX);
  Serial.print(" ");

  temp = FocusA.getStatus();
  Serial.print(temp, HEX);
  Serial.print(" ");
  temp = FocusB.getParam(CONFIG);
  Serial.print(temp, HEX);
  Serial.print(" ");
  temp = FocusB.getStatus();
  Serial.print(temp, HEX);
  Serial.println(" ");

  Serial.print("INIT OBJ/Y");
  Serial.print(" ");
  temp = ObjA.getParam(CONFIG);
  Serial.print(temp, HEX);
  Serial.print(" ");
  temp = ObjA.getStatus();
  Serial.print(temp, HEX);
  Serial.print(" ");
  temp = MicroC.getParam(CONFIG);
  Serial.print(temp, HEX);
  Serial.print(" ");
  temp = MicroC.getStatus();
  Serial.print(temp, HEX);
  Serial.println(" ");

  Serial.print("INIT X");
  Serial.print(" ");
  temp = MicroA.getParam(CONFIG);
  Serial.print(temp, HEX);
  Serial.print(" ");
  temp = MicroA.getStatus();
  Serial.print(temp, HEX);
  Serial.print(" ");
  temp = MicroB.getParam(CONFIG);
  Serial.print(temp, HEX);
  Serial.print(" ");
  temp = MicroB.getStatus();
  Serial.print(temp, HEX);
  Serial.println(" ");
 
  configureBoards();
 
 

  boardIndex[0]->hardHiZ();
  boardIndex[1]->hardHiZ();
  boardIndex[0]->setOscMode(INT_16MHZ_OSCOUT_16MHZ);
  //delay(10000);
  boardIndex[1]->setOscMode(EXT_16MHZ_OSCOUT_INVERT );

  boardIndex[4]->hardHiZ();
  boardIndex[5]->hardHiZ();
  boardIndex[4]->setOscMode(INT_16MHZ_OSCOUT_16MHZ);
  //delay(10000);
  boardIndex[5]->setOscMode(EXT_16MHZ_OSCOUT_INVERT );
  //delay(10000);
 
  getBoardConfigurations();

  prev_time = 0;
  pattern_mode = 0;
  last_serial_time = millis();
 
}

void ready() {
  sofar = 0; // clear input buffer
}
unsigned char got_light = 2;
//Process serial data inpus
void processCommand() {
 
 
  limit_switch = 0;
  char *str1, *str2;
  char *p = buffer;

  unsigned char got_xa = 0;
  unsigned char got_xb = 0;
  unsigned char got_y = 0;
  unsigned char got_za = 0;
  unsigned char got_zb = 0;
  unsigned char got_o = 0;

  long xa_dist = 0;
  long xb_dist = 0;
  long y_dist = 0;
  long za_dist = 0;
  long zb_dist = 0;

  long o_dist = 0;

  //X: + is towards room door
  //Y: + towards incubator door
  //Z: + is up
  //O: + is towards room door


  unsigned char motor_dir = 0;
  //Break up serial command into words by looking for spaces
  while ((str2 = strtok_r(p, " ", &p)) != NULL) {
    switch (str2[0]) {

      case 'X':
        if (str2[1] == 'A') {
          xa_dist = atol(str2 + 2);
          got_xa = 1;
        } else if (str2[1] == 'B') {
          xb_dist = atol(str2 + 2);
          got_xb = 1;
        } else {
          xa_dist = atol(str2 + 1);
          got_xa = 1;
          xb_dist = atol(str2 + 1);
          got_xb = 1;
        }
        break;
      case 'Y':
        y_dist = atol(str2 + 1);
        got_y = 1;
        break;
      case 'Z':
        if (str2[1] == 'A') {
          za_dist = atol(str2 + 2);
          got_za = 1;
        } else if (str2[1] == 'B') {
          zb_dist = atol(str2 + 2);
          got_zb = 1;
        } else {
          za_dist = atol(str2 + 1);
          got_za = 1;
          zb_dist = atol(str2 + 1);
          got_zb = 1;
        }
        break;
      case 'O':
        o_dist = atol(str2 + 1);
        got_o = 1;
        break;
      //Change motor feed rate
      case 'F':
        motor_speed = atol(str2 + 1);
        break;
      case 'I':
        if (str2[1] == 'D') {
          image_delay = atol(str2 + 2);
        } else {
          image_type = atol(str2 + 1);
          image_mode = 1;
          image_mode_time = millis();
          prevlight = light;
          light = 0;
          analogWrite(LED_BF, 255);
        }
        break;
      //LEDs
      case 'L':
        if (str2[1] == 'L') {
          if (str2[2]=='A') {
            got_light = 3;
          } else if (str2[2]=='B') {
            got_light = 2;
          } else if (str2[2]=='C') {
            got_light = 1;
          } else {
            got_light = str2[2] - '0';
          }

          //got_light = str2[2] - '0';        // convert char to int
          //if (got_light>9) {
          //  got_light = got_light -7;
          //}
          //Serial.println(got_light);
          //got_light = strtol(str2 + 2, NULL, 16);  // parse hex, e.g. "E" → 14, "F" → 15
          light = atol(str2 + 3);  
          //light = atol(str2 + 3);           // convert "65535" to long
        }
        if (str2[1] == 'H') {
          light = atol(str2 + 2);
          light = 4095-light;
          //light = atol(str2 + 2);
          //if (light < 0) light = 0;
          //if (light > 255) light = 255;
          //int light_tmp = 255 - light;
          //analogWrite(LED_BF, light_tmp);
          mcp.setChannelValue(MCP4728_CHANNEL_C, light);
        } else if (str2[1] == 'A') {
          light = atol(str2 + 2);
          light = 4095-light;
          //if (light < 0) light = 0;
          //if (light > 255) light = 255;
          //light = 255-light;
          //analogWrite(LED_FA, light);
          mcp.setChannelValue(MCP4728_CHANNEL_A, light);
        } else if (str2[1] == 'B') {
          light = atol(str2 + 2);
          light = 4095-light;
          //if (light < 0) light = 0;
          //if (light > 255) light = 255;
          //light = 255-light;
          //analogWrite(LED_FB, light);
          mcp.setChannelValue(MCP4728_CHANNEL_B, light);
        } else if (str2[1] == 'C') {
          //light = atol(str2 + 2);
          //if (light < 0) light = 0;
          //if (light > 255) light = 255;
          //light = 255-light;
          //analogWrite(LED_FC, light);
          
        } else if (str2[1] == 'N') {
          lightnum = atol(str2 + 2);
          analogWrite(LED_BF, 255);
          light = 0;
        } else if (str2[1] == 'P') {
          pulse_length = atol(str2 + 2);
        }
        break;
      case 'D':
        data_enabled = atol(str2 + 1);
        if (data_enabled == 0) {
          serial_write_count = 0;
          packet_pos = -1;
        }
        break;
      default:
        break;
    }
  }

  if (got_light !=0) {  
    //Serial.write("Changing light\n");
    tlc.begin();
    tlc.write();
    if (got_light>3) {
      tlc.setPWM(got_light-4, light);
      tlc.write();
    } else {
      if (got_light==1) {
        tlc.setPWM(4, light);
        tlc.write();
        tlc.setPWM(5, light);\
        tlc.write();
        tlc.setPWM(6, light);
        tlc.write();
        tlc.setPWM(7, light);
        tlc.write();
      }
      if (got_light==2) {
        tlc.setPWM(2, light);
        tlc.write();
        tlc.setPWM(3, light);
        tlc.write();
        tlc.setPWM(8, light);
        tlc.write();
        tlc.setPWM(9, light);
        tlc.write();
      }
      if (got_light==3) {
        tlc.setPWM(0, light);
        tlc.write();
        tlc.setPWM(1, light);
        tlc.write();
        tlc.setPWM(10, light);
        tlc.write();
        tlc.setPWM(11, light);
        tlc.write();
      }
     
    }
    //if (got_light>=2 && got_light<=5) {
          //} else {
     // for (int i = 0; i < 4; i++) {
      //  tlc.setPWM(i, light);
       // tlc.write();
      //}
    //}
    got_light = 0;
  }



  if (got_xa == 1) {
    unsigned char motor_dir = 1;
    MicroA.run(0, 0);
    if (xa_dist < 0) {
      xa_dist = -xa_dist;
      motor_dir = 0;
    }
    MicroA.setMaxSpeed(motor_speed);
    MicroA.move(motor_dir, xa_dist);
    motor_busy[6] = motor_busy[6] + 1;

  }
  if (got_xb == 1) {
    unsigned char motor_dir = 1;
    MicroB.run(0, 0);
    if (xb_dist < 0) {
      xb_dist = -xb_dist;
      motor_dir = 0;
    }
    MicroB.setMaxSpeed(motor_speed);
    MicroB.move(motor_dir, xb_dist);
    motor_busy[7] = motor_busy[7] + 1;
  }
  if (got_y == 1) {
    unsigned char motor_dir = 1;
    MicroC.run(0, 0);
    if (y_dist < 0) {
      y_dist = -y_dist;
      motor_dir = 0;
    }
    MicroC.setMaxSpeed(motor_speed);
    MicroC.move(motor_dir, y_dist);
    motor_busy[3] = motor_busy[3] + 1;
  }

  if (got_za == 1) {
    unsigned char motor_dir = 0;
    FocusA.run(0, 0);
    if (za_dist < 0) {
      za_dist = -za_dist;
      motor_dir = 1;
    }
    FocusA.setMaxSpeed(motor_speed);
    FocusA.move(motor_dir, za_dist);
    motor_busy[0] = motor_busy[0] + 1;
  }
  if (got_zb == 1) {
    unsigned char motor_dir = 0;
    FocusB.run(0, 0);
    if (zb_dist < 0) {
      zb_dist = -zb_dist;
      motor_dir = 1;
    }
    FocusB.setMaxSpeed(motor_speed);
    FocusB.move(motor_dir, zb_dist);
    motor_busy[1] = motor_busy[1] + 1;
  }
  if (got_o == 1) {
    unsigned char motor_dir = 0;
    ObjA.run(0, 0);
    if (o_dist < 0) {
      o_dist = -o_dist;
      motor_dir = 1;
    }
    ObjA.setMaxSpeed(motor_speed);
    ObjA.move(motor_dir, o_dist);
    motor_busy[2] = motor_busy[2] + 1;
  }
}



// loop() is going to wait to receive a character from the
//  host, then do something based on that character.
void loop() {
  /* Check connection */
  //  dataPacket[0] = 0xf0;
  // SPIXfer2();
  // delay(10);

  //Update all motor control patterns and serial data transmission
  updatePatterns();
 

  // listen for commands
  if ( Serial.available() ) { // if something is available
    char c = Serial.read(); // get it
    //Serial.print(c); // optional: repeat back what I got for debugging

    // store the byte as long as there's room in the buffer.
    // if the buffer is full some data might get lost
    if (sofar < MAX_BUF) buffer[sofar++] = c;
    // if we got a return character (\n) the message is done.
    if (c == '\n') {
      //Serial.print(F("\r\n")); // optional: send back a return for debugging

      // strings must end with a \0.
      buffer[sofar] = 0;
      bool got_end = false;

      //for (int i=0; i<MAX_BUF; i++) {
      //  if (buffer[i]==0) {
      //    got_end = true;
      //  }
      //  if (!got_end) {
      //    processed_command[i] = buffer[i];
      //  } else {
      //    processed_command[i] = 0;
      //  }
      //}
      //processed_command = buffer;
      processCommand(); // do something with the command
      ready();
    }
  }


}

// For ease of reading, we're just going to configure all the boards
//  to the same settings. It's working okay for me.
void configureBoards()
{
  int paramValue;
  Serial.println("Configuring boards...");
  for (int i = 0; i < NUM_BOARDS; i++)
  {
    Serial.println(motor_run_v[i]);
    // Before we do anything, we need to tell each board which SPI
    //  port we're using. Most of the time, there's only the one,
    //  but it's possible for some larger Arduino boards to have more
    //  than one, so don't take it for granted.
    boardIndex[i]->SPIPortConnect(&SPI);

    // Set the Overcurrent Threshold to 6A. The OC detect circuit
    //  is quite sensitive; even if the current is only momentarily
    //  exceeded during acceleration or deceleration, the driver
    //  will shutdown. This is a per channel value; it's useful to
    //  consider worst case, which is startup. These motors have a
    //  1.8 ohm static winding resistance; at 12V, the current will
    //  exceed this limit, so we need to use the KVAL settings (see
    //  below) to trim that value back to a safe level.
    //boardIndex[i]->setOCThreshold(OCD_TH_6000mA);

    // KVAL is a modifier that sets the effective voltage applied
    //  to the motor. KVAL/255 * Vsupply = effective motor voltage.
    //  This lets us hammer the motor harder during some phases
    //  than others, and to use a higher voltage to achieve better
    //  torqure performance even if a motor isn't rated for such a
    //  high current. This system has 3V motors and a 12V supply.
    boardIndex[i]->setRunKVAL(motor_run_v[i]);//192);  // 128/255 * 12V = 6V
    boardIndex[i]->setAccKVAL(motor_acc_v[i]);//192);  // 192/255 * 12V = 9V
    boardIndex[i]->setDecKVAL(motor_dec_v[i]);//192);
    //boardIndex[i]->setHoldKVAL(10);//32);  // 32/255 * 12V = 1.5V
    boardIndex[i]->setHoldKVAL(motor_hold_v[i]);//32);
    // When a move command is issued, max speed is the speed the
    //  motor tops out at while completing the move, in steps/s
    boardIndex[i]->setMaxSpeed(300);

    // Acceleration and deceleration in steps/s/s. Increasing this
    //  value makes the motor reach its full speed more quickly,
    //  at the cost of possibly causing it to slip and miss steps.
    boardIndex[i]->setAcc(motor_acc[i]);
    boardIndex[i]->setDec(motor_dec[i]);

  }
}

// Reads back the "config" register from each board in the series.
//  This should be 0x2e88 after a reset of the Autodriver board, or
//  of the control board (as it resets the Autodriver at startup).
//  A reading of 0x0000 means something is wrong with your hardware.
void getBoardConfigurations()
{
  int paramValue;
  Serial.println("Board configurations:");
  for (int i = 0; i < NUM_BOARDS ; i++)
  {
    // It's nice to know if our board is connected okay. We can read
    //  the config register and print the result; it should be 0x2e88
    //  on startup.
    paramValue = boardIndex[i]->getParam(CONFIG);
    Serial.print("Config value: ");
    Serial.println(paramValue, HEX);
  }
}