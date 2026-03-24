#include <string.h>
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>
#include <Ticker.h>

// 引入OLED必要库
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// 引入基于IIC通信的光照度传感器(BH1750)所必须的库
#include <Wire.h>
#include <BH1750.h>

// 初始化OLED显示屏
#define OLED_X 128
#define OLED_Y 64
Adafruit_SSD1306 oled(OLED_X, OLED_Y, &Wire, -1);

// 定义蜂鸣器
#define buzzerPin D5 // 设置蜂鸣器连接的引脚
#define LEDPIN D6

// 初始化光照度传感器对象
BH1750 lightMeter(0x23);

// 传感器数据初始化
int cur_light = 0; // LED灯状态
int curtain_status = 0;  // 窗帘的开闭窗台
float cur_brightness = 0.0;  // 光照度

int access_status = 0; // 监听门禁通过状态

int recv_light = 0; // 控制LED灯数据
int recv_curtain_status = 0;

int per_curtain_status = 0; // 用于表示上一次窗帘的状态

const char* ssid     = "3-205/E404";
const char* password = "ieqyydxq2021";
const char* host     = "192.168.1.109";  // Python服务器的IP地址
const uint16_t port  = 3000;

Ticker SendTicker;
Ticker GetTicker;
WiFiClient client;

const char* device_id = "A1_curtain";   // 传感器id，用于识别唯一标识

int seconds = 0;

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(LEDPIN,OUTPUT);
  pinMode(buzzerPin, OUTPUT); // 设置蜂鸣器引脚为输出模式
  Serial.begin(115200);

  // 初始化 wifi
  wifiInit(ssid, password);

  // 初始化 OLED显示屏
  oled.begin(SSD1306_SWITCHCAPVCC,0x3C);
  oled.setTextColor(WHITE);  //开像素点发光
  oled.clearDisplay();  //清屏
  oled_string_display(2,16,10,"B: ",0); // 光照度情况
  oled_string_display(2,16,30,"C: ",0); // 窗帘开闭情况
  oled_string_display(2,16,50,"S: ",0); // 距离开机间隔的描述

  // 窗帘驱动电机端口设置
  pinMode(D3, OUTPUT); 
  pinMode(D4, OUTPUT); 

  // 温湿度传感器端口设置
  Wire.begin(D1,D2);
  lightMeter.begin();

  // 初始化板载LED灯
  digitalWrite(LED_BUILTIN, HIGH);

  client.write(device_id); // 发送本设备device_id至Python服务器用于校验

  // 监听门禁是否通过
  listen_door_secur_access();

  // 初始化定期执行函数
  SendTicker.attach(3,sendMsgToGate);
  GetTicker.attach(3,getMsgFromGate);
}

void loop() {
  // 获取光照度传感器数据
  getBrightness();

  // 控制设备
  controlDevice();
  
  delay(1000);
}

// 初始化WiFi连接
void wifiInit(const char *ssid, const char *password){
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED)
    {
      delay(1000);
      Serial.println("WiFi not Connect");
    }
    
    if (!client.connect(host, port)) {
     Serial.println("Connection failed");
     return;
    }

    Serial.println("Connected to AP");
    Serial.print("Connecting to ");
    Serial.println(host);
}

// 监听门禁通过以开始通信
void listen_door_secur_access(){
  Serial.println("Start to listen user accessment...");
  while(1){
     if(client.available()){
      String jsonStr = client.readStringUntil('\n'); //获取数据，去除结尾回车符

      // 当网关发送来开启信号，则更新状态
      if(jsonStr == "start")
        Serial.println("User access successfully! Start to communication.");
        access_status = 1;
        break;
    }
    digitalWrite(D3,LOW); 
    digitalWrite(D4,LOW);
  }
}

void getBrightness(){
  float lux = lightMeter.readLightLevel();
  
  if (isnan(lux)) {
     Serial.println("Error reading brightness value!");
     cur_brightness = 0.0;
    } else {
    cur_brightness = lux;
   }

   oled_float_display(2,42,10,cur_brightness,1);
}

// 网关收发处理部分
void sendMsgToGate(){
  // 创建消息msg的JSON对象
  StaticJsonDocument<200> msg;
  msg["device_id"] = device_id;
  msg["Light_CU"] = cur_light;
  msg["Brightness"] = cur_brightness;
  msg["Curtain_status"] = curtain_status;

  // 序列化JSON对象为字符串，并发送至Python客户端
  String jsonStr;
  serializeJson(msg, jsonStr);
  client.print(jsonStr);
  Serial.println("SEND:"+jsonStr);
}

void getMsgFromGate(){
  if(client.available()){   
    StaticJsonDocument<200> msg;
    String jsonStr = client.readStringUntil('\n'); //获取数据，回车符作为结尾


    // 将消息字符串转换为json对象
    deserializeJson(msg,jsonStr);
  
    // 更新数据
    recv_curtain_status = msg["Curtain_status"];
    recv_light = msg["Light_CU"];
    Serial.println("RECV:"+ jsonStr);
  }
  Serial.println(recv_curtain_status);
}

// 设备控制函数 
void controlDevice(){
  if(recv_curtain_status == 1 && per_curtain_status != 1){ // 1 为开启指令
    Serial.println("Open.");

    buzzerStart(100);
    controlLight(1);

    // 驱动舵机
    digitalWrite(D3,LOW);
    digitalWrite(D4,HIGH);
    delay(500);

    curtain_status = 1;
    per_curtain_status = 1;

    oled_float_display(2,42,30,curtain_status,1);

    digitalWrite(D3,LOW); 
    digitalWrite(D4,LOW);
  }else if(recv_curtain_status == 0 && per_curtain_status != 0){ // 2 为关闭指令
    Serial.println("Closed");

    buzzerStart(100);
    controlLight(0);

    digitalWrite(D3,HIGH);
    digitalWrite(D4,LOW);
    delay(500);

    curtain_status = 0;
    per_curtain_status = 0;

    oled_float_display(2,42,30,curtain_status,1);

    digitalWrite(D3,LOW); 
    digitalWrite(D4,LOW);
  }

  showCurrSeconds();
}

void showCurrSeconds(){
  seconds += 1;
  oled_int_display(2,42,50,seconds,1);
}

// 触发蜂鸣器函数
void buzzerStart(int micro_second){
  digitalWrite(buzzerPin, HIGH); 
  delay(micro_second);
  digitalWrite(buzzerPin, LOW);
}

// 控制室内灯
void controlLight(int ifOpen){
  if(ifOpen == 1 && recv_light == 0){
    digitalWrite(LEDPIN, LOW);
  }else if(ifOpen == 0 && recv_light == 1){
    digitalWrite(LEDPIN, HIGH);
  }
}

// oled 显示函数
void oled_int_display(int textsize,int oled_x,int oled_y,int integer_num,int if_clear){
  if(if_clear == 1)
  oled.setTextColor(WHITE, BLACK);
  oled.setTextSize(textsize);
  oled.setCursor(oled_x,oled_y);
  oled.println(integer_num);
  oled.display(); 
}

void oled_float_display(int textsize,int oled_x,int oled_y,float float_num,int if_clear){
  if(if_clear == 1)
    oled.setTextColor(WHITE, BLACK);
  oled.setTextSize(textsize);
  oled.setCursor(oled_x,oled_y);
  oled.println(float_num);
  oled.display(); 
}

void oled_string_display(int textsize,int oled_x,int oled_y,char* str,int if_clear){
  if(if_clear == 1)
  oled.setTextColor(WHITE, BLACK);
  oled.setTextSize(textsize);//设置字体大小  
  oled.setCursor(oled_x,oled_y);//设置显示位置
  oled.println(str);
  oled.display(); 
}

/*
else if(recv_curtain_status == 0 && per_curtain_status != 0){ // 0 为待机指令
    Serial.println("Paused");

    digitalWrite(D3,LOW); 
    digitalWrite(D4,LOW);

    curtain_status = 0;
    per_curtain_status = 0;

    oled_float_display(2,42,30,curtain_status,1);
    delay(500);
  }
*/
