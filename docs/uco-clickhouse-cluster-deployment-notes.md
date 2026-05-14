# ClickHouse Operator Helm 部署常见问题

## 1. Operator 是否仅对特定 Namespace 生效

查看 Makefile 中的 `install_chop` 目标，重点关注以下两个参数：

- `--set configs.files.config\\.yaml.watch.namespaces={${NAMESPACE}}` —— 仅监听指定 namespace
- `--set rbac.namespaceScoped=true` —— 使用 namespace 级别 RBAC

当前配置仅对 `bi-clickhouse-prod` 生效。

## 2. Chart 是否会安装 CRD

`altinity-clickhouse-operator` chart 自带 4 个 CRD，首次 `helm install/upgrade` 会自动安装：

```bash
helm show crds clickhouse-operator/altinity-clickhouse-operator --version 0.25.3
```

| CRD | 缩写 |
|---|---|
| `clickhouseinstallations.clickhouse.altinity.com` | `chi` |
| `clickhouseinstallationtemplates.clickhouse.altinity.com` | `chit` |
| `clickhousekeeperinstallations.clickhouse-keeper.altinity.com` | `chk` |
| `clickhouseoperatorconfigurations.clickhouse.altinity.com` | `chop-config` |

> Helm 3 的 CRD 在首次安装时自动创建，但**后续 chart 升级不会自动更新 CRD**。如有变更需手动处理。

## 3. 如何确定资源的 apiVersion 和 kind

```bash
# 查看集群中已注册的所有 clickhouse 相关资源
kubectl api-resources | grep clickhouse

# 查看具体 CRD 的 group/version/kind
kubectl get crd clickhousekeeperinstallations.clickhouse-keeper.altinity.com -o yaml

# 查看某资源的详细字段说明
kubectl explain ClickHouseKeeperInstallation

# 递归查看全部字段结构（最完整）
kubectl explain ClickHouseKeeperInstallation --recursive
```

## 4. YAML 中的 kind 不能用缩写

`shortNames`（如 `chi`、`chk`）仅供 `kubectl` 命令行使用，YAML 中 `kind` 必须写完整名称：

```yaml
# ✅ 正确
kind: ClickHouseKeeperInstallation

# ❌ 错误
kind: chk
```

## 5. 如何编写 CRD 资源配置（ClickHouseInstallation / ClickHouseKeeperInstallation）

通过 `kubectl explain` 逐步探索字段结构：

```bash
# 顶层结构
kubectl explain ClickHouseInstallation.spec

# 深入具体字段
kubectl explain ClickHouseInstallation.spec.configuration.clusters
kubectl explain ClickHouseInstallation.spec.templates.podTemplates

# 递归查看全部字段
kubectl explain ClickHouseInstallation --recursive | grep -E "replicas|image|resources"
```

参考项目已有配置：
- `clickhouse-prod.yaml` —— ClickHouse 集群配置
- `keeper.yaml` —— Keeper 集群配置

## 6. 环境变量与 envsubst

`make build` 通过 `envsubst` 渲染模板：

```makefile
build:
	-mkdir build
	envsubst < clickhouse-prod.yaml > build/clickhouse-prod.yaml
	envsubst < keeper.yaml > build/keeper.yaml
```

Makefile 会 `include .env`，需要确保 `.env` 中包含模板里用到的变量。可以通过检查渲染后的文件是否还有残留的 `${...}` 占位符来验证：

```bash
grep -oE '\$\{[A-Za-z_][A-Za-z0-9_]*\}' build/clickhouse-prod.yaml build/keeper.yaml
```

无输出说明全部替换成功。

## 7. 查看已部署 Helm Release 的配置

```bash
# 查看用户自定义 values（安装时传入的 --set / -f）
helm get values clickhouse-operator -n bi-clickhouse-prod

# 查看合并后的全部 values（自定义 + chart 默认值）
helm get values clickhouse-operator -n bi-clickhouse-prod --all

# 查看渲染后的完整 K8s manifest
helm get manifest clickhouse-operator -n bi-clickhouse-prod
```

| 命令 | 内容 |
|---|---|
| `helm get values` | 配置输入（values 键值对） |
| `helm get manifest` | 渲染输出（K8s YAML 资源） |

## 8. 校验集群配置与本地配置是否一致

### 8.1 原生资源 / CRD（kubectl apply 部署）

对比 `spec` 部分即可，metadata/status 是集群生成的噪音：

```bash
# 导出集群当前配置
kubectl get ClickHouseKeeperInstallation ch-keeper -n bi-clickhouse-prod -o yaml > /tmp/cluster.yaml

# 提取 spec 并对比
python3 -c "import yaml; d=list(yaml.safe_load_all(open('/tmp/cluster.yaml')))[0]; yaml.dump(d.get('spec',{}), open('/tmp/cluster-spec.yaml','w'))"
python3 -c "import yaml; d=list(yaml.safe_load_all(open('build/keeper.yaml')))[0]; yaml.dump(d.get('spec',{}), open('/tmp/local-spec.yaml','w'))"

diff -u /tmp/local-spec.yaml /tmp/cluster-spec.yaml
```

无差异输出即表示一致。

### 8.2 Helm 部署的资源

应比对 `values` 而非 `manifest`，因为 manifest 包含 Helm 自动注入的 label、annotation、随机值等：

```bash
# 导出当前 values
helm get values clickhouse-operator -n bi-clickhouse-prod > /tmp/current-values.yaml

# 与本地 values 文件对比
diff -u helm-values.yaml /tmp/current-values.yaml
```

## 9. 部署后生成的是 Deployment 还是 StatefulSet

`make install_prod` 实际是对 `ClickHouseInstallation`（`chi`）执行 `kubectl apply`。ClickHouse Operator 收到后会为每个 shard/replica 创建 **StatefulSet**，而不是 Deployment。

### 如何确认

**1. 查看已有 StatefulSet**
```bash
kubectl get sts -n bi-clickhouse-prod
```
命名格式通常为 `chi-<chi-name>-<cluster-name>-<shard>-<replica>`。

**2. 从配置特征推断**
`clickhouse-prod.yaml` 中定义了：
- `podTemplate`
- `dataVolumeClaimTemplate` / `logVolumeClaimTemplate`

这些都是 StatefulSet 的典型特征（需要稳定的网络标识和持久化存储）。

**3. dry-run 的局限**
```bash
kubectl apply -f build/clickhouse-prod.yaml -n bi-clickhouse-prod --dry-run=client
```
该命令只能验证 `ClickHouseInstallation` 本身是否合法，**无法预览 Operator 最终会创建的 StatefulSet**。只能在 apply 后通过 `kubectl get` 查看实际生成的子资源。

## 10. 重新部署后 PVC 保留什么数据

`clickhouse-prod.yaml` 中定义了 `dataVolumeClaimTemplate` 和 `logVolumeClaimTemplate`，分别挂载到 `/var/lib/clickhouse` 和 `/var/log/clickhouse-server`。

### data PVC（`/var/lib/clickhouse`）

- **表结构定义**（`metadata/`）：数据库、表的 DDL
- **S3 磁盘元数据**（`disks/ceph_ssd/`、`disks/ceph_hdd/`、`disks/obs/`）：记录 part 在 S3 上的位置索引
- **系统表数据**：`system.*` 等本地表
- **未指定 S3 存储策略的表数据**：使用默认本地存储的实际数据

### log PVC（`/var/log/clickhouse-server`）

- ClickHouse 服务运行日志

### 关键结论

| 数据类型 | 实际存储位置 | 重新部署后 |
|---|---|---|
| 业务表数据（MergeTree 等）| S3（CEPH/OBS）| 不丢，数据在对象存储上 |
| 表结构定义、S3 元数据索引 | data PVC | PVC 重新挂载后保留 |
| 系统表、本地临时数据 | data PVC | PVC 重新挂载后保留 |
| 运行日志 | log PVC | PVC 重新挂载后保留 |

只要 `ClickHouseInstallation` 的 `metadata.name` 和集群结构不变，PVC 能正确重新挂载，ClickHouse 启动后就能识别到之前的表和 S3 数据。

## 11. Kafka 引擎表在重新部署后是否会继续消费

会。`ENGINE = Kafka()` 的表定义存储在 data PVC 的 `metadata/` 目录下，PVC 重新挂载后表会自动恢复，ClickHouse 启动后会继续消费。

### 消费进度

Kafka 的 offset 由 **Kafka broker 端的 consumer group** 维护，不在 ClickHouse 本地。只要 consumer group 没被 Kafka 清理，重启后会从上次 offset 继续消费。

### 风险点

| 情况 | 影响 |
|---|---|
| 正常重启/重新部署 | 无缝衔接，继续消费 |
| 停机超过 Kafka `offsets.retention.minutes`（默认 7 天）| consumer group 被清理，可能按默认策略重新消费 |
| 改了 `kafka_group_name` | 变成全新 consumer group，按默认策略消费 |

### 默认 offset 重置策略

SQL 中未显式设置 `kafka_auto_offset_reset` 时，ClickHouse Kafka 引擎底层使用 librdkafka，其默认值为 **`latest`**（从**最新消息**开始），而非 `earliest`。

如需从头消费历史数据，需在 `CREATE TABLE` 中显式指定：
```sql
SETTINGS
    ...
    kafka_auto_offset_reset = 'earliest'
```

## 12. K8s 中的 VIP

**VIP**（Virtual IP，虚拟 IP）指不绑定到具体物理网卡、通过软件层面实现流量转发和负载均衡的 IP。

### 常见类型

| 类型 | 说明 |
|---|---|
| **Service Cluster IP** | 每个 K8s Service 自动分配的内部虚拟 IP，由 kube-proxy（iptables/IPVS）负载均衡到后端 Pod。 |
| **LoadBalancer 外部 IP** | `type: LoadBalancer` 的 Service 从云厂商获取的外部 VIP，用于集群外访问。 |
| **控制平面 VIP** | 多 Master 集群通过 Keepalived + VRRP 为 kube-apiserver 配置的高可用 VIP。 |

### VIP vs Ingress VIP

| 维度 | 普通 VIP（Service） | Ingress VIP |
|---|---|---|
| **网络层** | L4（传输层） | L7（应用层） |
| **路由依据** | IP + 端口 | HTTP host、path、header |
| **功能** | 负载均衡、端口映射 | SSL 终止、重写、限速、基于域名的多服务路由 |
| **实现者** | kube-proxy | Ingress Controller（Nginx、Traefik 等） |
| **外部暴露** | 一个 VIP 对应一个 Service | 一个 VIP 可代理多个 Service |

> 普通 VIP 管"哪个端口进哪个 Pod"；Ingress VIP 管"哪个 URL 进哪个 Service"，还能做 HTTPS 证书卸载。

## 13. Pod 反复 CrashLoopBackOff（Exit Code 139）—— S3 磁盘元数据损坏

### 现象

- `clickhouse-pod` 容器不断重启，`kubectl get pod` 显示 `CrashLoopBackOff`，`RESTARTS` 持续增加。
- 日志中出现 `<Error> system.query_views_log (...): Loading of outdated parts failed. Will terminate to avoid undefined behaviour due to inconsistent set of parts. Exception: Code: 499. DB::Exception:  This error happened for S3 disk.`
- 随后触发 `Segmentation fault (11)` / `signal Aborted (6)`，最终 Exit Code **139**。

### 原因

S3 磁盘（如 `ceph_ssd`）上某个表的**本地元数据目录**损坏，或对应的 S3 对象被清理/缺失。ClickHouse 在启动时的 `DB::MergeTreeData::loadOutdatedDataParts(bool)` 阶段读取到无效 part 信息，触发空指针崩溃。

> 业务数据的实际内容在对象存储（S3）上，`data PVC` 里只保留 part 索引和元数据。

### 排查步骤

**1. 确认崩溃的表名**

```bash
kubectl logs -n bi-clickhouse-prod chi-prod-uco-bi-0-0-0 --previous --tail=500 | grep 'Loading of outdated parts failed'
```

日志中会直接打出表名，例如：

```
system.query_views_log (f2ec918b-b0d4-4223-b3cb-ccf0445db557): Loading of outdated parts failed...
```

**2. 在 `clickhouse-backup` 容器定位本地目录**

Pod 处于 `CrashLoopBackOff` 时，`clickhouse-backup` 容器通常仍在运行，且与 `clickhouse-pod` 共享同一个 data PVC：

```bash
# 查看该表对应的软链接
kubectl exec -n bi-clickhouse-prod chi-prod-uco-bi-0-0-0 -c clickhouse-backup -- ls -la /var/lib/clickhouse/data/system/ | grep query_views_log

# 示例输出：
# query_views_log -> ../../disks/ceph_ssd/store/f2e/f2ec918b-b0d4-4223-b3cb-ccf0445db557
```

### 修复（仅限系统日志表）

系统表（如 `system.query_views_log`、`system.query_log` 等）只记录查询日志，**数据可以安全清空**。操作如下：

```bash
# 1. 删除该表在 S3 磁盘上的本地元数据目录
kubectl exec -n bi-clickhouse-prod chi-prod-uco-bi-0-0-0 -c clickhouse-backup -- \
  rm -rf /var/lib/clickhouse/disks/ceph_ssd/store/f2e/f2ec918b-b0d4-4223-b3cb-ccf0445db557

# 2. 删除 data 目录下的软链接
kubectl exec -n bi-clickhouse-prod chi-prod-uco-bi-0-0-0 -c clickhouse-backup -- \
  rm -f /var/lib/clickhouse/data/system/query_views_log

# 3. 删除 Pod 触发 StatefulSet 重新创建
kubectl delete pod -n bi-clickhouse-prod chi-prod-uco-bi-0-0-0
```

重启后 ClickHouse 会根据 `metadata/system/query_views_log.sql` 重新初始化该表，目录和软链接会自动重建。

### 批量修复：stream 库下的 `_local` 表

`stream` 数据库中的 `_local` 表是 Kafka 物化视图的目标 MergeTree 表，数据可从 Kafka 重新消费。若日志中出现大量 S3 404，且崩溃表逐个出现在这些 `_local` 表上，可一次性清空所有 `_local` 表的本地元数据：

```bash
kubectl exec -n bi-clickhouse-prod chi-prod-uco-bi-0-0-0 -c clickhouse-backup -- sh -c '
for link in /var/lib/clickhouse/data/stream/*_local; do
  target=$(readlink "$link")
  if [ -n "$target" ]; then
    abs_target="/var/lib/clickhouse/data/stream/$target"
    rm -rf "$abs_target"
  fi
  rm -f "$link"
done
'

kubectl delete pod -n bi-clickhouse-prod chi-prod-uco-bi-0-0-0
```

重启后：
- Kafka 引擎表会自动恢复并继续消费（注意默认从 **latest** offset 开始）。
- 物化视图会继续将新数据写入重新创建的 `_local` 表中。
- **历史数据会丢失**，需评估是否可接受。

### 注意事项

- **系统日志表**和 **Kafka 对应的 `_local` 表**通常可以安全清空并重建。
- 对于其他业务表，删除本地元数据前务必确认数据是否可重建，或先通过 `clickhouse-backup` 等方式备份。
- 崩溃根因通常是 S3 端对象被清理或网络异常导致元数据不一致。若频繁出现，需检查 S3 生命周期策略及 ClickHouse 的 `merge_tree/max_suspicious_broken_parts` 等参数。

## 14. Kafka Consumer Group 与 ClickHouse Shard 的关系

### 14.1 数据落在哪个 shard

ClickHouse 的 Kafka 引擎表（`ENGINE = Kafka()`）配合 Materialized View 消费时，整个链路在**每个 shard 本地独立执行**：

```
Kafka 引擎表 -> Materialized View -> _local 表
```

**哪个 shard 消费了数据，数据就写入哪个 shard 的 `_local` 表。** 数据不会跨 shard 自动同步。

当通过 Distributed 表查询时，Distributed 表会聚合所有 shard 的 `_local` 表结果，所以查询层面通常感知不到差异。但如果直接连到某个 shard 查询，或做 shard-local 操作，就会看到数据分布不均匀。

### 14.2 kafka_num_consumers 的含义

`kafka_num_consumers` 是**单个 ClickHouse 节点（shard）**上的 consumer 线程数，不是整个集群的总量。

例如 `kafka_num_consumers = 2` 时，该节点会启动 2 个独立的 consumer 线程，它们属于同一个 `kafka_group_name`，Kafka coordinator 会把不同的 partition 分配给它们。

> 同一个节点上的多个 consumer 分担不同的 partition，但数据最终都写入该节点的 `_local` 表。

### 14.3 Kafka 如何分配 partition

Kafka 的 **Group Coordinator**（某个 broker）负责管理 consumer group：

1. 当 consumer 加入/离开 group 时，触发 **rebalance**
2. Coordinator 根据分配策略（默认 `RangeAssignor` 或 `CooperativeStickyAssignor`）决定每个 consumer 消费哪些 partition
3. **同一个 consumer group 内，一个 partition 在同一时刻只能被一个 consumer 消费**

当某个 shard 宕机，它的 consumers 断开，coordinator 会将其负责的 partition **重新分配**给其他在线 shard 的 consumers。这些 consumer 会从该 partition 上次 commit 的 offset 继续消费，数据写入它们所在 shard 的 `_local` 表。

### 14.4 Offset 的粒度

Offset 虽然说是按 consumer group 记录，但实际存储粒度是 **partition 级别**。Kafka 内部的 `__consumer_offsets` topic 中，每条记录的 key 是：

```
(group_id, topic, partition) -> committed_offset
```

同一个 group 消费的不同 partition，各自的进度完全独立。rebalance 换了 consumer 来读，只是换个人从这个 offset 继续。

### 14.5 集群卸载后 offset 能保留多久

Consumer group 的 offset 不是永久保留的。Kafka 有一个关键配置：

| 配置项 | 默认值 | 含义 |
|---|---|---|
| `offsets.retention.minutes` | **10080**（7 天） | consumer group 没有任何活跃成员后，其 committed offset 保留多久会被清理 |

**分两种情况：**

| 场景 | 结果 |
|---|---|
| 在保留期内（默认 7 天内）重启集群 | ✅ 能续上。重新加入同一个 `kafka_group_name`，Kafka 会找到之前各 partition 的 offset，从断点继续消费 |
| 超过保留期才重启 | ❌ offset 已被清理。此时 Kafka 视其为"有 group 名但没有 offset 记录"，按 `kafka_auto_offset_reset` 策略消费。未显式设置时默认是 `latest`，即从最新消息开始，**中间的数据会跳过** |

如需延长保留期，可在 Kafka `server.properties` 中调整：

```properties
offsets.retention.minutes=43200  # 30 天，按需调整
```

### 14.6 为什么不建议用重置 offset 来补数据

如果某个 shard 的 `_local` 表数据被清空（如 S3 元数据损坏修复），想通过重置 Kafka offset 让该 shard 重新消费历史数据来补齐，存在以下风险：

- 被清空的 shard 重新消费历史数据，写入自己的 `_local` 表
- 但其他 shard 在宕机期间已经消费了这部分数据（通过 rebalance），它们 `_local` 表里已经有这些数据
- 结果：同一条 Kafka 消息出现在多个 shard 的 `_local` 表中
- 对于 `ReplacingMergeTree`，跨 shard **不会去重**（只在单个 shard 内按 `ORDER BY` 去重）
- 对于 `MergeTree`，就是纯重复数据

Distributed 表查询时会聚合所有 shard，导致查询结果中出现重复。

> **结论**：重置 offset 来补数据会产生跨 shard 重复，风险大于收益。如果数据缺失可接受，建议通过 Distributed 表查询覆盖；如果必须补齐，考虑从其他 shard 迁移数据，而非重刷 Kafka。

### 14.7 卸载后重新部署，为什么表里有历史数据

**现象**

`ClickHouseInstallation` 卸载后重新 `install`，查询 `stream` 库下的表（如 `stream.jushita_trade`），发现表中包含卸载期间（如几天前）的历史数据。

**原因**

Kafka 引擎表的消费进度由 **Kafka broker 端的 consumer group offset** 维护，不在 ClickHouse 本地。卸载 ClickHouse 集群只是断开了 consumer，但只要：

1. 在 `offsets.retention.minutes`（默认 7 天）内重新部署
2. 使用相同的 `kafka_group_name`

Kafka 会保留之前的消费进度。重启后 ClickHouse 作为 consumer 重新加入该 group，从上次断点继续消费，因此会把卸载期间 Kafka 中积压的数据全部写入 `_local` 表。

**数据安全性**

| 情况 | 结果 |
|---|---|
| 在 7 天内重新部署 | 数据完整。卸载期间积压的 Kafka 消息会被补上 |
| 超过 7 天才重新部署 | offset 被清理。按 `kafka_auto_offset_reset` 策略消费，默认 `latest`（从最新消息开始），**中间的数据会跳过** |

> 数据不是从 S3 "冒出来"的，而是 Kafka 里本来就有，只是延迟消费到了 ClickHouse。

