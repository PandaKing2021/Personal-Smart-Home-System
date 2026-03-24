import mysql.connector
import socket
import _thread
import time
from MyComm import *

# 连接mysql的连接对象、游标对象初始化操作
db, cursor = 0, 0

# database服务器套接字初始化
serverSocket = {"ip": "", "gate_port": ""}


# 初始化mysql服务器函数
def mysql_init():
    global db, cursor
    try:
        # 创建连接对象
        db = mysql.connector.connect(
            host='localhost',
            port=3306,  # 要连接到的数据库端口号，MySQL是3306
            user='root',  # 数据库的用户名，默认为root
            password='1234',  # 数据库的密码，这里设置为1234
            database='user_test',  # 要操作的数据库
            charset='utf8'  # 码表
        )
        cursor = db.cursor()  # 创建数据库游标对象
        print("数据库初始化成功！")
    except Exception as error:
        print("数据库连接出现问题。 原因: ", str(error))


# 服务器基本配置初始化
def get_server_config():
    global serverSocket
    with open("serverConfig.txt") as f:
        serverSocket["ip"] = f.readline().replace("\n", "")
        serverSocket["gate_port"] = f.readline().replace("\n", "")
    print("数据库通信服务器初始化成功，服务器通信套接字：", serverSocket)


def client_handler(cs):
    try:
        while True:
            # 解析从网关处获得的数据
            recv_data = cs.recv(10280).decode("utf-8")
            command_code, data_code, status_code = decode_comm_data(recv_data)  # 指令码

            # 增加：存储用户功能、网关初始化检查
            if command_code == "check_userconfig_illegal":
                print("网关 ", cs, " 正在进行 check_userconfig_illegal 操作: ", end="")
                check_userconfig_illegal(cs, data_code)
            elif command_code == "add_new_user":
                print("网关 ", cs, " 正在进行 add_new_user 操作: ", end="")
                add_new_user(cs, data_code)
            elif command_code == "check_device_id":
                print("网关 ", cs, " 正在进行 check_device_id 操作: ", end="")
                check_device_id(cs, data_code)
    except Exception as error:
        print("与网关 ", cs, " 通信出现错误，请重启对应网关！ 原因: ", error)
    finally:
        cs.close()
        _thread.exit()


# 与绑定的各个网关通信进程
def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((serverSocket["ip"], int(serverSocket["gate_port"])))
    s.listen(1000)

    while True:
        cs, addr = s.accept()
        print("网关 ", addr, " 已经连接到服务器。")

        # 为新连接至服务器的网关开启一条线程
        _thread.start_new_thread(client_handler, (cs,))
        time.sleep(1)


# 数据库增加用户函数
# 向users数据表中增加元素
# data_code 指的是 需要增加的用户信息
def add_new_user(cs, data_code):
    global db, cursor
    send_to_gate_op = "add_new_user"
    # 解析用户数据
    to_add_username, to_add_password, to_add_device_key = decode_user_data(data_code)

    # 存入数据库逻辑
    try:
        # 执行数据库命令
        # 命令行 1
        sql_command = ("insert into users_data (username,password,owned_device_key) "
                       "values (%s,%s,%s)")
        cursor.execute(sql_command, (to_add_username, to_add_password, to_add_device_key))
        insert_status = cursor.rowcount

        # 命令行 2
        sql_command = ("update device_key "
                       "set owned_by_user = %s "
                       "where key_id = %s")
        cursor.execute(sql_command, (to_add_username, to_add_device_key))

        # 命令行 3
        sql_command = ("update device_key "
                       "set is_used = 1 "
                       "where owned_by_user = %s")
        cursor.execute(sql_command, (to_add_username,))

        db.commit()

        if insert_status != 0:
            print(f"更新用户信息成功！ 操作：INSERT。")
            cs.send(format_comm_data_string(send_to_gate_op, "NULL", 1).encode("utf-8"))  # 向网关发送状态数据
        else:
            print("更新用户信息失败。 操作：INSERT。 原因： 未插入数据，可能是由于主键或唯一键冲突。")
            cs.send(format_comm_data_string(send_to_gate_op, "NULL", 0).encode("utf-8"))
    except Exception as error:
        print("更新用户信息失败。 操作：INSERT。 原因： ", error)
        cs.send(format_comm_data_string(send_to_gate_op, error, 2).encode("utf-8"))


# 网关初始化时，检索用户配置表是否合法
def check_userconfig_illegal(cs, data_code):
    global db, cursor
    send_to_gate_op = "check_userconfig_illegal"
    # 解析用户数据
    check_username, check_password, check_device_key = decode_user_data(data_code)

    try:
        sql_command = ("select * from users_data "
                       "where username = %s "
                       "and password = %s "
                       "and owned_device_key = %s")
        cursor.execute(sql_command, (check_username, check_password, check_device_key))
        result = cursor.fetchall()

        if result:  # 1
            print(f"网关本地用户配置正常。 操作：SELECT。 ")
            cs.send(format_comm_data_string(send_to_gate_op, "NULL", 1).encode("utf-8"))
        elif not result:  # 0
            print(f"网关本地用户配置异常。 操作：SELECT。原因： 用户未注册 或 网关配置非法改动。 原因： ", end="")
            cs.send(format_comm_data_string(send_to_gate_op, "NULL", 0).encode("utf-8"))

            # 修改本地配置文件逻辑
            # 按用户名查询所用的用户名是否存在
            sql_command = ("select * from users_data "
                           "where username = %s")
            cursor.execute(sql_command, (check_username,))
            result = cursor.fetchall()

            if result:
                print(f"网关配置非法改动，正在进行修正...")
                check_username, check_password, check_device_key = result[0]
                cs.send(format_comm_data_string(send_to_gate_op, format_userdata_string(check_username, check_password,
                                                                                        check_device_key), 1).encode(
                    "utf-8"))
                print(f"网关配置修正完毕。")
            elif not result:
                print(f"用户未注册")
                cs.send(format_comm_data_string(send_to_gate_op, "NULL", 0).encode("utf-8"))

    except Exception as error:  # 2
        print(f"数据库服务器发生异常。 操作：SELECT。 原因: ", error)
        cs.send(format_comm_data_string(send_to_gate_op, error, 2).encode("utf-8"))


# 网关初始化时，本地配置的key接收对应的device数据
def check_device_id(cs, data_code):
    global db, cursor
    send_to_gate_op = "check_device_id"
    curr_device_key = data_code

    try:
        sql_command = ("select device_name from device_data "
                       "where bind_device_key = %s")
        cursor.execute(sql_command, (curr_device_key,))
        results = cursor.fetchall()

        device_list = ''
        for result in results:
            device_list += result[0] + "+"

        cs.send(format_comm_data_string(send_to_gate_op, device_list, 1).encode("utf-8"))

    except Exception as error:
        print(f"数据库服务器发生异常。 操作：SELECT。 原因: ", error)
        cs.send(format_comm_data_string(send_to_gate_op, error, 0).encode("utf-8"))


def loop():
    while True:
        pass


def main():
    # 初始化数据库服务器配置
    mysql_init()
    get_server_config()

    # 开始与网关进行通信
    _thread.start_new_thread(start_server, ())

    loop()


if __name__ == "__main__":
    main()
