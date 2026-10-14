"""LLM 多轮对话控制器（P2-4）。

职责：管理对话历史、系统提示词、发起异步请求，并在结果就绪时
通过回调交回 UI 层渲染。渲染本身不在此处 —— 本类只持有对话
「状态」与「请求」逻辑，让 UI 只负责展示。
"""
import threading


class LLMConversation:
    """封装一次多轮 LLM 对话的状态机与异步查询调度。

    history 为 [{role, content}, ...]。业务线程不直接写 history，
    所有写入均发生在主线程（start/ask/append_assistant），后台工作
    线程仅读取 history 传给 LLM，避免渲染与写入并发冲突。
    """

    def __init__(self, system_prompt, chat, on_answer, on_error):
        """
        system_prompt: 系统提示词。
        chat(history, system_prompt) -> str: 同步返回回答文本的函数。
        on_answer(answer): 主线程接收回答（由外部保证 after 转主线程）。
        on_error(exc): 主线程接收异常。
        """
        self.system_prompt = system_prompt
        self._chat = chat
        self._on_answer = on_answer
        self._on_error = on_error
        self.history = []
        self._busy = False

    @property
    def busy(self) -> bool:
        """是否有请求正在进行（用于追问防抖）。"""
        return self._busy

    def start(self, word):
        """以 word 作为首条用户消息开启全新对话。"""
        self.history = []
        self._append_user(word)
        self._respond()

    def ask(self, question) -> bool:
        """追加一条追问；当下一次请求进行中则忽略，返回是否真正发起。"""
        if self._busy:
            return False
        question = question.strip()
        if not question:
            return False
        self._append_user(question)
        self._respond()
        return True

    def append_assistant(self, content):
        """在对话末尾追加一条助手消息（由主线程在接收回答后调用）。"""
        self.history.append({"role": "assistant", "content": content})

    def latest_role(self):
        """最后一条消息的角色，供渲染判断是否展示 loading。"""
        return self.history[-1]["role"] if self.history else None

    def _append_user(self, text):
        self.history.append({"role": "user", "content": text})

    def _respond(self):
        self._busy = True
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        """后台线程：读取 history 调用 LLM，不修改 history。"""
        try:
            answer = self._chat(self.history, system_prompt=self.system_prompt).strip()
        except Exception as ex:
            self._done()
            self._on_error(ex)
            return
        self._done()
        self._on_answer(answer)

    def _done(self):
        self._busy = False