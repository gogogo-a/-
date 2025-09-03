#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}===== 租房系统启动脚本 =====${NC}"

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker未安装，请先安装Docker${NC}"
    exit 1
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: Docker Compose未安装，请先安装Docker Compose${NC}"
    exit 1
fi

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: Python3未安装，请先安装Python3${NC}"
    exit 1
fi

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建Python虚拟环境...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}虚拟环境创建成功${NC}"
fi

# 激活虚拟环境
echo -e "${YELLOW}激活虚拟环境...${NC}"
source venv/bin/activate

# 安装依赖
echo -e "${YELLOW}安装Python依赖...${NC}"
pip install -r requirements.txt
pip install cryptography pymysql redis

# 启动Docker容器
echo -e "${YELLOW}启动Docker容器...${NC}"
docker-compose down --remove-orphans  # 先停止所有容器
docker-compose up -d

# 等待MySQL和Redis启动
echo -e "${YELLOW}等待数据库服务启动...${NC}"
sleep 20

# 设置MySQL主从复制
echo -e "${YELLOW}设置MySQL主从复制...${NC}"
./setup_replication.sh

# 检查MySQL节点1连接
echo -e "${YELLOW}检查MySQL节点1连接...${NC}"
if ! docker exec -i mysql-node1 mysql -uroot -prootpassword -e "SELECT 1" &> /dev/null; then
    echo -e "${RED}错误: 无法连接到MySQL节点1，请检查Docker容器${NC}"
    exit 1
fi
echo -e "${GREEN}MySQL节点1连接成功${NC}"

# 检查MySQL节点2连接
echo -e "${YELLOW}检查MySQL节点2连接...${NC}"
if ! docker exec -i mysql-node2 mysql -uroot -prootpassword -e "SELECT 1" &> /dev/null; then
    echo -e "${RED}错误: 无法连接到MySQL节点2，请检查Docker容器${NC}"
    exit 1
fi
echo -e "${GREEN}MySQL节点2连接成功${NC}"

# 检查ProxySQL连接
echo -e "${YELLOW}检查ProxySQL连接...${NC}"
if ! docker exec -i proxysql mysql -uadmin -padmin -h127.0.0.1 -P6032 -e "SELECT 1" &> /dev/null; then
    echo -e "${YELLOW}ProxySQL管理接口不可用，尝试初始化...${NC}"
    # 等待ProxySQL启动
    sleep 10
    # 再次尝试
    if ! docker exec -i proxysql mysql -uadmin -padmin -h127.0.0.1 -P6032 -e "SELECT 1" &> /dev/null; then
        echo -e "${RED}错误: 无法连接到ProxySQL管理接口，请检查Docker容器${NC}"
    else
        echo -e "${GREEN}ProxySQL管理接口连接成功${NC}"
    fi
else
    echo -e "${GREEN}ProxySQL管理接口连接成功${NC}"
fi

# 检查应用数据库连接
echo -e "${YELLOW}检查应用数据库连接...${NC}"
if ! docker exec -i proxysql mysql -uroot -prootpassword -h127.0.0.1 -P6033 -e "SELECT 1" &> /dev/null; then
    echo -e "${RED}错误: 无法连接到应用数据库，请检查ProxySQL配置${NC}"
else
    echo -e "${GREEN}应用数据库连接成功${NC}"
fi

# 检查Redis主节点连接
echo -e "${YELLOW}检查Redis主节点连接...${NC}"
if ! docker exec -i redis-master redis-cli -a redis123 ping &> /dev/null; then
    echo -e "${RED}错误: 无法连接到Redis主节点，请检查Docker容器${NC}"
    exit 1
fi
echo -e "${GREEN}Redis主节点连接成功${NC}"

# 检查Redis从节点连接
echo -e "${YELLOW}检查Redis从节点连接...${NC}"
if ! docker exec -i redis-slave-1 redis-cli -a redis123 ping &> /dev/null; then
    echo -e "${RED}错误: 无法连接到Redis从节点1，请检查Docker容器${NC}"
    exit 1
fi
echo -e "${GREEN}Redis从节点1连接成功${NC}"

# 检查Redis哨兵连接
echo -e "${YELLOW}检查Redis哨兵连接...${NC}"
if ! docker exec -i redis-sentinel-1 redis-cli -p 26379 ping &> /dev/null; then
    echo -e "${RED}错误: 无法连接到Redis哨兵1，请检查Docker容器${NC}"
    exit 1
fi
echo -e "${GREEN}Redis哨兵1连接成功${NC}"

# 创建环境变量配置文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}创建环境变量配置文件...${NC}"
    cat > .env << EOL
# 基本配置
BASE_URL=http://127.0.0.1:9000/
FLASK_ENV=development

# 数据库配置 - 生产环境
DB_HOST=localhost
DB_PORT=6033
DB_USER=root
DB_PASS=rootpassword
DB_NAME=rental_house

# Redis配置 - 生产环境
REDIS_MODE=sentinel
REDIS_MASTER_NAME=mymaster
REDIS_PASSWORD=redis123
REDIS_SENTINEL_1_HOST=localhost
REDIS_SENTINEL_1_PORT=26379
REDIS_SENTINEL_2_HOST=localhost
REDIS_SENTINEL_2_PORT=26380
REDIS_SENTINEL_3_HOST=localhost
REDIS_SENTINEL_3_PORT=26381

# 日志配置
LOG_LEVEL=INFO
LOG_DIR=logs
EOL
    echo -e "${GREEN}环境变量配置文件创建成功${NC}"
fi

# 创建数据迁移配置文件
if [ ! -f ".env.migrate" ]; then
    echo -e "${YELLOW}创建数据迁移配置文件...${NC}"
    cat > .env.migrate << EOL
# 源数据库配置
SOURCE_DB_HOST=localhost
SOURCE_DB_PORT=3306
SOURCE_DB_USER=root
SOURCE_DB_PASSWORD=rootpassword
SOURCE_DB_NAME=rental_house

# 目标数据库配置
TARGET_DB_HOST=localhost
TARGET_DB_PORT=6033
TARGET_DB_USER=root
TARGET_DB_PASSWORD=rootpassword
TARGET_DB_NAME=rental_house
EOL
    echo -e "${GREEN}数据迁移配置文件创建成功${NC}"
fi

# 执行数据迁移
echo -e "${YELLOW}执行数据迁移...${NC}"
python migrate_data.py --import

# 检查数据库中的表
echo -e "${YELLOW}检查数据库中的表...${NC}"
python migrate_data.py --check

# 启动Flask应用
echo -e "${YELLOW}启动Flask应用...${NC}"
export FLASK_APP=app.py
export FLASK_ENV=development
flask run --host=0.0.0.0 --port=9000 &

echo -e "${GREEN}===== 租房系统已启动 =====${NC}"
echo -e "${GREEN}访问地址: http://127.0.0.1:9000/${NC}"
echo -e "${YELLOW}按Ctrl+C停止服务${NC}"

# 保持脚本运行
wait 