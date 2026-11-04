# Responses 思考摘要与续聊

服务端连接的 API Type 选择 `Responses` 后，网页聊天支持摘要的请求、流式展示、非流式保存及同模型续聊。

## 请求参数

- 网页的 `reasoning_effort` 转换为原生 `reasoning.effort`，不再作为未知顶层字段发送。
- 对现有识别规则中的 GPT-5 及以上和 o 系列推理模型，默认补 `reasoning.summary: "auto"`；旧 `o1-mini` / `o1-preview` 与名称中的 `-chat` 变体不自动补，可通过显式参数启用。
- 未知模型若显式设置了 effort 或原生 `reasoning` 对象，也会启用该映射。普通非推理模型不会被无条件加入 reasoning 参数。
- 原生 `reasoning` 中已有的值优先。effort 为 `none` 时不自动补摘要；显式的 `summary: null` 会保留。
- 启用推理参数时，将 `reasoning.encrypted_content` 合并进 `include`，保留原有 include 项，用于无状态续聊。

在模型自定义参数中可以指定摘要，例如：

```json
{
  "reasoning": {
    "effort": "medium",
    "summary": "auto"
  }
}
```

如果只想关闭可见摘要，可使用 `{"reasoning":{"summary":null}}`。具体模型或第三方网关接受哪些 effort 和 summary 值，以供应商支持为准。

## 保存与回传

非流式结果同时保留 Chat Completions 兼容的 `choices` 和原生 `output`；摘要文本放入 `reasoning_content`，原生摘要数组与加密内容供网页保存。

同模型的无状态历史、审批恢复和工具循环通过现有 `reasoning_details` 通路携带可回放的原生 reasoning。只有加密推理或真正原生推理内容才进入请求；只有展示摘要的旧记录继续显示，不冒充推理状态回传。此过程不修改数据库格式，也不补造旧记录缺失的加密内容。

切换模型时剥离 reasoning 的绑定详情、加密内容和原生标识；普通 Chat Completions 出口会移除 Responses 专有详情。启用 `previous_response_id` 的工具续聊只追加工具结果，避免重复发送服务端已保存的助手输出和 reasoning。

两类摘要 done 事件都能独立回填最终文本；重复 done 不重复拼接。上游最终对象遗漏摘要或加密内容时保留已累计的数据，非空最终值优先。前端保留已完成的先前工具轮次，最终 output 只替换当前轮次。
