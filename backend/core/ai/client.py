"""OpenAI 协议客户端，支持流式/非流式调用"""

import queue
import threading


class AIClient:
    """AI 客户端，基于 OpenAI 协议"""

    def __init__(self, config):
        """
        初始化客户端
        :param config: 配置字典，包含 api_key, base_url, model, temperature, max_tokens, system_prompt_prefix
        """
        self.config = config
        self._client = None

    def _get_client(self):
        """懒加载 openai 客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError("请安装 openai 库: pip install openai")

            self._client = OpenAI(
                api_key=self.config.get('api_key', ''),
                base_url=self.config.get('base_url') or 'https://api.openai.com/v1'
            )
        return self._client

    def chat_completion(self, messages, stream=True):
        """
        发送聊天请求
        :param messages: 消息列表 [{'role': 'system'|'user'|'assistant', 'content': str}]
        :param stream: 是否流式返回
        :return: 流式时返回生成器，非流式时返回完整文本
        """
        client = self._get_client()

        kwargs = {
            'model': self.config.get('model') or 'gpt-3.5-turbo',
            'messages': messages,
            'temperature': float(self.config.get('temperature', 0.7)),
            'stream': stream,
        }
        max_tokens = self.config.get('max_tokens')
        if max_tokens:
            kwargs['max_tokens'] = int(max_tokens)

        response = client.chat.completions.create(**kwargs)

        if stream:
            return self._iter_stream(response)
        else:
            return response.choices[0].message.content if response.choices else ''

    def _iter_stream(self, response):
        """迭代流式响应，逐 chunk 返回文本"""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def chat_completion_async(self, messages, chunk_queue, stream=True):
        """
        异步聊天请求（后台线程），将 chunk 放入队列
        :param messages: 消息列表
        :param chunk_queue: queue.Queue，用于传递 chunk 到 UI 线程
        :param stream: 是否流式
        """
        try:
            if stream:
                for chunk_text in self.chat_completion(messages, stream=True):
                    chunk_queue.put(('chunk', chunk_text))
                chunk_queue.put(('done', None))
            else:
                result = self.chat_completion(messages, stream=False)
                chunk_queue.put(('result', result))
                chunk_queue.put(('done', None))
        except Exception as e:
            chunk_queue.put(('error', str(e)))

    def test_connection(self):
        """
        测试 API 连接是否有效
        :return: (success: bool, message: str)
        """
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.config.get('model') or 'gpt-3.5-turbo',
                messages=[{'role': 'user', 'content': 'Hi'}],
                max_tokens=5,
                stream=False
            )
            if response.choices:
                return True, "连接成功"
            return False, "连接失败：无响应内容"
        except ImportError as e:
            return False, str(e)
        except Exception as e:
            return False, f"连接失败：{str(e)}"

    @staticmethod
    def list_models(config):
        """
        调用 /v1/models 接口获取可用模型列表
        :param config: 配置字典，包含 api_key, base_url
        :return: (success: bool, models: list[str] 或 error_message: str)
        """
        try:
            from openai import OpenAI
        except ImportError:
            return False, "请安装 openai 库: pip install openai"

        try:
            client = OpenAI(
                api_key=config.get('api_key', ''),
                base_url=config.get('base_url') or 'https://api.openai.com/v1'
            )
            models_page = client.models.list()
            model_ids = [m.id for m in models_page.data]
            # 按 id 排序，方便查找
            model_ids.sort()
            return True, model_ids
        except Exception as e:
            return False, f"获取模型列表失败: {str(e)}"
