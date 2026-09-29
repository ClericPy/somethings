# dsh-forward

把 `dsh web` 的 Web GUI 从 loopback 透传到局域网，**端口与路径都不变**，可选自己起 GUI 并出二维码。

## 为什么需要它

DSH 的 web 服务器 schema 只接受两个 host 字面量：

```ts
host: z.union([z.const("127.0.0.1"), z.const("0.0.0.0")]).required()
```

而 `dsh web` 的 CLI 只硬拦 `0.0.0.0` 一个字面量：

```js
if (options.host === "0.0.0.0") program.error("error: --host 0.0.0.0 is intentionally not supported yet for safety: ...");
```

所以 `--host 192.168.10.5` 能过 CLI 那道检查，却会死在 schema 校验上——**没有原生方式绑局域网地址**，只能外挂转发器。

## 还有一半在 dsh 那边：`--trusted-host`

DSH 在认证之前先做 Host/Origin 校验（`src/api-request-trust.ts`）：

```js
if (!isLoopbackHostname(hostUrl.hostname) && !isTrustedAuthority(hostUrl, trustedHosts)) return false; // → 403
```

而 LAN 字面量只在绑定 `0.0.0.0` 时才自动派生：

```js
const lanAddresses = bindHost === ALL_INTERFACES_HOST ? <所有非 internal IPv4> : [];
```

既然绑的是 loopback，`trustedHosts` 就只能靠 `--trusted-host` 显式给。**漏了这一步，页面能打开但 `/api` 与 WebSocket 全部 403。**

这不是推理，是实测（把请求发给正在运行的 GUI 的 loopback 端口，只换 Host 头）：

| 请求 | 结果 | 含义 |
|---|---|---|
| `Host: 127.0.0.1:<port>` → `/api` | 401 | Host 可信，只是没认证 |
| `Host: 192.168.10.5:<port>` → `/api` | **403** | Host 不可信，栅栏拦下 |
| `Host: 127.0.0.1:<port>` + `Origin: …192.168.10.5…` → `/api` | **403** | Origin 必须等于 Host |
| `Host: 192.168.10.5:<port>` → `GET /` | 401 | 根路径只有认证栅栏，带 `?token=` 能过 |

两端都要对上，缺一不可：

```powershell
dsh web --trusted-host <局域网IP> --no-open      # 一端；或用本工具的 --launch 代劳
uv run --no-project forward.py --launch          # 另一端（在 Python/dsh-forward 目录里跑）
```

## 运行环境

依赖写在 `forward.py` 顶部的 [PEP 723](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
元数据块里，`uv run` 会自动备好，**不需要手动建 venv**：

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["segno"]
# ///
```

```powershell
cd Python/dsh-forward
uv run --no-project forward.py --help
```

`--no-project` 是必要的：本目录位于一个带 `pyproject.toml` 的仓库里，不加它 uv 会试图用那个项目环境，
而不是脚本自己的元数据。

`segno` 是**唯一**第三方依赖，而且只在 `--qr` 时才需要它（`forward.py` 是懒加载 `qr` 模块的）：
缺了它转发照常工作，只是出不了二维码，并会明确报错。转发部分只用标准库，所以
`py -3 forward.py --launch`（不带 `--qr`）也能跑。

> 目录里若残留一个 `.venv`，那是早期"工具自带 venv"做法的遗留。它可能在被正在运行的实例占用
> （锁定 `Scripts\python.exe`），停掉之后再删即可；新流程不再需要它。

`--launch` 会自动定位 dsh：先找 PATH，再找 `%LOCALAPPDATA%\pnpm\bin\dsh.cmd`（本机上 dsh 不在 PATH，装在那里）。也可以用 `--dsh <绝对路径>` 指定。

## 一键启动（dsh-forward.bat）

双击 `dsh-forward.bat`，或从命令行带参数跑：

```bat
dsh-forward.bat                    REM 起 web + 转发 + 出二维码
dsh-forward.bat --no-update-dsh    REM 跳过 npm 版本检查
dsh-forward.bat --qr-open          REM 额外弹出 PNG 窗口（默认只用终端那张）
dsh-forward.bat --no-open-browser  REM 不要自动打开本机浏览器
dsh-forward.bat --port 8081        REM 换端口（转发器与它拉起的 GUI 一起跟着走）
```

它做的就是 `uv run --no-project forward.py --launch --qr --update-dsh %*`。**`--launch` 会自己起 web 模式**：以
`dsh web --no-open --port <target 的端口> --trusted-host <局域网IP>` 拉起子进程，抓它打印的
带 token URL，再在局域网地址上同端口转发，最后出二维码。Ctrl+C 退出时子进程**整棵进程树**一起收掉
——dsh 是 `.cmd` 包装器，只 `terminate()` 会留下继续占着 127.0.0.1:3080 的 node 孤儿，下次启动就撞端口。

启动后控制台会给**两条**带 token 的 URL：

- **局域网**那条给手机/其他设备，二维码编的也是它。
- **本机 `127.0.0.1`** 那条不是多余的：设置类页面（模型、提供商目录等）只在 loopback 页面上可用。
  客户端按**浏览器地址栏的 hostname** 判定 `isLoopback`（`pageLocation.hostname`），所以
  `--trusted-host` 解决不了它——那只管 `/api` 的信任栅栏。用 LAN 地址访问时设置页会报
  `加载提供商目录失败: settings are unavailable in this browser`，而对话、会话、工具全部正常。

配置存在 `$DSH_HOME` 下、同一个进程同时服务这两条 URL，所以在 `127.0.0.1` 上改完**立刻对手机那端生效**
（web 默认 `patchReload: live`）。一句话：**LAN 那条适合用，改配置走 127 那条。**

**端口绑定成功之后**（也就是真的起来了），会再用系统默认浏览器打开那条本机 URL——开的是
**带 token** 的那条，因为裸 `http://127.0.0.1:<port>/` 会因缺凭据返回 401。不想要就加
`--no-open-browser`；`--check` 是干跑，不会开。

### 版本检查与更新（`--update-dsh`）

启动前会先在控制台报告版本，并尝试升级到 npm 上最新的 stable 或 RC：

```
[INFO] 当前 dsh 版本: 0.1.7-rc.2
[INFO] npm 上最新 stable/RC: 0.2.0-rc.1
[INFO] 更新 @deepseek-ai/dsh 0.1.7-rc.2 -> 0.2.0-rc.1 ...
[INFO] 更新完成，当前版本: 0.2.0-rc.1
```

挑选规则对齐参照的启动器：只在 stable(`x.y.z`) 与 rc(`x.y.z-rc.N`) 里挑最新，
**alpha/beta 一律忽略**，`rc.10 > rc.9`（数字比较，不是字典序），stable 优先于同号 rc，
**绝不降级**（本地比 npm 新就跳过）。

参照的启动器里三处刻意没照搬，都有理由：

- **不静默安装 pnpm。** 参照的启动器在缺 pnpm 时会 `npm install -g pnpm`；启动器代改全局环境不合适，
  这里只警告并继续用已装版本。
- **查询失败不中断。** 离线或 npm 抽风时参照的启动器会 pause 住不启动；启动器应该照常把 GUI 起起来。
- **当前版本用 `dsh -V` 读**，而不是 `pnpm list -g`：前者是"实际会跑的那个"的真相，也便宜得多。

顺带一个简化：参照的启动器显式传 `--registry`，其实 npm 与 pnpm 都原生读 `NPM_CONFIG_REGISTRY`。

一个本机实际撞到过的 pnpm 坑：`pnpm add -g` 在**全局 bin 目录不在 PATH** 时会直接拒绝安装，报
`ERR_PNPM_GLOBAL_BIN_DIR_NOT_IN_PATH`。本工具在调 pnpm 时把该目录临时补进**子进程**的 PATH——只影响
那一次调用，不动你的环境。
失败时会把 pnpm 的原话一并打印出来，不再只给一个 `[WARN]`。

`dsh-forward.bat` 是 UTF-8 无 BOM + CRLF，且**内容全 ASCII**：中文输出全部来自 Python，这样控制台代码页
不会把它解析乱。bat 只负责 `chcp 65001`、切到本目录、并用 `uv run --no-project` 起脚本（uv 按脚本的
PEP 723 元数据备环境）。

## 用法

```powershell
# 看计划不绑端口（安全的自检）
uv run --no-project forward.py --check

# 自己起 GUI + 出二维码 + 转发（一条命令搞定）
uv run --no-project forward.py --launch --qr

# 只转发已在运行的 GUI（--trusted-host 得由启动方自己带上）
uv run --no-project forward.py --target 127.0.0.1:3080

# GUI 已在跑、只想补一张二维码
uv run --no-project forward.py --check --url "http://127.0.0.1:3080/?token=<43 字符>" --qr
```

主要参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--bind-ip` | 自动取无线网卡 | 留空时按 无线网卡 → 默认路由出口网卡 顺序探测 |
| `--port` | 3080 | 转发器监听端口，手机用这个端口 |
| `--target` | `127.0.0.1:3080` | 上游 host:port |
| `--launch` | 关 | 自己起 `dsh web --no-open --port <target 的端口> --trusted-host <bind-ip>` |
| `--update-dsh` | 关 | 启动前报告版本并升级到 npm 上最新 stable/RC（`--no-update-dsh` 关闭；只在 `--launch` 下有意义） |
| `--url` | 空 | 已在运行的 GUI 的带 token URL，仅用于出二维码 |
| `--qr` | 关 | 终端 ANSI 二维码 + PNG 落盘 |
| `--qr-png` | `dsh-qr.png` | PNG 路径 |
| `--qr-open` | 关 | 额外用系统看图器弹出 PNG（默认只用终端那张） |
| `--open-browser` | **开** | 绑端口成功后用默认浏览器打开本机 URL（带 token）；`--no-open-browser` 关闭，`--check` 不会开 |
| `--max-connections` | 64 | 并发连接上限，超出直接拒掉不排队 |
| `--idle-timeout` | 1800 | 空闲多少秒断开；0 = 不限。设太短会掐断 WebSocket |
| `--check` | 关 | 只打印解析结果，不绑端口 |

自动取 IP 的顺序里，无线网卡按 `MediaType -eq 'Native 802.11'` 过滤，而不是靠 `ipconfig` 里的本地化关键字（"IPv4 地址"/"默认网关"）或界面别名（"WLAN"/"Wi-Fi"），换系统语言不会失效。

## 二维码

`dsh web --no-open` 会打印一行（源码 `app.asar:1017600`）：

```
dsh web: http://127.0.0.1:3080/?token=<43 字符 base64url>[ (LAN: http://192.168.10.5:3080)]
```

同前缀还有一行**不带 URL** 的提示（`dsh web: opening the default browser; ...`），所以本工具的正则要求 `http://`，否则会误匹配那一行。

75 字符的 URL 落在二维码 version 5 / error M，密度很低，手机很好扫。终端打的是 ANSI 半块；**终端字体非等宽或窗口太窄时可能扫不出来，那就用 PNG**（segno 自带 PNG 编码，不需要 Pillow）。

**绝不要用在线二维码生成器** —— 那等于把 token 交给第三方。

## 能不能直接转发桌面端？

桌面端确实起了端口，但**现在不行**。查证结果：

```
127.0.0.1:19387  LISTENING  PID 12324 = "DeepSeek Harness.exe"
  ...dsh-desktop-host/lib/index.js  ...\.dsh\profiles\desktop
无 0.0.0.0:19387 → 只绑 loopback
```

它用的是同一套 `dsh-client-connection` 栅栏（上表的实测就是打给它的），而 `profiles/desktop/` 里没有任何 `trustedHosts`，loopback 绑定又派生不出 LAN 字面量——所以转发它只会得到一个"页面能开、`/api` 全 403"的死 GUI。

要让它成立，得给 `profiles/desktop/cordis.patch.yml` 加 `trustedHosts: ['192.168.10.5']`，并按"按 id 定位、顶层键整份替换"的规则把那一行的 `config` 全部重述一遍。**建议在关掉桌面端之后再做**：patch 写错是整个文件失效（fail loud），而它正承载着跑这个 patch 的那个会话。

还有一点值得留意：桌面端 app.asar 里带的 dsh 与全局 pnpm 装的 0.1.7-rc.2 可能不是同一版本（旧 junction 路径里写着 0.1.5-rc.3），asar 里带着 `dsh-session-format-v0-to-v1 / v1-to-v2 / v2-to-v3` 三套迁移包。两个版本共用同一个 `$DSH_HOME`，session 格式迁移是实打实的风险——这也是别随便起第二个 dsh 的硬理由。

## 防火墙（需要管理员）

WLAN 的网络配置文件通常是 `Public`，入站默认拦截。首次要用**管理员** PowerShell 放行：

```powershell
New-NetFirewallRule -DisplayName "dsh-forward 3080" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3080 -Profile Any
```

撤销：

```powershell
Remove-NetFirewallRule -DisplayName "dsh-forward 3080"
```

## 访问与 token 语义

手机打开 `http://<局域网IP>:<端口>/?token=<43 字符>`。本地不用手机也能验到 303 与 `Set-Cookie`，再用 cookie 复放确认 200——但那只覆盖"本机连自己的局域网 IP"，**证明不了另一台设备能连**：入站来自远端主机是防火墙的另一层过滤。这一条已由真机（手机）实测通过。

token 的实测语义（`authorizeIndex` / `processLaunchToken`）：

- 每进程只生成一次（`PROCESS_LAUNCH_TOKENS` WeakMap），每次请求用 `timingSafeEqual` 比对——**不是一次性的，整个进程生命周期内可反复使用**。
- 仅在 `GET /` 且恰好一个 `token` 参数时接受；命中后 `303 → ./`，下发
  `dsh-auth-<sha256(authority)>=v1.<body>.<hmac>; Max-Age=<cookieMaxAgeDays>; Path=/; HttpOnly; SameSite=Strict`，
  并带 `referrer-policy: no-referrer`、`cache-control: no-store`。
- cookie 与权威绑定（`payload.authority !== authority` 即失效）→ 给 `192.168.10.5:3080` 签的 cookie 换到 `127.0.0.1:3080` 没用。

所以**那条 URL / 那张二维码 ≈ 一个密码**，重启 `dsh web` 是唯一的轮换手段。

## 设计取舍

- **纯 TCP 透传，不改写 Host/Origin**。信任栅栏要求 `Origin` 等于 `Host`，cookie 名又是 `dsh-auth-<sha256(authority)>`（由请求权威派生）——改写头部会同时动到这两处语义。原样透传让它们按设计工作，WebSocket 也免费可用；上面那张"经转发与直连状态码逐项一致"的表就是这么验出来的。
- **绑具体 LAN IP，不绑 `0.0.0.0`**。探针实测（单进程内）：同一端口上 `127.0.0.1` 与 `192.168.10.5` 可以并存，但 `0.0.0.0` 也能绑成功，且会**抢走**发往具体 IP 的连接；绑 `0.0.0.0` 还会连 loopback 流量一起抢，转发到同端口形成自环。
- **不用协程**。`socketserver.ThreadingTCPServer` + `select` 双向搬运：并发量是"一个浏览器 ≈ 6 条 HTTP + 1~2 条 WebSocket"，几十个线程的量级，asyncio 只会多一层没有收益的管道。`--max-connections` 给线程数封了顶。
- **不设 `SO_REUSEADDR`**。Windows 上它允许别的进程抢绑同一地址，宁可让重复启动明确失败。
- **`--check` 先干跑**。绑端口是对外动作，先看计划再动手。

## 已知边界

- 并发上限是**拒绝**而不是排队：超出的连接被直接关闭，不会等名额。
- 空闲超时只看有没有字节流动。若 GUI 的 WebSocket 长时间不发数据，默认 1800 秒会把它断开（浏览器的自动重连通常无感）。嫌敏感就调大或设 0。
- 透传吞吐受 Python 逐字节搬运限制，远低于 Caddy 一类 C/Go 实现；只有"通过 GUI 传大文件"时才感觉得到。
- `--launch` 抓 URL 的正则按 `app.asar:1017600` 的实现写，已用真实格式与误导行做了用例，并已对着真的 `dsh web` 启动跑通（`token 交换 303 → /api 无凭据 401 → 带 cookie 取页 200`）。
- **`--update-dsh` 会改动全局 dsh 版本。** 本机 npm 上目前**一个 stable 都没有**，所以最新候选是
  `0.2.0-rc.1`——首跑就会把全局 dsh 从 `0.1.7-rc.2` 升到它。那是跨 minor 的跳变，也正是
  session 格式迁移最可能被触发的时候，而这个 `$DSH_HOME` 与桌面端共享。想避开就加 `--no-update-dsh`，
  或者给那次运行换个独立的 `DSH_HOME`。
- **设置页在 LAN 页面上不可用**（`settings are unavailable in this browser`）：客户端按地址栏 hostname
  判定 loopback，与 `--trusted-host` 无关，服务端绕不过去。改配置用启动时打印的 `127.0.0.1` 那条 URL。
- 只在 Windows 上验证过（无线网卡探测走 `Get-NetAdapter`，进程创建用 `CREATE_NO_WINDOW`）。

## 安全

暴露到局域网后，任何拿到 token 的人都能操作这个 GUI，而这个 GUI 能在这台机器上执行命令。`dsh web` 拒绝 `0.0.0.0` 的原话就是 "it would expose remote code execution to the network"。

会泄漏 token 的路径：明文 HTTP 过 WiFi（无 TLS，同网段可嗅探）、二维码截图进相册、浏览器历史。不会泄漏的：Referer（`no-referrer`）、跨站（`SameSite=Strict`）、JS 读 cookie（`HttpOnly`）、跨权威重放（authority-bound）。

真要防护就上 TLS + 认证——**那才是 Caddy 该出场的地方**；或者更彻底：别暴露到 LAN，走 Tailscale/WireGuard 这类隧道，只让自己的设备能连。只在可信网络里开，用完 Ctrl+C。

## 另一条路（不用转发器，但更宽）

web 服务器 schema 本身**接受** `0.0.0.0`，拒绝它的只是 CLI。理论上可以改 profile 的 `cordis.patch.yml`，把 webserver 行的 `host` 直接写成 `0.0.0.0` 绕开 CLI，此时 `resolveLanTrust` 会自动派生所有 LAN 字面量，连 `--trusted-host` 都不用。代价是绑到**每个**网卡（含 VirtualBox host-only、APIPA 等），且这条路被官方明确标注为不支持。

## 自检

```powershell
cd Python/dsh-forward
uv run --no-project test_forward.py
```

覆盖目标地址解析、IPv4 校验、URL 行解析（含必须拒绝的误导行）、访问 URL 改写、双向透传与半关闭、并发上限、空闲超时、以及带路径和查询串的端到端透传。只绑 loopback 与 OS 随机端口，不占 3080、不碰局域网地址。
