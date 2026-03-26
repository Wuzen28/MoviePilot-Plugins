import time
from typing import Any, List, Dict, Tuple, Optional
from app.log import logger
from app.plugins import _PluginBase

class PTQuizPro(_PluginBase):
    # 1. 基础元数据声明 (系统识别插件的关键)
    plugin_name = "彩虹岛 AI 答题助手"
    plugin_desc = "【诊断模式】用于验证插件加载协议是否正常"
    plugin_icon = "https://ptchdbits.co/favicon.ico"
    plugin_version = "1.0.0"
    plugin_author = "wuzen"
    
    # 2. 内部配置属性初始化
    _enabled = False

    def init_plugin(self, config: dict = None):
        """
        核心生命周期：插件初始化
        如果安装成功，你会在日志中看到这行输出
        """
        logger.info("【PTQuizPro】正在尝试初始化插件...")
        if config:
            self._enabled = config.get("enabled", False)
        logger.info(f"【PTQuizPro】初始化完成，当前状态: {self._enabled}")

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        核心生命周期：配置 UI 渲染
        如果此方法报错或格式不对，配置页面会显示“无配置项”
        """
        logger.info("【PTQuizPro】正在加载配置表单...")
        form_content = [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {'cols': 12},
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '验证模式：启用插件',
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
        default_config = {
            "enabled": False
        }
        return form_content, default_config

    def get_page(self) -> List[dict]:
        """
        核心生命周期：详情页渲染
        """
        return [
            {
                'component': 'div',
                'props': {'class': 'text-center pa-4'},
                'text': '诊断模式运行中，如果看到此文字，说明插件加载协议完全正常。'
            }
        ]

    def stop_service(self):
        """
        核心生命周期：停止服务
        """
        logger.info("【PTQuizPro】插件服务已停止")

    def get_state(self) -> str:
        """
        返回插件运行状态描述
        """
        return "运行中" if self._enabled else "已停止"
