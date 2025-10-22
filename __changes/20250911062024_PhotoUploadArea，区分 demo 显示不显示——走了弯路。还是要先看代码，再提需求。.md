1. 组件 FaceUploadController，增加传入参数（数组） demoUrls，并直接传递给组件 PlusButtonHintArea。

2. 组件 PlusButtonHintArea，增加传入参数（数组） demoUrls，指定 demo 图片的 url：

- 如果该参数有值，则显示 demo 区域，并应用 demoUrls（仅取前4个值），展示 demo 图片。
- 否则，不显示 demo 区域，并且当前组件的高度自动减小。

3. 组件 Generator1P，调用组件 FaceUploadController，传递参数 demoUrls（它的值从服务端获取）

4. 组件 Generator20P，调用组件 FaceUploadController，不指定参数 demoUrls（即，不显示 demo 图片）

-----------------------

Sonnet 4 实现之后，才发现 PlusButtonHintArea 已经有 demos 参数。因此撤销了代码，重新提需求（PlusButtonHintArea  改名为了 FaceUploadArea）：

-----------------------

我注意到 FaceUploadArea 其实已经有了 demos 参数，因此我撤回了本次修改的代码。有的文件内容有修改（或者文件改名了），请以本次提供的文件为准，重新读取本地文件。

请重新实现如下需求：

1. 组件 FaceUploadArea，调整 demos 的处理逻辑：

- 如果传入了该参数，则显示 demo 区域，并应用 demos（仅取前4个值），展示 demo 图片。
- 否则，不显示 demo 区域，并且当前组件的高度自动减小。

2. 组件 FaceUploadController，确保把 demos 参数正确传递给了 组件 FaceUploadArea。

3. 组件 Generator20P，调用组件 FaceUploadController，不指定参数 demos（即，不显示 demo 图片）