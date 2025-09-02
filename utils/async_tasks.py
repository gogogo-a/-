import threading
import time
import logging
import queue
from models import db, House, User, Recommend
from utils import redis_utils

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('async_tasks')

# 任务队列
task_queue = queue.Queue()

# 任务类型
TASK_UPDATE_HOT_HOUSES = 'update_hot_houses'
TASK_UPDATE_HIGH_VIEW_HOUSES = 'update_high_view_houses'
TASK_UPDATE_USER_HISTORY = 'update_user_history'
TASK_UPDATE_USER_COLLECTION = 'update_user_collection'
TASK_UPDATE_USER_RECOMMEND = 'update_user_recommend'
TASK_UPDATE_HOUSE_DETAIL = 'update_house_detail'
TASK_UPDATE_HOUSE_PAGE_VIEWS = 'update_house_page_views'

# 任务处理线程
class TaskWorker(threading.Thread):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.daemon = True  # 设置为守护线程，主线程退出时自动退出
        self.running = True
        
    def run(self):
        logger.info("异步任务处理线程已启动")
        while self.running:
            try:
                # 获取任务，最多等待1秒
                try:
                    task = task_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # 处理任务
                with self.app.app_context():
                    self.process_task(task)
                
                # 标记任务完成
                task_queue.task_done()
            except Exception as e:
                logger.error(f"处理任务时出错: {str(e)}")
        
        logger.info("异步任务处理线程已停止")
    
    def process_task(self, task):
        """处理任务"""
        task_type = task.get('type')
        
        if task_type == TASK_UPDATE_HOT_HOUSES:
            self.update_hot_houses()
        elif task_type == TASK_UPDATE_HIGH_VIEW_HOUSES:
            self.update_high_view_houses()
        elif task_type == TASK_UPDATE_USER_HISTORY:
            self.update_user_history(task.get('user_id'), task.get('house_id'))
        elif task_type == TASK_UPDATE_USER_COLLECTION:
            self.update_user_collection(task.get('user_id'), task.get('house_id'), task.get('action'))
        elif task_type == TASK_UPDATE_USER_RECOMMEND:
            self.update_user_recommend(task.get('user_id'), task.get('house_id'))
        elif task_type == TASK_UPDATE_HOUSE_DETAIL:
            self.update_house_detail(task.get('house_id'))
        elif task_type == TASK_UPDATE_HOUSE_PAGE_VIEWS:
            self.update_house_page_views(task.get('house_id'), task.get('views'))
    
    def update_hot_houses(self):
        """更新热点房源"""
        try:
            # 获取热点房源（按照随机排序，取前6个）
            hot_houses = House.query.order_by(db.func.random()).limit(6).all()
            # 缓存到Redis
            redis_utils.cache_hot_houses(hot_houses)
            logger.info("已更新热点房源")
        except Exception as e:
            logger.error(f"更新热点房源时出错: {str(e)}")
    
    def update_high_view_houses(self):
        """更新高浏览量房源"""
        try:
            # 获取高浏览量房源（按照浏览量降序排序，取前10个）
            high_view_houses = House.query.order_by(House.page_views.desc()).limit(10).all()
            # 缓存到Redis
            redis_utils.cache_high_view_houses(high_view_houses)
            logger.info("已更新高浏览量房源")
        except Exception as e:
            logger.error(f"更新高浏览量房源时出错: {str(e)}")
    
    def update_user_history(self, user_id, house_id):
        """更新用户浏览历史"""
        try:
            if not user_id:
                return
            
            user = User.query.get(user_id)
            if not user:
                return
            
            # 更新MySQL
            seen_ids = user.seen_id.split(',') if user.seen_id else []
            seen_ids = [x for x in seen_ids if x]
            
            # 如果已存在，先移除
            if str(house_id) in seen_ids:
                seen_ids.remove(str(house_id))
            
            # 添加到最前面
            seen_ids.insert(0, str(house_id))
            
            # 只保留最近20条
            seen_ids = seen_ids[:20]
            
            # 更新用户记录
            user.seen_id = ','.join(seen_ids)
            db.session.commit()
            
            # 更新Redis
            redis_utils.cache_user_history(user_id, seen_ids)
            
            logger.info(f"已更新用户 {user_id} 的浏览历史")
        except Exception as e:
            logger.error(f"更新用户浏览历史时出错: {str(e)}")
    
    def update_user_collection(self, user_id, house_id, action):
        """更新用户收藏"""
        try:
            if not user_id or not house_id:
                return
            
            user = User.query.get(user_id)
            if not user:
                return
            
            # 更新MySQL
            collect_ids = user.collect_id.split(',') if user.collect_id else []
            collect_ids = [x for x in collect_ids if x]
            
            if action == 'add':
                # 如果不存在，添加
                if str(house_id) not in collect_ids:
                    collect_ids.append(str(house_id))
                    # 更新用户记录
                    user.collect_id = ','.join(collect_ids)
                    db.session.commit()
                    # 更新Redis
                    redis_utils.cache_user_collection(user_id, collect_ids)
            elif action == 'remove':
                # 如果存在，删除
                if str(house_id) in collect_ids:
                    collect_ids.remove(str(house_id))
                    # 更新用户记录
                    user.collect_id = ','.join(collect_ids)
                    db.session.commit()
                    # 更新Redis
                    redis_utils.cache_user_collection(user_id, collect_ids)
            
            logger.info(f"已更新用户 {user_id} 的收藏 ({action}): {house_id}")
        except Exception as e:
            logger.error(f"更新用户收藏时出错: {str(e)}")
    
    def update_user_recommend(self, user_id, house_id):
        """更新用户推荐数据"""
        try:
            if not user_id or not house_id:
                return
            
            # 获取房源信息
            house = House.query.get(house_id)
            if not house:
                return
            
            # 查询推荐记录
            recommend = Recommend.query.filter_by(user_id=user_id, house_id=house_id).first()
            
            if recommend:
                # 更新得分
                recommend.score += 1
            else:
                # 创建新记录
                recommend = Recommend(
                    user_id=user_id,
                    house_id=house_id,
                    title=house.title,
                    address=house.address,
                    block=house.block,
                    score=1
                )
                db.session.add(recommend)
            
            # 提交更改
            db.session.commit()
            
            # 获取用户所有推荐数据
            recommends = Recommend.query.filter_by(user_id=user_id).all()
            
            # 更新Redis
            redis_utils.cache_user_recommend(user_id, recommends)
            
            logger.info(f"已更新用户 {user_id} 的推荐数据: {house_id}")
        except Exception as e:
            logger.error(f"更新用户推荐数据时出错: {str(e)}")
    
    def update_house_detail(self, house_id):
        """更新房源详情"""
        try:
            if not house_id:
                return
            
            # 获取房源信息
            house = House.query.get(house_id)
            if not house:
                return
            
            # 缓存到Redis
            redis_utils.cache_house_detail(house)
            
            logger.info(f"已更新房源详情: {house_id}")
        except Exception as e:
            logger.error(f"更新房源详情时出错: {str(e)}")
    
    def update_house_page_views(self, house_id, views):
        """更新房源浏览量"""
        try:
            if not house_id:
                return
            
            # 获取房源信息
            house = House.query.get(house_id)
            if not house:
                return
            
            # 更新浏览量
            house.page_views = views
            db.session.commit()
            
            # 更新Redis中的房源详情
            self.update_house_detail(house_id)
            
            logger.info(f"已更新房源 {house_id} 的浏览量: {views}")
        except Exception as e:
            logger.error(f"更新房源浏览量时出错: {str(e)}")
    
    def stop(self):
        """停止线程"""
        self.running = False

# 添加任务到队列
def add_task(task_type, **kwargs):
    """添加任务到队列"""
    task = {'type': task_type, **kwargs}
    task_queue.put(task)
    logger.debug(f"已添加任务: {task_type}")

# 启动任务处理线程
def start_task_worker(app):
    """启动任务处理线程"""
    worker = TaskWorker(app)
    worker.start()
    return worker

# 缓存初始数据
def cache_initial_data(app):
    """缓存初始数据"""
    with app.app_context():
        try:
            # 获取热点房源
            hot_houses = House.query.order_by(db.func.random()).limit(6).all()
            
            # 获取高浏览量房源
            high_view_houses = House.query.order_by(House.page_views.desc()).limit(10).all()
            
            # 缓存到Redis
            redis_utils.cache_initial_data(hot_houses, high_view_houses)
            
            logger.info("已缓存初始数据")
        except Exception as e:
            logger.error(f"缓存初始数据时出错: {str(e)}")

# 异步更新用户浏览历史
def async_update_user_history(user_id, house_id):
    """异步更新用户浏览历史"""
    add_task(TASK_UPDATE_USER_HISTORY, user_id=user_id, house_id=house_id)

# 异步更新用户收藏
def async_update_user_collection(user_id, house_id, action):
    """异步更新用户收藏"""
    add_task(TASK_UPDATE_USER_COLLECTION, user_id=user_id, house_id=house_id, action=action)

# 异步更新用户推荐数据
def async_update_user_recommend(user_id, house_id):
    """异步更新用户推荐数据"""
    add_task(TASK_UPDATE_USER_RECOMMEND, user_id=user_id, house_id=house_id)

# 异步更新房源详情
def async_update_house_detail(house_id):
    """异步更新房源详情"""
    add_task(TASK_UPDATE_HOUSE_DETAIL, house_id=house_id)

# 异步更新房源浏览量
def async_update_house_page_views(house_id, views):
    """异步更新房源浏览量"""
    add_task(TASK_UPDATE_HOUSE_PAGE_VIEWS, house_id=house_id, views=views)

# 定期更新热点房源和高浏览量房源
def schedule_periodic_updates():
    """定期更新热点房源和高浏览量房源"""
    add_task(TASK_UPDATE_HOT_HOUSES)
    add_task(TASK_UPDATE_HIGH_VIEW_HOUSES)
    
    # 每小时调度一次
    threading.Timer(3600, schedule_periodic_updates).start() 