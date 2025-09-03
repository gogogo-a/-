#!/usr/bin/env python3
import os
import sys
import pymysql
import time
import logging
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('migrate_data')

# 加载环境变量
load_dotenv()

# 数据库配置 - 使用root用户
DB_CONFIG = {
    'host': 'localhost',  # 直接使用localhost
    'port': 6033,  # ProxySQL端口
    'user': 'root',  # 使用root用户
    'password': 'rootpassword',  # 使用rootpassword密码
    'db': 'rental_house',  # 数据库名
    'charset': 'utf8mb4',
    'connect_timeout': 6000,  # 增加连接超时时间
}

def connect_db(config=None):
    """连接到数据库"""
    if config is None:
        config = DB_CONFIG
        
    try:
        # 先尝试连接不指定数据库，如果数据库不存在可以先创建
        try:
            conn = pymysql.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                charset=config['charset'],
                connect_timeout=config.get('connect_timeout', 30),
                cursorclass=pymysql.cursors.DictCursor
            )
            logger.info(f"成功连接到数据库服务器: {config['host']}:{config['port']}")
            
            # 创建数据库（如果不存在）
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config['db']}")
                conn.commit()
                logger.info(f"确保数据库 {config['db']} 存在")
                
                # 使用数据库
                cursor.execute(f"USE {config['db']}")
                
            return conn
        except Exception:
            # 如果无法创建数据库，尝试直接连接到指定数据库
            conn = pymysql.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                db=config['db'],
                charset=config['charset'],
                connect_timeout=config.get('connect_timeout', 30),
                cursorclass=pymysql.cursors.DictCursor
            )
            logger.info(f"成功连接到数据库: {config['host']}:{config['port']}/{config['db']}")
            return conn
    except Exception as e:
        logger.error(f"连接数据库失败: {str(e)}")
        return None

def check_tables():
    """检查数据库中的表"""
    logger.info("检查数据库中的表")
    
    conn = connect_db()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cursor.fetchall()]
            
            if tables:
                logger.info(f"数据库中已有 {len(tables)} 个表: {', '.join(tables)}")
                return True
            else:
                logger.warning("数据库中没有表，需要导入数据")
                return False
    except Exception as e:
        logger.error(f"检查表失败: {str(e)}")
        return False
    finally:
        conn.close()

def disable_read_only_via_docker():
    """通过Docker命令禁用MySQL的只读模式"""
    try:
        import subprocess
        logger.info("尝试通过Docker命令禁用MySQL的只读模式...")
        
        # 对mysql-node1执行命令
        cmd = "docker exec -i mysql-node1 mysql -uroot -prootpassword -e \"SET GLOBAL read_only = 0; SET GLOBAL super_read_only = 0;\""
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("成功通过Docker命令禁用MySQL节点1的只读模式")
            return True
        else:
            logger.error(f"禁用MySQL节点1的只读模式失败: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"执行Docker命令时出错: {str(e)}")
        return False

def import_from_sql_file():
    """从SQL文件导入数据到数据库"""
    logger.info("开始从SQL文件导入数据")
    
    # 先尝试通过Docker命令禁用只读模式
    disable_read_only_via_docker()
    
    # SQL文件路径
    sql_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'house.sql')
    
    # 检查多个可能的路径
    if not os.path.exists(sql_file_path):
        # 尝试其他可能的路径
        alt_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'house.sql'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'house.sql'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts', 'house.sql'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'house.sql'),
            'house.sql'
        ]
        
        for path in alt_paths:
            if os.path.exists(path):
                sql_file_path = path
                logger.info(f"在备选路径找到SQL文件: {path}")
                break
        else:
            logger.error(f"SQL文件不存在，已尝试以下路径: {sql_file_path} 和 {alt_paths}")
            return False
        
    logger.info(f"找到SQL文件: {sql_file_path}")
    file_size_mb = os.path.getsize(sql_file_path) / (1024 * 1024)
    logger.info(f"SQL文件大小: {file_size_mb:.2f} MB")
    
    # 连接数据库
    conn = connect_db()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            # 尝试禁用只读模式
            try:
                logger.info("尝试禁用只读模式...")
                cursor.execute("SET GLOBAL read_only = 0;")
                cursor.execute("SET GLOBAL super_read_only = 0;")
                conn.commit()
                logger.info("已禁用只读模式")
            except Exception as e:
                logger.warning(f"无法禁用只读模式，这可能是正常的: {str(e)}")
            
            # 读取SQL文件内容并执行
            logger.info("开始执行SQL文件...")
            
            # 对于大文件，逐行读取并执行
            with open(sql_file_path, 'r', encoding='utf8') as sql_file:
                # 初始化变量
                current_statement = ""
                success_count = 0
                error_count = 0
                line_count = 0
                
                # 逐行读取
                for line in sql_file:
                    line_count += 1
                    
                    # 跳过注释和空行
                    line = line.strip()
                    if line.startswith('--') or line.startswith('#') or not line:
                        continue
                    
                    # 添加到当前语句
                    current_statement += line + " "
                    
                    # 如果语句结束，执行它
                    if line.endswith(';'):
                        try:
                            cursor.execute(current_statement)
                            conn.commit()
                            success_count += 1
                            
                            # 每执行100条语句记录一次进度
                            if success_count % 100 == 0:
                                logger.info(f"已成功执行 {success_count} 条SQL语句")
                                
                        except Exception as e:
                            error_count += 1
                            error_msg = str(e)
                            
                            # 检查是否是只读错误
                            if "super-read-only" in error_msg or "read-only" in error_msg:
                                logger.error(f"遇到只读错误，尝试禁用只读模式 (行 {line_count}): {error_msg[:200]}...")
                                
                                # 尝试通过Docker命令禁用只读模式
                                if disable_read_only_via_docker():
                                    # 重试当前语句
                                    try:
                                        cursor.execute(current_statement)
                                        conn.commit()
                                        success_count += 1
                                        logger.info(f"禁用只读模式后重试成功")
                                        continue
                                    except Exception as retry_e:
                                        logger.error(f"禁用只读模式后重试失败: {str(retry_e)[:200]}...")
                            
                            logger.error(f"执行SQL语句时出错 (行 {line_count}): {error_msg[:200]}...")
                            conn.rollback()
                        
                        # 重置当前语句
                        current_statement = ""
                
                logger.info(f"SQL文件执行完成: 成功 {success_count} 条语句, 失败 {error_count} 条语句")
                return success_count > 0
    
    except Exception as e:
        logger.error(f"导入SQL文件时出错: {str(e)}")
        return False
    
    finally:
        conn.close()

def show_help():
    """显示帮助信息"""
    print("""
数据导入工具使用说明:

命令行参数:
   --import      从SQL文件导入数据到数据库
   --check       检查数据库中的表
   --help        显示此帮助信息

示例:
   python migrate_data.py --import   # 从SQL文件导入数据
   python migrate_data.py --check    # 检查数据库中的表
""")

if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--check":
            check_tables()
        elif sys.argv[1] == "--import":
            import_from_sql_file()
        elif sys.argv[1] == "--help":
            show_help()
        else:
            logger.error(f"未知参数: {sys.argv[1]}")
            show_help()
    else:
        # 默认执行导入操作
        if not check_tables():
            logger.info("数据库中没有表，自动执行导入操作")
            import_from_sql_file()
        else:
            logger.info("数据库中已有表，如需重新导入请使用 --import 参数")
        show_help() 