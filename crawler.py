import requests
import json
import time
import random
import logging
from urllib.parse import urljoin

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawler.log"),
        logging.StreamHandler()
    ]
)

class HuluxiaCrawler:
    """葫芦侠数据采集器"""
    
    def __init__(self):
        self.base_url = "http://floor.huluxia.com"
        self.headers = {
            'Host': 'floor.huluxia.com',
            'Accept': 'application/json, text/json, text/x-json, text/javascript, application/xml, text/xml',
            'User-Agent': 'PHP cURL Request',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip, deflate'
        }
    
    def get_categories(self):
        """获取葫芦侠板块信息"""
        try:
            # 使用需求文件中指定的板块接口
            url = urljoin(self.base_url, "/category/list/ANDROID/2.0")
            logging.info(f"开始获取板块信息: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()  # 如果请求不成功则抛出异常
            
            # 解析JSON响应
            data = response.json()
            logging.info(f"成功获取板块信息，状态消息: {data.get('msg', '')}")
            
            # 提取板块数据
            categories = data.get('categories', [])
            logging.info(f"共获取到 {len(categories)} 个板块")
            
            # 整理板块数据
            categories_data = []
            for category in categories:
                category_info = {
                    '板块ID': category.get('categoryID', ''),
                    '板块名称': category.get('title', ''),
                    '板块描述': category.get('description', ''),
                    '帖子数量': category.get('postCount', 0),
                    '浏览数量': category.get('viewCount', 0),
                    '板块图标': category.get('icon', ''),
                    '模型类型': category.get('model', 0),
                    '是否精品': category.get('isGood', 0),
                    '是否订阅': category.get('isSubscribe', 0),
                    '排序序号': category.get('seq', 0),
                    '订阅类型': category.get('subscribeType', 0),
                }
                
                # 提取版主信息
                moderators = category.get('moderator', [])
                moderator_names = [mod.get('nick', '') for mod in moderators]
                category_info['版主'] = '、'.join(moderator_names)
                
                # 提取子版块（标签）信息，包含ID和名称
                tags = category.get('tags', [])
                category_info['子版块'] = [{'ID': tag.get('ID', ''), '名称': tag.get('name', '')} for tag in tags]
                
                categories_data.append(category_info)
            
            return categories_data
            
        except Exception as e:
            logging.error(f"获取板块信息失败: {str(e)}")
            return []
    
    def save_to_json(self, data, filename):
        """将数据保存到JSON文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logging.info(f"数据已保存到 {filename}")
        except Exception as e:
            logging.error(f"保存数据到JSON失败: {str(e)}")
    
    def random_sleep(self, min_seconds=1, max_seconds=3):
        """随机休眠一段时间，避免请求过于频繁"""
        sleep_time = random.uniform(min_seconds, max_seconds)
        logging.info(f"休眠 {sleep_time:.2f} 秒")
        time.sleep(sleep_time)

    def display_categories(self, categories):
        """在控制台直接显示板块信息"""
        if not categories:
            print("未获取到任何板块信息")
            return
        
        print("\n" + "="*80)
        print(f"葫芦侠论坛板块信息 (共 {len(categories)} 个板块)")
        print("="*80)
        
        for i, category in enumerate(categories, 1):
            print(f"\n【{i}】 {category['板块名称']} (ID: {category['板块ID']})")
            print("-"*80)
            
            # 安全处理可能为None的描述值
            description = category['板块描述'] or ''
            if len(description) > 100:
                description = description[:100] + '...'
            print(f"描述: {description}")
            
            print(f"帖子数: {category['帖子数量']}   浏览量: {category['浏览数量']}")
            
            if category['版主']:
                print(f"版主: {category['版主']}")
            
            # 显示子版块信息
            if category['子版块']:
                print("\n  子版块:")
                for sub in category['子版块']:
                    if sub['名称'] != '全部':  # 不显示"全部"这个子版块
                        print(f"    ├─ {sub['名称']} (ID: {sub['ID']})")
            
            print(f"\n图标URL: {category['板块图标']}")
            print("-"*80)
        
        print("\n" + "="*80 + "\n")

    def display_specific_category(self, categories, target_name=None, target_id=None):
        """显示指定的板块信息"""
        if not categories:
            print("未获取到任何板块信息")
            return
        
        # 查找目标板块
        target_category = None
        for category in categories:
            # 通过名称或ID匹配
            if (target_name and target_name in category['板块名称']) or \
               (target_id and str(target_id) == str(category['板块ID'])):
                target_category = category
                break
        
        if not target_category:
            print(f"未找到指定的板块: {target_name or target_id}")
            return
        
        # 显示找到的板块信息
        print("\n" + "="*80)
        print(f"【{target_category['板块名称']}】(ID: {target_category['板块ID']})")
        print("="*80)
        
        # 显示子版块信息
        if target_category['子版块']:
            print("\n子版块列表:")
            for i, sub in enumerate(target_category['子版块'], 1):
                print(f"{i}. {sub['名称']} (ID: {sub['ID']})")
        else:
            print("\n该板块没有子版块")
        
        print("\n" + "="*80)

    def display_all_categories_with_subcategories(self, categories):
        """显示所有板块及其子版块信息"""
        if not categories:
            print("未获取到任何板块信息")
            return
        
        print("\n" + "="*80)
        print(f"葫芦侠论坛所有板块及子版块信息 (共 {len(categories)} 个板块)")
        print("="*80)
        
        for i, category in enumerate(categories, 1):
            print(f"\n【{i}】 {category['板块名称']} (ID: {category['板块ID']})")
            print("-"*80)
            
            # 显示子版块信息
            if category['子版块']:
                print("子版块列表:")
                for j, sub in enumerate(category['子版块'], 1):
                    print(f"  {j}. {sub['名称']} (ID: {sub['ID']})")
            else:
                print("该板块没有子版块")
            
            print("-"*80)
        
        print("\n" + "="*80)


if __name__ == "__main__":
    crawler = HuluxiaCrawler()
    categories = crawler.get_categories()
    
    # 显示所有板块及其子版块
    crawler.display_all_categories_with_subcategories(categories)
    logging.info("板块信息获取完成") 