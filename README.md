# bilibili-favorites-manager

B站收藏夹管理工具 —— **简单的增删改查（CRUD）**。基于 `bilibili-API-collect/docs/fav/` 实现，命令少、职责单一，全部操作可审计、可重跑。

## 环境要求

- Python 3.7+，**仅需标准库，无第三方依赖**（请求层用 `urllib` 实现，不需要 `curl` 或 `requests`）

## 命令一览

### 收藏夹

| 命令 | CRUD | 说明 |
|---|---|---|
| `bili.py folders` | R | 查看全部收藏夹（名称/id/公开/数量） |
| `bili.py folder-add <标题>` | C | 新建收藏夹（公开，返回新 id） |
| `bili.py folder-rename <id> <新名>` | U | 收藏夹改名 |
| `bili.py folder-del <id>` | D | 删除收藏夹（自动先清空内容，⚠️ 夹内收藏会一并移除） |

### 收藏内容

| 命令 | CRUD | 说明 |
|---|---|---|
| `bili.py list <media_id>` | R | 查看某收藏夹内容（标题/BV/UP主/时长/失效状态） |
| `bili.py fetch` | R | 把全部收藏夹内容备份快照到 `data/` |
| `bili.py add <avid…> --to <夹id> [--from <夹id>]` | C | 添加视频。默认逐条直接添加（不依赖源夹）；提供 `--from` 时改为从源夹批量复制 |
| `bili.py remove <avid…> --from <夹id>` | D | 从收藏夹移除视频 |
| `bili.py clean <media_id…>` | D | 清空收藏夹内全部失效内容 |

### 示例

```bash
./bili.py folders                                        # 查看收藏夹
./bili.py list 1262420668                                # 查看默认收藏夹内容
./bili.py add 678050583 --to 1262420668                  # 收藏一个视频
./bili.py add 678050583 927074448 --from 3273814068 --to 1262420668  # 从某夹复制
./bili.py remove 927074448 --from 1262420668             # 取消收藏
./bili.py clean 1262420668                               # 清失效
./bili.py folder-add 新分类 → folder-rename → folder-del  # 夹的增改删
```

## 参数

- `--cookie PATH`：cookie 文件，默认 `./cookie.txt`（也可设环境变量 `BILI_COOKIE`）。需要含 `SESSDATA`、`bili_jct`（CSRF）、`DedeUserID`，后两者自动提取。⚠️ cookie 是你的**登录凭据**，请勿提交到 git、分享或截图外传。
- `--outdir DIR`：数据目录，默认 `./data`，仅 `fetch` 使用。

## data/ 目录是什么

`data/` 是 **fetch 生成的收藏内容快照**，纯离线数据，供查看、审计与恢复参考：

| 文件 | 内容 |
|---|---|
| `folders.json` | 收藏夹列表（id/名称/公开与否/数量，即 `folder/created/list-all` 原始返回） |
| `<media_id>.json` | 单个收藏夹的完整内容明细（每条含 avid/bvid/标题/UP主/时长/收藏时间等原始字段），文件名即收藏夹 id |

## 关联文档

API 完整参考见 `bilibili-API-collect/docs/fav/{info,list,action}.md`。
收藏夹 id（mlid）形如 `1262420668`，由 `folders` 命令获取。