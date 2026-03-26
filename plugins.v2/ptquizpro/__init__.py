import logging

# 使用系统标准的 logging，避免依赖 app.log
logger = logging.getLogger("PTQuizPro")

class PTQuizPro:
    # 基础元数据属性
    plugin_name = "彩虹岛 AI 答题助手"
    plugin_desc = "极致兼容性测试"
    plugin_version = "1.0.3"
    
    def __init__(self, *args, **kwargs):
        pass

    def init_plugin(self, config: dict = None):
        logger.info("PTQuizPro: 插件已加载")

    def get_form(self):
        return [], {}

    def get_page(self):
        return []

    def get_service(self):
        return []
