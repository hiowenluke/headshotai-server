不懂就问。关于 UUID 和 provider_sub 的区别。



# 我

我注意到你的 sql 语句使用 id='7b9835be-aab3-4b39-972f-3d8f26b127f3'，但是 public/upload 下的 id 是 112327427190669663663。为什么这两个不同？



# Codex

你看到的这两个值分别来自不同的体系，所以不一致是正常的：

## ❶ 数据库里的 `id` 是 UUID

- `public.users` 表的主键 `id` 使用 UUID（例如 `7b9835be-aab3-4b39-972f-3d8f26b127f3`）。
- `user_identities` 表里记录了 OAuth 提供方返回的 [provider_sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)（Google 的 [sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)），是你看到的长数字串 `112327427190669663663`。
- 我们通过这两个表的关联把 Google 账号和用户行关联在一起。

## ❷ `public/upload/...` 目录名使用的是“用户标识”

- 本地磁盘目录命名不会用 UUID，而是用一个简化的 “user ident” 字符串。
- 代码中 [_sanitize_user()](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 会优先取 [session['sub'\]](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)，也就是 [provider_sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)；只有没有 [sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 才退回 email。
- 所以目录 [112327427190669663663](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 实际写的就是 provider_sub 经过清洗后的结果。

## ✅ 映射关系

因此，两种 ID 同时存在、且一个是 UUID、一个是 Google 提供的数值字符串，是系统设计的一部分：
```
users.id (UUID)  <—>  user_identities.provider_sub (Google sub)
                         |
                         +—> 用来命名本地上传目录
```


- 数据层面用 UUID 做主键更安全统一；
- 文件存储用 [sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 方便直接定位到用户目录。



# 我

user_identities.provider_sub (Google sub)

意思是，这个 id 是 google 提供的。

那么，如果用户使用 facebook 账号登录，则会获得另一个由 facebook 提供的 id？



# Codex

是的，逻辑完全一样。`user_identities` 里保存了三件事：

- [user_id](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)：我们自己 `users` 表的主键（UUID）。
- [provider](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)：[google](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) / `facebook` / 其他。
- [provider_sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)：对应第三方的唯一 ID。

所以：

- 用 Google 登录时，`provider = 'google'`，`provider_sub` 存 Google 的 [sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)。
- 用 Facebook 登录时，同一列会改成 [provider = 'facebook'](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)，[provider_sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 就存 Facebook 回传的那个用户 ID（一般是类似形状的长数字串或者字母数字组合），用来作为你的账号在 Facebook 身边的唯一标识。

多家登录并存时，就会在 `user_identities` 表里出现同一个 [user_id](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 对应多条记录，例如：

| user_id | provider | provider_sub          |
| ------- | -------- | --------------------- |
| (uuid)  | google   | 112327427190669663663 |
| (uuid)  | facebook | 1029384756...         |

这样就能把不同 OAuth 平台的身份都映射到同一个本地用户。



# 我

如果这个用户使用同一个 email，在数据库里有唯一的 uuid，当他先用 google 账号登录，上传照片，保存在 public/upload/112327427190669663663 下，然后换成 facebook 账号登录，那么他能看到之前用 google 账号登录时上传的照片吗？



# Codex

先说结论：照现在的实现，**同一个邮箱的用户换成 Facebook 登录后看不到先前用 Google 登录时上传的照片**，原因是前后使用了不同的“用户标识”来存取文件。

------

## 体系现状

1. **数据库层面**
   - `users` 表的主键 `id` 是 UUID。
   - [upsert_user()](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 里先按 email 查找，如果已有记录则复用同一行，所以 Google / Facebook 账号都会落在同一个 [user_id](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)。
2. **身份表 `user_identities`**
   - 每条记录保存一个 [provider_sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)（Google [sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 或 Facebook ID）和对应 [provider](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)。
   - 同一个 [user_id](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 可以挂多条 identity。
3. **文件命名关键：[user_ident](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)**
   - 上传 API 里用 [_sanitize_user()](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 来决定目录名，它优先取 [session['sub'\]](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)，只有没有 [sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 时才退回 email。
   - 因此：
     - Google 登录 → 目录是 `public/upload/<Google sub>/faces/...`
     - Facebook 登录（同邮箱）→ 目录会变成 `public/upload/<Facebook id>/faces/...`
4. **前端、后端读取缩略图也都是用同一个 [user_ident](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)**
   - 前端 `currentUserId = authState.user?.sub || authState.user?.email`。
   - 后端 [list_recent_faces_for_user()](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 同样优先走 [sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)。

结果就是两个 provider 对应两个不同目录，彼此互不共享，新的登录方式自然看不到旧目录中的文件。

------

## 如果想打通的思路

- **统一目录键**：改成用数据库 [user_id](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)（UUID）或 email 作为上传路径，这样跨 provider 共享同一目录。要注意改动范围大（上传接口、历史数据迁移、静态文件引用）。
- **做迁移脚本**：把旧目录里的文件搬到统一目录下，并更新缓存/引用。
- **兼容策略**：登录后既查当前 [sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 目录，也查历史 [sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)（可通过 `user_identities` 表获取），合并结果。缺点是多目录遍历稍复杂。

目前默认行为就是“按照登录 provider 隔离”，如果期望同邮箱的用户跨平台共享，得以上述方案之一做调整。



# 我

“按照登录 provider 隔离”，这样做的好处是什么呢？



# Codex

先梳理当前做法的意图，再列出按 provider 隔离上传目录带来的正面作用和潜在成本。

## 设计动机与收益

- **避免 ID 冲突与替换**：[provider_sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 在各平台内保证唯一，直接拿来做目录名，不需要额外映射；如果用户后来绑定多个社交账号，也不会互相覆盖文件。
- **安全与隐私隔离**：不同平台的认证态通常被视为不同“身份”，即便邮箱相同，也可能是同一人刻意切换身份或测试账号；独立目录让每个身份只看得到自己上传的素材，减少误爆隐私的概率。
- **调试和追踪简单**：目录名和后台日志里的 [sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 一一对应，排查“谁上传了这批照片”时可以直接从文件路径反推出 OAuth 身份。
- **兼容多邮箱绑定**：某些平台允许用户改邮箱或隐藏邮箱（比如 Facebook），把目录和 [sub](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 绑定而非 email，可避免邮箱变动导致找不到原记录。
- **降低偶然账号共享的风险**：如果多人共用同一个 email（少见但存在，例如公司公共邮箱），按 provider 切分可以防止不同人的照片意外混在一起。

## 需要权衡的点

- 同邮箱跨平台登录时无法自动看到之前的照片（你刚才提到的问题）——如果产品需要跨平台共享，就得改成用 [user_id](vscode-file://vscode-app/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html) 或 email 做目录、或做迁移脚本。
- 目录数量会随登录 provider 增加；管理上需要知道“某个 UUID 下面有哪些 provider_sub”才能做批量迁移或清理。
- 未来如果支持账号合并（把两个 provider 身份手动合并），也要同步合并文件目录。

总结：当前策略的优势在于隔离明确、实现简单、安全稳妥，但牺牲了“同人跨平台共享素材”的便利性。是否维持取决于业务更看重隐私隔离还是跨平台共享；要共享，可以改为以 `users.id` 为主键去存储并补迁移流程。



# 总结

目前不需要改动。

