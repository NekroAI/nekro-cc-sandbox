---
name: gh
description: This skill should be used when the user asks to use gh CLI for GitHub operations, including PR review, issue management, repo management, and API calls.
version: 1.0.0
---

# gh CLI 实战经验

## 是什么
- GitHub 官方 CLI 工具，用 Go 编写
- 官网: https://cli.github.com/
- 安装: `brew install gh` / `npm install -g gh` / 下载二进制

## 认证

### 交互式登录
```bash
gh auth login
# 会打开浏览器进行 GitHub OAuth 认证
```

### 环境变量认证（适合 CI/CD）
```bash
export GH_TOKEN="your_github_personal_access_token"
# 或
export GITHUB_TOKEN="your_token"
```

### 检查认证状态
```bash
gh auth status
```

## 常用命令速查

### 仓库操作
```bash
gh repo view              # 查看当前仓库信息
gh repo view <owner>/<repo>  # 查看指定仓库
gh repo view --web        # 在浏览器打开
gh repo view --json name,owner,defaultBranchRef  # JSON 输出
gh repo fork              # fork 当前仓库
gh repo clone <repo>      # 克隆仓库
```

### PR 操作
```bash
gh pr list                # 列出 PR
gh pr view <pr-number>    # 查看 PR
gh pr checkout <pr-number>  # 检出 PR
gh pr create              # 创建 PR
gh pr merge <pr-number>   # 合并 PR
gh pr review <pr-number>  # 审阅 PR
```

### Issue 操作
```bash
gh issue list             # 列出 Issue
gh issue view <number>    # 查看 Issue
gh issue create           # 创建 Issue
gh issue close <number>   # 关闭 Issue
```

### 运行和 Workflow
```bash
gh run list               # 列出 CI/CD 运行
gh run view <run-id>      # 查看运行详情
gh run watch <run-id>     # 监控运行
gh workflow list          # 列出 workflow
gh workflow view <wf-id>  # 查看 workflow
```

### Gist
```bash
gh gist list              # 列出 gist
gh gist create <file>     # 创建 gist
gh gist view <gist-id>    # 查看 gist
```

### Codespace
```bash
gh codespace list         # 列出 codespace
gh codespace ssh <name>   # SSH 连接
gh codespace delete <name>  # 删除
```

## API 调用（重要功能）

`gh api` 可以直接调用 GitHub REST/GraphQL API：

```bash
# GET 请求
gh api repos/{owner}/{repo}
gh api repos/vercel-labs/agent-browser -q '.full_name + " ⭐ " + (.stargazers_count|tostring)'

# 使用 jq 过滤（推荐）
gh api user/repos --jq '.[].name'

# POST 请求
gh api repos/{owner}/{repo}/issues -f title="Bug" -f body="Description"

# GraphQL
gh api graphql -f query='query { viewer { login } }'

# 设置请求头
gh api -H "Accept: application/vnd.github.v3+json" ...

# 传递变量
gh api graphql -f query='query($owner: String!) { ... }' -F owner=myorg
```

### jq 常用技巧
```bash
# 提取数组
gh api user/repos --jq '.[].name'

# 提取单个值
gh api user --jq '.login'

# 过滤
gh api user/repos --jq '.[] | select(.fork == false) | .name'

# 格式化输出
gh api repos/{owner}/{repo}/commits --paginate --jq '.[0:3] | .[] | "\(.sha[0:7]) \(.commit.message | split("\n")[0])"'
```

## 格式化输出

```bash
# JSON 字段选择
gh repo view --json name,owner,description

# jq 表达式
gh pr list --jq '.[].number'

# 表格输出（默认）
gh pr list

# CSV
gh api user/repos --csv > repos.csv
```

## 配置管理

```bash
gh config list             # 查看配置
gh config get <key>        # 获取配置
gh config set <key> <val>  # 设置配置

# 常用配置
gh config set editor vim
gh config set prompt disabled
gh config set pager less
```

## 别名

```bash
# 创建别名
gh alias set prc 'pr checkout'
gh alias set co 'pr checkout'
gh alias set todo 'issue list --assignee @me --state all'

# 列出别名
gh alias list

# 使用别名
gh prc 123
```

## 实际测试中的发现

### 1. 认证是必须的
- 大部分命令需要认证才能使用
- `gh auth status` 可检查当前状态
- 未登录时只能查看公开仓库的部分信息

### 2. API 调用的 {owner}/{repo} 占位符
- 可以从当前 git 目录自动推断
- 也可以用 `GH_REPO` 环境变量指定

### 3. jq 语法灵活
- `split("\n")[0]` 可以提取多行消息的第一行
- `.[0:3]` 可以限制数组长度
- 支持复杂的条件过滤

### 4. --paginate 自动处理分页
```bash
gh api user/repos --paginate
# 自动获取所有页面的数据
```

### 5. 输出格式选择
- 脚本用 `--jq` 或 `--json`
- 交互式查看用默认表格格式

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| 未登录 | 运行 `gh auth login` 或设置 `GH_TOKEN` |
| API 限流 | 认证后提高限额，添加 `--paginate` 避免重复调用 |
| 找不到仓库 | 确保当前目录是 git 仓库或设置 `GH_REPO` |
| 权限错误 | 检查 token 权限范围 (repo, workflow 等) |

## 工作流示例

### 快速审阅 PR
```bash
gh pr list                           # 查看 PR 列表
gh pr view 123 --json title,body,files  # 查看详情
gh pr checkout 123                   # 检出代码
gh pr review 123 --approve           # 批准
gh pr merge 123                      # 合并
```

### 监控 CI/CD
```bash
gh run list
gh run view <id> --json status,conclusion
gh run watch <id> --interval 10      # 每 10 秒刷新
```

### 批量操作 Issues
```bash
gh issue list --state all --jq '.[].number'
gh issue close 1 2 3                 # 批量关闭
```
