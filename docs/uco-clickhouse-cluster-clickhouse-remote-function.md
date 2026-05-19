# ClickHouse remote / remoteSecure 表函数与 K8s DNS 解析

## 1. 语法与参数

```sql
remote(addresses_expr, [db, table, user [, password], sharding_key])
remote(addresses_expr, [db.table, user [, password], sharding_key])
remote(named_collection[, option=value [,..]])

remoteSecure(addresses_expr, [db, table, user [, password], sharding_key])
remoteSecure(addresses_expr, [db.table, user [, password], sharding_key])
remoteSecure(named_collection[, option=value [,..]])
```

| 参数 | 说明 |
|------|------|
| `addresses_expr` | 远程服务器地址，`host` 或 `host:port`。支持 IPv4/IPv6（IPv6 需用 `[]`）。多个地址用逗号分隔（分布式处理）。 |
| `db` | 数据库名。仅传 `addresses_expr` 时默认 `system.one`。 |
| `table` | 表名。 |
| `user` | 用户名，默认 `default`。 |
| `password` | 密码，默认空。 |
| `sharding_key` | 分片键，如 `rand()`，用于 INSERT 时分发数据。 |

**默认端口：**
- `remote`：9000
- `remoteSecure`：9440

## 2. 使用示例

### 查询远程表

```sql
SELECT * FROM remote('127.0.0.1', db.remote_engine_table) LIMIT 3;

-- 或
SELECT * FROM remote('127.0.0.1:9000', 'mydb', 'mytable', 'default', 'password');
```

### 向远程表写入数据

```sql
INSERT INTO FUNCTION remote('127.0.0.1', currentDatabase(), 'remote_table')
VALUES ('test', 42);
```

### Named Collection

```sql
CREATE NAMED COLLECTION creds AS
  host = '127.0.0.1',
  database = 'db';

SELECT * FROM remote(creds, table='remote_engine_table') LIMIT 3;
```

### 安全连接 remoteSecure

```sql
SELECT *
FROM remoteSecure('clusterA.us-west-2.aws.clickhouse.cloud:9440', 'db1.table1', 'default', 'Password123!');
```

### 多地址分布式查询

```sql
SELECT * FROM remote('host1:9000,host2:9000', 'db', 'table', 'user', 'password');
```

### 数据迁移

```sql
INSERT INTO db.table
SELECT * FROM remoteSecure('source-host', 'db', 'table', 'exporter', 'password');
```

## 3. 注意事项

- `remote` **每次查询都会重新建立连接**，性能不如预创建的 `Distributed` 表。
- 推荐仅用于：
  - 一次性数据迁移
  - 临时调试、数据对比
  - 跨集群研究查询
  - 手动执行的低频分布式请求
- 对于高并发生产查询，应提前创建 `Distributed` 表。

## 4. Kubernetes 环境下 DNS 解析规则

### 4.1 同 namespace

可以直接用 **service 短名称**，K8s DNS 会自动补全当前 namespace：

```sql
SELECT * FROM remote('clickhouse-prod:9000', 'db', 'table', 'user', 'password');
-- 等效于
SELECT * FROM remote('clickhouse-prod.bi-clickhouse.svc.cluster.local:9000', ...);
```

K8s 在 Pod 的 `/etc/resolv.conf` 中配置 search domain：

```bash
search bi-clickhouse.svc.cluster.local svc.cluster.local cluster.local
```

### 4.2 跨 namespace

**必须显式指定目标 namespace**，否则只会解析到当前 namespace：

```sql
-- ✅ 正确：目标在 bi-clickhouse-prod namespace
SELECT * FROM remote('clickhouse-prod.bi-clickhouse-prod:9000', ...);

-- ❌ 错误：只写 clickhouse-prod 会解析到当前 namespace
SELECT * FROM remote('clickhouse-prod:9000', ...);
```

**关键原理**：K8s DNS search domain 只补全当前 Pod 所在 namespace，不会自动遍历其他 namespace。即使当前 namespace 没有同名 service，解析失败后也不会 fallback 到其他 namespace。

### 4.3 完整 FQDN（最保险）

```sql
SELECT * FROM remote('clickhouse-prod.bi-clickhouse-prod.svc.cluster.local:9000', ...);
```

## 5. 验证 DNS 解析

在 source ClickHouse 中测试：

```sql
-- 测试短名称是否能正确解析到目标
SELECT * FROM remote('clickhouse-prod:9000', 'system', 'one');
```

若报错 `Connection refused` 或解析到错误 IP，说明需要补全 namespace 或端口。
