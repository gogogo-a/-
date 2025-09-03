from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from models import House, User, Recommend
from settings import db, BASE_URL
import random
from sqlalchemy import func, desc, or_
from predict.price_prediction import predict_price_trend, get_room_type_distribution, get_top_communities, get_price_by_room_type
from utils import redis_utils, async_tasks
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('house_api')

# 创建蓝图
house_api = Blueprint('house_api', __name__)

# 首页路由
@house_api.route('/')
def index():
    # 尝试从Redis获取热点房源
    recommended_houses = redis_utils.get_hot_houses()
    
    if recommended_houses is None:
        # Redis中没有数据，从数据库获取
        logger.info("Redis缓存未命中: 热点房源")
        recommended_houses_db = House.query.order_by(House.page_views.desc()).limit(6).all()
        
        # 缓存到Redis
        redis_utils.cache_hot_houses(recommended_houses_db)
        
        # 转换为字典列表
        recommended_houses = []
        for house in recommended_houses_db:
            recommended_houses.append({
                'id': house.id,
                'title': house.title,
                'price': house.price,
                'area': house.area,
                'rooms': house.rooms,
                'region': house.region,
                'block': house.block,
                'address': house.address
            })
    else:
        logger.info("Redis缓存命中: 热点房源")
    
    # 尝试从Redis获取高浏览量房源
    hot_houses = redis_utils.get_high_view_houses()
    
    if hot_houses is None:
        # Redis中没有数据，从数据库获取
        logger.info("Redis缓存未命中: 高浏览量房源")
        hot_houses_db = House.query.order_by(db.func.random()).limit(4).all()
        
        # 缓存到Redis
        redis_utils.cache_high_view_houses(hot_houses_db)
        
        # 转换为字典列表
        hot_houses = []
        for house in hot_houses_db:
            hot_houses.append({
                'id': house.id,
                'title': house.title,
                'price': house.price,
                'area': house.area,
                'rooms': house.rooms,
                'region': house.region,
                'block': house.block,
                'address': house.address
            })
    else:
        logger.info("Redis缓存命中: 高浏览量房源")
    
    # 获取房源总数
    house_count = House.query.count()
    
    return render_template('index.html', 
                          recommended_houses=recommended_houses, 
                          hot_houses=hot_houses,
                          house_count=house_count)

# 房源详情页
@house_api.route('/house/<int:house_id>')
def house_detail(house_id):
    # 从数据库获取房源详情
    house = House.query.get_or_404(house_id)
    
    # 更新浏览量（先更新MySQL）
    house.page_views += 1
    db.session.commit()
    
    # 更新Redis缓存
    redis_utils.cache_house_detail(house)
    logger.info(f"更新Redis缓存: 房源详情 {house_id}")
    
    # 记录用户浏览历史
    if 'user_id' in session:
        user_id = session['user_id']
        
        # 异步更新用户浏览历史（先更新MySQL，再更新Redis）
        async_tasks.async_update_user_history(user_id, house_id)
        logger.info(f"异步更新: 用户 {user_id} 浏览历史 {house_id}")
        
        # 异步更新推荐数据
        async_tasks.async_update_user_recommend(user_id, house_id)
        logger.info(f"异步更新: 用户 {user_id} 推荐数据 {house_id}")
    
    # 获取相似推荐房源
    similar_houses = House.query.filter(
        House.id != house_id,
        House.region == house.region,
        House.block == house.block
    ).order_by(func.rand()).limit(4).all()
    
    return render_template('detail_page.html', house=house, similar_houses=similar_houses)

# 房源列表页
@house_api.route('/list')
def house_list():
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示的房源数量
    
    # 获取筛选参数
    region = request.args.get('region', '')
    price_min = request.args.get('price_min', '')
    price_max = request.args.get('price_max', '')
    rooms = request.args.get('rooms', '')
    
    # 构建查询
    query = House.query
    
    if region:
        query = query.filter(House.region == region)
    
    if price_min and price_max:
        query = query.filter(House.price >= price_min, House.price <= price_max)
    
    if rooms:
        query = query.filter(House.rooms == rooms)
    
    # 获取房源总数
    total_houses = query.count()
    total_pages = (total_houses + per_page - 1) // per_page  # 计算总页数
    
    # 获取当前页的房源
    houses = query.order_by(House.id).offset((page - 1) * per_page).limit(per_page).all()
    
    return render_template('list.html', houses=houses, current_page=page, total_pages=total_pages)

# 搜索结果页
@house_api.route('/search')
def search_houses():
    keyword = request.args.get('keyword', '')
    search_type = request.args.get('search_type', 'region')
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示的房源数量
    
    # 如果没有关键词，显示空结果页面
    if not keyword:
        return render_template('search_list.html', houses=[], keyword='', current_page=1, total_pages=0)
    
    # 根据搜索类型和关键词搜索房源
    if search_type == 'rooms':
        # 户型搜索 - 处理中文数字和阿拉伯数字
        search_keywords = [keyword]
        
        # 中文数字到阿拉伯数字的映射
        cn_to_arabic = {
            '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
            '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'
        }
        
        # 阿拉伯数字到中文数字的映射
        arabic_to_cn = {v: k for k, v in cn_to_arabic.items()}
        
        # 转换关键词中的数字（如果有）
        converted_keyword = keyword
        for cn, ar in cn_to_arabic.items():
            converted_keyword = converted_keyword.replace(cn, ar)
        
        # 如果转换后的关键词不同于原关键词，添加到搜索关键词列表
        if converted_keyword != keyword:
            search_keywords.append(converted_keyword)
        
        # 转换阿拉伯数字到中文数字
        converted_keyword = keyword
        for ar, cn in arabic_to_cn.items():
            converted_keyword = converted_keyword.replace(ar, cn)
        
        # 如果转换后的关键词不同于原关键词，添加到搜索关键词列表
        if converted_keyword != keyword and converted_keyword not in search_keywords:
            search_keywords.append(converted_keyword)
        
        # 构建查询条件
        conditions = []
        for kw in search_keywords:
            conditions.append(House.rooms.like(f'%{kw}%'))
        
        query = House.query.filter(or_(*conditions))
    else:
        # 地区搜索
        query = House.query.filter(
            or_(
                House.title.like(f'%{keyword}%'),
                House.region.like(f'%{keyword}%'),
                House.block.like(f'%{keyword}%'),
                House.address.like(f'%{keyword}%'),
                House.traffic.like(f'%{keyword}%')
            )
        )
    
    # 获取搜索结果总数
    total_houses = query.count()
    total_pages = (total_houses + per_page - 1) // per_page  # 计算总页数
    
    # 获取当前页的搜索结果
    houses = query.order_by(House.id).offset((page - 1) * per_page).limit(per_page).all()
    
    return render_template('search_list.html', houses=houses, keyword=keyword, current_page=page, total_pages=total_pages)

# 搜索关键词提示API
@house_api.route('/search/keyword/')
def search_keyword():
    keyword = request.args.get('keyword', '')
    
    if not keyword:
        return jsonify([])
    
    # 根据关键词查找相关的地区、小区或房源标题
    results = []
    
    # 查找匹配的地区
    regions = db.session.query(House.region).filter(
        House.region.like(f'%{keyword}%')
    ).distinct().limit(5).all()
    for region in regions:
        results.append({'name': region[0], 'type': 'region'})
    
    # 查找匹配的小区
    blocks = db.session.query(House.block).filter(
        House.block.like(f'%{keyword}%')
    ).distinct().limit(5).all()
    for block in blocks:
        results.append({'name': block[0], 'type': 'block'})
    
    # 查找匹配的房源标题
    titles = db.session.query(House.title).filter(
        House.title.like(f'%{keyword}%')
    ).distinct().limit(5).all()
    for title in titles:
        results.append({'name': title[0], 'type': 'title'})
    
    return jsonify(results)

# 添加收藏API
@house_api.route('/add/collection/<int:house_id>')
def add_collection(house_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': '请先登录'})
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'status': 'error', 'message': '用户不存在'})
    
    # 检查房源是否存在
    house = House.query.get(house_id)
    if not house:
        return jsonify({'status': 'error', 'message': '房源不存在'})
    
    # 获取用户收藏列表
    collect_ids = user.collect_id.split(',') if user.collect_id else []
    collect_ids = [x for x in collect_ids if x]
    
    # 检查是否已收藏
    if str(house_id) in collect_ids:
        return jsonify({'status': 'error', 'message': '已经收藏过该房源'})
    
    # 异步更新收藏（先更新MySQL，再更新Redis）
    async_tasks.async_update_user_collection(user_id, house_id, 'add')
    logger.info(f"异步更新: 用户 {user_id} 添加收藏 {house_id}")
    
    return jsonify({'status': 'success', 'message': '收藏成功', 'valid': '1', 'msg': '收藏成功'})

# 取消收藏API
@house_api.route('/collect_off', methods=['POST'])
def collect_off():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': '请先登录'})
    
    user_id = session['user_id']
    house_id = request.form.get('house_id')
    
    if not house_id:
        return jsonify({'status': 'error', 'message': '参数错误'})
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': 'error', 'message': '用户不存在'})
    
    # 检查房源是否存在
    house = House.query.get(house_id)
    if not house:
        return jsonify({'status': 'error', 'message': '房源不存在'})
    
    # 异步更新收藏（先更新MySQL，再更新Redis）
    async_tasks.async_update_user_collection(user_id, house_id, 'remove')
    logger.info(f"异步更新: 用户 {user_id} 取消收藏 {house_id}")
    
    return jsonify({'status': 'success', 'message': '取消收藏成功'})

# 检查房源是否已收藏API
@house_api.route('/check/collection/<int:house_id>')
def check_collection(house_id):
    if 'user_id' not in session:
        return jsonify({'is_collected': False})
    
    user_id = session['user_id']
    
    # 尝试从Redis获取收藏状态
    is_collected = redis_utils.check_user_collection(user_id, house_id)
    
    if is_collected is None:
        # Redis中没有数据，从数据库获取
        logger.info(f"Redis缓存未命中: 用户 {user_id} 收藏状态 {house_id}")
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'is_collected': False})
        
        # 获取用户收藏列表
        collect_ids = user.collect_id.split(',') if user.collect_id else []
        collect_ids = [x for x in collect_ids if x]
        
        # 检查是否已收藏
        is_collected = str(house_id) in collect_ids
        
        # 缓存到Redis
        if is_collected:
            redis_utils.cache_user_collection(user_id, collect_ids)
            logger.info(f"更新Redis缓存: 用户 {user_id} 收藏列表")
    else:
        logger.info(f"Redis缓存命中: 用户 {user_id} 收藏状态 {house_id}")
    
    return jsonify({'is_collected': bool(is_collected)})

# 价格走势预测API
@house_api.route('/api/price_trend/<string:location>')
def price_trend_api(location):
    parts = location.split('-')
    region = parts[0] if len(parts) > 0 else ''
    block = parts[1] if len(parts) > 1 else None
    
    logger.info(f"调用价格走势预测: {region}-{block if block else ''}")
    # 调用预测模型
    trend_data = predict_price_trend(region, block)
    
    return jsonify(trend_data)

# 户型占比API
@house_api.route('/api/room_distribution/<string:location>')
def room_distribution_api(location):
    parts = location.split('-')
    region = parts[0] if len(parts) > 0 else ''
    block = parts[1] if len(parts) > 1 else None
    
    logger.info(f"调用户型分布统计: {region}-{block if block else ''}")
    # 获取户型分布数据
    distribution_data = get_room_type_distribution(region, block)
    
    return jsonify(distribution_data)

# 小区房源数量TOP20 API
@house_api.route('/api/community_ranking/<string:location>')
def community_ranking_api(location):
    parts = location.split('-')
    region = parts[0] if len(parts) > 0 else ''
    block = parts[1] if len(parts) > 1 else None
    
    logger.info(f"调用小区排名统计: {region}-{block if block else ''}")
    # 获取小区排名数据
    ranking_data = get_top_communities(region, block)
    
    return jsonify(ranking_data)

# 户型价格走势API
@house_api.route('/api/room_price/<string:location>')
def room_price_api(location):
    parts = location.split('-')
    region = parts[0] if len(parts) > 0 else ''
    block = parts[1] if len(parts) > 1 else None
    
    logger.info(f"调用户型价格分析: {region}-{block if block else ''}")
    # 获取户型价格数据
    price_data = get_price_by_room_type(region, block)
    
    return jsonify(price_data)

# 数据可视化API - 散点图数据
@house_api.route('/get/scatterdata/<string:location>')
def get_scatter_data(location):
    parts = location.split('-')
    region = parts[0] if len(parts) > 0 else ''
    block = parts[1] if len(parts) > 1 else ''
    
    query = House.query
    
    if region:
        query = query.filter(House.region == region)
    if block:
        query = query.filter(House.block == block)
    
    houses = query.all()
    
    data = []
    for house in houses:
        # 提取面积数字部分
        area_str = house.area.replace('平方米', '').strip()
        try:
            area = float(area_str)
            price = int(house.price)
            data.append([area, price])
        except (ValueError, TypeError):
            continue
    
    return jsonify({'data': data})

# 数据可视化API - 饼图数据
@house_api.route('/get/piedata/<string:location>')
def get_pie_data(location):
    parts = location.split('-')
    region = parts[0] if len(parts) > 0 else ''
    block = parts[1] if len(parts) > 1 else ''
    
    query = House.query
    
    if region:
        query = query.filter(House.region == region)
    if block:
        query = query.filter(House.block == block)
    
    houses = query.all()
    
    # 统计户型分布
    room_counts = {}
    for house in houses:
        room_type = house.rooms
        if room_type in room_counts:
            room_counts[room_type] += 1
        else:
            room_counts[room_type] = 1
    
    # 转换为饼图数据格式
    data = [{'value': count, 'name': room_type} for room_type, count in room_counts.items()]
    
    return jsonify({'data': data})

# 数据可视化API - 柱状图数据
@house_api.route('/get/columndata/<string:location>')
def get_column_data(location):
    parts = location.split('-')
    region = parts[0] if len(parts) > 0 else ''
    block = parts[1] if len(parts) > 1 else ''
    
    # 获取该区域/商圈中房源数量最多的前20个小区
    query = db.session.query(House.address, func.count(House.id).label('count'))
    
    if region:
        query = query.filter(House.region == region)
    if block:
        query = query.filter(House.block == block)
    
    results = query.group_by(House.address).order_by(desc('count')).limit(20).all()
    
    data = {
        'addresses': [result[0] for result in results],
        'counts': [result[1] for result in results]
    }
    
    return jsonify({'data': data})

# 数据可视化API - 折线图数据
@house_api.route('/get/brokenlinedata/<string:location>')
def get_broken_line_data(location):
    parts = location.split('-')
    region = parts[0] if len(parts) > 0 else ''
    block = parts[1] if len(parts) > 1 else ''
    
    query = House.query
    
    if region:
        query = query.filter(House.region == region)
    if block:
        query = query.filter(House.block == block)
    
    # 获取不同户型的平均价格
    room_types = ['1室0厅', '1室1厅', '2室1厅', '2室2厅', '3室1厅', '3室2厅', '4室1厅', '4室2厅']
    avg_prices = []
    
    for room_type in room_types:
        avg_price = query.filter(House.rooms == room_type).with_entities(func.avg(func.cast(House.price, db.Float))).scalar()
        avg_prices.append(round(avg_price, 2) if avg_price else 0)
    
    data = {
        'room_types': room_types,
        'avg_prices': avg_prices
    }
    
    return jsonify({'data': data}) 