# -*- coding: utf-8 -*-
import json
import requests
import datetime
import os
import sys
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest

CONFIG_FILE = '/opt/scripts/config.json'

def load_config():
    if not os.path.exists(CONFIG_FILE):
        sys.exit(1)
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def send_tg_report(tg_conf, message):
    if not tg_conf.get('bot_token') or not tg_conf.get('chat_id'):
        return
    try:
        url = f"https://api.telegram.org/bot{tg_conf['bot_token']}/sendMessage"
        data = {"chat_id": tg_conf['chat_id'], "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=data)
    except:
        pass

def get_cdt_traffic(client):
    try:
        request = CommonRequest()
        request.set_domain('cdt.aliyuncs.com')
        request.set_version('2021-08-13')
        request.set_action_name('ListCdtInternetTraffic')
        request.set_method('POST')
        response = client.do_action_with_exception(request)
        data = json.loads(response.decode('utf-8'))
        total_bytes = sum(d.get('Traffic', 0) for d in data.get('TrafficDetails', []))
        return total_bytes / (1024 ** 3)
    except:
        return 0.0

def get_current_month_bill(client):
    try:
        billing_cycle = datetime.datetime.now().strftime("%Y-%m")
        request = CommonRequest()
        request.set_domain('business.ap-southeast-1.aliyuncs.com') # 强制国际站接口
        request.set_version('2017-12-14')
        request.set_action_name('QueryBillOverview')
        request.add_query_param('BillingCycle', billing_cycle)
        
        response = client.do_action_with_exception(request)
        data = json.loads(response.decode('utf-8'))
        items = data.get('Data', {}).get('Items', {}).get('Item', [])
        total_money = sum(item.get('PretaxAmount', 0) for item in items)
        return total_money, billing_cycle
    except Exception as e:
        print(f"BSS Error: {e}")
        return -1, "Error"

def main():
    config = load_config()
    users = config.get('users', [])
    tg_conf = config.get('telegram', {})
    
    report_lines = []
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    report_lines.append(f"📊 *[阿里云多账号 - 每日财报]*")
    report_lines.append(f"📅 日期: {today}\n")

    for user in users:
        try:
            client = AcsClient(user['ak'], user['sk'], user['region'])
            traffic_gb = get_cdt_traffic(client)
            quota = user.get('quota', 200)
            percent = (traffic_gb / quota) * 100
            bill_amount, _ = get_current_month_bill(client)
            
            if bill_amount == -1:
                bill_str = "查询失败"
            else:
                bill_str = f"$\{bill_amount:.2f}"

            status_icon = "✅" if (traffic_gb < quota and bill_amount < 1.0) else "⚠️"
            user_report = (
                f"👤 *{user['name']}*\n"
                f"   📉 流量: {traffic_gb:.2f} GB ({percent:.1f}%)\n"
                f"   💰 账单: *{bill_str}*\n"
                f"   📝 状态: {status_icon}\n"
            )
            report_lines.append(user_report)
        except Exception as e:
            report_lines.append(f"❌ *{user['name']}* 出错: {str(e)}\n")

    final_msg = "\n".join(report_lines)
    send_tg_report(tg_conf, final_msg)

if __name__ == "__main__":
    main()
