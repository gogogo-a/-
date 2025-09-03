from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv
import redis
from redis.sentinel import Sentinel

# 加载环境变量
load_dotenv()
BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:9000/')

# 创建Flask应用
app = Flask(__name__, template_folder='templates', static_folder='static')

# 配置MySQL连接
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key'

# 数据库连接配置
DB_HOST = os.getenv('DB_HOST', 'localhost')  # 默认本地，生产环境使用ProxySQL
DB_PORT = os.getenv('DB_PORT', '6033')       # 使用ProxySQL端口6033
DB_USER = os.getenv('DB_USER', 'root')       # 使用root用户
DB_PASS = os.getenv('DB_PASS', 'rootpassword')   # 使用rootpassword密码
DB_NAME = os.getenv('DB_NAME', 'rental_house')

# 构建数据库URI
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

# 创建SQLAlchemy实例
db = SQLAlchemy(app)

# Redis配置
REDIS_SENTINELS = [
    (os.getenv('REDIS_SENTINEL_1_HOST', 'localhost'), 
     int(os.getenv('REDIS_SENTINEL_1_PORT', 26379))),
    (os.getenv('REDIS_SENTINEL_2_HOST', 'localhost'), 
     int(os.getenv('REDIS_SENTINEL_2_PORT', 26380))),
    (os.getenv('REDIS_SENTINEL_3_HOST', 'localhost'), 
     int(os.getenv('REDIS_SENTINEL_3_PORT', 26381)))
]
REDIS_MASTER_NAME = os.getenv('REDIS_MASTER_NAME', 'mymaster')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', 'redis123')

# 创建Redis哨兵连接
sentinel = Sentinel(REDIS_SENTINELS, socket_timeout=10.0, password=REDIS_PASSWORD)

# 获取Redis主节点连接（用于写操作）
def get_redis_master():
    try:
        # 使用本地端口映射连接Redis主节点
        return redis.Redis(host='localhost', port=6380, password=REDIS_PASSWORD, 
                          socket_timeout=10.0, db=0, decode_responses=True)
    except Exception as e:
        print(f"直接连接Redis主节点失败: {e}")
        # 如果直接连接失败，尝试通过哨兵连接
        return sentinel.master_for(REDIS_MASTER_NAME, socket_timeout=10.0, 
                                  password=REDIS_PASSWORD, db=0, decode_responses=True)

# 获取Redis从节点连接（用于读操作）
def get_redis_slave():
    try:
        # 使用本地端口映射连接Redis从节点1
        return redis.Redis(host='localhost', port=6381, password=REDIS_PASSWORD, 
                          socket_timeout=10.0, db=0, decode_responses=True)
    except Exception as e:
        print(f"直接连接Redis从节点失败: {e}")
        # 如果直接连接失败，尝试通过哨兵连接
        return sentinel.slave_for(REDIS_MASTER_NAME, socket_timeout=10.0, 
                                 password=REDIS_PASSWORD, db=0, decode_responses=True)

# 测试Redis连接
try:
    redis_master = get_redis_master()
    redis_master.ping()
    print("Redis主节点连接成功")
except Exception as e:
    print(f"Redis主节点连接失败: {e}")

try:
    redis_slave = get_redis_slave()
    redis_slave.ping()
    print("Redis从节点连接成功")
except Exception as e:
    print(f"Redis从节点连接失败: {e}")