# 租房系统 (Rental Housing System)

## 项目概述
基于Flask的高性能租房系统，提供房源浏览、搜索、收藏、用户管理等功能，并集成数据可视化和推荐系统。系统采用分布式架构设计，支持高并发访问和水平扩展。

## 系统架构

### 核心技术栈
- **后端框架**: Flask + SQLAlchemy
- **数据库**: MySQL (主从复制)
- **缓存**: Redis (主从 + Sentinel)
- **代理**: ProxySQL (读写分离)
- **容器化**: Docker

### 高可用设计
- MySQL主从复制确保数据库高可用
- Redis Sentinel提供缓存服务的故障转移
- ProxySQL实现数据库读写分离，优化查询性能

### 数据库主从复制机制

#### MySQL主从复制
MySQL采用异步复制机制，通过以下方式实现：

1. **主节点配置**:
   - `server-id=1`: 唯一标识主节点
   - `log_bin=mysql-bin`: 启用二进制日志
   - `binlog_format=ROW`: 使用行级复制格式
   - `binlog_do_db=rental_house`: 只复制指定数据库

2. **从节点配置**:
   - `server-id=2`: 唯一标识从节点
   - `log_bin=mysql-bin`: 启用二进制日志
   - `relay-log=slave-relay-bin`: 设置中继日志
   - `read_only=ON`: 从节点设为只读
   - `replicate_do_db=rental_house`: 只复制指定数据库

3. **复制过程**:
   - 主节点记录所有数据变更到二进制日志(binlog)
   - 从节点的I/O线程连接到主节点，请求二进制日志
   - 主节点发送二进制日志到从节点
   - 从节点的SQL线程执行接收到的变更操作

4. **复制初始化**:
   - 获取主节点当前二进制日志文件名和位置
   - 在从节点执行`CHANGE MASTER TO`命令，指定主节点信息
   - 启动从节点复制线程(`START SLAVE`)
   - 验证复制状态(`SHOW SLAVE STATUS`)

#### Redis主从复制
Redis采用异步复制机制，结合哨兵模式实现高可用：

1. **主从配置**:
   - 从节点通过`replicaof redis-master 6379`指令连接到主节点
   - 从节点设置`replica-read-only yes`确保只读
   - 主从节点都配置`requirepass`和`masterauth`实现安全认证

2. **复制过程**:
   - 初次同步：主节点创建RDB快照，发送给从节点
   - 增量同步：主节点将写命令发送给从节点
   - 从节点异步应用接收到的命令

3. **哨兵机制**:
   - 3个哨兵节点监控主从节点健康状态
   - 哨兵配置`sentinel monitor mymaster redis-master 6379 2`(仲裁数为2)
   - 当主节点故障时，哨兵自动选择从节点升级为新主节点
   - 应用程序通过哨兵发现当前主节点

### ProxySQL流量分配机制

ProxySQL实现了MySQL的读写分离和流量分配：

1. **服务器配置**:
   - 主节点(mysql-node1)和从节点(mysql-node2)都在同一个hostgroup(10)
   - 主节点权重为1000，从节点权重为500，实现2:1的流量分配比例

2. **查询规则**:
   - 所有查询(SELECT、UPDATE、INSERT等)都路由到同一个hostgroup
   - 在hostgroup内部按权重分配连接

3. **连接管理**:
   - 每个节点最大连接数为500
   - 支持连接池和多路复用，减少连接开销

## 功能模块

### 房源管理
- 房源浏览与搜索
- 高级筛选 (区域、价格、户型等)
- 房源详情展示
- 热门房源推荐

### 用户系统
- 用户注册与登录
- 个人中心管理
- 浏览历史记录
- 房源收藏功能

### 数据分析与可视化

#### 房价走势预测
- 基于多项式回归模型分析历史数据
- 预测未来3个月房价走势
- 支持按区域和板块筛选

#### 户型分布统计
- 分析特定区域内不同户型占比
- 直观饼图展示户型分布情况

#### 小区排名分析
- 统计区域内房源数量最多的小区
- 提供Top20小区排行榜

#### 户型价格分析
- 比较不同户型的价格分布
- 展示各户型的平均价格、最低价格和最高价格

## 缓存设计

### Redis缓存策略
系统采用"先更新MySQL，再更新Redis"的策略确保数据一致性。

#### 缓存键值设计
| 缓存类型 | 键模式 | 值类型 | 缓存策略 | 过期时间 |
|---------|-------|-------|---------|---------|
| 热点房源 | rental_house:hot_houses | JSON字符串 | 随机热门房源 | 1天 |
| 高浏览量房源 | rental_house:high_view_houses | JSON字符串 | 浏览量Top10 | 1天 |
| 用户浏览历史 | rental_house:user_history:{user_id} | 列表 | 最近20条记录 | 1天 |
| 用户收藏 | rental_house:user_collection:{user_id} | 集合 | 全部收藏ID | 1天 |
| 推荐数据 | rental_house:recommend:{user_id} | JSON字符串 | 个性化推荐 | 1天 |
| 房源详情 | rental_house:house_detail:{house_id} | JSON字符串 | 访问过的房源 | 1天 |

### 异步任务处理
- 使用Python的threading和queue模块实现异步任务队列
- 后台线程处理数据更新、缓存刷新等任务
- 定期更新热点数据，提升系统响应速度

## 部署指南

### 环境要求
- Docker 和 Docker Compose
- Python 3.8+
- MySQL 8.0+
- Redis 6.0+

### 快速启动
```bash
# 克隆仓库
git clone <repository-url>

# 启动系统
./start.sh

# 导入数据
python migrate_data.py --import
```

### 配置说明
系统配置通过环境变量和配置文件管理，主要包括：
- 数据库连接配置
- Redis连接配置
- 应用服务配置

## 水平扩展能力
- MySQL主从复制支持数据库高可用
- Redis主从复制与哨兵机制支持缓存服务高可用
- 应用服务支持多实例部署，通过负载均衡分发请求
- 支持容器化部署，便于云环境弹性扩展

## 性能优化
- ProxySQL实现流量分配，主节点与从节点权重比为2:1
- Redis缓存减轻数据库负载
- 异步任务处理避免阻塞用户请求
- 合理的缓存策略优化内存使用
