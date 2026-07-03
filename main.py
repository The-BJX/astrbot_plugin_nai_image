import asyncio
import base64
import os
import time
from typing import Optional

import aiohttp
from aiohttp import web
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image as Img, Plain
from astrbot.api.star import Context, Star, register

IMAGE_GEN_BASE_URL_DEFAULT = "https://nai.sta1n.cn"
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8765

IMAGE_STYLES = {
    "vertical": "韩漫小清新风",
    "comicDoujin": "漫画同人风",
    "r18": "2.5D唯美风",
    "lolita25d": "2.5D唯美风（萝）",
    "anime": "本子里番风",
    "galgame": "GalGame风",
    "custom": "自定义",
}

IMAGE_SIZES = {
    "竖图": "portrait",
    "横图": "landscape",
    "方图": "square",
}

DEFAULT_ARTISTS = {
    "vertical": "masterpiece, best quality,[[[artist:dishwasher1910]]], {{yd_(orange_maru)}}, [artist:ciloranko], [artist:sho_(sho_lwlw)], [ningen mame], soft lighting,year 2024",
    "comicDoujin": "masterpiece,best quality,ultra detailed,by 小田武士,by 内尾和正,by あずーる,TV anime screencap,clean cel shading,soft lineart,subtle bloom glow",
    "r18": (
        "20::best quality, absurdres, very aesthetic, detailed, masterpiece::, 20::highly finished::, "
        "10::ultra detailed::, 5::masterpiece::, 5::best quality::, "
        "2.4::kidmo::, 1.2::omone hokoma agm::, 1.1::dino, wanke, liduke::, "
        "0.8::rurudo, mignon, artist:pottsness, artist:toosaka asagi::, 0.7::misaka_12003-gou::, "
        "0.6::artist:chocoan, artist:ciloranko, artist:rhasta, artist:sho_sho_lwlw::, "
        "dino_(dinoartforame), agoto, akakura, "
        "year 2025, textless version, no text, The image is highly intricate finished drawn. "
        "1.35::A highly finished photo-style artwork that has graphic texture, realistic skin surface, "
        "and lifelike flesh with little obliques::, smooth line, glossy skin, realistic, 4k, "
        "1.63::photorealistic::, 1.63::photo(medium)::, 3::simple background::, 2::depth of field::, "
        "1.5::vivid color, lively color::, desaturated, muted tones, cinematic desaturation, "
        "pale aesthetic, silver-toned, -2::green::, -1.5::vibrant, colorful, saturated::"
    ),
    "lolita25d": (
        "20::best quality, absurdres, very aesthetic, detailed, masterpiece::, 20::highly finished::, "
        "10::ultra detailed::, 5::masterpiece::, 5::best quality::, "
        "2.4::kidmo::, 1.2::omone hokoma agm::, 1.1::dino, wanke, liduke::, "
        "0.8::rurudo, mignon, artist:pottsness, artist:toosaka asagi::, 0.7::misaka_12003-gou::, "
        "0.6::artist:chocoan, artist:ciloranko, artist:rhasta, artist:sho_sho_lwlw::, "
        "dino_(dinoartforame), agoto, akakura, "
        "0.9::rurudo(Only body shape), mignon(Only body shape)::, "
        "year 2025, textless version, {{petite,loli}}, Petite figure, no text, "
        "1.35::A highly finished photo-style artwork that has graphic texture, realistic skin surface, "
        "and lifelike flesh with little obliques::, smooth line, glossy skin, realistic, 4k, "
        "1.63::photorealistic::, 1.63::photo(medium)::, 3::simple background::, 2::depth of field::, "
        "1.5::vivid color, lively color::, desaturated, muted tones, "
        "-2::green::, -1.5::vibrant, colorful, saturated::"
    ),
    "anime": (
        "1.4::asanagi::,{{{{{artist:asanagi}}}}},1.2::xiaoluo_xl::,1.3::Artist: misaka_12003-gou::,"
        "1.2::Artist:shexyo::,0.7::Artist:b.sa_(bbbs)::,1::Artist:qiandaiyiyu::,"
        "1.05::artist:natedecock::,1.05::artist:kunaboto::,0.75::artist:kandata_nijou::,"
        "1.05::artist:zer0.zer0::,1.05::artist:jasony::,0.75::misaka_12003-gou::, "
        "dino_(dinoartforame), wanke, liduke, year 2025, realistic, 4k, -2::green::, "
        "{textless version, The image is highly intricate finished drawn,write realistically,true to life}, "
        "1.35::A highly finished photo-style artwork that has lively color, graphic texture, "
        "realistic skin surface, and lifelike flesh with little obliques::, "
        "1.63::photorealistic::,3::age slider::,1.63::photo(medium)::, "
        "2::best quality, absurdres, very aesthetic, detailed, masterpiece::,-4::Muscle definition, abs::"
    ),
    "galgame": (
        "artist:ningen_mame,, noyu_(noyu23386566),, toosaka asagi,, location,\\n"
        "20::best quality, absurdres, very aesthetic, detailed, masterpiece::,:,, "
        "very aesthetic, masterpiece, no text,"
    ),
}

DEFAULT_NEGATIVE = (
    "{{bad anatomy}},{bad feet},bad hands,{{{bad proportions}}},{blurry},cloned face,cropped,"
    "{{{deformed}}},{{{disfigured}}},error,{{{extra arms}}},{extra digit},{{{extra legs}}},extra limbs,"
    "{{extra limbs}},{fewer digits},{{{fused fingers}}},gross proportions,ink eyes,ink hair,"
    "jpeg artifacts,{{{{long neck}}}},low quality,{malformed limbs},{{missing arms}},{missing fingers},"
    "{{missing legs}},{{{more than 2 nipples}}},mutated hands,{{{mutation}}},normal quality,owres,"
    "{{poorly drawn face}},{{poorly drawn hands}},reen eyes,signature,text,{{too many fingers}},"
    "{{{ugly}}},username,uta,watermark,worst quality,{{{more than 2 legs}}},"
    "awkward hand sign,weird hand gesture,contorted hand,unnatural finger pose,deformed hand gesture,"
    "{shaka},{hang loose},{{rock on}},{shaka sign}"
)


def _parse_args(text: str) -> dict:
    import re

    args = {"prompt": "", "n": None, "style": None, "size": None}
    flags = re.findall(r"--(\w+)=([^\s]+)", text)
    for k, v in flags:
        if k in args:
            args[k] = v
    prompt = re.sub(r"--\w+=[^\s]+", "", text).strip()
    args["prompt"] = prompt
    return args


@register("astrbot_plugin_nai_image", "缪缪的小水泡", "基于 nai.sta1n.cn 的 NovelAI 生图插件", "1.0.0")
class NAIGenerateImagePlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context, config)
        self.base_url: str = (config.get("base_url") or IMAGE_GEN_BASE_URL_DEFAULT).strip() or IMAGE_GEN_BASE_URL_DEFAULT
        self.image_gen_key: str = (config.get("image_gen_key") or "").strip()
        self.image_style: str = config.get("image_style") or "vertical"
        self.image_size: str = config.get("image_size") or "竖图"
        try:
            self.image_count: int = max(1, min(6, int(config.get("image_count") or 2)))
        except (TypeError, ValueError):
            self.image_count = 2
        self.custom_artists: str = config.get("custom_artists") or ""
        self.model: str = config.get("model") or "nai-diffusion-4-5-full"
        try:
            self.steps: int = int(config.get("steps") or 40)
        except (TypeError, ValueError):
            self.steps = 40
        try:
            self.scale: int = int(config.get("scale") or 6)
        except (TypeError, ValueError):
            self.scale = 6
        try:
            self.cfg_value: int = int(config.get("cfg") or 0)
        except (TypeError, ValueError):
            self.cfg_value = 0
        self.sampler: str = config.get("sampler") or "k_dpmpp_2m_sde"
        self.noise_schedule: str = config.get("noise_schedule") or "karras"
        neg = config.get("negative")
        self.negative: str = neg if neg else DEFAULT_NEGATIVE
        # 预输入模板（私聊hook、群聊、/image 命令都生效）
        self.enable_template: bool = bool(config.get("enable_template", True))
        self.character_preset: str = (config.get("character_preset") or "").strip()
        self._session: Optional[aiohttp.ClientSession] = None
        # 代理服务器（陪伴插件 → 本代理 → nai.sta1n.cn）
        self.proxy_runner: Optional[web.AppRunner] = None
        self.proxy_port: int = int(config.get("proxy_port") or PROXY_PORT)

    def _build_full_prompt(self, user_prompt: str) -> str:
        """拼接模板：角色预设 + 用户提示词"""
        if not self.enable_template or not self.character_preset:
            return user_prompt.strip()
        return f"{self.character_preset}, {user_prompt.strip()}"

    async def initialize(self):
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180))
        logger.info(f"[NAI-Image] plugin initialized, base_url={self.base_url}, token exists: {bool(self.image_gen_key)}")
        # 启动本地代理服务器
        try:
            await self._start_proxy_server()
        except Exception as e:
            logger.error(f"[NAI-Image] 代理服务器启动失败: {e!r}")

    async def terminate(self):
        await self._stop_proxy_server()
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("[NAI-Image] plugin terminated")

    def _resolve_artists(self, style: str) -> str:
        if style == "custom":
            return self.custom_artists or DEFAULT_ARTISTS.get("vertical", "")
        return DEFAULT_ARTISTS.get(style, DEFAULT_ARTISTS["vertical"])

    def _resolve_size(self, size: str) -> str:
        return IMAGE_SIZES.get(size, "portrait")

    async def _check_status(self) -> tuple[bool, int]:
        if not self._session:
            return False, -1
        start = time.perf_counter()
        try:
            async with self._session.get(self.base_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                latency = int((time.perf_counter() - start) * 1000)
                return True, latency
        except Exception as e:
            logger.warning(f"[NAI-Image] status check failed: {e}")
            return False, -1

    async def _fetch_quota(self) -> Optional[int]:
        if not self.image_gen_key or not self._session:
            return None
        url = f"{self.base_url.rstrip('/')}/api/api/getUser"
        try:
            async with self._session.post(
                url,
                json={"toUserId": self.image_gen_key},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if data.get("status") == "ok" and data.get("type") == "sta1n":
                    val = int(data.get("data", {}).get("value", 0))
                    return val
                return None
        except Exception as e:
            logger.warning(f"[NAI-Image] quota fetch failed: {e}")
            return None

    async def _generate_one(self, prompt: str, style: str, size: str) -> Optional[bytes]:
        if not self.image_gen_key or not self._session:
            return None
        artists = self._resolve_artists(style)
        from urllib.parse import quote

        # 应用模板拼接（如果启用）
        full_prompt = self._build_full_prompt(prompt)
        logger.debug(f"[NAI-Image] final prompt: {full_prompt[:100]}")

        url = (
            f"{self.base_url.rstrip('/')}/generate"
            f"?tag={quote(full_prompt)}"
            f"&token={self.image_gen_key}"
            f"&model={self.model}"
            f"&artist={quote(artists)}"
            f"&size={size}"
            f"&steps={self.steps}"
            f"&scale={self.scale}"
            f"&cfg={self.cfg_value}"
            f"&sampler={self.sampler}"
            f"&negative={quote(self.negative)}"
            f"&nocache=0"
            f"&noise_schedule={self.noise_schedule}"
        )
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status != 200:
                    logger.warning(f"[NAI-Image] generate failed, status={resp.status}")
                    return None
                return await resp.read()
        except asyncio.TimeoutError:
            logger.warning("[NAI-Image] generate timeout")
            return None
        except Exception as e:
            logger.warning(f"[NAI-Image] generate error: {e}")
            return None

    async def _start_proxy_server(self):
        """启动本地代理服务器，陪伴插件的 OpenAI 格式请求直接通过 NAI 插件自己的 _generate_one 生图"""
        app = web.Application()
        app.router.add_post("/v1/images/generations", self._proxy_handle_generations)
        app.router.add_post("/v1/images/edits", self._proxy_handle_edits)
        app.router.add_get("/v1/images/generations", self._proxy_handle_health)
        app.router.add_get("/v1/proxy_status", self._proxy_handle_health)
        self.proxy_runner = web.AppRunner(app)
        await self.proxy_runner.setup()
        site = web.TCPSite(self.proxy_runner, PROXY_HOST, self.proxy_port)
        await site.start()
        logger.info(
            f"[NAI-Image] 本地代理已启动: http://{PROXY_HOST}:{self.proxy_port}/v1/images/generations"
        )

    async def _stop_proxy_server(self):
        if self.proxy_runner:
            try:
                await self.proxy_runner.cleanup()
                logger.info("[NAI-Image] 本地代理已停止")
            except Exception as e:
                logger.warning(f"[NAI-Image] 代理停止异常: {e!r}")
            self.proxy_runner = None

    async def _proxy_handle_health(self, request: web.Request):
        return web.json_response({
            "status": "ok",
            "plugin": "astrbot_plugin_nai_image",
            "base_url": self.base_url,
            "token_configured": bool(self.image_gen_key),
        })

    async def _proxy_handle_generations(self, request: web.Request):
        if not self.image_gen_key or not self._session:
            return web.json_response(
                {"error": {"message": "NAI 插件未配置 image_gen_key", "type": "invalid_request_error"}},
                status=400,
            )
        try:
            body = await request.json()
        except Exception as e:
            return web.json_response(
                {"error": {"message": f"invalid json: {e!r}", "type": "invalid_request_error"}},
                status=400,
            )
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            return web.json_response(
                {"error": {"message": "prompt is required", "type": "invalid_request_error"}},
                status=400,
            )
        # size 取 OpenAI 格式 "WxH"，传给 NAI 插件 _generate_one 用
        size = body.get("size") or "1024x1024"
        n = max(1, min(4, int(body.get("n") or 1)))

        if not self.image_gen_key:
            return web.json_response(
                {"error": {"message": "NAI 插件未配置 image_gen_key", "type": "invalid_request_error"}},
                status=400,
            )

        # 直接复用 NAI 插件自己的 _generate_one —— 站点和 key 都由 NAI 插件自己管
        logger.info(f"[NAI-Image] proxy 收到请求: prompt={prompt[:80]} size={size}")
        try:
            img_bytes = await self._generate_one(prompt, self.image_style, size)
        except Exception as e:
            logger.warning(f"[NAI-Image] proxy _generate_one 异常: {e!r}")
            return web.json_response(
                {"error": {"message": f"generate exception: {e!r}", "type": "internal_error"}},
                status=500,
            )

        if not img_bytes:
            return web.json_response(
                {"error": {"message": "generate failed (no bytes returned)", "type": "upstream_error"}},
                status=502,
            )

        b64 = base64.b64encode(img_bytes).decode()
        logger.info(f"[NAI-Image] proxy 生成成功: {len(img_bytes)} bytes")
        return web.json_response(
            {
                "created": int(time.time()),
                "data": [{"b64_json": b64} for _ in range(n)],
            }
        )

    async def _proxy_handle_edits(self, request: web.Request):
        """降级方案：OpenAI 风格的 /v1/images/edits（multipart/form-data，参考图改图）。

        陪伴插件在自拍/自拍改图场景默认走这个接口，但我们搭的代理 server
        没接 nai.sta1n.cn 的改图 API，所以这里把请求里的 multipart 字段解析出来，
        丢弃参考图，按纯文生图处理，避免 404。
        """
        if not self.image_gen_key or not self._session:
            return web.json_response(
                {"error": {"message": "NAI 插件未配置 image_gen_key", "type": "invalid_request_error"}},
                status=400,
            )
        prompt = ""
        size = "1024x1024"
        n = 1
        try:
            reader = await request.multipart()
            async for part in reader:
                if part.name == "prompt":
                    prompt = (await part.text()).strip()
                elif part.name == "size":
                    raw_size = (await part.text() or "").strip()
                    if raw_size:
                        size = raw_size
                elif part.name == "n":
                    try:
                        n = max(1, min(4, int((await part.text() or "").strip())))
                    except Exception:
                        n = 1
                elif part.name in ("image", "mask", "image[]", "mask[]"):
                    # 显式丢弃参考图 / 蒙版，按纯文生图降级
                    await part.read()
        except Exception as e:
            logger.warning(f"[NAI-Image] proxy edits multipart 解析失败: {e!r}")
            return web.json_response(
                {"error": {"message": f"invalid multipart: {e!r}", "type": "invalid_request_error"}},
                status=400,
            )
        if not prompt:
            return web.json_response(
                {"error": {"message": "prompt is required", "type": "invalid_request_error"}},
                status=400,
            )
        logger.info(
            f"[NAI-Image] proxy edits 降级到纯文生图: prompt={prompt[:80]} size={size} n={n} (参考图已丢弃)"
        )
        try:
            img_bytes = await self._generate_one(prompt, self.image_style, size)
        except Exception as e:
            logger.warning(f"[NAI-Image] proxy edits _generate_one 异常: {e!r}")
            return web.json_response(
                {"error": {"message": f"generate exception: {e!r}", "type": "internal_error"}},
                status=500,
            )
        if not img_bytes:
            return web.json_response(
                {"error": {"message": "generate failed (no bytes returned)", "type": "upstream_error"}},
                status=502,
            )
        b64 = base64.b64encode(img_bytes).decode()
        logger.info(f"[NAI-Image] proxy edits 生成成功: {len(img_bytes)} bytes")
        return web.json_response(
            {
                "created": int(time.time()),
                "data": [{"b64_json": b64} for _ in range(n)],
            }
        )

    @filter.command("image")
    async def image(self, event: AstrMessageEvent):
        """生图指令。用法: /image <提示词> [--n=数量] [--style=风格] [--size=尺寸]"""
        text = event.message_str or ""
        if not text.strip():
            yield event.plain_result(
                "用法: /image <提示词> [--n=1-6] [--style=vertical|comicDoujin|r18|lolita25d|anime|galgame|custom] [--size=竖图|横图|方图]"
            )
            return

        args = _parse_args(text)
        prompt = args["prompt"]
        if not prompt:
            yield event.plain_result("请提供提示词。")
            return

        if not self.image_gen_key:
            yield event.plain_result("未配置 image_gen_key，请先在插件配置中填写 token。")
            return

        try:
            n = int(args["n"]) if args["n"] else self.image_count
        except (TypeError, ValueError):
            n = self.image_count
        n = max(1, min(6, n))

        style = args["style"] or self.image_style
        size_cn = args["size"] or self.image_size
        size = self._resolve_size(size_cn)

        if style not in IMAGE_STYLES and style != "custom":
            yield event.plain_result(
                f"未知风格: {style}\n可选: {', '.join(IMAGE_STYLES.keys())}"
            )
            return

        yield event.plain_result(
            f"提示词: {prompt}\n风格: {IMAGE_STYLES.get(style, style)}，比例: {size_cn}，共 {n} 张"
        )

        success = 0
        for i in range(n):
            img_bytes = await self._generate_one(prompt, style, size)
            if img_bytes:
                success += 1
                yield event.chain_result([
                    Plain(f"[{i + 1}/{n}]"),
                    Img.fromBytes(img_bytes),
                ])
            else:
                yield event.plain_result(f"第 {i + 1}/{n} 张生成失败。")

        if success == 0:
            yield event.plain_result("全部图片生成失败，请检查 token 或网络。")

    @filter.command("quota")
    async def quota(self, event: AstrMessageEvent):
        """查询 NAI 生图 token 配额。"""
        if not self.image_gen_key:
            yield event.plain_result("未配置 image_gen_key。")
            return
        yield event.plain_result("正在查询配额...")
        val = await self._fetch_quota()
        if val is None:
            yield event.plain_result("配额查询失败，请检查 token 或网络。")
        else:
            yield event.plain_result(f"剩余配额: {val}")

    @filter.command("imgstatus")
    async def imgstatus(self, event: AstrMessageEvent):
        """检查 NAI 生图服务连通性。"""
        yield event.plain_result("正在检查生图服务...")
        ok, latency = await self._check_status()
        if ok:
            yield event.plain_result(f"生图服务可用，延迟约 {latency}ms")
        else:
            yield event.plain_result("生图服务不可用，请稍后重试。")


    @filter.on_decorating_result()
    async def auto_generate_for_companion(self, event: AstrMessageEvent):

        return

    def _save_companion_image(self, img_bytes: bytes, prompt: str) -> Optional[str]:
        try:
            import hashlib
            from datetime import datetime
            from pathlib import Path

            save_dir = Path("./data/companion_images")
            save_dir.mkdir(parents=True, exist_ok=True)

            name = (
                f"companion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                f"_{hashlib.md5(prompt.encode()).hexdigest()[:8]}.jpg"
            )
            save_path = save_dir / name
            save_path.write_bytes(img_bytes)
            return str(save_path)
        except Exception as e:
            logger.warning(f"[NAI-Image] 保存图片失败: {e}")
            return None
