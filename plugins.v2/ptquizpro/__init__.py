import re
import requests
from bs4 import BeautifulSoup
from typing import Any, List, Dict, Tuple, Optional
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase

class PTQuizPro(_PluginBase):
    # 插件元数据属性
    plugin_name = "彩虹岛 AI 答题助手"
    plugin_desc = "自动访问彩虹岛答题页面，利用 AI 识别并提交答案。"
    plugin_icon = "https://ptchdbits.co/favicon.ico"
    plugin_version = "1.0.1"
    plugin_author = "wuzen"
    plugin_order = 100
    auth_level = 2

    # 私有配置属性
    _enabled = False
    _onlyonce = False
    _notify = False
    _cron = None
    _proxy = None
    _api_key = None
    _api_url = None
    _model = None
    _cookie = None

    def init_plugin(self, config: dict = None):
        """
        初始化插件配置
        """
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._notify = config.get("notify")
            self._cron = config.get("cron")
            self._proxy = config.get("proxy")
            self._api_key = config.get("api_key")
            self._api_url = config.get("api_url")
            self._model = config.get("model")
            self._cookie = config.get("site_cookie")

        # 立即运行一次逻辑
        if self._enabled and self._onlyonce:
            self.info("检测到立即运行指令，开始执行答题任务...")
            self.solve_quiz()
            # 运行后关闭一次性开关并更新配置
            new_config = config.copy()
            new_config["onlyonce"] = False
            self.update_config(new_config)

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件定时服务
        """
        if self._enabled and self._cron:
            try:
                return [
                    {
                        "id": "PTQuizProService",
                        "name": "彩虹岛自动答题服务",
                        "trigger": CronTrigger.from_crontab(self._cron),
                        "func": self.solve_quiz,
                        "kwargs": {}
                    }
                ]
            except Exception as e:
                self.error(f"Cron 表达式解析失败: {str(e)}")
        return []

    def solve_quiz(self):
        """
        核心答题逻辑
        """
        if not self._cookie:
            self.error("未配置站点 Cookie，任务停止")
            return

        site_url = "https://ptchdbits.co/bakatest.php"
        headers = {
            "User-Agent": settings.USER_AGENT,
            "Cookie": self._cookie,
            "Referer": "https://ptchdbits.co/"
        }
        
        proxies = {
            "http": self._proxy,
            "https": self._proxy
        } if self._proxy else None
        
        try:
            # 1. 抓取题目页面
            res = requests.get(site_url, headers=headers, proxies=proxies, timeout=20)
            res.encoding = res.apparent_encoding
            
            if res.status_code != 200:
                self.error(f"访问站点失败: HTTP {res.status_code}")
                return

            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 2. 识别题目 (匹配 NexusPHP 答题页面的特征)
            q_td = soup.find('td', class_='text', string=re.compile(r'请问|单选|多选'))
            if not q_td or "识别" in q_td.text:
                self.info("未发现待回答题目，可能今日已完成。")
                return

            question_text = q_td.get_text(strip=True)
            self.info(f"获取题目成功: {question_text}")
            
            # 3. 提取选项
            options_row = q_td.find_parent('tr').find_next_sibling('tr')
            options_td = options_row.find('td', class_='text')
            inputs = options_td.find_all('input')
            
            options_list = []
            for inp in inputs:
                label = inp.next_sibling
                text = label.strip() if label and isinstance(label, str) else ""
                options_list.append(text)

            # 4. 调用 AI 解析答案
            ans_indices = self._call_ai(question_text, options_list, proxies)
            
            if not ans_indices:
                self.error("AI 未能返回任何有效答案编号")
                return

            # 5. 构造提交表单
            post_data = {}
            for idx_str in ans_indices:
                idx = int(idx_str) - 1
                if 0 <= idx < len(inputs):
                    name = inputs[idx].get('name')
                    val = inputs[idx].get('value')
                    if name in post_data:
                        if not isinstance(post_data[name], list):
                            post_data[name] = [post_data[name]]
                        post_data[name].append(val)
                    else:
                        post_data[name] = val

            # 6. 提交答案
            submit_res = requests.post(site_url, headers=headers, data=post_data, proxies=proxies, timeout=20)
            
            if "回答正确" in submit_res.text or "succeed" in submit_res.text.lower():
                status_msg = f"✅ 答题成功！\n题目: {question_text}\nAI 选择: {ans_indices}"
                self.info(status_msg)
            else:
                status_msg = f"❌ 提交结果未知，请检查站点页面反馈。"
                self.warn(status_msg)
                
            if self._notify:
                self.post_message(title="PT 答题助手", text=status_msg)

        except Exception as e:
            err_msg = f"💥 运行异常: {str(e)}"
            self.error(err_msg)
            if self._notify:
                self.post_message(title="PT 答题助手", text=err_msg)

    def _call_ai(self, question: str, options: List[str], proxies: Optional[Dict]):
        """
        调用 AI 接口
        """
        opts_str = "\n".join([f"[{i+1}] {text}" for i, text in enumerate(options)])
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个百科专家，精通 PT 站规则。只输出正确选项的数字编号，逗号分隔，严禁解释。"
                },
                {
                    "role": "user",
                    "content": f"题目: {question}\n选项:\n{opts_str}"
                }
            ],
            "temperature": 0.1
        }
        
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(self._api_url, json=payload, headers=headers, proxies=proxies, timeout=30)
            res_json = response.json()
            content = res_json['choices'][0]['message']['content']
            return re.findall(r'\d+', content)
        except Exception as e:
            self.error(f"AI 调用失败: {str(e)}")
            return None

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                {'component': 'VSwitch', 'props': {'model': 'enabled', 'label': '启用插件'}}
                            ]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                {'component': 'VSwitch', 'props': {'model': 'onlyonce', 'label': '立即运行一次'}}
                            ]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [
                                {'component': 'VSwitch', 'props': {'model': 'notify', 'label': '开启通知'}}
                            ]}
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [
                                {'component': 'VCronField', 'props': {'model': 'cron', 'label': '执行周期 (Cron)', 'placeholder': '0 9 * * *'}}
                            ]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [
                                {'component': 'VTextField', 'props': {'model': 'proxy', 'label': 'HTTP 代理', 'placeholder': 'http://127.0.0.1:7890'}}
                            ]}
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [
                                {'component': 'VTextField', 'props': {'model': 'api_url', 'label': 'API URL'}}
                            ]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [
                                {'component': 'VTextField', 'props': {'model': 'model', 'label': 'AI 模型'}}
                            ]}
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {'component': 'VCol', 'props': {'cols': 12}, 'content': [
                                {'component': 'VTextField', 'props': {'model': 'api_key', 'label': 'API KEY', 'type': 'password'}}
                            ]}
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {'component': 'VCol', 'props': {'cols': 12}, 'content': [
                                {'component': 'VTextarea', 'props': {'model': 'site_cookie', 'label': '站点 Cookie', 'rows': 3}}
                            ]}
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "notify": True,
            "cron": "0 9 * * *",
            "proxy": "",
            "api_url": "https://openrouter.ai/api/v1/chat/completions",
            "model": "google/gemini-2.0-flash-001",
            "api_key": "",
            "site_cookie": ""
        }

    def get_page(self) -> List[dict]:
        """
        插件详情页
        """
        return [
            {
                'component': 'div',
                'props': {'class': 'text-center pa-4'},
                'text': '答题结果请查看 MoviePilot 系统日志。'
            }
        ]

    def stop_service(self):
        pass
