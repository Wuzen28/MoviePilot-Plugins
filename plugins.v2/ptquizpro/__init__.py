import re
import requests
from bs4 import BeautifulSoup
from typing import Any, List, Dict, Tuple, Optional
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase

class PTQuizPro(_PluginBase):
    # 插件元数据
    plugin_name = "彩虹岛 AI 答题助手"
    plugin_desc = "利用 AI 识别并提交答案。"
    plugin_icon = "https://ptchdbits.co/favicon.ico"
    plugin_version = "1.0.2"
    plugin_author = "wuzen"
    plugin_order = 100
    auth_level = 2

    # 私有配置属性
    _enabled = False
    _onlyonce = False
    _notify = False
    _cron = "0 9 * * *"
    _proxy = ""
    _api_key = ""
    _api_url = "https://openrouter.ai/api/v1/chat/completions"
    _model = "google/gemini-2.0-flash-001"
    _cookie = ""

    def init_plugin(self, config: dict = None):
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

        if self._enabled and self._onlyonce:
            self.info("检测到立即运行指令，开始执行答题任务...")
            self.solve_quiz()
            config['onlyonce'] = False
            self.update_config(config)

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._cron:
            return [{
                "id": "PTQuizProService",
                "name": "彩虹岛自动答题服务",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self.solve_quiz,
                "kwargs": {}
            }]
        return []

    def get_state(self) -> bool:
        """
        实现抽象方法：返回插件启用状态
        """
        return self._enabled

    def get_api(self) -> List[Dict[str, Any]]:
        """
        实现抽象方法：暴露 API 接口（此处返回空列表）
        """
        return []

    def solve_quiz(self):
        if not self._cookie:
            self.error("未配置站点 Cookie")
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
            res = requests.get(site_url, headers=headers, proxies=proxies, timeout=20)
            res.encoding = res.apparent_encoding
            
            if res.status_code != 200:
                self.error(f"访问站点失败: HTTP {res.status_code}")
                return

            soup = BeautifulSoup(res.text, 'html.parser')
            q_td = soup.find('td', class_='text', string=re.compile(r'请问|单选|多选'))
            if not q_td or "识别" in q_td.text:
                self.info("未发现待回答题目。")
                return

            question_text = q_td.get_text(strip=True)
            self.info(f"获取题目成功: {question_text}")
            
            options_row = q_td.find_parent('tr').find_next_sibling('tr')
            options_td = options_row.find('td', class_='text')
            inputs = options_td.find_all('input')
            
            options_list = []
            for inp in inputs:
                label = inp.next_sibling
                text = label.strip() if label and isinstance(label, str) else ""
                options_list.append(text)

            ans_indices = self._call_ai(question_text, options_list, proxies)
            
            if not ans_indices:
                self.error("AI 未能返回有效答案")
                return

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

            submit_res = requests.post(site_url, headers=headers, data=post_data, proxies=proxies, timeout=20)
            
            if "回答正确" in submit_res.text or "succeed" in submit_res.text.lower():
                status_msg = f"✅ 答题成功！
题目: {question_text}
AI 选择: {ans_indices}"
                self.info(status_msg)
            else:
                status_msg = f"❌ 提交结果未知，请检查站点页面。"
                self.warn(status_msg)
                
            if self._notify:
                self.post_message(title="PT 答题助手", text=status_msg)

        except Exception as e:
            self.error(f"运行异常: {str(e)}")

    def _call_ai(self, question, options, proxies):
        opts_str = "
".join([f"[{i+1}] {text}" for i, text in enumerate(options)])
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "你是一个百科专家，精通 PT 站规则。只输出正确选项的数字编号，逗号分隔，严禁解释。"},
                {"role": "user", "content": f"题目: {question}
选项:
{opts_str}"}
            ],
            "temperature": 0.1
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        try:
            response = requests.post(self._api_url, json=payload, headers=headers, proxies=proxies, timeout=30)
            res_json = response.json()
            content = res_json['choices'][0]['message']['content']
            return re.findall(r'\d+', content)
        except Exception as e:
            self.error(f"AI 调用失败: {str(e)}")
            return None

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                'component': 'VForm',
                'content': [
                    {'component': 'VRow', 'content': [
                        {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VSwitch', 'props': {'model': 'enabled', 'label': '启用插件'}}]},
                        {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VSwitch', 'props': {'model': 'onlyonce', 'label': '立即运行一次'}}]},
                        {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VSwitch', 'props': {'model': 'notify', 'label': '开启通知'}}]}
                    ]},
                    {'component': 'VRow', 'content': [
                        {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [{'component': 'VCronField', 'props': {'model': 'cron', 'label': '执行周期 (Cron)'}}]},
                        {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [{'component': 'VTextField', 'props': {'model': 'proxy', 'label': 'HTTP 代理'}}]}
                    ]},
                    {'component': 'VRow', 'content': [
                        {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [{'component': 'VTextField', 'props': {'model': 'api_url', 'label': 'API URL'}}]},
                        {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [{'component': 'VTextField', 'props': {'model': 'model', 'label': 'AI 模型'}}]}
                    ]},
                    {'component': 'VCol', 'props': {'cols': 12}, 'content': [{'component': 'VTextField', 'props': {'model': 'api_key', 'label': 'API KEY', 'type': 'password'}}]},
                    {'component': 'VCol', 'props': {'cols': 12}, 'content': [{'component': 'VTextarea', 'props': {'model': 'site_cookie', 'label': '站点 Cookie', 'rows': 3}}]}
                ]
            }
        ], {
            "enabled": False, "onlyonce": False, "notify": True, "cron": "0 9 * * *",
            "proxy": "", "api_url": "https://openrouter.ai/api/v1/chat/completions",
            "model": "google/gemini-2.0-flash-001", "api_key": "", "site_cookie": ""
        }

    def get_page(self) -> List[dict]:
        return [{'component': 'div', 'props': {'class': 'text-center pa-4'}, 'text': '请查看系统日志。'}]

    def stop_service(self):
        pass
