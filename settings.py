from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv
import pathlib

# 加载.env文件
env_path = pathlib.Path('/Users/haogeng/Desktop/genghao/test/python_venv/school1/Rental_housing_system/templates/.env')
load_dotenv(dotenv_path=env_path)

# 获取BASE_URL环境变量
BASE_URL = os.getenv('BASE_URL')

# 创建Flask应用实例
app = Flask(__name__)

# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:rootpassword@localhost:3306/rental_house?charset=utf8mb4'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'rental_housing_secret_key'

# 创建SQLAlchemy实例
db = SQLAlchemy(app) 