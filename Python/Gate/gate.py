import warnings
import paho.mqtt.client as mqtt
import mysql.connector
import socket
import time
import datetime
import json
import _thread
import hashlib
import hmac
import logging
from MyComm import *

# 网关配置初始化
# isServer:source(sensor),android  isClient:databaseServer
gate_socket = {"ip": "", "source_port": "", "android_port": ""}
db_server_socket = {"ip": "", "db_server_port": ""}
gate_db_config = {"user": "", "password": "", "database": ""}
conn = 0
db_socket = 0  # 对于网关而言，需要全程和数据库服务器通信

# 移动应用程序通信必要信息初始化
# 通信信息单元的格式
permitted_user = {"permitted_username": '', "permitted_password": '', "user_device_key": ''}
login_status = 0

# 阿里云初始化
options = {
    'productKey': 'k0gpoX7HaYl',
    'deviceName': 'all_devices',
    'deviceSecret': '96a38823b47d9d310ee2d31f17ac5170',
    'regionId': 'cn-shanghai'
}

HOST = options['productKey'] + '.iot-as-mqtt.' + options['regionId'] + '.aliyuncs.com'
PORT = 1883
PUB_TOPIC = "/sys/" + options['productKey'] + "/" + options['deviceName'] + "/thing/event/property/post";

# 设备节点数据初始化
permitted_device = []
status = {}
preview = {}
door_permission = 0
data_from_source = {"Door_Secur_Card_id": "", "Door_Security_Status": 0, "Light_TH": 0, "Temperature": 0, "Humidity": 0,
                    "Light_CU": 0, "Brightness": 0,
                    "Curtain_status": 1}  # 设备节点数据字典
threshold_data = {"Light_TH": 0, "Temperature": 0, "Humidity": 0, "Brightness": 0}  # 设备节点阈值设置
source_start_flag = 0  # 设备节点开始收集数据


# 初始化日志文件
def init_log_record():
    log_file = './gateLogs.log'
    FORMAT = '[%(asctime)s][%(levelname)s][%(name)s][%(filename)s line %(lineno)d] %(message)s'  # 定义记录格式
    logging.basicConfig(level=logging.INFO,
                        filename=log_file,
                        format=FORMAT)


# 读取网关配置数据
def get_gate_config():
    global gate_socket, db_server_socket, gate_db_config
    with open("GateConfig.txt") as f:
        gate_socket["ip"] = f.readline().replace("\n", "")
        db_server_socket["ip"] = f.readline().replace("\n", "")
        gate_socket["source_port"] = f.readline().replace("\n", "")
        gate_socket["android_port"] = f.readline().replace("\n", "")
        db_server_socket["db_server_port"] = f.readline().replace("\n", "")
        gate_db_config["user"] = f.readline().replace("\n", "")
        gate_db_config["password"] = f.readline().replace("\n", "")
        gate_db_config["database"] = f.readline().replace("\n", "")

    print("网关将会在 地址:", gate_socket["ip"], "上开启，")
    logging.info("网关将会在 地址:" + gate_socket["ip"] + "上开启，")
    print("接收数据源端口号: ", gate_socket["source_port"], " 移动应用程序通信端口号: ", gate_socket["android_port"])
    logging.info("接收数据源端口号: " + gate_socket["source_port"] + " 移动应用程序通信端口号: " + gate_socket["android_port"])
    print("网关即将连接至 地址: ", db_server_socket["ip"], " 端口号: ", db_server_socket["db_server_port"],
          " 的数据库服务器。")
    logging.info("网关即将连接至 地址: " + db_server_socket["ip"] + " 端口号: " + db_server_socket["db_server_port"] +
                 " 的数据库服务器。")
    print("网关本地数据库已开启，基本配置情况:  用户名:", gate_db_config["user"], " 密码: ", gate_db_config["password"],
          " 连接至 ",
          gate_db_config["database"], " 。")
    logging.info(
        "网关本地数据库已开启，基本配置情况:  用户名:" + gate_db_config["user"] + " 密码: " + gate_db_config[
            "password"] + " 连接至 " +
        gate_db_config["database"] + " 。")


# 读取本地用户配置数据
def get_user_config():
    global permitted_user
    with open("UserConfig.txt") as f:
        permitted_user["permitted_username"] = f.readline().replace("\n", "")
        permitted_user["permitted_password"] = f.readline().replace("\n", "")
        permitted_user["user_device_key"] = f.readline().replace("\n", "")
    print("允许登录用户信息读取成功！")
    logging.info("允许登录用户信息读取成功！")


# 初始化网关本地数据库，获取数据库连接对象
def init_gate_database_connection():
    global gate_db_config, conn
    try:
        # 创建连接对象，用于第一次的初始化
        conn = mysql.connector.connect(
            host='localhost',
            port=3306,  # 要连接到的数据库端口号，MySQL是3306
            user='root',  # 数据库的用户名，默认为root
            password='1234',  # 数据库的密码，这里设置为1234
            charset='utf8'  # 码表
        )
        cursor = conn.cursor()

        # 首次运行的初始化配置
        cursor.execute("CREATE DATABASE IF NOT EXISTS `gate_database`;")  # 初次运行时，建立网关数据库
        cursor.execute("USE `gate_database`;")
        cursor.execute("CREATE TABLE IF NOT EXISTS `gate_database`.`gate_local_data`  ("
                       "`timestamp` datetime NOT NULL,"
                       "`light_th` int NULL,"
                       "`temperature` float(5) NULL,"
                       "`humidity` float(5) NULL,"
                       "`light_cu` int NULL,"
                       "`brightness` float(5) NULL,"
                       "`curtain_status` int NULL);")
        conn.commit()
        conn.close()

        conn = mysql.connector.connect(
            host='localhost',
            port=3306,  # 要连接到的数据库端口号，MySQL是3306
            user='root',  # 数据库的用户名，默认为root
            password='1234',  # 数据库的密码，这里设置为1234
            database='gate_database',
            charset='utf8'  # 码表)
        )
        print("本地数据库初始化成功！")
        logging.info("本地数据库初始化成功！")
    except Exception as error:
        print("本地数据库连接出现问题。 原因: ", error)
        logging.info("本地数据库连接出现问题。 原因: " + str(error))


# 根据设备密钥初始化允许通信设备list
def init_permitted_device():
    global permitted_device, permitted_user, db_socket

    try:
        db_socket.send(format_comm_data_string("check_device_id", permitted_user["user_device_key"], 1).encode("utf-8"))
        op, device_list, status_code = decode_comm_data(db_socket.recv(10280).decode("utf-8"))

        # 获取本账户key对应的device，实现访问设备的控制
        if status_code == "1":
            for device in device_list.split("+"):
                if device != '':
                    permitted_device.append(device)
            print("获取允许设备信息成功！ 允许设备信息列表: ", permitted_device)
            logging.info("获取允许设备信息成功！ 允许设备信息列表: " + str(permitted_device))

        elif status_code == "0":
            print("数据库服务器出现错误！ 原因: ", device_list)
            logging.info("数据库服务器出现错误！ 原因: " + str(device_list))

    except Exception as error:
        print("获取允许设备信息时出现错误！ 原因: ", str(error))
        logging.info("获取允许设备信息时出现错误！ 原因: " + str(error))


# 写入userConfig.txt
def write_to_user_config(username, password, user_device_key):
    with open("UserConfig.txt", "w") as f:
        new_user_data = username + "\n" + password + "\n" + user_device_key
        f.writelines(new_user_data)


# 获取设备节点数据函数，用于从设备节点处接收
# 接收间隔：3秒
def get_from_sensor(cs):
    global threshold_data, status, data_from_source, preview
    status_ac = {'Light_TH': 0}
    status_cu = {'Light_CU': 0, 'Curtain_status': 1}

    print("网关接收线程启动！")
    logging.info("网关接收线程启动！")

    try:
        while True:
            # 获得设备节点数据
            data_recv = cs.recv(10240)

            # 解析设备节点数据
            try:
                data_from_source.update(dict(json.loads(data_recv)))
                del data_from_source["device_key"]
            except:
                pass  # 忽略粘包

            print("从设备节点接收: 空调情况:", data_from_source['Light_TH'],
                  ",温度情况:", data_from_source['Temperature'],
                  ",湿度情况:", data_from_source["Humidity"],
                  ",光感灯情况:", data_from_source["Light_CU"],
                  ",光照情况:", data_from_source["Brightness"],
                  ",窗帘情况:", data_from_source["Curtain_status"], )
            logging.info("从设备节点接收: 空调情况:" + str(data_from_source['Light_TH']) +
                         ",温度情况:" + str(data_from_source['Temperature']) +
                         ",湿度情况:" + str(data_from_source["Humidity"]) +
                         ",光感灯情况:" + str(data_from_source["Light_CU"]) +
                         ",光照情况:" + str(data_from_source["Brightness"]) +
                         ",窗帘情况:" + str(data_from_source["Curtain_status"]))

            try:
                # 网关接收数据存入数据库部分
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO `gate_database`.`gate_local_data` (`timestamp`, `light_th`, `temperature`, "
                               "`humidity`,`light_cu`,`brightness`,`curtain_status`)"
                               "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                               (timestamp, data_from_source["Light_TH"], data_from_source["Temperature"],
                                data_from_source["Humidity"], data_from_source["Light_CU"],
                                data_from_source["Brightness"],
                                data_from_source["Curtain_status"]))
                conn.commit()
            except Exception as error:
                pass

            # 网关功能处理部分
            # 温湿度设备节点处理部分
            if (float(data_from_source['Temperature']) >= float(threshold_data['Temperature']) and
                    float(data_from_source['Humidity']) >= float(threshold_data['Humidity'])):
                if data_from_source['Light_TH'] == 0:
                    status_ac = {'Light_TH': 1}
            else:
                if data_from_source['Light_TH'] == 1:
                    status_ac = {'Light_TH': 0}
            status.update(status_ac)

            # 光照度设备节点处理部分
            if float(data_from_source['Brightness']) >= float(threshold_data['Brightness']):
                if data_from_source['Light_CU'] == 1 and data_from_source['Curtain_status'] == 0:
                    status_cu = {'Light_CU': 0, 'Curtain_status': 1}
            else:
                if data_from_source['Light_CU'] == 0 and data_from_source['Curtain_status'] == 1:
                    status_cu = {'Light_CU': 1, 'Curtain_status': 0}
            status.update(status_cu)

            # 更新字典
            data_from_source.update(status)
            time.sleep(3)

    except Exception as error:
        print("设备节点接收数据出现问题,  原因：", error)
        logging.info("设备节点接收数据出现问题,  原因：" + str(error))


# 设备节点发送数据函数，改变设备节点状态
# 发送间隔: 1秒
def send_to_sensor(cs):
    print("网关发送线程启动")
    logging.info("网关发送线程启动")

    try:
        while True:
            data_send = data_from_source
            cs.send((str(data_send) + '\n').encode())
            print("向设备节点发送: 发送情况:", data_send)
            logging.info("向设备节点发送: 发送情况:" + str(data_send))
            time.sleep(3)
    except Exception as error:
        print("网关接收设备节点线程出现问题！ 原因: ", error)
        logging.info("网关接收设备节点线程出现问题！ 原因: " + str(error))


# 单元设备节点处理线程
def sensor_client_handler(cs):
    global source_start_flag
    try:
        # 获取连接情况，设备节点拒绝连接返回0，否则返回设备节点id
        device_id = cs.recv(1024).decode("utf-8")

        # 阻塞式监听用户门禁是否通过
        if door_permission == 0:
            listen_door_security(device_id, cs)

        if device_id != "0":
            # 连入设备识别码是否是允许设备逻辑
            conn_device = device_id
            connection = check_device_id_with_key(conn_device)

            if connection == 1 and door_permission == 1:  # 如果是允许的设备则开启发送和接收线程
                print("设备节点 名称为：", conn_device, "已经连入网关！")
                logging.info("设备节点 名称为：" + str(conn_device) + "已经连入网关！")

                source_start_flag = 1  # 标记设备节点正在接收数据
                cs.send(b"start\n")
                _thread.start_new_thread(get_from_sensor, (cs,))
                _thread.start_new_thread(send_to_sensor, (cs,))

                loop()
            else:
                if connection != 1 and door_permission == 1:
                    print("连接的设备节点", conn_device, "不属于本用户")
                    logging.info("连接的设备节点" + str(conn_device) + "不属于本用户")
                elif door_permission == 0:
                    print("门禁未被激活，进入失败!")
                    logging.info("门禁未被激活，进入失败!")

        else:
            print('设备节点拒绝连接！')
            logging.info('设备节点拒绝连接！')
    except Exception as error:
        print("网关接收设备节点线程出现问题！ 原因: ", error)
        logging.info("网关接收设备节点线程出现问题！ 原因: " + str(error))
    finally:
        cs.close()
        _thread.exit()


# 检查接入的设备是否存在于允许的设备之中的函数
def check_device_id_with_key(conn_device):
    global permitted_device
    if conn_device in permitted_device:
        return 1
    else:
        return 0


# 设备节点主处理函数
def sensor_handler():
    global gate_socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((gate_socket["ip"], int(gate_socket["source_port"])))
    s.listen(1000)
    print("设备节点通信端口已开启。")
    logging.info("设备节点通信端口已开启。")

    try:
        while True:
            cs, addr = s.accept()
            print('连接设备节点成功，设备节点套接字: ', addr)
            logging.info('连接设备节点成功，设备节点套接字: ' + str(addr))

            _thread.start_new_thread(sensor_client_handler, (cs,))

    except Exception as error:
        print("与设备节点通信出现错误,  原因: ", error)
        logging.info("与设备节点通信出现错误,  原因: " + str(error))
        _thread.exit()


# 阻塞式门禁状态监听函数
def listen_door_security(security_device_data, cs):
    global door_permission, data_from_source

    if "security" in security_device_data:
        print("发现门禁设备接入!")
        logging.info("发现门禁设备接入!")
        while True:
            recv_data = dict(json.loads(cs.recv(1024).decode("utf-8")))
            security_status = recv_data["Door_Security_Status"]  # 获取门禁情况

            # 门禁逻辑判断
            if int(security_status) == 1:
                print("用户门禁通过！")
                logging.info("用户门禁通过！")
                door_permission = 1
                data_from_source.update(recv_data)
                break

            else:
                print("用户门禁未通过！")
                logging.info("用户门禁未通过！")
    else:
        # 其他设备节点接入
        print("发现非门禁设备接入!等待门禁通过。")
        logging.info("发现非门禁设备接入!等待门禁通过。")

        # 阻塞式监听门禁通过
        while True:
            if door_permission == 1:
                break


# 移动应用程序通信主线程
def android_handler():
    global gate_socket
    print("移动应用程序通信端口已开启。")
    logging.info("移动应用程序通信端口已开启。")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((gate_socket["ip"], int(gate_socket["android_port"])))
    s.listen(1000)

    while True:
        cs, addr = s.accept()

        print("移动应用程序 地址为：",addr,"已连接至网关，准备开始通信！")
        logging.info("移动应用程序 地址为："+ str(addr) + "已连接至网关，准备开始通信！")

        _thread.start_new_thread(android_client_handler, (cs,))


# 创建单个移动应用程序设备的子线程
def android_client_handler(cs):
    try:
        recv_from_android_data = cs.recv(40690).decode("utf-8")
        # 解析移动应用程序收到的数据
        android_state, curr_user, status_code = decode_comm_data(recv_from_android_data)

        # 解析用户json数据
        curr_user = json.loads(curr_user)

        if android_state == "login":
            android_login(cs, curr_user)
        elif android_state == "register":
            android_register(cs, curr_user)
            get_user_config()

        loop()
    except Exception as error:
        print("与移动应用程序通信出现错误。 原因： ", error)
        logging.info("与移动应用程序通信出现错误。 原因： " + str(error))
    finally:
        cs.close()
        _thread.exit()


# 移动应用程序登录功能
def android_login(cs, curr_user):
    global permitted_user, login_status
    print("用户正在登录", curr_user)
    logging.info("用户正在登录" + str(curr_user))

    if permitted_user['permitted_username'] == curr_user["account"] and permitted_user['permitted_password'] == \
            curr_user["password"]:
        cs.send(b'1\n')
        login_status = 1
        print("登录成功！登录状态码：", login_status)
        logging.info("登录成功！登录状态码：" + str(login_status))

        # 阻塞式监听设备节点的连接
        listen_if_sensor_connected()

        # 与移动应用程序通信函数
        _thread.start_new_thread(get_from_android, (cs,))
        _thread.start_new_thread(send_to_android, (cs,))

    else:
        cs.send(b'0\n')
        login_status = 0
        print("登录失败！登录状态码：", login_status)
        logging.info("登录失败！登录状态码：" + str(login_status))
        cs.close()


# 向移动应用程序发送设备节点数据
# 发送间隔： 3秒
def send_to_android(cs):
    global data_from_source
    print("移动应用程序发送子线程开启，地址: ", cs)
    logging.info("移动应用程序发送子线程开启，地址: " + str(cs))

    try:
        while True:
            cs.send((str(data_from_source) + "\n").encode("utf-8"))
            print("向移动应用程序发送： ", data_from_source)
            logging.info("向移动应用程序发送： " + str(data_from_source))
            time.sleep(3)
    except Exception as error:
        print("向移动应用程序发送数据时出现错误，发送线程被迫关闭。 原因： ", error)
        logging.info("向移动应用程序发送数据时出现错误，发送线程被迫关闭。 原因： " + str(error))
        _thread.exit()


# 移动应用程序向网关发送数据
# 接收间隔： 3秒
def get_from_android(cs):
    global threshold_data
    print("移动应用程序接收子线程开启，地址: ", cs)
    logging.info("移动应用程序接收子线程开启，地址: " + str(cs))

    try:
        while True:
            recv_from_android_data = cs.recv(40690).decode("utf-8")
            # 解析移动应用程序收到的数据
            android_operation, operation_value, status_code = decode_comm_data(recv_from_android_data)

            # 设备节点阈值处理部分
            # 智能空调处理部分
            if android_operation == "light_th_open":  # 控制灯光的开启与关闭
                threshold_data["Temperature"] = -1
                threshold_data["Humidity"] = -1
                print("从移动应用程序接收: 智能空调 灯光开启。")
                logging.info("从移动应用程序接收: 智能空调 灯光开启。")
            elif android_operation == "light_th_close":
                threshold_data["Temperature"] = 101
                threshold_data["Humidity"] = 101
                print("从移动应用程序接收: 智能空调 灯光关闭。")
                logging.info("从移动应用程序接收: 智能空调 灯光关闭。")
            # 温湿度处理部分
            elif android_operation == "change_temperature_threshold":  # 设置温度阈值
                threshold_data["Temperature"] = operation_value
            elif android_operation == "change_humidity_threshold":  # 设置湿度阈值
                threshold_data["Humidity"] = operation_value

            # 智能窗帘控制处理部分
            # 光照度设备节点部分
            elif android_operation == "curtain_close":  # 控制窗帘的开启与关闭
                threshold_data["Brightness"] = 65535
            elif android_operation == "curtain_open":
                threshold_data["Brightness"] = -2
            elif android_operation == "change_brightness_threshold":
                threshold_data["Brightness"] = operation_value

            # 网关输出设备节点接收信息
            print("从移动应用程序接收: 智能空调 设置温度阈值: ", threshold_data["Temperature"], " 湿度阈值: ",
                  threshold_data["Humidity"], " ; 智能窗帘 设置光照度阈值: ", threshold_data["Brightness"])
            logging.info(
                "从移动应用程序接收: 智能空调 设置温度阈值: " + str(threshold_data["Temperature"]) + " 湿度阈值: " + str(
                    threshold_data["Humidity"]) + " ; 智能窗帘 设置光照度阈值: " + str(threshold_data["Brightness"]))

    except Exception as error:
        print("接收移动应用程序发送来的数据时出现错误，接收线程被迫关闭。 原因： ", error)
        logging.info("接收移动应用程序发送来的数据时出现错误，接收线程被迫关闭。 原因： " + str(error))
        _thread.exit()


# 移动应用程序注册功能
def android_register(cs, given_user):
    global db_socket
    print("用户正在注册", given_user)
    logging.info("用户正在注册" + str(given_user))

    # 将注册的用户信息写入远程mysql服务器,即发送至databaseServer
    db_data_send = format_comm_data_string("add_new_user", format_userdata_string(given_user["account"], given_user[
        "password"], given_user["device_Key"]), 1)

    db_socket.send(db_data_send.encode("utf-8"))
    print("向数据库服务器发送: ", db_data_send)
    logging.info("向数据库服务器发送: " + db_data_send)

    # 接收mysql数据库服务器数据，解析
    db_data_recv = db_socket.recv(10280).decode("utf-8")
    if db_data_recv.split("|")[2] == "1":

        # 处理从移动应用程序发送来的键值对
        write_to_user_config(given_user["account"], given_user["password"], given_user["device_Key"])

        print("注册成功！用户信息已更新。")
        logging.info("注册成功！用户信息已更新。")
        cs.send(b'1\n')
    elif db_data_recv.split("|")[2] == "0" or db_data_recv.split("|")[2] == "2":
        print("注册失败。 原因：", db_data_recv.split("|")[1])
        logging.info("注册失败。 原因：" + db_data_recv.split("|")[1])
        cs.send(b'0\n')


# 阿里云初始化配置函数
def on_connect(client, userdata, flags, rc):
    print("阿里云:Connected with result code " + str(rc))


def on_message(client, userdata, msg):
    print(msg.topic + " " + str(msg.payload))


def hmacsha1(key, msg):
    return hmac.new(key.encode(), msg.encode(), hashlib.sha1).hexdigest()


# 阿里云通信配置函数
def get_aliyun_IoT_client():
    timestamp = str(int(time.time()))
    CLIENT_ID = "paho.py|securemode=3,signmethod=hmacsha1,timestamp=" + timestamp + "|"
    CONTENT_STR_FORMAT = "clientIdpaho.pydeviceName" + options['deviceName'] + "productKey" + options[
        'productKey'] + "timestamp" + timestamp
    # set username/password.
    USER_NAME = options['deviceName'] + "&" + options['productKey']
    PWD = hmacsha1(options['deviceSecret'], CONTENT_STR_FORMAT)
    try:
        client = mqtt.Client(client_id=CLIENT_ID, clean_session=False)
    except Exception:
        pass
    client.username_pw_set(USER_NAME, PWD)
    return client


# 阿里云上传函数部分
# 发送间隔：10秒
def aliyun_connection_init():
    client = get_aliyun_IoT_client()
    client.on_connect = on_connect
    client.on_message = on_message

    global data_from_source, source_start_flag
    timestamp = 0

    # 阻塞式等待设备节点的连接
    listen_if_sensor_connected()

    if source_start_flag == 1:
        print("开始向阿里云服务器发送数据。")
        logging.info("开始向阿里云服务器发送数据。")

        while True:
            timeStamp = timestamp + 1
            try:
                client.connect(HOST, 1883, 300)
                data_from_source = dict(data_from_source)

                # 阿里云payload json设置
                payload_json = {
                    'id': timestamp,
                    'params': {
                        'Light_TH': data_from_source['Light_TH'],
                        'Temperature': data_from_source['Temperature'],
                        'Humidity': data_from_source['Humidity'],
                        'Light_CU': data_from_source['Light_CU'],
                        'Brightness': data_from_source['Brightness'],
                        'Curtain_status': data_from_source['Curtain_status'],
                    },
                    'method': "thing.event.property.post"
                }
                print('向阿里云IoT服务器发送数据:', str(payload_json))
                logging.info('向阿里云IoT服务器发送数据:' + str(payload_json))

                client.publish(PUB_TOPIC, payload=str(payload_json), qos=1)

            except:
                pass

            time.sleep(5)


# 阿里云线程启动
def aliyun_handler():
    print("阿里云上传线程启动。")
    logging.info("阿里云上传线程启动。")
    _thread.start_new_thread(aliyun_connection_init, ())
    time.sleep(2)


# 阻塞式监听设备节点开启状态函数
def listen_if_sensor_connected():
    while True:
        if source_start_flag == 1:
            break
    print("设备节点已连接。")


# 连接数据库服务器
def init_db_server():
    global db_server_socket, db_socket

    try:
        db_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        db_socket.connect((db_server_socket["ip"], int(db_server_socket["db_server_port"])))
        print("与数据库服务器连接成功！")
        logging.info("与数据库服务器连接成功！")
    except Exception:
        print("与数据库服务器连接失败，请检查原因。")
        logging.info("与数据库服务器连接失败，请检查原因。")


# 初始化检查本地用户文件
def init_user_config():
    global permitted_user, db_socket

    get_user_config()
    u, p, k = permitted_user
    to_check_user = format_userdata_string(permitted_user[u], permitted_user[p], permitted_user[k])

    try:
        db_socket.send(format_comm_data_string("check_userconfig_illegal", to_check_user, 1).encode("utf-8"))
        op, data, status_code = decode_comm_data(db_socket.recv(10280).decode("utf-8"))

        if status_code == "1":
            print("本地用户配置正常，用户信息初始化成功！ \n允许登录的用户信息: ", permitted_user)
            logging.info("本地用户配置正常，用户信息初始化成功！ \n允许登录的用户信息: " + str(permitted_user))

        elif status_code == "0":
            print("本地用户配置异常，请重新注册。 原因： ", end="")
            logging.info("本地用户配置异常，请重新注册。 原因： 用户未注册 或 网关配置非法改动。")

            # 修改逻辑
            corr_data = db_socket.recv(10280).decode("utf-8")
            op, corr_data, status_code = decode_comm_data(corr_data)

            if status_code == "0":
                print("用户未注册！")
            elif status_code == "1":
                print("网关配置非法改动! 正在进行纠正...")
                logging.info("网关配置非法改动! 正在进行纠正...")

                # 纠正并写入文件
                corr_user, corr_pwd, corr_key = decode_user_data(corr_data)
                write_to_user_config(corr_user, corr_pwd, corr_key)

                print("网关配置纠正成功！ 请重启网关！")
                logging.info("网关配置纠正成功！ 请重启网关！")

        elif status_code == "2":
            print("网关本地用户配置异常 或 数据库服务器发生异常。请重启网关或检查数据库服务器！")
            logging.info("网关本地用户配置异常 或 数据库服务器发生异常。请重启网关或检查连接情况！")
    except Exception as error:
        print("发生了错误，用户信息初始化失败。请重启网关。 原因: ", error)
        logging.info("发生了错误，用户信息初始化失败。请重启网关。 原因: " + str(error))


# loop保证线程的正常运行
def loop():
    while True:
        pass


def main():
    # 初始化配置
    warnings.filterwarnings('ignore')
    init_log_record()
    get_gate_config()
    init_gate_database_connection()
    init_db_server()
    init_user_config()
    init_permitted_device()

    # 创建并启动各个线程
    _thread.start_new_thread(android_handler, ())
    _thread.start_new_thread(sensor_handler, ())
    _thread.start_new_thread(aliyun_handler, ())

    time.sleep(1)
    print("就绪！")
    logging.info("就绪！")

    loop()


if __name__ == '__main__':
    main()
