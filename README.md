# SUSTech 2024-Fall-CS305-Computer-Network-Project
SUSTech CS305 Computer Network Project -- Online Remote Conference


## 环境要求

Python 3.9.20

## 如何设置本地仓库

1. **安装Git**: 确保你的计算机上安装了Git。可以从[Git官网](https://git-scm.com/)下载并安装。
2. **克隆仓库**:
   ```bash
   git clone https://github.com/Scott-Einstein/SUSTech-CS305-Computer-Network-Project.git
   ```
   这将创建一个本地副本的仓库。

## Git 基本操作

### 创建分支
```bash
git checkout -b <branch-name>
```
这将创建一个新的分支并切换到该分支。

### 添加文件
```bash
git add <file-name>
```
将文件添加到暂存区。

### 提交更改
```bash
git commit -m "Commit message"
```
提交你的更改。

### 推送到远程仓库
```bash
git push origin <branch-name>
```
将你的更改推送到GitHub上的远程仓库。

### 拉取最新代码
```bash
git pull origin <branch-name>
```
从远程仓库拉取最新代码。

### 合并分支
如果你需要将一个分支的更改合并到另一个分支：
```bash
git checkout <target-branch>
git merge <source-branch>
```
切换到目标分支，然后合并源分支。

### 解决合并冲突
如果合并时出现冲突，你需要手动解决它们，然后再次提交。

## 贡献指南

请遵循以下指南来贡献代码：
- 确保你的代码风格与项目保持一致。
- 在提交之前运行测试，确保没有引入新的错误。
- 如果你添加了新功能，请添加相应的文档。

## 许可证

请指定你的项目使用的许可证。

---

请根据你的项目具体内容，填充上述模板中的各个部分。README文件应该简洁明了，同时提供足够的信息以帮助其他开发者快速上手。
