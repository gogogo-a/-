#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}===== 租房系统停止脚本 =====${NC}"

# 停止Flask应用
echo -e "${YELLOW}停止Flask应用...${NC}"
pkill -f "flask run --host=0.0.0.0 --port=9000"

# 停止Docker容器
echo -e "${YELLOW}停止Docker容器...${NC}"
docker-compose down --remove-orphans

echo -e "${GREEN}===== 租房系统已停止 =====${NC}" 