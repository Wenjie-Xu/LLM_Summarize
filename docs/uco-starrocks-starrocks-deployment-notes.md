# StarRocks 部署与升级注意事项

## 1. 版本选择

### StarRocks 版本

- **生产环境优先使用已验证的稳定版本**，不要急于使用最新版
- uco-ods 使用 4.0.0 稳定运行，uco-dw 最初尝试 4.1.0 遇到 CN Segmentation fault（exit code 139），降级至 4.0.0 后正常
- 同一环境中多个集群建议保持相同版本，降低运维复杂度

### Operator 版本

- 当前使用 **v1.11.4**
- Operator 负责 CR → StatefulSet/Service/PVC 的调和（reconcile），版本过低可能不支持新特性
- 升级 Operator 前需确认新版本与现有 StarRocks 版本的兼容性

### Helm Chart 版本

```bash
# 查看仓库中所有 chart
helm search repo starrocks

# 查看某个 chart 的所有可用版本
helm search repo starrocks/starrocks --versions
helm search repo starrocks/operator --versions
```

**注意**：`starrocks/starrocks` 是集群 chart，`starrocks/operator` 是 Operator chart，两者版本号独立。

## 2. 配置文件注意事项

### YAML 重复键

StarRocks 的 Helm values 较长，拷贝修改时容易遗漏重复键。例如 `starrocksFESpec` 下的：

```yaml
startupProbeFailureSeconds: 600    # 旧值
livenessProbeFailureSeconds: 15    # 旧值
readinessProbeFailureSeconds: 15   # 旧值
# ... 中间隔了其他配置 ...
startupProbeFailureSeconds: 420    # 新值
livenessProbeFailureSeconds: 30    # 新值
readinessProbeFailureSeconds: 30   # 新值
```

**后果**：Helm 渲染时报 `Map keys must be unique` 错误，或后加载的值被覆盖。

**建议**：每次修改后用 `helm template` 预渲染检查：

```bash
make template_uco_dw
```

### Probe 配置

- `startupProbeFailureSeconds`：FE 元数据加载慢，建议 ≥ 420 秒（7 分钟）
- `livenessProbeFailureSeconds` / `readinessProbeFailureSeconds`：建议 30 秒

## 3. Storage 与 Shared-Data 模式

### 默认存储路径

shared-data 集群的默认数据存储在 `fe.conf` 中配置：

```yaml
starrocksFESpec:
  config:
    aws_s3_path: "${STARROCKS_UCO_DW_DL_PATH}"
    run_mode: shared_data
    enable_load_volume_from_conf: true
```

**重要**：不要在初始化 SQL 中执行 `SET <volume> AS DEFAULT STORAGE VOLUME`，这会覆盖 `fe.conf` 中的默认路径，导致新建表写到错误的 S3 路径。

### Storage Volume 使用原则

| Volume 类型 | 用途 | 是否设为默认 |
|-------------|------|--------------|
| `fe.conf` 内置 | 主数据存储 | ✅ 默认 |
| `obs_*_backup` | 集群快照/元数据备份 | ❌ 仅用于 `ADMIN SET AUTOMATED CLUSTER SNAPSHOT` |
| `*_ceph_hdd` | 冷数据/归档 | ❌ 建表时显式指定 `PROPERTIES ("storage_volume" = "xxx")` |

### 集群快照（Cluster Snapshot）

```sql
-- 开启自动化快照
ADMIN SET AUTOMATED CLUSTER SNAPSHOT ON STORAGE VOLUME <backup_volume>;

-- 查看快照状态
SELECT * FROM information_schema.cluster_snapshot_jobs;
SELECT * FROM information_schema.cluster_snapshots;

-- 关闭
ADMIN SET AUTOMATED CLUSTER SNAPSHOT OFF;
```

**新集群注意**：`config/cluster_snapshot_*.yaml` 若配置了旧集群的 snapshot path，会导致 FE 启动时尝试恢复旧元数据，引发 CN "already exists" 等异常。全新集群应保持该文件为空（全部注释掉）。

## 4. 网络与访问

### NodePort

- NodePort 在集群节点上是**全局**的，不同 Service 不能使用相同端口
- 但不同集群的 Service 若在不同命名空间，NodePort 值本身可以相同（K8s 不允许，需确认）
- uco-dw 当前使用：HTTP 30080，MySQL 30090

### Ingress

- Ingress（nginx）默认只支持 HTTP/HTTPS，**不支持 MySQL 协议**
- 如需域名访问 MySQL 端口，需配置 nginx-ingress 的 `tcp-services` ConfigMap
- Ingress 域名仅用于 Web UI 和 HTTP API

## 5. 资源与扩缩容

### CN 资源调整

CN（Compute Node）资源可根据业务负载调整：

```yaml
starrocksCnSpec:
  replicas: 3
  resources:
    requests:
      cpu: 16
      memory: 48Gi
    limits:
      cpu: 16
      memory: 48Gi
```

**扩缩容方式**：
- 修改 `replicas` 后执行 `helm upgrade`
- 修改 CPU/内存后，StatefulSet 会滚动更新 Pod

**注意**：CN 有本地缓存（cache 和 spill），滚动更新时会重新从 S3 加载热数据，短期内查询性能可能下降。

### load_process_max_memory_limit_percent

导入任务内存限制百分比，默认较小。大数据量导入时建议调高：

```yaml
starrocksCnSpec:
  config:
    load_process_max_memory_limit_percent = 60
```

## 6. PVC / PV 生命周期

### 删除集群时

```bash
helm uninstall uco-dw -n bi-starrocks
```

- **PVC**：随 Helm release 删除而删除
- **PV**：取决于 StorageClass 的 `reclaimPolicy`
  - `Delete`：PVC 删除后 PV 自动删除，数据清空
  - `Retain`：PVC 删除后 PV 变为 `Released` 状态，数据保留，需手动清理

### 清理 Released PV

```bash
# 查看 Released 的 PV
kubectl get pv | grep Released

# 删除（确认无需要保留的数据后）
kubectl delete pv <pv-name>
```

**注意**：即使 PV 未删除，已分配但未使用的存储空间**不会**释放回 Ceph/云盘供其他资源使用（取决于存储后端）。建议及时清理无用 PV。

## 7. 部署流程 checklist

```bash
# 1. 确认版本
export VERSION=4.0.0
export OPERATOR_VERSION=1.11.4

# 2. 生成配置
make config

# 3. 预渲染检查
make template_uco_dw

# 4. 部署集群
make install_uco_dw

# 5. 监控状态（FE 先 Ready，CN 再创建）
watch kubectl get pods -n bi-starrocks | grep uco-dw

# 6. 部署 Ingress（集群稳定后）
make install_uco_dw_ingress

# 7. 执行初始化 SQL
make generate_uco_dw_sql
mysql -h <node_ip> -P 30090 -u root -p < build/sqls/uco_dw.sql
```

## 8. 常见问题

### CN CrashLoopBackOff + "Compute node already exists"

**根因**：通常是 CN 进程崩溃（如 4.1.0 segfault）后重启，向 FE 注册时发现同名节点已存在。

**解决**：
1. 确认不是 snapshot 恢复导致（检查 `cluster_snapshot_dw.yaml`）
2. 查看 CN 日志确认真实崩溃原因：`kubectl logs uco-dw-cn-0 -n bi-starrocks`
3. 如为版本 bug，降级 StarRocks 版本后重建集群

### Init Password Job 失败

**表现**：`uco-dw-initpwd` Pod 报错 `ERROR 2003 Can't connect to MySQL server`

**原因**：FE 尚未完全启动，MySQL 端口未监听。

**解决**：无需处理，Job 会自动重试，FE Ready 后会成功。

### Segmentation fault (exit code 139)

**根因**：StarRocks C++ 二进制崩溃，通常是版本兼容性或硬件/指令集问题。

**排查**：
- 对比相同配置下其他版本是否正常（控制变量法）
- 检查节点内核版本、CPU 型号是否满足要求
- 查看 CN/BE 日志中的 stack trace
