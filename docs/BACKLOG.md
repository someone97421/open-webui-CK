# 待议事项

## 工具结果历史图片持续重发

- 现状：Terminal 读图会先生成预览图（JPEG，长边 ≤ 2048，单张 ≤ 2MB，见 `open_terminal/env.py` 的 `OPEN_TERMINAL_IMAGE_MAX_*`），不会发送原图。WebUI 不再二次处理，之后每轮工具续接都会把会话中全部历史工具图片转为 base64 原样重发（`backend/open_webui/utils/middleware.py` 中 `convert_output_to_messages(..., flatten_tool_images=True)` 与 `convert_url_images_to_base64`）。
- 影响：多轮读图任务（图表、幻灯片预览校验等）中请求体和图片 token 持续累积，首字延迟变长，模型回空或网关超时的概率上升。
- 候选方案：在 `normalize_messages_for_model` 统一出口，把较早的工具结果图片降级为确定性缩略图（如长边 512、固定 JPEG 参数）；最近若干张保持原样。
- 缓存约束：提示缓存按前缀匹配，替换旧图会让该位置之后的缓存失效。必须批量降级（超过阈值后一次性降级一批），不能按滑动窗口逐张降级；缩略图生成参数要固定，保证相同输入得到相同字节。
- 待定：是否实施、保留张数、批量大小、缩略图尺寸，以及是否覆盖用户直接上传的图片。
