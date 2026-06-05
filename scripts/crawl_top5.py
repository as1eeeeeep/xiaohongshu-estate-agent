import os
import json
import subprocess
import sys
from datetime import datetime

def main():
    print("🚀 启动小红书爆款评论自动抓取工具...")
    
    # 1. 确保配置好环境变量和编码环境
    env = os.environ.copy()
    env["PATH"] = r"C:\Users\azzi\.local\bin;" + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    
    # 定义输出目录
    output_dir = r"d:\xiaohongshu-cli\output"
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 已创建输出文件夹: {output_dir}")
    
    # 定义 xhs 执行程序路径
    xhs_bin = r"C:\Users\azzi\.local\bin\xhs.exe"
    
    # 2. 执行搜索获取最热的“香港房产”笔记
    search_keyword = "香港房产"
    print(f"🔍 正在小红书检索关键词: '{search_keyword}' 并按最热排序...")
    
    try:
        search_cmd = [xhs_bin, "search", search_keyword, "--sort", "popular", "--json"]
        result = subprocess.run(
            search_cmd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True
        )
        search_data = json.loads(result.stdout)
    except Exception as e:
        print(f"❌ 检索失败: {e}")
        if 'result' in locals() and result.stderr:
            print(f"错误详情:\n{result.stderr}")
        sys.exit(1)
        
    if not search_data.get("ok"):
        print("❌ 小红书搜索返回失败状态")
        sys.exit(1)
        
    items = search_data.get("data", {}).get("items", [])
    if not items:
        print("❌ 未搜索到任何相关的笔记！")
        sys.exit(0)
        
    # 取前5篇笔记
    top_5_items = items[:5]
    print(f"✅ 成功获取最热前 {len(top_5_items)} 篇笔记列表。开始逐篇抓取评论区...")
    
    # 3. 逐篇抓取评论区
    for idx, item in enumerate(top_5_items, start=1):
        note_id = item.get("id")
        xsec_token = item.get("xsec_token")
        
        # 解析元数据
        note_card = item.get("note_card", {})
        title = note_card.get("display_title", "").strip()
        author = note_card.get("user", {}).get("nickname", "").strip()
        
        # 拼接网页链接
        note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_share"
        
        print(f"\n──────────────────────────────────────────────────")
        print(f"📝 正在抓取第 {idx}/5 篇笔记:")
        print(f"   标题: {title}")
        print(f"   作者: {author}")
        print(f"   链接: {note_url}")
        
        try:
            # 调用 comments 命令抓取全部评论
            comments_cmd = [xhs_bin, "comments", note_id, "--xsec-token", xsec_token, "--all", "--json"]
            print(f"   ⏳ 正在拉取该笔记的完整评论（包含多级子评论）...")
            
            c_result = subprocess.run(
                comments_cmd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True
            )
            
            comments_data = json.loads(c_result.stdout)
            
            # 整合元数据与链接
            output_payload = {
                "note_id": note_id,
                "note_url": note_url,
                "title": title,
                "author": author,
                "extracted_at": datetime.now().isoformat(),
                "comments_data": comments_data.get("data", comments_data)
            }
            
            # 保存为独立的 JSON 文件
            safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).strip()[:15]
            file_name = f"note_{idx}_{note_id}_{safe_title}.json" if safe_title else f"note_{idx}_{note_id}.json"
            output_path = os.path.join(output_dir, file_name)
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_payload, f, ensure_ascii=False, indent=2)
                
            print(f"   🎉 抓取成功！保存至: {output_path}")
            
        except Exception as e:
            print(f"   ❌ 第 {idx} 篇笔记抓取失败: {e}")
            if 'c_result' in locals() and c_result.stderr:
                print(f"   错误详情:\n{c_result.stderr}")
                
    print(f"\n==================================================")
    print(f"✨ 任务全部完成！请前往 {output_dir} 查看导出的 5 份爆款评论 JSON 文件。")

if __name__ == "__main__":
    main()
