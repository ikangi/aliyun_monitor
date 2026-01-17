#!/bin/bash
# 注意：首行用 sh 是为了兼容 Alpine 默认环境，脚本内会自动安装并切换 bash
# -------------------------------------------------------------
# 脚本名称: Alpine to Debian 13 (Static IP Fix Version)
# 功能: 自动提取当前网络参数 -> 静态IP安装 -> 杜绝重启失联
# -------------------------------------------------------------

# --- 1. 基础依赖自检与修复 ---
if [ ! -f /bin/bash ]; then
    echo "系统未检测到 Bash，正在自动安装..."
    apk update >/dev/null 2>&1
    apk add bash iproute2 ipcalc grep gawk >/dev/null 2>&1
fi

set -e

# --- 2. 安全性检查 ---
if [ "$(id -u)" != "0" ]; then
    echo "错误：必须使用 Root 用户运行。"
    exit 1
fi

# --- 3. 交互配置 ---
clear
echo "=== Alpine to Debian 全自动安装脚本 (防失联版) ==="
echo "脚本将自动提取当前 IP 配置，执行静态 IP 安装。"
echo ""

# 使用兼容方式获取输入
if [ -z "$PORT" ]; then
    read -p "SSH 端口 [回车默认 22]: " PORT
    PORT=${PORT:-22}
fi
if [ -z "$PASSWORD" ]; then
    read -p "Root 密码 [回车默认 yiwan123]: " PASSWORD
    PASSWORD=${PASSWORD:-yiwan123}
fi

echo ""
echo "配置已确认：端口 $PORT / 密码 $PASSWORD"
echo "5秒后开始全自动安装..."
sleep 5

# --- 4. 核心执行逻辑 ---

echo "[1/5] 提取网络配置..."
# 获取主网卡名称 (通常是 eth0)
MAIN_IFace=$(ip route show | grep default | awk '{print $5}' | head -n1)

# 获取 IP 地址 (例如 192.168.1.100)
MAIN_IP=$(ip -4 addr show $MAIN_IFace | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n 1)

# 获取网关 (例如 192.168.1.1)
MAIN_GATE=$(ip route show default | awk '/default/ {print $3}')

# 获取子网掩码 (需要将 CIDR /24 转为 255.255.255.0)
# 获取 CIDR 数字 (例如 24)
CIDR_NUM=$(ip -4 addr show $MAIN_IFace | grep -oP '(?<=inet\s)\d+(\.\d+){3}/\d+' | head -n 1 | awk -F'/' '{print $2}')
# 计算掩码 (利用 ipcalc)
MAIN_MASK=$(ipcalc -m $MAIN_IP/$CIDR_NUM | cut -d= -f2)

echo "检测到网络配置："
echo "IP: $MAIN_IP"
echo "Gateway: $MAIN_GATE"
echo "Netmask: $MAIN_MASK"

echo "[2/5] 清理磁盘签名与分区..."
sed -i 's/^#\(.*community\)$/\1/' /etc/apk/repositories
apk update >/dev/null 2>&1
apk add curl util-linux parted e2fsprogs grub grub-bios >/dev/null 2>&1
umount /boot 2>/dev/null || true
swapoff -a 2>/dev/null || true

DISK="/dev/vda"

dd if=/dev/zero of=$DISK bs=1K seek=32 count=992 conv=notrunc status=none
dd if=/dev/zero of=$DISK bs=512 seek=1 count=33 conv=notrunc status=none
SECTORS=$(cat /sys/block/vda/size)
dd if=/dev/zero of=$DISK bs=512 seek=$((SECTORS-33)) count=33 conv=notrunc status=none
sync

echo "[3/5] 修复 MBR 引导..."
# 尝试挂载，失败也不影响后续 DD
mount ${DISK}1 /boot 2>/dev/null || true
grub-install --recheck $DISK >/dev/null 2>&1 || true

echo "[4/5] 下载安装脚本..."
wget --no-check-certificate -qO InstallNET.sh 'https://raw.githubusercontent.com/leitbogioro/Tools/master/Linux_reinstall/InstallNET.sh' && chmod a+x InstallNET.sh

echo "[5/5] 启动 Debian 安装程序 (静态IP模式)..."
echo "系统即将重启。请等待 10-15 分钟后使用新密码登录。"

# 运行 InstallNET 并传入静态 IP 参数
# 注意：这里增加了 --ip-addr, --ip-gate, --ip-mask
bash InstallNET.sh \
    -debian 11 \
    -port "${PORT}" \
    -pwd "${PASSWORD}" \
    -mirror "http://deb.debian.org/debian/" \
    --ip-addr "${MAIN_IP}" \
    --ip-gate "${MAIN_GATE}" \
    --ip-mask "${MAIN_MASK}" \
    --cloudkernel "0" \
    --bbr \
    --motd \
    --setdns

# 强制重启
reboot
