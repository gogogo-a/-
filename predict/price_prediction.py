import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
import pandas as pd
from models import House, db
from sqlalchemy import func, desc, or_
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('price_prediction')

def predict_price_trend(region, block=None):
    """
    预测特定区域或小区的房价走势
    
    参数:
    region: 区域名称
    block: 街区名称，可选
    
    返回:
    预测结果字典，包含x轴（面积）和y轴（价格）数据
    """
    try:
        logger.info(f"开始预测区域 {region}-{block if block else ''} 的房价走势")
        
        # 查询指定区域/街区的房源数据，使用模糊匹配
        query = House.query.filter(House.region.like(f'%{region}%'))
        if block:
            query = query.filter(House.block.like(f'%{block}%'))
        
        houses = query.all()
        logger.info(f"查询到 {len(houses)} 条房源数据")
        
        # 提取面积和价格数据
        areas = []
        prices = []
        for house in houses:
            try:
                # 提取面积数字部分
                area_str = house.area.replace('平方米', '').strip()
                area = float(area_str)
                # 确保价格是数值类型
                price = float(house.price)
                areas.append(area)
                prices.append(price)
            except (ValueError, TypeError) as e:
                logger.warning(f"处理房源数据时出错: {e}, 房源ID: {house.id}")
                continue
        
        if len(areas) < 5:  # 数据太少，无法进行有效预测
            logger.warning(f"数据点数量不足，无法进行预测: {len(areas)} < 5")
            return {
                'actual': {'x': areas, 'y': prices},
                'predicted': {'x': [], 'y': []}
            }
        
        # 将数据转换为numpy数组
        X = np.array(areas).reshape(-1, 1)
        y = np.array(prices)
        
        # 创建多项式特征
        poly = PolynomialFeatures(degree=2)
        X_poly = poly.fit_transform(X)
        
        # 拟合线性回归模型
        model = LinearRegression()
        model.fit(X_poly, y)
        
        # 生成预测数据点
        X_pred = np.linspace(min(areas), max(areas), 50).reshape(-1, 1)
        X_pred_poly = poly.transform(X_pred)
        y_pred = model.predict(X_pred_poly)
        
        # 返回实际数据点和预测数据点
        result = {
            'actual': {'x': areas, 'y': prices},
            'predicted': {'x': X_pred.flatten().tolist(), 'y': y_pred.tolist()}
        }
        
        logger.info(f"房价走势预测完成，实际数据点: {len(areas)}，预测数据点: {len(X_pred)}")
        return result
    
    except Exception as e:
        logger.error(f"房价走势预测失败: {str(e)}")
        # 返回空结果
        return {
            'actual': {'x': [], 'y': []},
            'predicted': {'x': [], 'y': []}
        }

def get_room_type_distribution(region, block=None):
    """
    获取特定区域或小区的户型分布
    
    参数:
    region: 区域名称
    block: 街区名称，可选
    
    返回:
    户型分布数据，适用于饼图
    """
    try:
        logger.info(f"开始获取区域 {region}-{block if block else ''} 的户型分布")
        
        # 查询指定区域/街区的房源数据，使用模糊匹配
        query = House.query.filter(House.region.like(f'%{region}%'))
        if block:
            query = query.filter(House.block.like(f'%{block}%'))
        
        # 使用SQLAlchemy进行分组统计
        result = query.with_entities(
            House.rooms, 
            func.count(House.id).label('count')
        ).group_by(House.rooms).all()
        
        # 转换为饼图数据格式
        data = [{'name': room_type, 'value': count} for room_type, count in result]
        
        logger.info(f"户型分布获取完成，共 {len(data)} 种户型")
        return data
    
    except Exception as e:
        logger.error(f"户型分布获取失败: {str(e)}")
        return []

def get_top_communities(region, block=None, limit=20):
    """
    获取特定区域或街区中房源数量最多的小区
    
    参数:
    region: 区域名称
    block: 街区名称，可选
    limit: 返回的小区数量，默认为20
    
    返回:
    小区名称和对应的房源数量
    """
    try:
        logger.info(f"开始获取区域 {region}-{block if block else ''} 的小区房源数量排名")
        
        # 查询指定区域/街区的房源数据，使用模糊匹配
        query = db.session.query(
            House.address, 
            func.count(House.id).label('count')
        ).filter(House.region.like(f'%{region}%'))
        
        if block:
            query = query.filter(House.block.like(f'%{block}%'))
        
        # 按小区分组并按房源数量降序排序
        result = query.group_by(House.address).order_by(desc('count')).limit(limit).all()
        
        # 转换为柱状图数据格式
        addresses = [item[0] for item in result]
        counts = [item[1] for item in result]
        
        logger.info(f"小区房源数量排名获取完成，共 {len(addresses)} 个小区")
        return {
            'addresses': addresses,
            'counts': counts
        }
    
    except Exception as e:
        logger.error(f"小区房源数量排名获取失败: {str(e)}")
        return {
            'addresses': [],
            'counts': []
        }

def get_price_by_room_type(region, block=None):
    """
    获取特定区域或小区不同户型的平均价格
    
    参数:
    region: 区域名称
    block: 街区名称，可选
    
    返回:
    户型和对应的平均价格
    """
    try:
        logger.info(f"开始获取区域 {region}-{block if block else ''} 的户型价格")
        
        # 常见户型列表
        common_room_types = ['1室0厅', '1室1厅', '2室1厅', '2室2厅', '3室1厅', '3室2厅', '4室1厅', '4室2厅']
        
        # 查询指定区域/街区的房源数据，使用模糊匹配
        query = House.query.filter(House.region.like(f'%{region}%'))
        if block:
            query = query.filter(House.block.like(f'%{block}%'))
        
        # 获取每种户型的平均价格
        result = []
        for room_type in common_room_types:
            try:
                avg_price = query.filter(House.rooms == room_type).with_entities(
                    func.avg(func.cast(House.price, db.Float))
                ).scalar()
                
                if avg_price:
                    result.append({
                        'room_type': room_type,
                        'avg_price': round(avg_price, 2)
                    })
            except Exception as e:
                logger.warning(f"获取户型 {room_type} 的价格时出错: {str(e)}")
        
        # 转换为折线图数据格式
        room_types = [item['room_type'] for item in result]
        avg_prices = [item['avg_price'] for item in result]
        
        logger.info(f"户型价格获取完成，共 {len(room_types)} 种户型")
        return {
            'room_types': room_types,
            'avg_prices': avg_prices
        }
    
    except Exception as e:
        logger.error(f"户型价格获取失败: {str(e)}")
        return {
            'room_types': [],
            'avg_prices': []
        } 