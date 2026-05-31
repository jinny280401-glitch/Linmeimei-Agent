---
name: ai-model-cloudbase
description: CloudBase 调用 AI 模型完整指南 - 涵盖 JS/Node SDK 与微信小程序。文本生成、流式响应及图像生成全解析。
alwaysApply: false
---
## 何时使用此技能

运用此技能 **通过云开发调用 AI 模型** 跨所有平台。

**支持的平台：**

| 平台 | 软件开发工具包/应用程序编程接口 | 章节 |
| ---------------- | --------------------------- | ----------------- |
| 网页（浏览器） | @cloudbase/js-sdk | 第一部分 |
| Node.js（服务器/云函数） | @cloudbase/node-sdk ≥3.16.0 | 第一部分（相同 API，不同初始化） |
| 任何平台（HTTP） | HTTP API / OpenAI SDK | 第二部分 |
| 微信小程序 | wx.cloud.extend.AI | 第三部分 ⚠️ 不同 API |

***

## 如何使用此技能（针对编程代理）

1. **确定目标平台** 请问您正在为哪个平台进行开发？
2. **确认云开发环境** - 收到 env（环境 ID）与凭据
3. **选择相应部分** - **第一部分** 对于 JS/Node SDK，**第三部分** 针对微信小程序
4. **严格遵循 CloudBase API 的接口规范** - 请勿自行创建新的 API 接口

***

# 第一部分：CloudBase JS SDK 与 Node SDK

**JS SDK 与 Node SDK 共享同一套 AI API。** 仅初始化方式不同。

## 安装

```bash
# For Web (Browser)
npm install @cloudbase/js-sdk

# For Node.js (Server/Cloud Functions)
npm install @cloudbase/node-sdk
```

⚠️ **Node SDK AI 功能需要 3.16.0 或更高版本。** 检查您的版本是否与 npm list @cloudbase/node-sdk.

## 初始化 - Web（JS SDK）

```js
import cloudbase from "@cloudbase/js-sdk";

const app = cloudbase.init({
  env: "<YOUR_ENV_ID>",
  accessKey: "<YOUR_PUBLISHABLE_KEY>" // Get from CloudBase console
});

const auth = app.auth();
await auth.signInAnonymously();

const ai = app.ai();
```

## 初始化 - Node.js (Node SDK)

```js
const tcb = require('@cloudbase/node-sdk');
const app = tcb.init({ env: '<YOUR_ENV_ID>' });

exports.main = async (event, context) => {
  const ai = app.ai();
  // Use AI features - same API as JS SDK
};
```

## generateText() - 非流式处理

```js
const model = ai.createModel("hunyuan-exp");

const result = await model.generateText({
  model: "hunyuan-lite",
  messages: [{ role: "user", content: "你好，请你介绍一下李白" }],
});

console.log(result.text); // Generated text string
console.log(result.usage); // { prompt_tokens, completion_tokens, total_tokens }
console.log(result.messages); // Full message history
console.log(result.rawResponses); // Raw model responses
```

## streamText() - 流式传输

```js
const model = ai.createModel("hunyuan-exp");

const res = await model.streamText({
  model: "hunyuan-turbos-latest",
  messages: [{ role: "user", content: "你好，请你介绍一下李白" }],
});

// Option 1: Iterate text stream (recommended)
for await (let text of res.textStream) {
  console.log(text); // Incremental text chunks
}

// Option 2: Iterate data stream for full response data
for await (let data of res.dataStream) {
  console.log(data); // Full response chunk with metadata
}

// Option 3: Get final results
const messages = await res.messages; // Full message history
const usage = await res.usage; // Token usage
```

## generateImage() - 图像生成

⚠️ **图像生成功能目前仅支持在 Node SDK 中使用。** 不在 JS SDK（Web 端）或微信小程序中。

```js
// Node SDK only
const imageModel = ai.createImageModel("hunyuan-image");

const res = await imageModel.generateImage({
  model: "hunyuan-image",
  prompt: "一只可爱的猫咪在草地上玩耍",
  size: "1024x1024",
  version: "v1.9",
});

console.log(res.data[0].url); // Image URL (valid 24 hours)
console.log(res.data[0].revised_prompt); // Revised prompt if revise=true
```

***

# 第二部分：CloudBase HTTP API

## API 端点

```
https://<ENV_ID>.api.tcloudbasegateway.com/v1/ai/<PROVIDER>/v1/chat/completions
```

## cURL - 非流式传输

```bash
curl -X POST 'https://<ENV_ID>.api.tcloudbasegateway.com/v1/ai/deepseek/v1/chat/completions' \
  -H 'Authorization: Bearer <YOUR_API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{"model": "deepseek-r1", "messages": [{"role": "user", "content": "你好"}], "stream": false}'
```

## cURL - 流式传输

```bash
curl -X POST 'https://<ENV_ID>.api.tcloudbasegateway.com/v1/ai/deepseek/v1/chat/completions' \
  -H 'Authorization: Bearer <YOUR_API_KEY>' \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{"model": "deepseek-r1", "messages": [{"role": "user", "content": "你好"}], "stream": true}'
```

## OpenAI SDK 兼容

```js
const OpenAI = require("openai");

const client = new OpenAI({
  apiKey: "<YOUR_API_KEY>",
  baseURL: "https://<ENV_ID>.api.tcloudbasegateway.com/v1/ai/deepseek/v1",
});

const completion = await client.chat.completions.create({
  model: "deepseek-r1",
  messages: [{ role: "user", content: "你好" }],
  stream: true,
});

for await (const chunk of completion) {
  console.log(chunk);
}
```

***

# 第三部分：微信小程序

⚠️ **微信小程序 API 与 JS/Node SDK 不同。** 注意参数结构。

**需要基础库版本 3.7.1 及以上。无需额外 SDK。**

## 初始化

```js
// app.js
App({
  onLaunch: function() {
    wx.cloud.init({ env: "<YOUR_ENV_ID>" });
  }
})
```

## generateText() - 非流式处理

⚠️ **与 JS/Node SDK 的区别：** 返回值为原始模型响应。

```js
const model = wx.cloud.extend.AI.createModel("hunyuan-exp");

const res = await model.generateText({
  model: "hunyuan-lite",
  messages: [{ role: "user", content: "你好" }],
});

// ⚠️ Return value is RAW model response, NOT wrapped like JS/Node SDK
console.log(res.choices[0].message.content); // Access via choices array
console.log(res.usage); // Token usage
```

## streamText() - 流式传输

⚠️ **与 JS/Node SDK 的区别：** 必须将参数包裹在 data 对象，支持回调。

```js
const model = wx.cloud.extend.AI.createModel("hunyuan-exp");

// ⚠️ Parameters MUST be wrapped in `data` object
const res = await model.streamText({
  data: { // ⚠️ Required wrapper
    model: "hunyuan-lite",
    messages: [{ role: "user", content: "hi" }]
  },
  onText: (text) => { // Optional: incremental text callback
    console.log("New text:", text);
  },
  onEvent: ({ data }) => { // Optional: raw event callback
    console.log("Event:", data);
  },
  onFinish: (fullText) => { // Optional: completion callback
    console.log("Done:", fullText);
  }
});

// Async iteration also available
for await (let str of res.textStream) {
  console.log(str);
}

// Check for completion with eventStream
for await (let event of res.eventStream) {
  console.log(event);
  if (event.data === "[DONE]") { // ⚠️ Check for [DONE] to stop
    break;
  }
}
```

***

# API 对比：JS/Node SDK 与 微信小程序

| 功能 | JS/Node SDK | 微信小程序 |
| ----------------- | -------------------------- | --------------------------- |
| **命名空间** | app.ai() | wx.cloud.extend.AI |
| **生成文本参数** | 直接宾语 | 直接宾语 |
| **生成文本返回** | { text, usage, messages } | 原始：{ choices, usage } |
| **streamText 参数** | 直接宾语 | ⚠️ 已封装 data: {...} |
| **流式文本返回** | { textStream, dataStream } | { textStream, eventStream } |
| **回调函数** | 不支持 | onText, onEvent, onFinish |
| **图像生成** | 仅限 Node SDK | 暂无可用信息 |

***

# 类型定义

## JS/Node SDK - 基础聊天模型输入

```ts
interface BaseChatModelInput {
  model: string; // Required: model name
  messages: Array<ChatModelMessage>; // Required: message array
  temperature?: number; // Optional: sampling temperature
  topP?: number; // Optional: nucleus sampling
}

type ChatModelMessage =
  | { role: "user"; content: string }
  | { role: "system"; content: string }
  | { role: "assistant"; content: string };
```

## JS/Node SDK - generateText() 返回值

```ts
interface GenerateTextResult {
  text: string; // Generated text
  messages: Array<ChatModelMessage>; // Full message history
  usage: Usage; // Token usage
  rawResponses: Array<unknown>; // Raw model responses
  error?: unknown; // Error if any
}

interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}
```

## JS/Node SDK - streamText() 返回值

```ts
interface StreamTextResult {
  textStream: AsyncIterable<string>; // Incremental text stream
  dataStream: AsyncIterable<DataChunk>; // Full data stream
  messages: Promise<ChatModelMessage[]>; // Final message history
  usage: Promise<Usage>; // Final token usage
  error?: unknown; // Error if any
}

interface DataChunk {
  choices: Array<{
    finish_reason: string;
    delta: ChatModelMessage;
  }>;
  usage: Usage;
  rawResponse: unknown;
}
```

## 微信小程序 - streamText() 输入

```ts
interface WxStreamTextInput {
  data: { // ⚠️ Required wrapper object
    model: string;
    messages: Array<{
      role: "user" | "system" | "assistant";
      content: string;
    }>;
  };
  onText?: (text: string) => void; // Incremental text callback
  onEvent?: (prop: { data: string }) => void; // Raw event callback
  onFinish?: (text: string) => void; // Completion callback
}
```

## 微信小程序 - streamText() 返回值

```ts
interface WxStreamTextResult {
  textStream: AsyncIterable<string>; // Incremental text stream
  eventStream: AsyncIterable<{ // Raw event stream
    event?: unknown;
    id?: unknown;
    data: string; // "[DONE]" when complete
  }>;
}
```

## 微信小程序 - generateText() 返回值

```ts
// Raw model response (OpenAI-compatible format)
interface WxGenerateTextResponse {
  id: string;
  object: "chat.completion";
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message: {
      role: "assistant";
      content: string;
    };
    finish_reason: string;
  }>;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}
```

## HunyuanGenerateImageInput（仅限 JS/Node SDK）

```ts
interface HunyuanGenerateImageInput {
  model: "hunyuan-image" | string; // Required
  prompt: string; // Required: image description
  version?: "v1.8.1" | "v1.9"; // Default: "v1.8.1"
  size?: string; // Default: "1024x1024"
  negative_prompt?: string; // v1.9 only
  style?: string; // v1.9 only
  revise?: boolean; // Default: true
  n?: number; // Default: 1
  footnote?: string; // Watermark, max 16 chars
  seed?: number; // Range: [1, 4294967295]
}

interface HunyuanGenerateImageOutput {
  id: string;
  created: number;
  data: Array<{
    url: string; // Image URL (24h valid)
    revised_prompt?: string;
  }>;
}
```

***

# 最佳实践

1. **对长响应使用流式传输** - 提升用户体验
2. **优雅地处理错误** - 将 AI 调用封装在 try/catch 块中
3. **确保 API 密钥安全** 切勿在客户端代码中暴露
4. **尽早初始化** 在应用入口点初始化 SDK/云服务
5. **检查 [DONE]** - 在微信小程序直播中，检查 event.data === "[DONE]" 停止
