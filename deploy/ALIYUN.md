# 阿里云部署说明

- 服务器：`root@8.131.69.97`
- 远端目录：`/opt/steam-group-rec`
- 服务名：`steam-group-rec`
- 默认端口：`8673`
- DeepSeek 环境文件：`/etc/steam-group-rec.env`

本项目不把 Steam API key、AI key、用户库存写入服务器数据库。服务器只保存可共享的游戏属性缓存。

## 部署

```bash
./scripts/deploy_aliyun.sh
```

项目当前无第三方运行时依赖，脚本中的 `pip install -r requirements.txt` 会快速完成。

部署脚本会从本机 `配置.md` 读取 DeepSeek key，并写入远端 `/etc/steam-group-rec.env`。该文件不进 git。

## 常用运维

```bash
ssh root@8.131.69.97 'systemctl status steam-group-rec --no-pager'
ssh root@8.131.69.97 'journalctl -u steam-group-rec -n 100 --no-pager'
ssh root@8.131.69.97 'systemctl restart steam-group-rec'
```
