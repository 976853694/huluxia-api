from flask import Flask, render_template, jsonify, request
import requests
from urllib.parse import urljoin
import logging
from datetime import datetime

app = Flask(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("web_app.log"),
        logging.StreamHandler()
    ]
)

# 添加时间戳格式化过滤器
@app.template_filter('datetime')
def format_datetime(timestamp):
    """将时间戳转换为可读的日期时间格式"""
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return '未知时间'

@app.template_filter('format_content')
def format_content(content):
    """将帖子内容中的复杂格式转换为HTML"""
    if not content:
        return ""
    
    import re
    
    # 1. 处理<text>标签，并添加段落标签
    def process_text(match):
        text = match.group(1)
        if text.strip():  # 如果文本不为空
            return f'<p class="post-text">{text}</p>'
        return ''
    
    content = re.sub(r'<text>(.*?)</text>', process_text, content)
    
    # 2. 收集所有图片URL
    image_urls = []
    
    # 处理<image>标签中的图片URL
    def collect_image_from_tag(match):
        image_url = match.group(1).split(',')[0]
        image_urls.append(image_url)
        return ''  # 移除标签，后面会重新添加图片
    
    content = re.sub(r'<image>(.*?)</image>', collect_image_from_tag, content)
    
    # 处理@URL格式的图片
    def collect_image_from_url(match):
        url = match.group(1)
        image_urls.append(url)
        return ''  # 移除URL，后面会重新添加图片
    
    content = re.sub(r'@(http[s]?://\S+)', collect_image_from_url, content)
    
    # 3. 将换行符转换为HTML段落
    paragraphs = content.split('\n')
    content = ''.join([f'<p class="post-text">{p}</p>' for p in paragraphs if p.strip()])
    
    # 4. 将收集到的图片按每行3张的方式添加到内容后面，并支持Lightbox点击放大
    if image_urls:
        content += '<div class="post-image-gallery">'
        
        for i in range(0, len(image_urls), 3):
            content += '<div class="post-image-row">'
            # 获取当前行的图片（最多3张）
            row_images = image_urls[i:i+3]
            for j, img_url in enumerate(row_images):
                img_index = i + j + 1  # 图片索引从1开始
                content += f'''
                <div class="post-image-container">
                    <a href="{img_url}" data-lightbox="post-images" data-title="帖子图片 {img_index}">
                        <img src="{img_url}" alt="帖子图片" class="post-image">
                    </a>
                </div>
                '''
            content += '</div>'
        
        content += '</div>'
    
    return content

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
        # 帖子列表请求头
        self.post_headers = {
            'Connection': 'close',
            'Host': 'floor.huluxia.com',
            'Accept-Encoding': 'gzip',
            'User-Agent': 'okhttp/3.8.1',
            'Content-Type': 'application/json; charset=utf-8'
        }
        # 帖子详情请求头
        self.detail_headers = {
            'Connection': 'close',
            'Host': 'floor.huluxia.com',
            'Accept-Encoding': 'gzip',
            'User-Agent': 'okhttp/3.8.1',
            'Content-Type': 'application/json; charset=utf-8'
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
    
    def get_posts(self, cat_id, tag_id=0, count=20, sort_by=0):
        """获取特定板块的帖子列表
        
        参数:
            cat_id (int): 板块ID
            tag_id (int): 子版块ID，默认为0（全部）
            count (int): 每页显示的帖子数量，默认为20
            sort_by (int): 排序方式，默认为0
        """
        try:
            # 构建帖子列表接口URL
            url = f"{self.base_url}/post/list/ANDROID/4.1.8"
            params = {
                'platform': 2,
                'gkey': '000000',
                'app_version': '4.3.0.3',
                'versioncode': 20141494,
                'market_id': 'floor_web',
                'count': count,
                'cat_id': cat_id,
                'tag_id': tag_id,
                'sort_by': sort_by
            }
            
            logging.info(f"开始获取板块帖子列表: 板块ID={cat_id}, 子版块ID={tag_id}")
            
            response = requests.get(url, headers=self.post_headers, params=params, timeout=10)
            response.raise_for_status()
            
            # 解析JSON响应
            data = response.json()
            logging.info(f"成功获取板块帖子列表，状态消息: {data.get('msg', '')}")
            
            # 提取帖子数据
            posts = data.get('posts', [])
            more = data.get('more', 0)  # 是否有更多帖子
            
            # 整理帖子数据
            posts_data = []
            for post in posts:
                post_info = {
                    '帖子ID': post.get('postID', ''),
                    '标题': post.get('title', ''),
                    '内容': post.get('detail', ''),
                    '图片': post.get('images', []),
                    '点击数': post.get('hit', 0),
                    '评论数': post.get('commentCount', 0),
                    '创建时间': post.get('createTime', 0),
                    '活跃时间': post.get('activeTime', 0),
                    '是否精华': post.get('isGood', 0),
                }
                
                # 提取用户信息
                user = post.get('user', {})
                post_info['用户'] = {
                    '用户ID': user.get('userID', 0),
                    '昵称': user.get('nick', ''),
                    '头像': user.get('avatar', ''),
                    '性别': user.get('gender', 0),
                    '等级': user.get('level', 0),
                }
                
                posts_data.append(post_info)
            
            return {
                '帖子列表': posts_data,
                '是否有更多': more,
                '板块ID': cat_id,
                '子版块ID': tag_id,
            }
            
        except Exception as e:
            logging.error(f"获取板块帖子列表失败: {str(e)}")
            return {'帖子列表': [], '是否有更多': 0, '板块ID': cat_id, '子版块ID': tag_id}

    def get_post_detail(self, post_id, page_no=1, page_size=20):
        """获取帖子详细内容
        
        参数:
            post_id (int): 帖子ID
            page_no (int): 评论页码，默认为1
            page_size (int): 每页评论数量，默认为20
        """
        try:
            # 构建帖子详情接口URL
            url = f"{self.base_url}/post/detail/ANDROID/2.3"
            params = {
                'platform': 2,
                'gkey': '000000',
                'app_version': '4.0.1.7',
                'versioncode': 300,
                'market_id': 'tool_web',
                '_key': '',
                'device_code': '[d]c24a6dbd-5823-4c08-a559-19569c07c6fa',
                'post_id': post_id,
                'page_no': page_no,
                'page_size': page_size,
                'doc': 1
            }
            
            logging.info(f"开始获取帖子详情: 帖子ID={post_id}")
            
            response = requests.get(url, headers=self.detail_headers, params=params, timeout=10)
            response.raise_for_status()
            
            # 解析JSON响应
            data = response.json()
            
            # 从 post 对象中提取帖子详情数据
            post_data = data.get('post', {})
            
            # 保存原始帖子内容，不进行任何预处理
            content = post_data.get('detail', '') or post_data.get('description', '')
            
            post_detail = {
                '帖子ID': post_data.get('postID', ''),
                '标题': post_data.get('title', ''),
                '内容': content,  # 保存原始内容
                '图片': post_data.get('images', []),
                '点击数': post_data.get('hit', 0),
                '评论数': post_data.get('commentCount', 0),
                '创建时间': post_data.get('createTime', 0),
                '活跃时间': post_data.get('updateTime', 0) or post_data.get('createTime', 0),
                '是否精华': post_data.get('isGood', 0),
                '评论列表': data.get('comments', []),
                '是否有更多评论': len(data.get('comments', [])) >= page_size,
                '当前页码': page_no,
                '每页数量': page_size,
            }
            
            # 提取用户信息
            user = post_data.get('user', {})
            post_detail['用户'] = {
                '用户ID': user.get('userID', 0),
                '昵称': user.get('nick', ''),
                '头像': user.get('avatar', ''),
                '性别': user.get('gender', 0),
                '等级': user.get('level', 0),
            }
            
            return post_detail
            
        except Exception as e:
            logging.error(f"获取帖子详情失败: {str(e)}")
            return None

# 创建爬虫实例
crawler = HuluxiaCrawler()

@app.route('/')
def index():
    """首页，显示所有板块列表"""
    categories = crawler.get_categories()
    return render_template('index.html', categories=categories)

@app.route('/category/<int:category_id>')
def category_detail(category_id):
    """显示特定板块的详细信息"""
    categories = crawler.get_categories()
    
    # 查找目标板块
    target_category = None
    for category in categories:
        if str(category_id) == str(category['板块ID']):
            target_category = category
            break
    
    if not target_category:
        return render_template('error.html', message=f"未找到ID为 {category_id} 的板块")
    
    # 获取子版块ID参数
    tag_id = request.args.get('tag_id', 0, type=int)
    
    # 获取板块帖子列表
    posts_data = crawler.get_posts(category_id, tag_id)
    
    return render_template('category.html', category=target_category, posts=posts_data, current_tag_id=tag_id)

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    """显示帖子详细内容"""
    page_no = request.args.get('page', 1, type=int)
    page_size = request.args.get('size', 20, type=int)
    
    post_data = crawler.get_post_detail(post_id, page_no, page_size)
    
    if not post_data:
        return render_template('error.html', message=f"未找到ID为 {post_id} 的帖子")
    
    return render_template('post.html', post=post_data)

@app.route('/api/categories')
def api_categories():
    """API接口，返回所有板块信息的JSON数据"""
    categories = crawler.get_categories()
    return jsonify(categories)

@app.route('/api/category/<int:category_id>')
def api_category(category_id):
    """API接口，返回特定板块信息的JSON数据"""
    categories = crawler.get_categories()
    
    # 查找目标板块
    target_category = None
    for category in categories:
        if str(category_id) == str(category['板块ID']):
            target_category = category
            break
    
    if not target_category:
        return jsonify({"error": f"未找到ID为 {category_id} 的板块"}), 404
    
    return jsonify(target_category)

@app.route('/api/posts/<int:category_id>')
def api_posts(category_id):
    """API接口，返回特定板块帖子列表的JSON数据"""
    tag_id = request.args.get('tag_id', 0, type=int)
    count = request.args.get('count', 20, type=int)
    sort_by = request.args.get('sort_by', 0, type=int)
    
    posts_data = crawler.get_posts(category_id, tag_id, count, sort_by)
    return jsonify(posts_data)

@app.route('/api/post/<int:post_id>')
def api_post(post_id):
    """API接口，返回帖子详情的JSON数据"""
    page_no = request.args.get('page', 1, type=int)
    page_size = request.args.get('size', 20, type=int)
    
    post_data = crawler.get_post_detail(post_id, page_no, page_size)
    
    if not post_data:
        return jsonify({"error": f"未找到ID为 {post_id} 的帖子"}), 404
    
    return jsonify(post_data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 