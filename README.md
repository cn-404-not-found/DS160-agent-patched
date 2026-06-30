# DS-160 Visa Assistant

一个本地运行的 DS-160 填写辅助工具，面向中国 B1/B2 申请资料整理和半自动填表。

> 非官方工具。请在提交前自行核对所有 DS-160 内容。

## 功能

- 手动录入申请资料，导出统一 dossier JSON
- 导入 dossier 后按页面自动填写 CEAC DS-160
- 支持断点续填、页面识别、基础校验和本地审计日志
- 支持加密导出/导入申请资料

## 快速开始

从 GitHub Release 下载对应平台的 `ds160-assistant`，解压后运行：

```bash
./ds160-assistant
```

程序会启动本地服务并打开：

```text
http://127.0.0.1:8765
```

需要本机已安装 Chrome 或 Chromium。

## 使用流程

1. 打开首页，进入“填写资料”
2. 填写申请人信息并导出 dossier JSON
3. 进入“开始填写”，导入 dossier JSON
4. 在 Chrome 中完成 CEAC 验证码和人工确认步骤
5. 按页面点击“一键填入”或“填完并翻页”

## 从源码运行

```bash
bash scripts/install-deps.sh
bash scripts/start.sh
```

构建发布包：

```bash
bash scripts/build.sh
```

构建单文件版本：

```bash
bash scripts/build.sh onefile
```

## 首个 Release

建议首发版本：`v0.1.0`

Release 标题：

```text
DS-160 Visa Assistant v0.1.0
```

Release 说明：

```text
首个可发行版本。

- 本地 DS-160 dossier 采集页
- CEAC 页面自动识别和逐页填入
- China B1/B2 样例资料结构
- 资料加密导出/导入
- 断点续填和基础审计日志

注意：这是非官方辅助工具。请在 CEAC 页面提交前人工核对全部内容。
```

## 开发验证

```bash
PYTHONPATH=src python -m pytest tests/
```

更多细节见 [QUICKSTART.md](QUICKSTART.md)。
