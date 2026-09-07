---
layout: page
title: "Tell You · 我还有未说完的"
permalink: /Get/Tell/
---

任何除了使用Flathub官方或直接运行python的，在安装前，最好先安装Flathub来获取所需依赖，避免各种奇奇怪怪的依赖问题：

---

## 我有Flathub吗？

如果你不太确定你有没有Flathub，你可以运行下面这条命令，若输出有Flathub，则代表你有Flathub

```sh
flatpak remotes
```

---

## 添加Flathub

你可以用这条命令添加Flathub
```sh
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

> 如果出了奇奇怪怪的问题，请前往[Flathub官方提供的安装教程](https://flathub.org/zh-hans/setup/)，在里面选择好你的发行版，然后跟着教程一步一步做就行了

---

## 下载速度慢

建议配置一下国内镜像，可用下面这条命令添加镜像（前提是已经有Flathub了）

```sh
sudo flatpak remote-modify flathub --url=https://mirror.sjtu.edu.cn/flathub
```

>若下载速度更慢了或提升效果不理想，可以再换个镜像：
>```sh
># USTC 中国科学技术大学开源软件镜像
>sudo flatpak remote-modify flathub --url=https://mirrors.ustc.edu.cn/flathub
>```
>```sh
># CERNET 校园网联合镜像站
>sudo flatpak remote-modify flathub --url=https://mirrors.cernet.edu.cn/flathub
>```
>或切回Flathub官方镜像
>```sh
>sudo flatpak remote-modify flathub --url=https://dl.flathub.org/repo
>```