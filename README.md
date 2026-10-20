# LItsshP

**简体中文** · [English](README_en.md)

一个扁平风格、Termius 式的 [trzsz-ssh (tssh)](https://github.com/trzsz/trzsz-ssh)
图形界面。它**不是** SSH 客户端的重新实现：每个会话都是一个真实的
`tssh <alias>` 进程，运行在伪终端里，因此 ProxyJump、`encPassword`、trzsz
文件传输、`#!!` 选项以及 tssh 的其他一切行为都和命令行里完全一致。

会话不存在单独的数据库里。图形界面和命令行读写的是同一个 `~/.ssh/config`，
所以在这里添加的主机立刻就能用 `tssh <alias>` 连接，反过来也一样。

```
┌────────────────┬──────────────────────────────────────────────┐
│  LItsshP       │  ● localtest  ✕  │  ● prod-web  ✕            │
│  tssh · ~/.ssh │──────────────────────────────────────────────│
│  2 hosts       │  LIPiston@host  ~                             │
│  [search]      │  $ ls --color=always /                        │
│  All  lab  web │  bin  boot  dev  etc  home  ...               │
│  ▸ localtest   │──────────────────────────────────────────────│
│  ▸ prod-web    │  tssh localtest        ~/.ssh/config          │
│  New host  ⚙   │                                               │
└────────────────┴──────────────────────────────────────────────┘
```

## 运行环境

- Windows 10/11（PTY 层通过 `pywinpty` 使用 ConPTY）
- Python 3.10+
- `PATH` 中有 [tssh](https://github.com/trzsz/trzsz-ssh)（或用 `LITSSHP_TSSH`
  指向可执行文件）
- 一个 OpenSSH 客户端 —— tssh 会调用 `ssh`

## 安装与运行

```bat
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
run.bat
```

或者直接启动：

```bat
.venv\Scripts\python -m app.main
```

## 与 tssh 的对应关系

| 界面概念 | tssh / OpenSSH 中的实现 |
| --- | --- |
| 主机列表 | `~/.ssh/config`（以及被 `Include` 的文件）里的每个具体 `Host` 块 |
| 分组 | `#!! GroupLabels prod web` |
| 隐藏主机 | `#!! HideHost yes` |
| 密码字段 | `#!! encPassword <hex>` 加 `#!! encQuestionAnswer1`，与 tssh 字节级兼容 |
| 明文密码 | 编辑时保持 `#!! Password <text>` 原样，不会自动转换 |
| 启动命令 | `#!! StartupCommand <text>` —— LItsshP 自己的选项，在 shell 就绪后输入 |
| 高级标签页 | `ProxyJump`、`ProxyCommand`、`IdentityFile`、`IdentitiesOnly` |
| 端口转发 | 主机块里的 `LocalForward`、`RemoteForward`、`DynamicForward` |
| 原始块编辑器 | 该块的原文，原样写回 |

密码使用 tssh 自己的方案编码 —— 一个固定的 AES-256-GCM 密钥，只用于混淆，
不提供保护。任何能读到配置文件的人都能解开，和 tssh 本身一样。

编辑主机不会重写无关的块：未被改动的主机保持字节级不变，包括注释、顺序、
CRLF 换行和 UTF-8 BOM。

## 界面

外观参考 [Pebrel](https://github.com/Kuddev/pebrel)：平面化、没有悬浮卡片，
只用一个强调色，且仅用于选中态和主要操作；用发丝线而不是边框分隔；没有阴影
和层级；圆角梯级紧凑（4 芯片 / 6 控件 / 7 图标块 / 8 浮层 / 14 启动器）。
内置两个主题系列，各含深色和浅色两个成员：**Catppuccin**（Mocha / Latte）和
**Mono**（灰阶，用亮度而不是色相区分状态）。

主题就是普通的 YAML 文件，首次启动时写入应用数据目录
（`%APPDATA%\LItsshP\themes`），此后可以直接编辑 —— 调整某个颜色、增加一个
变体，或定义一整个新系列，然后在 Settings → Appearance（设置 → 外观）里点
**Reload** 即可。
`~/.ssh` 下的任何内容都不会被碰：那个目录属于 ssh 工具自己。解析失败的文件
会被跳过，原因显示在按钮旁边，所以一个笔误只会退回内置配色，而不会让窗口失去
主题。终端配色同样由这份 YAML 派生，所以会话区域不会看起来像贴进窗口的一块
黑色方块。控件来自
[material-components-qml](https://github.com/sudoevolve/material-components-qml.git)，
放在 `third_party/md3` 下，其 C++ 样式单例用 Python 重新实现
（`app/style.py`），因此不需要 C++ 工具链。

### 快捷键

| 快捷键 | 操作 |
| --- | --- |
| `Ctrl+T` | 聚焦主机搜索框 |
| `Ctrl+N` | 新建主机 |
| `Ctrl+W` | 关闭当前标签页（会话仍在运行时先确认） |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | 下一个 / 上一个标签页 |
| `Ctrl+,` | 设置 |
| `Ctrl+B` | 显示 / 隐藏侧边栏 |
| `Ctrl+Shift+P` | 命令面板 |
| `Ctrl+Shift+T` | 端口转发面板 |
| `Ctrl+F` | 在当前终端的回滚内容中搜索 |
| `Ctrl+Shift+D` | 分屏（弹出选择器挑选第二个窗格） |
| `Ctrl+Shift+O` | 恢复上次会话的标签页 |
| `Ctrl+R` | 重连当前会话 |
| `Ctrl+Shift+R` | 从磁盘重新读取主机 |
| `Ctrl+Shift+C` / `Ctrl+Shift+V` | 复制选中内容 / 粘贴 |
| `Ctrl+Shift+A` | 全选可见屏幕 |
| `Ctrl+Shift+E` | 聚焦命令输入条 |
| `Shift+PgUp` / `Shift+PgDn` | 向上 / 向下滚动（单独的 PgUp/PgDn 交给终端里的程序） |
| `Ctrl+Home` / `Ctrl+End` | 回滚内容顶部 / 回到实时画面 |

单独的 `Ctrl+C` 在可能表示 SIGINT 时永远不会被拦截，只有 `Ctrl+Shift+C`
才复制。右键点击终端会弹出 Copy / Paste / Select all / Clear selection，
而当 vim、tmux 之类的程序正在接管鼠标时，点击仍会照常传给它们（`Shift` +
右键始终弹出应用菜单）。

侧边栏顶部同时充当标题栏：拖动它移动窗口，双击最大化。

### 命令输入条

终端下方有一条输入区，可以在会话忙碌时先把一条命令（或一小段命令）写好。它
不会拦截正常输入 —— 除非输入框获得焦点，按键仍然进入终端。回车插入换行，
`Ctrl+Enter` 发送，`Ctrl+Up` / `Ctrl+Down` 调出之前的条目。可以用标签栏上的
键盘图标、`Ctrl+Shift+E`，或设置里的开关来切换。

发送时按手敲的方式逐字符输入给 shell，因此续行和多行块的表现和正常输入一致，
不会停留在粘贴缓冲区里。

### 搜索、日志与重连

`Ctrl+F` 会在当前终端上方打开搜索栏。它同时搜索回滚内容和可见屏幕，高亮所有
命中（当前命中更明显），`Enter` / `Shift+Enter` 在命中之间跳转。按下 `Aa`
按钮之前搜索不区分大小写。`Escape` 关闭搜索栏，并把滚动位置留在最后找到的
命中处。

让长时间会话活下来的两个开关在设置里（界面文案是英文）：

- **Write session output to a log file**（会话日志）把每个会话的可打印输出
  追加到 `%APPDATA%\LItsshP\logs` 下的文件。转义序列会被剥离，被回车重新绘制
  的行只保留最后一版，所以文件读起来像屏幕内容而不是原始 PTY 流量。开关旁边
  的 **Open folder** 会打开该文件夹。
- **Reconnect automatically when a connection drops**（自动重连）会重启被断开
  的会话，退避间隔有上限（1、2、4、8、16 秒，之后每 30 秒一次，尝试五次后
  放弃）。只有掉线才会重试：tssh 的保活超时（退出码 205）和传输失败（255）。
  你自己 `exit` 退出的 shell、你关掉的标签页，以及你主动重连的会话都不会被
  处理。

保活间隔（关 / 15 / 30 / 60 秒）在主机自身配置没有设置时作为
`ServerAliveInterval` 传入，所以 `~/.ssh/config` 里显式写的值总是优先。

### 字体、中文与回退字体

设置里可以选择终端字体和一个**缺失字形回退字体**。大多数编程字体不带 CJK，
没有回退时 `中文`、`日本語` 和全角标点会由系统随便挑一个字体绘制 —— 往往是
一个和终端文字完全不搭的衬线体。指定回退字体后，这些字符来自指定字体，其余
字符仍用主字体。

替换是逐字符进行的：只有主字体没有该字形时才用回退字体绘制。Qt 的
`setFamilies` 列表看起来能做到这件事，但它只决定字体*族*的解析顺序 —— 无论
第二项写什么，用的都是同一个 CJK 字体 —— 所以终端用
`QRawFont.supportsCharacter` 检查覆盖情况，并自己绘制这些例外。单元格尺寸
始终来自主字体，所以切换回退字体永远不会让网格重排。菜单里只列出真正包含 CJK
字形的字体；如果保存的默认字体没有安装，就改用第一个已安装的。

全角字符占两列，字形在两列宽度的格子里居中。这不只是观感问题：只有当每个宽
字形都正好前进两格时，`htop`、`vim` 这类工具画出的线框和表格才会对齐。

### 分屏

`Ctrl+Shift+D`（或状态栏里的 **Split**）会弹出选择器，列出已打开的标签页和
空闲主机；选中一个就会把它显示在当前会话旁边。两个窗格都是普通标签页，因此
关闭分屏就回到单窗格，两边的 shell 都不会丢。

分屏工具栏会显示两个主机名，带一个 **Broadcast** 开关和一个关闭按钮。开启
Broadcast 后，命令输入条会同时向两个窗格输入，这是在一台以上服务器上跑同一条
命令的常用方式。输出、搜索、日志和重连仍然各窗格独立；分屏本身不会被复制到
另一个窗口。

### 片段与启动命令

片段是存在 `state.json` 里的具名命令（或一小段命令）。命令面板会列出它们，
选中即输入到当前会话中。面板里的 **Manage snippets** 打开编辑器，编辑器也能
立即执行某个片段。

主机还可以在主机编辑器里带一条启动命令，保存为 `#!! StartupCommand`。它在
shell 报告就绪之后才被输入，而不是作为远程命令传入，所以 `cd /srv/app`、
`tmux attach` 或 `source` 的表现和手敲完全一样。这个选项是 LItsshP 自己的：
`tssh` 会忽略它，所以命令行也需要执行的动作请放回 shell 自己的配置文件里。

### SSH 密钥与 known hosts

侧边栏底部的 **Keys**（或设置里的 **Manage keys**）列出 `~/.ssh` 中的所有密钥
对，包括被主机的 `IdentityFile` 引用但存在别处的密钥。每行显示类型、位数、
注释，以及从公钥 blob 本地算出的 `SHA256:` 指纹 —— 与 `ssh-keygen -lf`
打印的值相同。

在这里可以：

- 创建 ed25519 密钥（或供老服务器使用的 RSA），可设置口令和注释；已存在的
  文件永远不会被覆盖；
- 复制公钥，或**把它安装到某台主机上** —— 这会打开（或复用）该主机的会话，
  并把该行追加到 `~/.ssh/authorized_keys` 且设置正确权限。之所以通过会话而
  不是 SFTP 完成，是因为首次登录仍需要密码，而且该目录可能还不存在；
- 删除密钥对（两半都删，删除前确认）；
- 查看并**忘记** `known_hosts` 中的条目，包括哈希过的 `|1|` 行（哈希行没有
  可读名字，因此按位置删除）；
- **Trust a host**（信任主机）会用 `ssh-keyscan` 扫描主机并显示其指纹，由你
  核对后再添加。扫描本身不会信任任何东西。

创建密钥会调用 `ssh-keygen`。列出和计算指纹不会：指纹由公钥 blob 本地算出，
所以带口令的密钥和没装 `ssh-keygen` 的机器都能正常列出。

### 恢复上次会话

LItsshP 会把打开的标签页、当前标签和分屏记录在 `state.json` 里，但启动时
从不自行拨号。**Reopen last session**（在空状态页、命令面板里，或
`Ctrl+Shift+O`）会恢复它们；已经从配置中删除的主机会被跳过。恢复之所以是
显式操作，是因为一个启动就连生产环境的终端在按流量计费的网络上会是个惊吓，
而且无人值守的启动不应该产生登录尝试。

### 端口转发

规则就是主机块里普通的 `LocalForward`、`RemoteForward` 和 `DynamicForward`
行，在主机编辑器中修改。命令行上的 `ssh` 和 `tssh` 也能看到它们，所以在这里
配好的隧道在图形界面之外照样能用。

转发是连接的属性，而不是后台服务。当主机有打开的会话时，由该会话提供这些
规则 —— 不会启动第二个进程，否则它会和会话抢同一个本地端口。会话结束时，转发
也随之结束。

`Ctrl+Shift+T`（或 `swap_horiz` 图标）打开转发面板。每台主机列出它当前提供的
规则、这些规则来自主机块还是来自 `Host *` 规则，以及各自的状态。
**Keep running** 是让转发活过会话的选项：标签页关闭后，应用会启动自己的
`tssh -N <alias>` 并接管端口。这些进程在应用退出时仍会被停止，所以窗口关掉
之后不会有东西继续监听。

如果你重新打开一台主机，而保活的隧道已经占着它的转发，新会话会以
`ClearAllForwardings=yes` 启动，以免争抢同一个本地端口。

来自通配块或 `Include` 块的规则以只读方式显示：在某一台主机的编辑器里删除
它们，会悄悄改变所有匹配该块的主机。主机设置了 `ClearAllForwardings yes`
时，转发同样不会启动。

### 传输进度

标签栏会显示一条实时进度条，包含当前传输的路线（`本机 → 主机` 或
`主机 → 本机`）、百分比，以及同时有多个传输时的 `+N`。`swap_vert` 图标打开
正在进行的传输列表和最近历史，每项使用同样的路线标注；有传输在运行时该图标会
变成强调色，数量本身则放在悬浮提示里。

进度是从 sftp 自己的进度计抓取的：传输运行在伪终端下，因为 sftp 只有在拥有
终端时才会绘制那个进度计。元数据调用仍然使用干净的批处理模式。

在终端里，`Shift` 会覆盖鼠标上报，所以即使 vim、htop、tmux 这类全屏程序正在
抓取鼠标，你仍然可以选择文本。

### 主机操作

右键点击侧边栏里的任意主机：

| 菜单项 | 操作 |
| --- | --- |
| Edit | 打开主机面板（常规 / 高级 / 原始块） |
| Transfer files | 为该主机打开一个独立的 SFTP 窗口 |
| Delete | 请求确认，然后从 `~/.ssh/config` 中移除该块 |

（界面目前只有英文文案，所以这里照抄菜单里实际显示的名字，方便对照。）

删除是两步的：对话框会点名主机并说明会移除什么，只有确认后才会写入。其他主机
及其保存的密码保持字节级不变。

### 传输文件

传输窗口是一个独立的顶层窗口，左边是本地窗格，右边是远程窗格。单击一行勾选它，
双击文件夹进入，然后用 **Upload ↑** / **Download ↓**。目录会递归传输。

两个窗格都会打开在一个可用的目录，而不是假定某个目录一定可用：

- 本地窗格从你的用户目录开始；当用户目录不可写时，改用 `%TEMP%\LItsshP`；
- 远程窗格从账号的 `~` 开始，如果无法列出就依次尝试 `~` → `/` → `/tmp`，
  打开第一个可读的，并告诉你最终停在哪个目录。

尚不存在但可以创建的文件夹也算可用，所以像 `D:\incoming` 这样的下载目标在
文件夹存在之前就能用。如果目标确实不可写，下载会退回到 `%TEMP%\LItsshP`
而不是失败，权限问题会显示在状态行里，而不是留下一个空白窗格。

底部的工具栏还负责管理远程文件夹：**New folder**、**Rename** 和
**Delete** 走与列表相同的批处理 `sftp` 通道，所以不需要额外连接。删除总是
先确认。

传输通过 OpenSSH 的 `sftp` 客户端进行，使用与会话相同的 `~/.ssh/config`
条目，因此 ProxyJump、`IdentityFile` 和 agent 设置都生效。这里刻意避开 trzsz，
因为那需要先在服务器上安装 `trz` 和 `tsz`；纯 SFTP 对任何 OpenSSH 服务器
都有效。

## 架构

```
app/
  main.py            入口：QML 单例、图像提供者、窗口几何
  controller.py      QML 侧控制器：主机、标签页、设置、会话
  config.py          字节保真的 ~/.ssh/config 解析与写入（含 Include）
  secret.py          与 tssh 兼容的 encPassword 编解码
  pty_session.py     ConPTY 中的 tssh 进程；读取线程 + GUI 侧定时器
  screen.py          pyte 屏幕子类：回滚、备用屏幕、鼠标模式
  terminal_model.py  网格 → QImage 渲染器、键盘/鼠标输入、选中
  terminal_theme.py  由当前 Pebrel 主题派生的终端配色
  sftp_client.py     批处理 sftp 取元数据，PTY 驱动的带进度传输
  tunnel.py          转发描述 + 受监管的 `tssh -N` 进程
  keys.py            密钥列举/指纹、ssh-keygen 封装、known_hosts
  theme.py           Pebrel 调色板、皮肤 token、颜色运算、圆角梯级
  style.py           QML 库读取的 StyleManager / ColorHelper 单例
  qml/               Main、HostSidebar、Workspace、TerminalPane、TransferWindow…
third_party/md3/     内置的 material-components-qml QML 模块
```

终端在 Python 里光栅化，再通过图像提供者
（`image://terminal/<id>?<revision>`）交给 QML。PTY 输出在工作线程读取并只
入队；GUI 线程上的定时器排空队列、喂给 pyte 并重绘，因此任何 Qt 对象都不会被
跨线程访问。

## 配置

LItsshP 自身只在 `%APPDATA%\LItsshP\state.json` 里保存界面偏好（窗口几何、
主题、字体、片段、上次会话的标签页），主题则放在
`%APPDATA%\LItsshP\themes`。主机和凭据永远不会离开 `~/.ssh/config`。

环境变量覆盖，便于针对临时配置进行测试：

- `LITSSHP_CONFIG` —— 配置文件路径（默认 `~/.ssh/config`）
- `LITSSHP_TSSH` —— tssh 可执行文件路径
- `LITSSHP_SFTP` —— 传输窗口使用的 `sftp` 可执行文件路径
- `LITSSHP_STATE` —— 界面状态文件路径
- `LITSSHP_LOGS` —— 会话日志文件夹（默认 `%APPDATA%\LItsshP\logs`）

## 文档

[`docs/`](docs/README.md) 放的是*开发*这个项目所需的材料，而不是使用它的材料：

- [`docs/skills/`](docs/skills/index.md) —— 安装、缺陷诊断、终端渲染器、
  文件传输和配置写入的实操手册；
- [`docs/skills/reference/`](docs/skills/reference/index.md) —— 架构、每次
  改动都必须保持的不变量、验证门禁，以及完整的 QML 侧 API。

这些门禁可以直接运行，覆盖最常见的破坏：

```bash
.venv/Scripts/python docs/skills/reference/qml_load_gate.py
.venv/Scripts/python docs/skills/reference/config_roundtrip_gate.py
.venv/Scripts/python docs/skills/reference/forward_roundtrip_gate.py
.venv/Scripts/python docs/skills/reference/session_features_gate.py
```
