#!/bin/bash

echo "等待MySQL服务启动..."
sleep 10

echo "配置主从复制..."

# 获取主节点状态
MASTER_STATUS=$(docker exec mysql-node1 mysql -uroot -prootpassword -e "SHOW MASTER STATUS\G")
MASTER_LOG_FILE=$(echo "$MASTER_STATUS" | grep File | awk '{print $2}')
MASTER_LOG_POS=$(echo "$MASTER_STATUS" | grep Position | awk '{print $2}')

echo "主节点日志文件: $MASTER_LOG_FILE"
echo "主节点日志位置: $MASTER_LOG_POS"

# 配置从节点
docker exec mysql-node2 mysql -uroot -prootpassword -e "STOP SLAVE;"
docker exec mysql-node2 mysql -uroot -prootpassword -e "CHANGE MASTER TO MASTER_HOST='mysql-node1', MASTER_USER='root', MASTER_PASSWORD='rootpassword', MASTER_LOG_FILE='$MASTER_LOG_FILE', MASTER_LOG_POS=$MASTER_LOG_POS;"
docker exec mysql-node2 mysql -uroot -prootpassword -e "START SLAVE;"

# 检查从节点状态
docker exec mysql-node2 mysql -uroot -prootpassword -e "SHOW SLAVE STATUS\G"

echo "主从复制配置完成" 