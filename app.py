from flask import Flask, render_template, session
from settings import app, db, BASE_URL
from routes.user_api import user_api
from routes.house_api import house_api
from middleware import setup_request_logging
from utils import async_tasks
import os

# 注册蓝图
app.register_blueprint(house_api)
app.register_blueprint(user_api)

# 设置请求日志记录
setup_request_logging(app)

# 全局上下文处理器
@app.context_processor
def inject_user():
    user_info = None
    if 'user_id' in session:
        user_id = session['user_id']
        user_name = session['user_name']
        user_info = {'id': user_id, 'name': user_name}
    return {'user_info': user_info, 'BASE_URL': BASE_URL}

# 错误处理
@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('index.html'), 500

# 初始化Redis缓存和启动异步任务处理线程
def init_app():
    # 缓存初始数据
    async_tasks.cache_initial_data(app)
    
    # 启动异步任务处理线程
    worker = async_tasks.start_task_worker(app)
    
    # 启动定期更新任务
    async_tasks.schedule_periodic_updates()
    
    return worker

if __name__ == '__main__':
    # 确保实例文件夹存在
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # 初始化Redis缓存和启动异步任务处理线程
    worker = init_app()
    
    try:
        # 从BASE_URL中提取端口号
        port = 9000
        app.run(debug=True, host='0.0.0.0', port=port)
    finally:
        # 停止异步任务处理线程
        if worker:
            worker.stop()
