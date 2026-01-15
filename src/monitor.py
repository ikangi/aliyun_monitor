# -*- coding: utf-8 -*-
import json
import sys
import logging
import os
import requests
from logging.handlers import TimedRotatingFileHandler
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkecs.request.v20140526.StartInstanceRequest import StartInstanceRequest
from aliyunsdkecs.request.v20140526.StopInstanceRequest import StopInstanceRequest
from aliyunsdkecs.request.v20140526.DescribeInstancesRequest import DescribeInstancesRequest

# 配置文件路径
CONFIG_FILE = '/opt/scripts/config.json'
LOG_FILE = '/opt/scripts/monitor.log'

# 初始化日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = TimedRotatingFileHandler(LOG_FILE, when='D', interval=1, backupCount=7, encoding='utf-8')
    handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    logger.addHandler(handler)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        logger.error("配置文件 config.json 不存在")
        sys.exit(1)
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def send_tg_alert(tg_conf, title, message, color_status):
    if not tg_conf.get('bot_token') or not tg_conf.get('chat_id'):
        return
    icon = "✅" if color_status == "green" else "🚨"
    try:
        url = f"https://api.telegram.org/bot{tg_conf['bot_token']}/sendMessage"
        text = f"{icon} *[{title}]*\n\n{message}"
        data = {"chat_id": tg_conf['chat_id'], "text": text, "parse_mode": "Markdown"}
        requests.post(url, json=data, timeout=5)
    except Exception as e:
        logger.error(f"TG发送失败: {e}")

def check_and_act(user, tg_conf):
    try:
        client = AcsClient(user['ak'], user['sk'], user['region'])
        
        # 1. 获取流量
        req_traffic = CommonRequest()
        req_traffic.set_domain('cdt.aliyuncs.com')
        req_traffic.set_version('2021-08-13')
        req_traffic.set_action_name('ListCdtInternetTraffic')
        req_traffic.set_method('POST')
        resp_traffic = client.do_action_with_exception(req_traffic)
        data_traffic = json.loads(resp_traffic.decode('utf-8'))
        total_bytes = sum(d.get('Traffic', 0) for d in data_traffic.get('TrafficDetails', []))
        curr_gb = total_bytes / (1024 ** 3)
        
        # 2. 获取实例状态
        req_ecs = DescribeInstancesRequest()
        req_ecs.set_InstanceIds(json.dumps([user['instance_id']]))
        resp_ecs = client.do_action_with_exception(req_ecs)
        data_ecs = json.loads(resp_ecs.decode('utf-8'))
        instances = data_ecs.get("Instances", {}).get("Instance", [])
        
        if not instances:
            logger.error(f"[{user['name']}] 未找到实例: {user['instance_id']}")
            return 
        status = instances[0].get("Status")
        
        # 3. 决策
        limit = user.get('traffic_limit', 180)
        
        if curr_gb < limit:
            if status == "Stopped":
                logger.info(f"[{user['name']}] 流量安全，正在启动...")
                start_req = StartInstanceRequest()
                start_req.set_InstanceId(user['instance_id'])
                client.do_action_with_exception(start_req)
                msg = f"机器: {user['name']}\n当前流量: {curr_gb:.2f}GB\n动作: 恢复运行"
                send_tg_alert(tg_conf, "恢复监控", msg, "green")
            else:
                logger.info(f"[{user['name']}] 状态正常 - {curr_gb:.2f}GB")
        else:
            if status == "Running":
                logger.info(f"[{user['name']}] 流量超标，正在停止...")
                stop_req = StopInstanceRequest()
                stop_req.set_InstanceId(user['instance_id'])
                client.do_action_with_exception(stop_req)
                msg = f"机器: {user['name']}\n当前流量: {curr_gb:.2f}GB\n动作: 强制止损关机"
                send_tg_alert(tg_conf, "流量预警", msg, "red")
            else:
                logger.info(f"[{user['name']}] 已停止止损 - {curr_gb:.2f}GB")
    except Exception as e:
        logger.error(f"[{user['name']}] 检查出错: {e}")

def main():
    config = load_config()
    for user in config.get('users', []):
        check_and_act(user, config.get('telegram', {}))

if __name__ == "__main__":
    main()
