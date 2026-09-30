# data/ —— 运行时数据，不进版本库

这个目录存放 **PocketBase** 导出和 **Station** 主库的 SQLite 文件：

| 文件 | 用途 |
|------|------|
| `pb_data/data.db` | PocketBase 主库（用户、认证、集合配置） |
| `pb_data/auxiliary.db` | PocketBase 本地附件缓存 |
| `station.db` | Station 业务库（agents / tasks / messages / memories / workflows / crons） |

它们已被 `.gitignore` 排除，理由有二：

1. **体积**：每次运行都会产生 diff，仓库迅速膨胀。
2. **安全**：这些库里有 `_superusers` 表（bcrypt 密码哈希）与
   PocketBase `tokenKey`（**JWT 签名密钥**）。拿到 tokenKey 就能伪造令牌。
   2026-09-29 之前它们曾被误提交，已从 git 历史中彻底清除。

## 第一次运行

应用会自动建库。若需初始化 PocketBase：

```bash
./run.sh          # 或 run.bat
```

## 备份

```bash
cp data/station.db ~/backup/station-$(date +%F).db
```

数据库文件本身就是完整备份，直接拷走即可。
