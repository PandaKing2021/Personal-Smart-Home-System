#include <string.h>
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>
#include <Ticker.h>

// 引入读卡器必要库
#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>

// 引入OLED必要库
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// 初始化OLED显示屏
#define OLED_X 128
#define OLED_Y 64
Adafruit_SSD1306 oled(OLED_X, OLED_Y, &Wire, -1);

// 初始化读卡器引脚
#define RST_PIN   D1
#define SS_PIN    D2

// 初始化蜂鸣器引脚
#define buzzerPin D0 

// 创建新的RFID实例
MFRC522 mfrc522(SS_PIN, RST_PIN);   
MFRC522::MIFARE_Key key;

// 初始化卡uid字符串
String permittedUid = "4341e313";
String cardUid = ""; 
int permitStatus = 0;

const char* ssid     = "3-205/E404";
const char* password = "ieqyydxq2021";
const char* host     = "192.168.1.107";  // Python服务器的IP地址
const uint16_t port  = 3000;

WiFiClient client;

const char* device_id = "A1_door_security";   // 传感器id，用于识别唯一标识
// 注意，门禁设备id内必须包含"security"字样

void setup() {
  SPI.begin();        // SPI开始
  Wire.begin(D3,D4);  // ICC开始
  Serial.begin(115200); 

   // 初始化 wifi
  wifiInit(ssid, password);

  // 初始化 OLED显示屏
  oled.begin(SSD1306_SWITCHCAPVCC,0x3C);
  oled.setTextColor(WHITE);  //开像素点发光
  oled.clearDisplay();  //清屏
  oled_string_display(2,16,30,"S: ",0); // 距离开机间隔的描述

  pinMode(buzzerPin, OUTPUT); // 设置蜂鸣器引脚为输出模式

  mfrc522.PCD_Init();

  client.write(device_id);  // 发送本设备device_id到Python服务器
}

void loop() {
  cardLogic();

  delay(1000);
}

// 卡识别主函数
void cardLogic(){
    if ( ! mfrc522.PICC_IsNewCardPresent()) {
    //Serial.println("没有找到卡");
    return;
  }

   // 选择一张卡
  if ( ! mfrc522.PICC_ReadCardSerial()) {
    Serial.println("没有卡可选");
    return;
  }

  // 显示卡片的详细信息
  Serial.print(F("卡片 UID:"));
  dump_byte_array(mfrc522.uid.uidByte, mfrc522.uid.size);
  Serial.println();
  Serial.print(F("卡片类型: "));
  MFRC522::PICC_Type piccType = mfrc522.PICC_GetType(mfrc522.uid.sak);
  Serial.println(mfrc522.PICC_GetTypeName(piccType));
  
  // 卡片判别
  if(cardUid == permittedUid){
    permitStatus = 1;
    buzzerStart(100);
    oled_string_display(2,42,30,"Allowed",1); // 距离开机间隔的描述
  }else{
    permitStatus = 0;
    buzzerStart(100);
    delay(100);
    buzzerStart(100);
    oled_string_display(2,42,30,"Denied ",1); // 距离开机间隔的描述
  }

  sendMsgToGate();

  // 检查兼容性
  if (piccType != MFRC522::PICC_TYPE_MIFARE_MINI
          &&  piccType != MFRC522::PICC_TYPE_MIFARE_1K
          &&  piccType != MFRC522::PICC_TYPE_MIFARE_4K) {
    Serial.println(F("仅仅适合Mifare Classic卡的读写"));
    return;
  }

  //停止 PICC
  mfrc522.PICC_HaltA();
  //停止加密PCD
  mfrc522.PCD_StopCrypto1();
  
  return;
}

// 向网关发送消息
void sendMsgToGate(){
  StaticJsonDocument<200> msg;
  msg["device_id"] = device_id;
  msg["Door_Security_Status"] = permitStatus;
  msg["Door_Secur_Card_id"] = cardUid;
  
  // 序列化JSON对象为字符串，并发送至Python客户端
  String jsonStr;
  serializeJson(msg, jsonStr);
  client.print(jsonStr);
  Serial.println("SEND:"+jsonStr);
}

// 初始化 wifi 连接
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

// 将字节数组转储为串行的十六进制值
void dump_byte_array(byte *buffer, byte bufferSize) {
  cardUid = "";
  for (byte i = 0; i < bufferSize; i++) {
    Serial.print(buffer[i] < 0x10 ? " 0" : " ");
    Serial.print(buffer[i], HEX);
    cardUid = cardUid + String(buffer[i], HEX);
  }
}

void buzzerStart(int micro_second){
  digitalWrite(buzzerPin, HIGH); 
  delay(micro_second);
  digitalWrite(buzzerPin, LOW);
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
