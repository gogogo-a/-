import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(app):
    """设置日志配置"""
    # 确保日志目录存在
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 清除现有的处理器
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 创建文件处理器 - 应用日志
    app_log_file = os.path.join(log_dir, 'app.log')
    app_file_handler = RotatingFileHandler(app_log_file, maxBytes=10485760, backupCount=10)  # 10MB, 最多10个备份
    app_file_handler.setLevel(logging.INFO)
    app_file_handler.setFormatter(formatter)
    root_logger.addHandler(app_file_handler)
    
    # 创建文件处理器 - 缓存命中日志
    cache_log_file = os.path.join(log_dir, 'cache.log')
    cache_file_handler = RotatingFileHandler(cache_log_file, maxBytes=10485760, backupCount=5)  # 10MB, 最多5个备份
    cache_file_handler.setLevel(logging.INFO)
    cache_file_handler.setFormatter(formatter)
    
    # 创建缓存日志过滤器
    class CacheFilter(logging.Filter):
        def filter(self, record):
            return "Redis缓存" in record.getMessage() or "更新Redis" in record.getMessage()
    
    cache_filter = CacheFilter()
    cache_file_handler.addFilter(cache_filter)
    root_logger.addHandler(cache_file_handler)
    
    # 创建文件处理器 - 异步任务日志
    task_log_file = os.path.join(log_dir, 'tasks.log')
    task_file_handler = RotatingFileHandler(task_log_file, maxBytes=10485760, backupCount=5)  # 10MB, 最多5个备份
    task_file_handler.setLevel(logging.INFO)
    task_file_handler.setFormatter(formatter)
    
    # 创建异步任务日志过滤器
    class TaskFilter(logging.Filter):
        def filter(self, record):
            return "异步更新" in record.getMessage() or "async_tasks" in record.name
    
    task_filter = TaskFilter()
    task_file_handler.addFilter(task_filter)
    root_logger.addHandler(task_file_handler)
    
    # 设置Flask日志
    app.logger.setLevel(logging.INFO)
    for handler in root_logger.handlers:
        app.logger.addHandler(handler)
    
    # 禁用Werkzeug默认日志处理器
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)
    
    # 记录应用启动日志
    app.logger.info('应用启动')
    
    return root_logger 