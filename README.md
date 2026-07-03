# astrbot-plugin-nai-image

基于 [nai.sta1n.cn](https://nai.sta1n.cn) (NovelAI) 的 AstrBot 生图插件。

## 指令

| 指令 | 说明 |
| --- | --- |
| `/image <提示词>` | 根据提示词生成图片 |
| `/image <提示词> --n=4` | 生成 4 张图片 (1-6) |
| `/image <提示词> --style=anime` | 指定风格 |
| `/image <提示词> --size=横图` | 指定比例 |
| `/quota` | 查询 token 剩余配额 |
| `/imgstatus` | 检查生图服务连通性 |

风格：`vertical` / `comicDoujin` / `r18` / `lolita25d` / `anime` / `galgame` / `custom`
尺寸：`竖图` / `横图` / `方图`

## 配置

插件管理面板填写 `image_gen_key`（必填）及其他高级参数。
详细配置项见 `_conf_schema.json`。
