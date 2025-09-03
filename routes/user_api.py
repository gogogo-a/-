from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from models import User, House, Recommend
from settings import db, BASE_URL
import hashlib
from utils import redis_utils, async_tasks
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('user_api')

# 创建蓝图
user_api = Blueprint('user_api', __name__)

# 用户注册
@user_api.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')
    
    if not username or not password:
        return jsonify({'status': 'error', 'message': '用户名和密码不能为空'})
    
    # 检查用户名是否已存在
    if User.query.filter_by(name=username).first():
        return jsonify({'status': 'error', 'message': '用户名已存在'})
    
    # 创建新用户（不加密密码）
    new_user = User(
        name=username,
        password=password,  # 不使用加密
        email=email,
        addr='',
        collect_id='',
        seen_id=''
    )
    
    db.session.add(new_user)
    db.session.commit()
    logger.info(f"新用户注册成功: {username}")
    
    # 登录新用户
    session['user_id'] = new_user.id
    session['user_name'] = new_user.name
    
    return jsonify({'status': 'success', 'message': '注册成功'})

# 用户登录
@user_api.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        return jsonify({'status': 'error', 'message': '用户名和密码不能为空'})
    
    # 查询用户（不使用加密密码）
    user = User.query.filter_by(name=username, password=password).first()
    
    if user:
        # 登录成功，保存用户信息到session
        session['user_id'] = user.id
        session['user_name'] = user.name
        logger.info(f"用户登录成功: {username}")
        return jsonify({'status': 'success', 'message': '登录成功'})
    else:
        logger.info(f"用户登录失败: {username}")
        return jsonify({'status': 'error', 'message': '用户名或密码错误'})

# 用户退出
@user_api.route('/logout')
def logout():
    # 清除session
    if 'user_name' in session:
        logger.info(f"用户退出登录: {session['user_name']}")
    session.pop('user_id', None)
    session.pop('user_name', None)
    return jsonify({'status': 'success', 'message': '退出成功', 'valid': '1'})

# 用户中心页面
@user_api.route('/user/<username>')
def user_page(username):
    # 检查用户是否登录
    if 'user_id' not in session:
        return redirect(url_for('house_api.index'))
    
    user_id = session['user_id']
    user = User.query.get_or_404(user_id)
    
    # 获取收藏的房源
    collected_houses = []
    
    # 尝试从Redis获取收藏列表
    collection_ids = redis_utils.get_user_collection(user_id)
    
    if collection_ids is None:
        # Redis中没有数据，从数据库获取
        logger.info(f"Redis缓存未命中: 用户 {user_id} 收藏列表")
        if user.collect_id:
            collect_ids = user.collect_id.split(',')
            collected_houses = House.query.filter(House.id.in_(collect_ids)).all()
            
            # 缓存到Redis
            redis_utils.cache_user_collection(user_id, collect_ids)
            logger.info(f"更新Redis缓存: 用户 {user_id} 收藏列表")
    else:
        # 使用Redis中的数据
        logger.info(f"Redis缓存命中: 用户 {user_id} 收藏列表")
        if collection_ids:
            collected_houses = House.query.filter(House.id.in_(collection_ids)).all()
    
    # 获取浏览历史
    history_houses = []
    
    # 尝试从Redis获取浏览历史
    history_ids = redis_utils.get_user_history(user_id)
    
    if history_ids is None:
        # Redis中没有数据，从数据库获取
        logger.info(f"Redis缓存未命中: 用户 {user_id} 浏览历史")
        if user.seen_id:
            seen_ids = user.seen_id.split(',')
            history_houses = House.query.filter(House.id.in_(seen_ids)).all()
            
            # 缓存到Redis
            redis_utils.cache_user_history(user_id, seen_ids)
            logger.info(f"更新Redis缓存: 用户 {user_id} 浏览历史")
    else:
        # 使用Redis中的数据
        logger.info(f"Redis缓存命中: 用户 {user_id} 浏览历史")
        if history_ids:
            history_houses = House.query.filter(House.id.in_(history_ids)).all()
    
    # 获取推荐房源
    recommend_houses = []
    
    # 尝试从Redis获取推荐数据
    recommends_data = redis_utils.get_user_recommend(user_id)
    
    if recommends_data is None:
        # Redis中没有数据，从数据库获取
        logger.info(f"Redis缓存未命中: 用户 {user_id} 推荐数据")
        recommends = Recommend.query.filter_by(user_id=user_id).order_by(Recommend.score.desc()).limit(3).all()
        
        for rec in recommends:
            house = House.query.get(rec.house_id)
            if house:
                recommend_houses.append(house)
        
        # 缓存到Redis
        redis_utils.cache_user_recommend(user_id, recommends)
        logger.info(f"更新Redis缓存: 用户 {user_id} 推荐数据")
    else:
        # 使用Redis中的数据
        logger.info(f"Redis缓存命中: 用户 {user_id} 推荐数据")
        for rec in recommends_data:
            house = House.query.get(rec['house_id'])
            if house:
                recommend_houses.append(house)
    
    return render_template('user_page.html', 
                           user=user, 
                           collected_houses=collected_houses, 
                           history_houses=history_houses,
                           recommend_houses=recommend_houses)

# 修改用户信息 - 用户名
@user_api.route('/modify/userinfo/name', methods=['POST'])
def modify_user_name():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': '请先登录'})
    
    user_id = session['user_id']
    user = User.query.get_or_404(user_id)
    
    name = request.form.get('name')
    if not name:
        return jsonify({'status': 'error', 'message': '用户名不能为空'})
    
    # 检查用户名是否已存在
    if User.query.filter(User.name == name, User.id != user_id).first():
        return jsonify({'status': 'error', 'message': '用户名已存在'})
    
    old_name = user.name
    user.name = name
    session['user_name'] = name
    db.session.commit()
    logger.info(f"用户修改用户名: {old_name} -> {name}")
    
    return jsonify({'status': 'success', 'message': '用户名修改成功', 'ok': '1'})

# 修改用户信息 - 地址
@user_api.route('/modify/userinfo/addr', methods=['POST'])
def modify_user_addr():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': '请先登录'})
    
    user_id = session['user_id']
    user = User.query.get_or_404(user_id)
    
    addr = request.form.get('addr')
    if not addr:
        return jsonify({'status': 'error', 'message': '地址不能为空'})
    
    user.addr = addr
    db.session.commit()
    logger.info(f"用户 {user.name} 修改地址: {addr}")
    
    return jsonify({'status': 'success', 'message': '地址修改成功', 'ok': '1'})

# 修改用户信息 - 密码
@user_api.route('/modify/userinfo/pd', methods=['POST'])
def modify_user_password():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': '请先登录'})
    
    user_id = session['user_id']
    user = User.query.get_or_404(user_id)
    
    password = request.form.get('pd')
    if not password:
        return jsonify({'status': 'error', 'message': '密码不能为空'})
    
    # 更新密码（不加密）
    user.password = password
    db.session.commit()
    logger.info(f"用户 {user.name} 修改密码")
    
    return jsonify({'status': 'success', 'message': '密码修改成功', 'ok': '1'})

# 修改用户信息 - 邮箱
@user_api.route('/modify/userinfo/email', methods=['POST'])
def modify_user_email():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': '请先登录'})
    
    user_id = session['user_id']
    user = User.query.get_or_404(user_id)
    
    email = request.form.get('email')
    if not email:
        return jsonify({'status': 'error', 'message': '邮箱不能为空'})
    
    user.email = email
    db.session.commit()
    logger.info(f"用户 {user.name} 修改邮箱: {email}")
    
    return jsonify({'status': 'success', 'message': '邮箱修改成功', 'ok': '1'})

# 删除浏览记录
@user_api.route('/del_record', methods=['POST'])
def del_record():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': '请先登录'})
    
    user_id = session['user_id']
    user = User.query.get_or_404(user_id)
    
    # 清空浏览记录（先清空MySQL，再清空Redis）
    user.seen_id = ''
    db.session.commit()
    redis_utils.cache_user_history(user_id, [])
    logger.info(f"用户 {user.name} 清空浏览记录")
    
    return jsonify({'status': 'success', 'message': '浏览记录已清空', 'valid': '1'})

# 取消收藏
@user_api.route('/collect_off', methods=['POST'])
def collect_off():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': '请先登录'})
    
    user_id = session['user_id']
    user = User.query.get_or_404(user_id)
    
    house_id = request.form.get('house_id')
    if not house_id:
        return jsonify({'status': 'error', 'message': '参数错误'})
    
    # 异步更新收藏（先更新MySQL，再更新Redis）
    async_tasks.async_update_user_collection(user_id, house_id, 'remove')
    logger.info(f"用户 {user.name} 取消收藏: {house_id}")
    
    return jsonify({'status': 'success', 'message': '取消收藏成功', 'valid': '1'})

# 记录浏览历史
@user_api.route('/record_view/<int:house_id>')
def record_view(house_id):
    # 检查用户是否登录
    if 'user_id' not in session:
        return jsonify({'status': 'success'})
    
    user_id = session['user_id']
    
    # 异步更新浏览历史（先更新MySQL，再更新Redis）
    async_tasks.async_update_user_history(user_id, house_id)
    logger.info(f"异步更新: 用户 {user_id} 浏览历史 {house_id}")
    
    # 异步更新推荐数据
    async_tasks.async_update_user_recommend(user_id, house_id)
    logger.info(f"异步更新: 用户 {user_id} 推荐数据 {house_id}")
    
    return jsonify({'status': 'success'}) 