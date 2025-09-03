import redis
import json
from functools import wraps
import time
import logging
from settings import get_redis_master, get_redis_slave

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('redis_utils')

# 键前缀
KEY_PREFIX = 'rental_house:'
# 过期时间（秒）
EXPIRE_TIME = 3600 * 24  # 1天

# 键名定义
HOT_HOUSES_KEY = f"{KEY_PREFIX}hot_houses"              # 热点房源
HIGH_VIEW_HOUSES_KEY = f"{KEY_PREFIX}high_view_houses"  # 高浏览量房源
USER_HISTORY_KEY = f"{KEY_PREFIX}user_history:"         # 用户浏览历史，后面加用户ID
USER_COLLECTION_KEY = f"{KEY_PREFIX}user_collection:"   # 用户收藏，后面加用户ID
RECOMMEND_KEY = f"{KEY_PREFIX}recommend:"               # 推荐数据，后面加用户ID
HOUSE_DETAIL_KEY = f"{KEY_PREFIX}house_detail:"         # 房源详情，后面加房源ID

def redis_operation(read_only=False):
    """Redis操作装饰器，处理连接和异常"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                # 根据操作类型选择主节点或从节点
                if read_only:
                    redis_conn = get_redis_slave()
                    logger.debug(f"使用Redis从节点: {func.__name__}")
                else:
                    redis_conn = get_redis_master()
                    logger.debug(f"使用Redis主节点: {func.__name__}")
                
                # 测试连接
                try:
                    redis_conn.ping()
                except Exception as e:
                    logger.error(f"Redis连接测试失败: {str(e)}")
                    return None
                
                result = func(redis_conn, *args, **kwargs)
                end_time = time.time()
                logger.debug(f"Redis操作成功: {func.__name__} - 耗时: {(end_time - start_time)*1000:.2f}ms")
                return result
            except redis.RedisError as e:
                logger.error(f"Redis操作错误: {func.__name__} - {str(e)}")
                # 如果是从节点操作失败，尝试使用主节点
                if read_only:
                    try:
                        logger.warning(f"从节点操作失败，尝试使用主节点: {func.__name__}")
                        redis_conn = get_redis_master()
                        # 测试连接
                        try:
                            redis_conn.ping()
                        except Exception as e2:
                            logger.error(f"Redis主节点连接测试失败: {str(e2)}")
                            return None
                        
                        result = func(redis_conn, *args, **kwargs)
                        end_time = time.time()
                        logger.debug(f"Redis主节点操作成功: {func.__name__} - 耗时: {(end_time - start_time)*1000:.2f}ms")
                        return result
                    except Exception as e2:
                        logger.error(f"Redis主节点操作也失败: {func.__name__} - {str(e2)}")
                return None
            except Exception as e:
                logger.error(f"未知错误: {func.__name__} - {str(e)}")
                return None
        return wrapper
    return decorator

# 热点房源相关操作
@redis_operation(read_only=False)
def cache_hot_houses(redis_conn, houses, expire=EXPIRE_TIME):
    """缓存热点房源"""
    house_list = [{'id': house.id, 'title': house.title, 'price': house.price, 
                  'area': house.area, 'rooms': house.rooms, 'region': house.region,
                  'block': house.block, 'address': house.address} 
                 for house in houses]
    redis_conn.set(HOT_HOUSES_KEY, json.dumps(house_list))
    redis_conn.expire(HOT_HOUSES_KEY, expire)
    logger.info(f"已缓存 {len(house_list)} 个热点房源, 过期时间: {expire}秒")
    return True

@redis_operation(read_only=True)
def get_hot_houses(redis_conn):
    """获取热点房源"""
    data = redis_conn.get(HOT_HOUSES_KEY)
    if data:
        houses = json.loads(data)
        logger.debug(f"从Redis获取热点房源: {len(houses)}个")
        return houses
    logger.debug("Redis中没有热点房源数据")
    return None

# 高浏览量房源相关操作
@redis_operation(read_only=False)
def cache_high_view_houses(redis_conn, houses, expire=EXPIRE_TIME):
    """缓存高浏览量房源"""
    house_list = [{'id': house.id, 'title': house.title, 'price': house.price, 
                  'area': house.area, 'rooms': house.rooms, 'region': house.region,
                  'block': house.block, 'address': house.address, 'page_views': house.page_views} 
                 for house in houses]
    redis_conn.set(HIGH_VIEW_HOUSES_KEY, json.dumps(house_list))
    redis_conn.expire(HIGH_VIEW_HOUSES_KEY, expire)
    logger.info(f"已缓存 {len(house_list)} 个高浏览量房源, 过期时间: {expire}秒")
    return True

@redis_operation(read_only=True)
def get_high_view_houses(redis_conn):
    """获取高浏览量房源"""
    data = redis_conn.get(HIGH_VIEW_HOUSES_KEY)
    if data:
        houses = json.loads(data)
        logger.debug(f"从Redis获取高浏览量房源: {len(houses)}个")
        return houses
    logger.debug("Redis中没有高浏览量房源数据")
    return None

# 用户浏览历史相关操作
@redis_operation(read_only=False)
def cache_user_history(redis_conn, user_id, house_ids, expire=EXPIRE_TIME):
    """缓存用户浏览历史"""
    key = f"{USER_HISTORY_KEY}{user_id}"
    redis_conn.delete(key)  # 先删除旧数据
    if house_ids:
        redis_conn.rpush(key, *house_ids)
        redis_conn.expire(key, expire)
        logger.info(f"已缓存用户 {user_id} 的 {len(house_ids)} 条浏览历史, 过期时间: {expire}秒")
    else:
        logger.info(f"已清空用户 {user_id} 的浏览历史")
    return True

@redis_operation(read_only=True)
def get_user_history(redis_conn, user_id):
    """获取用户浏览历史"""
    key = f"{USER_HISTORY_KEY}{user_id}"
    data = redis_conn.lrange(key, 0, -1)
    if data:
        logger.debug(f"从Redis获取用户 {user_id} 的浏览历史: {len(data)}条")
        return data
    logger.debug(f"Redis中没有用户 {user_id} 的浏览历史数据")
    return None

@redis_operation(read_only=False)
def add_user_history(redis_conn, user_id, house_id, expire=EXPIRE_TIME):
    """添加用户浏览历史（单条）"""
    key = f"{USER_HISTORY_KEY}{user_id}"
    # 如果已存在，先删除
    redis_conn.lrem(key, 0, str(house_id))
    # 添加到列表开头
    redis_conn.lpush(key, str(house_id))
    # 只保留最近20条
    redis_conn.ltrim(key, 0, 19)
    redis_conn.expire(key, expire)
    logger.info(f"已为用户 {user_id} 添加浏览历史: {house_id}, 过期时间: {expire}秒")
    return True

# 用户收藏相关操作
@redis_operation(read_only=False)
def cache_user_collection(redis_conn, user_id, house_ids, expire=EXPIRE_TIME):
    """缓存用户收藏"""
    key = f"{USER_COLLECTION_KEY}{user_id}"
    redis_conn.delete(key)  # 先删除旧数据
    if house_ids:
        redis_conn.sadd(key, *house_ids)
        redis_conn.expire(key, expire)
        logger.info(f"已缓存用户 {user_id} 的 {len(house_ids)} 条收藏, 过期时间: {expire}秒")
    else:
        logger.info(f"已清空用户 {user_id} 的收藏")
    return True

@redis_operation(read_only=True)
def get_user_collection(redis_conn, user_id):
    """获取用户收藏"""
    key = f"{USER_COLLECTION_KEY}{user_id}"
    data = redis_conn.smembers(key)
    if data:
        logger.debug(f"从Redis获取用户 {user_id} 的收藏: {len(data)}条")
        return list(data)
    logger.debug(f"Redis中没有用户 {user_id} 的收藏数据")
    return None

@redis_operation(read_only=False)
def add_user_collection(redis_conn, user_id, house_id, expire=EXPIRE_TIME):
    """添加用户收藏（单条）"""
    key = f"{USER_COLLECTION_KEY}{user_id}"
    redis_conn.sadd(key, str(house_id))
    redis_conn.expire(key, expire)
    logger.info(f"已为用户 {user_id} 添加收藏: {house_id}, 过期时间: {expire}秒")
    return True

@redis_operation(read_only=False)
def remove_user_collection(redis_conn, user_id, house_id):
    """删除用户收藏（单条）"""
    key = f"{USER_COLLECTION_KEY}{user_id}"
    redis_conn.srem(key, str(house_id))
    logger.info(f"已为用户 {user_id} 删除收藏: {house_id}")
    return True

@redis_operation(read_only=True)
def check_user_collection(redis_conn, user_id, house_id):
    """检查用户是否收藏了某个房源"""
    key = f"{USER_COLLECTION_KEY}{user_id}"
    result = redis_conn.sismember(key, str(house_id))
    logger.debug(f"检查用户 {user_id} 是否收藏房源 {house_id}: {result}")
    return result

# 推荐数据相关操作
@redis_operation(read_only=False)
def cache_user_recommend(redis_conn, user_id, recommends, expire=EXPIRE_TIME):
    """缓存用户推荐数据"""
    key = f"{RECOMMEND_KEY}{user_id}"
    recommend_list = [{'house_id': rec.house_id, 'title': rec.title, 
                      'address': rec.address, 'block': rec.block, 'score': rec.score} 
                     for rec in recommends]
    redis_conn.set(key, json.dumps(recommend_list))
    redis_conn.expire(key, expire)
    logger.info(f"已缓存用户 {user_id} 的 {len(recommend_list)} 条推荐数据, 过期时间: {expire}秒")
    return True

@redis_operation(read_only=True)
def get_user_recommend(redis_conn, user_id):
    """获取用户推荐数据"""
    key = f"{RECOMMEND_KEY}{user_id}"
    data = redis_conn.get(key)
    if data:
        recommends = json.loads(data)
        logger.debug(f"从Redis获取用户 {user_id} 的推荐数据: {len(recommends)}条")
        return recommends
    logger.debug(f"Redis中没有用户 {user_id} 的推荐数据")
    return None

@redis_operation(read_only=False)
def update_user_recommend(redis_conn, user_id, house_id, title, address, block, score, expire=EXPIRE_TIME):
    """更新用户推荐数据（单条）"""
    key = f"{RECOMMEND_KEY}{user_id}"
    data = redis_conn.get(key)
    if data:
        recommends = json.loads(data)
        # 查找是否已存在
        found = False
        for rec in recommends:
            if rec['house_id'] == house_id:
                rec['score'] = score
                found = True
                break
        # 如果不存在，添加新记录
        if not found:
            recommends.append({
                'house_id': house_id,
                'title': title,
                'address': address,
                'block': block,
                'score': score
            })
        # 按得分排序
        recommends.sort(key=lambda x: x['score'], reverse=True)
        # 保存回Redis
        redis_conn.set(key, json.dumps(recommends))
        redis_conn.expire(key, expire)
        logger.info(f"已更新用户 {user_id} 的推荐数据: {house_id}, 得分: {score}")
    return True

# 房源详情相关操作
@redis_operation(read_only=False)
def cache_house_detail(redis_conn, house, expire=EXPIRE_TIME):
    """缓存房源详情"""
    key = f"{HOUSE_DETAIL_KEY}{house.id}"
    house_data = {
        'id': house.id,
        'title': house.title,
        'price': house.price,
        'area': house.area,
        'rooms': house.rooms,
        'direction': house.direction,
        'rent_type': house.rent_type,
        'region': house.region,
        'block': house.block,
        'address': house.address,
        'traffic': house.traffic,
        'publish_time': house.publish_time,
        'facilities': house.facilities,
        'highlights': house.highlights,
        'matching': house.matching,
        'travel': house.travel,
        'page_views': house.page_views,
        'landlord': house.landlord,
        'phone_num': house.phone_num,
        'house_num': house.house_num
    }
    redis_conn.set(key, json.dumps(house_data))
    redis_conn.expire(key, expire)
    logger.info(f"已缓存房源详情: {house.id}, 过期时间: {expire}秒")
    return True

@redis_operation(read_only=True)
def get_house_detail(redis_conn, house_id):
    """获取房源详情"""
    key = f"{HOUSE_DETAIL_KEY}{house_id}"
    data = redis_conn.get(key)
    if data:
        house_data = json.loads(data)
        logger.debug(f"从Redis获取房源详情: {house_id}")
        return house_data
    logger.debug(f"Redis中没有房源 {house_id} 的详情数据")
    return None

@redis_operation(read_only=False)
def increment_house_page_views(redis_conn, house_id):
    """增加房源浏览量"""
    key = f"{HOUSE_DETAIL_KEY}{house_id}"
    data = redis_conn.get(key)
    if data:
        house_data = json.loads(data)
        house_data['page_views'] += 1
        redis_conn.set(key, json.dumps(house_data))
        logger.info(f"已增加房源 {house_id} 的浏览量, 当前浏览量: {house_data['page_views']}")
    return True

# 批量操作
@redis_operation(read_only=False)
def cache_initial_data(redis_conn, hot_houses, high_view_houses, expire=EXPIRE_TIME):
    """缓存初始数据（应用启动时调用）"""
    # 缓存热点房源
    if hot_houses:
        cache_hot_houses(hot_houses, expire)
    
    # 缓存高浏览量房源
    if high_view_houses:
        cache_high_view_houses(high_view_houses, expire)
    
    logger.info("已完成初始数据缓存")
    return True

# Redis健康检查
@redis_operation(read_only=True)
def check_redis_health(redis_conn):
    """检查Redis连接是否正常"""
    try:
        redis_conn.ping()
        logger.info("Redis连接正常")
        return True
    except Exception as e:
        logger.error(f"Redis连接异常: {str(e)}")
        return False 