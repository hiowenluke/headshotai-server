import os
import time

def rename_md_files(folder_path):
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".md"):
                old_path = os.path.join(root, file)
                filename = os.path.basename(file)

                # 检查是否以14位数字开头
                if not (len(filename) >= 14 and filename[:14].isdigit()):
                    # 获取文件最后修改时间
                    stat = os.stat(old_path)
                    modify_time = stat.st_mtime  # 文件最后修改时间（秒）
                    timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime(modify_time))

                    new_filename = f"{timestamp}_{filename}"
                    new_path = os.path.join(root, new_filename)

                    # 避免覆盖已有文件
                    if not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                        print(f"重命名: {filename} -> {new_filename}")
                    else:
                        print(f"跳过: {new_filename} 已存在")

if __name__ == "__main__":
    folder = "./__changes"  # 如果是相对路径，则是相对于当前脚本调用者的路径
    rename_md_files(folder)