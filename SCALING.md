# 租房系统水平扩展架构

本文档详细说明了租房系统的水平扩展架构设计、部署方法和运维指南。

## 1. 架构概述

### 1.1 核心组件

- **应用层**：Flask Web应用
- **数据库层**：
  - MySQL Group Replication（多主模式）
  - ProxySQL（读写分离代理）
- **缓存层**：
  - Redis主从复制
  - Redis Sentinel（高可用）
- **数据同步**：异步任务队列

### 1.2 设计理念

- **高可用性**：消除单点故障，确保系统24/7可用
- **可扩展性**：支持水平扩展以应对流量增长
- **数据一致性**：保证在分布式环境下的数据一致性
- **性能优化**：通过读写分离和缓存提升系统性能

## 2. MySQL水平扩展

### 2.1 Group Replication架构

我们采用MySQL Group Replication的多主模式（Multi-Primary Mode），允许所有节点同时处理读写请求：

- **节点1**：主要处理写操作
- **节点2**：主要处理读操作
- 任一节点宕机时，另一节点可自动接管所有读写流量

### 2.2 ProxySQL读写分离

ProxySQL作为中间层，根据SQL语句类型智能路由请求：

- SELECT查询 → 读节点（节点2）
- INSERT/UPDATE/DELETE操作 → 写节点（节点1）
- 节点故障时自动切换路由规则

### 2.3 配置说明

- **节点配置**：
  - `server-id`：每个节点唯一标识
  - `gtid_mode=ON`：启用全局事务ID
  - `group_replication_*`：Group Replication相关参数
  
- **ProxySQL规则**：
  - 写操作路由到hostgroup 10（节点1）
  - 读操作路由到hostgroup 20（节点2）
  - 故障检测和自动切换

## 3. Redis水平扩展

### 3.1 主从架构

- **主节点**：处理写操作，数据变更同步到从节点
- **从节点**：处理读操作，减轻主节点负担
- 从节点设置为只读模式，防止数据不一致

### 3.2 Sentinel高可用

Redis Sentinel提供以下功能：

- **监控**：检查主从节点是否正常工作
- **通知**：通过API通知系统管理员或其他程序
- **自动故障转移**：主节点故障时提升从节点为新主节点
- **配置提供者**：客户端连接时提供服务信息

### 3.3 配置说明

- **主节点**：
  - `bind 0.0.0.0`：允许远程连接
  - `requirepass`：设置访问密码
  - `appendonly yes`：启用AOF持久化
  
- **从节点**：
  - `replicaof redis-master 6379`：指定主节点
  - `replica-read-only yes`：设置只读模式
  
- **Sentinel**：
  - `sentinel monitor mymaster redis-master 6379 2`：监控主节点
  - `sentinel down-after-milliseconds mymaster 5000`：故障检测时间
  - `sentinel failover-timeout mymaster 60000`：故障转移超时

## 4. 应用层适配

### 4.1 数据库连接配置

应用通过ProxySQL连接MySQL集群：

```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:app_pass@proxysql:6033/rental_house'
```

### 4.2 Redis连接配置

应用通过Sentinel连接Redis集群：

```python
# Redis哨兵配置
REDIS_SENTINELS = [
    ('redis-sentinel-1', 26379),
    ('redis-sentinel-2', 26380),
    ('redis-sentinel-3', 26381)
]
REDIS_MASTER_NAME = 'mymaster'

# 获取Redis主节点连接（写操作）
def get_redis_master():
    return sentinel.master_for(REDIS_MASTER_NAME, ...)

# 获取Redis从节点连接（读操作）
def get_redis_slave():
    return sentinel.slave_for(REDIS_MASTER_NAME, ...)
```

### 4.3 读写分离策略

- **读操作**：优先从Redis缓存读取，缓存未命中时从MySQL读取
- **写操作**：先写入MySQL，然后异步更新Redis缓存
- **缓存失效**：采用TTL机制，定期刷新热点数据

## 5. 部署指南

### 5.1 前置条件

- Docker 19.03+
- Docker Compose 1.27+
- Python 3.8+
- 至少8GB可用内存
- 至少20GB磁盘空间

### 5.2 部署步骤

1. **克隆代码仓库**：
   ```
   git clone <repository-url>
   cd Rental_housing_system
   ```

2. **启动服务**：
   ```
   ./start.sh
   ```
   
   此脚本会：
   - 创建并配置Python虚拟环境
   - 启动Docker容器（MySQL、Redis等）
   - 执行数据迁移
   - 启动Flask应用

3. **验证部署**：
   访问 http://127.0.0.1:9000/ 确认系统正常运行

4. **停止服务**：
   ```
   ./stop.sh
   ```

### 5.3 数据迁移

从单节点迁移到集群：

```
python migrate_data.py
```

验证数据一致性：

```
python migrate_data.py --check
```

## 6. 监控与维护

### 6.1 健康检查

- **MySQL**：`docker exec -i mysql-node1 mysql -uroot -proot -e "SHOW STATUS LIKE 'group_replication%'"`
- **ProxySQL**：`docker exec -i proxysql mysql -u admin -padmin -h 127.0.0.1 -P 6032 -e "SELECT * FROM mysql_servers"`
- **Redis**：`docker exec -i redis-sentinel-1 redis-cli -p 26379 sentinel master mymaster`

### 6.2 常见问题处理

1. **MySQL节点故障**：
   - 检查日志：`docker logs mysql-node1`
   - 重启节点：`docker restart mysql-node1`
   - 重新加入集群：`docker exec -i mysql-node1 mysql -uroot -proot -e "START GROUP_REPLICATION"`

2. **Redis故障转移**：
   - 查看主节点：`docker exec -i redis-sentinel-1 redis-cli -p 26379 sentinel master mymaster`
   - 手动故障转移：`docker exec -i redis-sentinel-1 redis-cli -p 26379 sentinel failover mymaster`

3. **应用连接问题**：
   - 检查ProxySQL路由：`docker exec -i proxysql mysql -u admin -padmin -h 127.0.0.1 -P 6032 -e "SELECT * FROM mysql_query_rules"`
   - 检查应用日志：`tail -f app.log`

## 7. 性能优化

### 7.1 MySQL优化

- 配置InnoDB缓冲池大小：`innodb_buffer_pool_size=1G`
- 优化查询缓存：`query_cache_type=1`
- 配置连接池大小：`max_connections=1000`

### 7.2 Redis优化

- 内存管理策略：`maxmemory-policy=allkeys-lru`
- 启用延迟释放：`lazyfree-lazy-eviction=yes`
- 多线程IO：`io-threads=4`

### 7.3 应用层优化

- 使用连接池管理数据库连接
- 实现分页查询减少数据传输量
- 定期清理过期缓存数据

## 8. 扩展建议

### 8.1 进一步扩展

- **MySQL**：增加更多节点，配置分片
- **Redis**：配置Redis Cluster实现数据分片
- **应用服务器**：部署多实例，配置负载均衡器

### 8.2 高级特性

- **数据分区**：按时间或地区分区表
- **读写分离中间件**：考虑使用MyCat或ShardingSphere
- **分布式缓存**：使用Redis Cluster实现更大规模缓存

## 9. 总结

本水平扩展架构通过MySQL Group Replication和Redis Sentinel实现了系统的高可用性和可扩展性，同时保证了数据一致性。通过ProxySQL实现了智能的读写分离，提高了系统性能。

该架构适用于中等规模的租房系统，可根据业务增长进一步扩展。 