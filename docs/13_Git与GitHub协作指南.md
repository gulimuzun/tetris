# Git 与 GitHub 分工协作指南

这里记的是我们三人开发时统一使用的 Git 流程。目的很简单：各自的代码在功能分支上完成，通过 Pull Request 审查后再合并。

## 1. 分支结构

```text
feature/scoring ─────┐
feature/game-core ───┤
feature/ui ──────────┼──> develop ──> main
feature/network-app ─┘
```

- `main`：通过完整测试的稳定版本。
- `develop`：日常集成分支。
- `feature/*`：每项任务的开发分支。
- 功能代码不得直接推送到 `main` 或 `develop`。

## 2. 创建 GitHub 空仓库

组长在 GitHub 点击 `New repository`，例如命名为 `tetris-lan`。创建时先不勾选 README、`.gitignore` 或许可证，然后复制 HTTPS 地址：

```text
https://github.com/组长用户名/tetris-lan.git
```

## 3. 建立公共初始提交

Git 需要一个共同提交才能正常创建分支。组长克隆空仓库：

```bash
git clone https://github.com/组长用户名/tetris-lan.git
cd tetris-lan
mkdir -p docs tetris tests
```

初始仓库只放以下内容，不放现有项目实现：

```text
docs/11_小组分工与集成方案.md
docs/12_完整接口文档.md
docs/13_Git与GitHub协作指南.md
tetris/__init__.py
requirements.txt
.gitignore
```

`requirements.txt`：

```text
pygame>=2.6,<3
```

`.gitignore`：

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
.vscode/
.idea/
.DS_Store
.pytest_cache/
*.log
```

提交公共起点：

```bash
git add .gitignore requirements.txt docs tetris/__init__.py
git commit -m "chore: 初始化项目结构和接口文档"
git branch -M main
git push -u origin main
git switch -c develop
git push -u origin develop
```

## 4. 邀请成员与保护分支

在 GitHub 仓库进入：

```text
Settings → Collaborators → Add people
```

邀请两名成员。然后进入：

```text
Settings → Branches → Add branch protection rule
```

为 `main` 和 `develop` 启用：

- Require a pull request before merging
- Require approvals：1
- Block force pushes

## 5. 成员配置并克隆

首次使用 Git：

```bash
git config --global user.name "GitHub用户名"
git config --global user.email "GitHub账号邮箱"
```

克隆仓库：

```bash
git clone https://github.com/组长用户名/tetris-lan.git
cd tetris-lan
git switch develop
python -m pip install -r requirements.txt
```

## 6. 创建任务分支

### 组长先实现计分接口

```bash
git switch develop
git pull origin develop
git switch -c feature/scoring
git push -u origin feature/scoring
```

负责 `ScoreSystem` 和计分测试。该 PR 应最先合并。

### 成员一实现玩法

计分 PR 合并后：

```bash
git switch develop
git pull origin develop
git switch -c feature/game-core
git push -u origin feature/game-core
```

负责 `config.py`、除计分外的 `core.py` 和玩法测试。

### 成员二实现 UI

```bash
git switch develop
git pull origin develop
git switch -c feature/ui
git push -u origin feature/ui
```

负责 `ui.py` 和建议新增的 `screens.py`。独立 `screens.py` 可以避免与组长共同修改 `app.py`。

### 组长实现应用与联机

玩法和 UI 接口进入 `develop` 后：

```bash
git switch develop
git pull origin develop
git switch -c feature/network-app
git push -u origin feature/network-app
```

负责 `main.py`、`app.py`、`network.py` 和联机测试。

## 7. 日常提交

确认位于自己的功能分支：

```bash
git branch --show-current
git status
```

查看、暂存、提交和推送：

```bash
git diff
git add 自己负责的文件
git diff --staged
git commit -m "feat(core): 实现方块移动和碰撞"
git push
```

尽量不要使用 `git add .`，避免提交缓存或他人的文件。

提交信息格式：

```text
类型(模块): 修改说明
```

常用类型：`feat`、`fix`、`refactor`、`test`、`docs`、`chore`。

示例：

```text
feat(scoring): 实现消行和连击计分
feat(core): 实现7-bag和旋转墙踢
feat(ui): 实现棋盘与预览绘制
feat(network): 实现TCP快照同步
fix(core): 修复落地计时重复累计
```

## 8. 创建 Pull Request

功能完成并推送后，在 GitHub 点击 `Compare & pull request`，确认：

```text
base: develop
compare: feature/自己的分支
```

不能把功能分支直接合并到 `main`。

PR 描述模板：

```markdown
## 完成内容

- 实现了哪些功能
- 修复了哪些问题

## 接口变化

- 新增或修改了哪些公开接口
- 如果没有变化，填写“无”

## 测试

```bash
python -m unittest discover -s tests -v
```

测试结果：全部通过。

## 注意事项

- 需要审查者重点检查的内容
```

## 9. PR 审查与合并

- 成员一、成员二的 PR 由组长审查。
- 组长的 PR 由至少一名成员审查。
- 至少一人 `Approve` 后才能合并。
- 推荐使用 `Squash and merge`，让一个 PR 在集成分支中对应一个清晰提交。

审查项目：

- 是否只修改负责范围？
- 是否符合接口文档？
- 是否重复实现其他人的逻辑？
- 是否存在调试代码、缓存或临时文件？
- 注释是否解释关键原因？
- 测试是否通过？

推荐合并顺序：

```text
1. feature/scoring → develop
2. feature/game-core → develop
3. feature/ui → develop
4. feature/network-app → develop
5. develop → main
```

## 10. 同步 develop

其他 PR 合并后，在自己的功能分支同步：

```bash
git switch develop
git pull origin develop
git switch feature/自己的分支
git merge develop
git push
```

对初学者推荐 `merge`，不要随意对已经推送的提交执行 rebase 或强制推送。

## 11. 解决冲突

冲突文件中会出现：

```text
<<<<<<< HEAD
自己的内容
=======
develop中的内容
>>>>>>> develop
```

对照接口文档保留正确内容，删除标记，然后：

```bash
python -m unittest discover -s tests -v
git add 冲突文件
git commit -m "merge: 同步develop并解决冲突"
git push
```

放弃本次合并：

```bash
git merge --abort
```

不要用 `git reset --hard` 或 `git checkout -- .` 粗暴解决，否则可能丢失代码。

## 12. 临时保存未完成代码

```bash
git stash push -m "暂存未完成工作"
git switch 其他分支
```

恢复：

```bash
git switch 原分支
git stash pop
```

## 13. 集成与发布

全部功能进入 `develop` 后，组长执行：

```bash
git switch develop
git pull origin develop
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python main.py
```

还要完成本机双进程和两台局域网设备测试。修复集成问题时创建 `fix/integration` 分支并通过 PR 合并。

验证通过后创建最后一个 PR：

```text
base: main
compare: develop
```

合并后创建版本：

```bash
git switch main
git pull origin main
git tag -a v1.0.0 -m "俄罗斯方块第一版"
git push origin v1.0.0
```

## 14. 每天最短工作流程

```bash
# 同步
git switch develop
git pull origin develop
git switch feature/自己的分支
git merge develop

# 开发后提交
git status
git diff
git add 自己负责的文件
git commit -m "类型(模块): 修改说明"
git push
```

功能完成后：运行测试、创建 PR、等待审查、合并 `develop`。

## 15. 必须遵守的规则

1. 不直接向 `main`、`develop` 推送功能代码。
2. 只修改分工文档中属于自己的接口。
3. 接口变化前先讨论并更新接口文档。
4. PR 合并前必须通过测试并由另一人审查。
5. 不提交缓存、虚拟环境、IDE 配置和日志。
6. 冲突按接口逐行解决，不能用整个文件覆盖他人代码。
