# Zotero-MCP

通过 [zotero-mcp-server](https://github.com/54yyyu/zotero-mcp)（PyPI: `zotero-mcp-server`）让 Claude Code 搜索、阅读、整理 Zotero 文献库。

## 1. 获取 Zotero API Key 和 userID

1. 打开 <https://www.zotero.org/settings/keys>
2. 页面顶部 "Your user ID for use in API calls is XXXXXXX" 即 **userID**
3. **Create new private key** → 勾选 *Allow library access*、*Allow notes access*、*Allow write access* → Save Key（key 只显示一次）
4. PDF 全文：Zotero 设置 → 同步 → 开启文件同步，附件需上传到 Zotero 服务器

## 2. 安装

```bash
uv tool install zotero-mcp-server
```

## 3. 注册到 Claude Code（Web API 模式）

```bash
claude mcp add zotero -s user \
  -e ZOTERO_LOCAL=false \
  -e ZOTERO_API_KEY=<你的 API Key> \
  -e ZOTERO_LIBRARY_ID=<你的 userID> \
  -e ZOTERO_LIBRARY_TYPE=user \
  -- zotero-mcp serve
```

> Claude Code 云端会话：API Key 存为环境的 network secret（host `api.zotero.org`），由代理注入，
> 此时 `ZOTERO_API_KEY` 填占位符 `proxy-injected` 即可，不要把真实 key 写进配置或仓库。

本地电脑也可用本地模式（Zotero 7 需开启 设置 → 高级 → "允许此计算机上的其他应用程序与 Zotero 通信"）：

```bash
claude mcp add zotero -s user -e ZOTERO_LOCAL=true -- zotero-mcp serve
```

验证：

```bash
claude mcp list
```

## 4. 用法示例

在 Claude Code 里直接说：

- "列出我 Zotero 的所有分类"
- "在 LLC 分类里找关于同步整流的论文，总结它们的控制方法"
- "读一下 <论文标题> 的全文 / PDF 第 3–5 页，提炼主要贡献"
- "给最近添加的 10 篇文献按主题打标签并移到对应分类"
- "导出 Thesis 分类的 BibTeX"

共 35 个工具，包括搜索、元数据、全文/PDF 页读取、批注与笔记、分类管理、标签批量更新、添加条目、导出参考文献等。
