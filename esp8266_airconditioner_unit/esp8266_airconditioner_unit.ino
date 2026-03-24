#include <string.h>
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>
#include <Ticker.h>

// 引入OLED必要库
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// 引入温湿度传感器(DH11)必要库
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <DHT_U.h>

// 初始化OLED显示屏
#define OLED_X 128
#define OLED_Y 64
Adafruit_SSD1306 oled(OLED_X, OLED_Y, &Wire, -1);

//设置温湿度通信端口数据
#define DHTPIN D5
#define LEDPIN D6 
#define DHTTYPE DHT11
DHT_Unified dht(DHTPIN, DHTTYPE);

int cur_light = 0; // LED灯状态
float cur_temperature = 0.0; // 温度
float cur_humidity = 0.0; // 湿度

int access_status = 0; // 监听门禁通过状态

int recv_light = 0; // 控制LED灯数据

const char* ssid     = "3-205/E404";
const char* password = "ieqyydxq2021";
const char* host     = "192.168.1.107";  // Python服务器的IP地址
const uint16_t port  = 3000;

Ticker SendTicker;
Ticker GetTicker;
Ticker TimeTicker;
WiFiClient client;

const char* device_id = "A1_tem_hum";   // 传感器id，用于识别唯一标识

int seconds = 0;
 
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(LEDPIN,OUTPUT);
  Wire.begin(D1,D2);
  Serial.begin(115200);

  // 初始化 wifi
  wifiInit(ssid, password);

  // 初始化 OLED显示屏
  oled.begin(SSD1306_SWITCHCAPVCC,0x3C);
  oled.setTextColor(WHITE);  //开像素点发光
  oled.clearDisplay();  //清屏
  oled_string_display(2,16,10,"T: ",0); // 温度值情况
  oled_string_display(2,16,30,"H: ",0); // 湿度值情况
  oled_string_display(2,16,50,"S: ",0); // 距离开机间隔的秒数

  // 初始化温湿度传感器
  dht.begin();
  sensor_t sensor;
  dht.temperature().getSensor(&sensor);

  // 初始化板载LED灯
  digitalWrite(LED_BUILTIN, HIGH);

  // 发送本设备device_id到Python服务器
  client.write(device_id);  

  // 监听门禁是否通过
  listen_door_secur_access();

  // 初始化定期执行函数
  SendTicker.attach(3,sendMsgToGate);
  GetTicker.attach(3,getMsgFromGate);
}

void loop() {
  // 获得传感器数据
  getTemperature_Humidity();
  getLightStatus();

  // 计时器
  showCurrSeconds(seconds++);

  delay(1000);
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
  }
}


// 获取温湿度传感数据
void getTemperature_Humidity(){
    sensors_event_t event;
    dht.temperature().getEvent(&event);
    int tem_t = event.temperature;
    dht.humidity().getEvent(&event);
    int hum_t = event.relative_humidity;

    if (isnan(tem_t) && isnan(hum_t)) {
     Serial.println("Error reading temperature or humidty!");
     cur_temperature = 0.0;
     cur_humidity = 0.0;
    } else {
    cur_temperature = tem_t;
    cur_humidity = hum_t;
   }
   
   oled_float_display(2,42,10,cur_temperature,1);
   oled_float_display(2,42,30,cur_humidity,1);
}

// 获取LED灯光数据
void getLightStatus(){
    cur_light = digitalRead(LEDPIN);
}

void sendMsgToGate(){
  // 创建消息msg的JSON对象
  StaticJsonDocument<200> msg;
  msg["device_id"] = device_id;
  msg["Light_TH"] = cur_light;
  msg["Temperature"] = cur_temperature;
  msg["Humidity"] = cur_humidity;

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
    recv_light = msg["Light_TH"];
    Serial.println("RECV:"+ jsonStr);
  }

    // 控制设备
  controlDevice();
}

// 控制空调灯的开关情况
void controlDevice(){
   if(recv_light == 0)
    digitalWrite(LEDPIN, LOW);
  else if(recv_light == 1)
    digitalWrite(LEDPIN, HIGH);
}

void showCurrSeconds(int seconds){
  oled_int_display(2,42,50,seconds,1);
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
