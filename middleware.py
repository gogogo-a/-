import time
from functools import wraps
from flask import request, g
from models import db, RequestLog
import datetime
import json
import traceback
import inspect
import importlib
import os
import sys

# 获取routes目录下的所有模块
def get_route_modules():
    route_modules = []
    routes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'routes')
    
    # 确保routes目录存在
    if not os.path.exists(routes_dir):
        return route_modules
    
    # 获取routes目录下的所有Python文件
    for filename in os.listdir(routes_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            module_name = filename[:-3]  # 去掉.py后缀
            route_modules.append(f"routes.{module_name}")
    
    return route_modules

# 获取routes目录下的所有路由函数
def get_route_functions():
    route_functions = set()
    route_modules = get_route_modules()
    
    for module_name in route_modules:
        try:
            module = importlib.import_module(module_name)
            
            # 获取模块中的所有函数
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and hasattr(obj, '__module__') and obj.__module__ == module_name:
                    route_functions.add(obj)
        except ImportError:
            continue
    
    return route_functions

def log_request_info():
    """记录请求信息的中间件装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 记录请求开始时间
            start_time = time.time()
            
            # 获取请求信息
            ip = request.remote_addr
            user_agent = request.headers.get('User-Agent', '')
            path = request.path
            method = request.method
            user_id = None
            
            # 尝试从session获取用户ID
            from flask import session
            if 'user_id' in session:
                user_id = session['user_id']
            
            # 获取请求参数
            if method == 'GET':
                request_data = dict(request.args)
            else:
                if request.is_json:
                    request_data = request.get_json()
                else:
                    request_data = dict(request.form)
            
            # 执行视图函数
            try:
                response = f(*args, **kwargs)
                status_code = response.status_code if hasattr(response, 'status_code') else 200
                
                # 提取响应数据
                if hasattr(response, 'get_data'):
                    try:
                        response_data = response.get_data(as_text=True)
                    except:
                        response_data = str(response)
                else:
                    response_data = str(response)
                
                # 计算执行时间
                execution_time = time.time() - start_time
                
                # 记录日志
                log_entry = RequestLog(
                    ip_address=ip,
                    user_id=user_id,
                    path=path,
                    method=method,
                    user_agent=user_agent,
                    request_data=json.dumps(request_data, ensure_ascii=False),
                    response_data=response_data[:500],  # 限制长度
                    status_code=status_code,
                    execution_time=execution_time,
                    created_at=datetime.datetime.now()
                )
                
                db.session.add(log_entry)
                db.session.commit()
                
                return response
                
            except Exception as e:
                # 计算执行时间
                execution_time = time.time() - start_time
                
                # 记录错误日志
                error_info = traceback.format_exc()
                log_entry = RequestLog(
                    ip_address=ip,
                    user_id=user_id,
                    path=path,
                    method=method,
                    user_agent=user_agent,
                    request_data=json.dumps(request_data, ensure_ascii=False),
                    response_data=str(e)[:500],
                    status_code=500,
                    execution_time=execution_time,
                    error_info=error_info[:1000],  # 限制长度
                    created_at=datetime.datetime.now()
                )
                
                db.session.add(log_entry)
                db.session.commit()
                
                # 重新抛出异常，让Flask处理
                raise
                
        return decorated_function
    return decorator

def setup_request_logging(app):
    """设置请求日志记录"""
    # 获取routes目录下的所有路由函数
    route_functions = get_route_functions()
    
    # 获取routes目录下的所有蓝图
    route_blueprints = []
    for rule in app.url_map.iter_rules():
        endpoint = rule.endpoint
        if '.' in endpoint:  # 蓝图路由的格式为 blueprint_name.function_name
            blueprint_name = endpoint.split('.')[0]
            if blueprint_name in ['house_api', 'user_api']:  # 只记录这些蓝图的路由
                route_blueprints.append(blueprint_name)
    
    route_blueprints = set(route_blueprints)
    
    @app.before_request
    def before_request():
        g.start_time = time.time()
        
        # 检查当前请求是否是routes目录下的接口
        endpoint = request.endpoint
        if endpoint and '.' in endpoint:
            blueprint_name = endpoint.split('.')[0]
            if blueprint_name not in route_blueprints:
                g.skip_logging = True  # 跳过非routes目录下的接口
            else:
                g.skip_logging = False
        else:
            g.skip_logging = True  # 跳过没有蓝图的路由
    
    @app.after_request
    def after_request(response):
        # 如果请求已经被单独的视图装饰器处理，则跳过
        if hasattr(g, 'logged') and g.logged:
            return response
        
        # 如果不是routes目录下的接口，则跳过
        if hasattr(g, 'skip_logging') and g.skip_logging:
            return response
        
        # 计算执行时间
        execution_time = time.time() - g.start_time
        
        # 获取请求信息
        ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        path = request.path
        method = request.method
        user_id = None
        
        # 尝试从session获取用户ID
        from flask import session
        if 'user_id' in session:
            user_id = session['user_id']
        
        # 获取请求参数
        if method == 'GET':
            request_data = dict(request.args)
        else:
            if request.is_json:
                try:
                    request_data = request.get_json()
                except:
                    request_data = {}
            else:
                request_data = dict(request.form)
        
        # 提取响应数据
        try:
            response_data = response.get_data(as_text=True)
        except:
            response_data = str(response)
        
        # 记录日志
        log_entry = RequestLog(
            ip_address=ip,
            user_id=user_id,
            path=path,
            method=method,
            user_agent=user_agent,
            request_data=json.dumps(request_data, ensure_ascii=False),
            response_data=response_data[:500],  # 限制长度
            status_code=response.status_code,
            execution_time=execution_time,
            created_at=datetime.datetime.now()
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
        return response
    
    @app.teardown_request
    def teardown_request(exception):
        if exception:
            # 如果请求已经被单独的视图装饰器处理，则跳过
            if hasattr(g, 'logged') and g.logged:
                return
            
            # 如果不是routes目录下的接口，则跳过
            if hasattr(g, 'skip_logging') and g.skip_logging:
                return
            
            # 计算执行时间
            execution_time = time.time() - g.start_time if hasattr(g, 'start_time') else 0
            
            # 获取请求信息
            ip = request.remote_addr
            user_agent = request.headers.get('User-Agent', '')
            path = request.path
            method = request.method
            user_id = None
            
            # 尝试从session获取用户ID
            from flask import session
            if 'user_id' in session:
                user_id = session['user_id']
            
            # 获取请求参数
            if method == 'GET':
                request_data = dict(request.args)
            else:
                if request.is_json:
                    try:
                        request_data = request.get_json()
                    except:
                        request_data = {}
                else:
                    request_data = dict(request.form)
            
            # 记录错误日志
            error_info = traceback.format_exc() if exception else None
            log_entry = RequestLog(
                ip_address=ip,
                user_id=user_id,
                path=path,
                method=method,
                user_agent=user_agent,
                request_data=json.dumps(request_data, ensure_ascii=False),
                response_data=str(exception)[:500] if exception else None,
                status_code=500,
                execution_time=execution_time,
                error_info=error_info[:1000] if error_info else None,  # 限制长度
                created_at=datetime.datetime.now()
            )
            
            db.session.add(log_entry)
            try:
                db.session.commit()
            except:
                db.session.rollback() 