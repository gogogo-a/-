#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}===== 租房系统启动脚本 =====${NC}"

# 检查必要依赖
check_dependency() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}错误: $2未安装，请先安装$2${NC}"
        exit 1
    fi
}

check_dependency docker "Docker"
check_dependency docker-compose "Docker Compose"
check_dependency python3 "Python3"

# 准备Python环境
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建Python虚拟环境...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}虚拟环境创建成功${NC}"
fi

# 激活虚拟环境并安装依赖
echo -e "${YELLOW}激活虚拟环境并安装依赖...${NC}"
source venv/bin/activate
pip install -r requirements.txt
pip install cryptography pymysql redis

# 启动Docker容器
echo -e "${YELLOW}启动Docker容器...${NC}"
docker-compose down --remove-orphans  # 先停止所有容器
docker-compose up -d

# 等待服务启动
echo -e "${YELLOW}等待数据库服务启动...${NC}"
sleep 20

# 设置MySQL主从复制
echo -e "${YELLOW}设置MySQL主从复制...${NC}"
./setup_replication.sh

# 检查服务连接
check_mysql_connection() {
    echo -e "${YELLOW}检查$1连接...${NC}"
    if ! docker exec -i $2 mysql -uroot -prootpassword -e "SELECT 1" &> /dev/null; then
        echo -e "${RED}错误: 无法连接到$1，请检查Docker容器${NC}"
        return 1
    fi
    echo -e "${GREEN}$1连接成功${NC}"
    return 0
}

check_redis_connection() {
    echo -e "${YELLOW}检查$1连接...${NC}"
    if ! docker exec -i $2 redis-cli $3 ping &> /dev/null; then
        echo -e "${RED}错误: 无法连接到$1，请检查Docker容器${NC}"
        return 1
    fi
    echo -e "${GREEN}$1连接成功${NC}"
    return 0
}

# 检查MySQL连接
check_mysql_connection "MySQL节点1" "mysql-node1" || exit 1
check_mysql_connection "MySQL节点2" "mysql-node2" || exit 1

# 检查ProxySQL连接
echo -e "${YELLOW}检查ProxySQL连接...${NC}"
if ! docker exec -i proxysql mysql -uadmin -padmin -h127.0.0.1 -P6032 -e "SELECT 1" &> /dev/null; then
    echo -e "${YELLOW}ProxySQL管理接口不可用，尝试初始化...${NC}"
    sleep 10
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

# 检查Redis连接
check_redis_connection "Redis主节点" "redis-master" "-a redis123" || exit 1
check_redis_connection "Redis从节点1" "redis-slave-1" "-a redis123" || exit 1
check_redis_connection "Redis哨兵1" "redis-sentinel-1" "-p 26379" || exit 1

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