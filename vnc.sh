cat << 'EOF' > install.sh
#!/bin/sh
ROOT_PASS="yiwan123"
TARGET_DEV="/dev/vda"
REPO_URL="http://mirrors.aliyun.com/alpine/latest-stable/main"
COMMUNITY_URL="http://mirrors.aliyun.com/alpine/latest-stable/community"

if [ ! -b "$TARGET_DEV" ]; then
    echo "Error Disk not found"
    exit 1
fi

setup-interfaces -a -r >/dev/null 2>&1

cat << ANSWER > /tmp/answerfile
KEYMAPOPTS="us us"
HOSTNAMEOPTS="-n alpine"
INTERFACESOPTS="auto lo
iface lo inet loopback
auto eth0
iface eth0 inet dhcp
"
DNSOPTS="-d 223.5.5.5 8.8.8.8"
TIMEZONEOPTS="-z PRC"
PROXYOPTS="none"
APKREPOSOPTS="$REPO_URL"
SSHDOPTS="-c openssh"
NTPOPTS="-c chrony"
USEROPTS="-n"
DISKOPTS="-m sys -s 0 $TARGET_DEV"
ANSWER

export ERASE_DISKS="$TARGET_DEV"
setup-alpine -f /tmp/answerfile -e

mount ${TARGET_DEV}2 /mnt 2>/dev/null || mount ${TARGET_DEV}3 /mnt 2>/dev/null

if [ -d "/mnt/etc" ]; then
    echo "root:$ROOT_PASS" | chroot /mnt chpasswd
    sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /mnt/etc/ssh/sshd_config
    echo "$COMMUNITY_URL" >> /mnt/etc/apk/repositories

    cat << 'PHASE2' > /mnt/root/phase2.sh
#!/bin/sh
sleep 5
apk update
apk add curl vim bash
rm /etc/local.d/phase2.start
rm /root/phase2.sh
rc-update del local default
PHASE2
    
    chmod +x /mnt/root/phase2.sh

    cat << 'STARTUP' > /mnt/etc/local.d/phase2.start
#!/bin/sh
/root/phase2.sh
STARTUP
    chmod +x /mnt/etc/local.d/phase2.start
    chroot /mnt /sbin/rc-update add local default > /dev/null 2>&1

    sleep 3
    reboot
else
    exit 1
fi
EOF

chmod +x install.sh
./install.sh
