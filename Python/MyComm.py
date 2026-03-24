# 网关与数据库服务器的通信格式
# 通信格式："指令码 | 数据码 | 状态码(一般为0或者1)" ， 通信单元分隔符"|"
# eg: 1.网关to服务器 需要存储新用户: add_new_user | {UserDetail} | 1
#       UserDetail: username + password + deviceKey , 数据码分隔符"+"
#       服务器to网关 成功: add_new_user | "NULL" | 1   失败: add_new_user | "NULL" | 0
#     2.网关to服务器 网关初始化时检查UserConfig.txt的合法性: check_user_illegal | {UserDetail} | 1
#       服务器to网关 合法: check_user_illegal | "NULL" | 1  非法: check_user_illegal | "NULL" | 0

# 网关与数据库服务器的用户格式
# 用户格式："用户名 + 密码 + 设备id" ， 用户单元分隔符"+"


# 整合通信字符串
def format_comm_data_string(operation, data, status_code):
    operation, data, status_code = str(operation), str(data), str(status_code)
    return operation + "|" + data + "|" + status_code


# 整合用户单元字符串
def format_userdata_string(username, password, device_key):
    username, password, device_key = str(username), str(password), str(device_key)
    return username + "+" + password + "+" + device_key


# 解包通信字符串
def decode_comm_data(to_decode_data):
    operation, data, status_code = to_decode_data.split("|")
    return operation, data, status_code


# 解包用户单元字符串
def decode_user_data(to_decode_data):
    username, password, device_key = to_decode_data.split("+")
    return username, password, device_key
