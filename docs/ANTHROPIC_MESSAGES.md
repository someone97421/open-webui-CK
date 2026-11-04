# 网页聊天接入 Anthropic Messages

在管理员的连接设置中添加服务端连接，将 **API Type** 选为 **Anthropic Messages**。官方基础地址为 `https://api.anthropic.com/v1`；该地址在未指定其他协议时会自动识别为 Messages。第三方服务填写其原生 Messages 基础地址，后端会追加 `/messages`，不要填写完整的 `/messages` 路径。

官方连接的默认 API 密钥通过 `x-api-key` 发送，并自动补上 `anthropic-version`。第三方连接沿用所选鉴权方式；需要 `x-api-key` 的网关可选择无鉴权，在自定义请求头中配置该字段。自定义 `Authorization`、`anthropic-version`、`anthropic-beta` 等请求头会保留。连接验证与模型列表也使用对应协议；未提供模型列表接口的网关可手动填写模型 ID。

支持普通与流式文本、图片、函数工具定义、并行工具调用及工具结果（含图片）。网页实时显示供应商返回的思考文本；思考块结束后保存完整签名或 redacted thinking，供同模型的历史与工具续聊回传。无签名思考不会冒充有效思考块回传，跨模型思考详情沿用现有剥离规则。

## 思考参数

未指定输出上限时默认 `max_tokens=4096`。配置通用 `reasoning_effort` 时，使用 `thinking: {"type":"adaptive"}`，并映射为原生 `output_config.effort`：

| reasoning_effort | output_config.effort |
| --- | --- |
| minimal | low |
| low | low |
| medium | medium |
| high | high |
| xhigh | xhigh |
| max | max |
| none / disabled | 关闭 thinking，不生成 effort |

档位字符串会去除两端空白并转为小写；空字符串按未配置处理。除 `minimal` 归一为 `low` 外，不静默降低档位。具体模型支持哪些 effort 由供应商判断；例如 Sonnet 5.5 使用 adaptive thinking，已不接受手动预算。未配置通用档位时，不自动开启思考。

原生自定义参数优先：显式 `thinking` 的 enabled/disabled 模式不受通用档位影响；显式 adaptive 模式可从通用档位补齐 effort；已有 `output_config.effort` 不覆盖。`output_config` 的其他字段（例如 format）保留，并可同时补齐 effort。

**旧模型兼容：** 通用档位不再自动生成固定思考预算。只接受旧式预算的模型，需在自定义参数中显式配置，例如 `thinking={"type":"enabled","budget_tokens":8192}`。未指定输出上限且额度不足时，仍自动设为预算加 4096；显式输出上限必须大于预算。原生自定义参数不按模型名称推断或改写。

开启思考时不转发采样参数，以避免协议冲突。强制指定工具、或工具续聊缺少有效思考块时，本次请求不启用思考，以保留工具调用的可用性。

协议参考：Claude 官方文档的 [Effort](https://platform.claude.com/docs/en/build-with-claude/effort) 与 [Extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)。

## 范围与验证

本功能用于经过 WebUI 后端的网页聊天连接，不覆盖浏览器直连模式，也不支持 Azure OpenAI 连接。原生服务器工具、音频、PDF 内容块等未纳入本次适配；不支持的内容类型返回错误，不静默丢弃。OpenAI 专有参数不会作为未知字段发送给 Anthropic。

本次仅做源码静态检查，未调用真实 Anthropic/第三方服务，未运行测试、构建、CI 或镜像构建。上线后仍需验证实际模型的思考参数、工具续聊与流式行为。
