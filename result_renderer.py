"""词典结果内容渲染器（P2-5）。

职责：决定「查到的数据长什么样」。只负责把 data 渲染成控件并放入
给定的容器 frame；不依赖 DictionaryApp 其它逻辑。窗口级行为
（canvas 尺寸、状态记录）仍留在 UI 层；换行高度感知收口在本类内部。
"""
from tkinter import Label, Frame, Button
from ui_constants import COLORS, FONTS, PAD
from audio_player import play_audio


class ResultRenderer:
    """把一条词典/LLM 结果渲染进目标 frame。

    依赖注入（避免反向持有整个 App）：
      frame:          渲染目标父容器。
      get_frame_width: 返回当前可用的逻辑宽度，供初始换行计算兜底。

    动态换行管理收口在此：渲染时登记需要随窗口宽重排的 label，
    由 UI 在画布尺寸变化时调用 update_wraplength() 统一刷新。
    """

    def __init__(self, frame, get_frame_width):
        self.frame = frame
        self._width = get_frame_width
        self._wrap_labels = []

    def _text_wraplength(self):
        """计算文本换行像素宽度（优先取容器实测宽，不足回退窗口逻辑宽）。"""
        w = self.frame.winfo_width()
        if w < 100:
            w = self._width() - 40
        return w - 20

    def update_wraplength(self, frame_width):
        """画布宽度变化时，刷新登记的 label 换行宽度。

        frame_width: 画布对结果区的实际像素宽度（含边距余量）。
        """
        plain_wrap = max(120, frame_width - 20)
        sentence_wrap = max(90, frame_width - 50)
        for label, label_type in self._wrap_labels:
            label.config(wraplength=sentence_wrap if label_type == "sentence" else plain_wrap)

    def render(self, data):
        self._wrap_labels = []
        word = data.get("word", "")
        result_type = data.get("result_type", "")
        is_phrase = data.get("is_phrase", False)

        frame = self.frame
        text_wraplength = self._text_wraplength()
        is_long_text = len(word) > 80

        if is_long_text:
            word_label = Label(frame, text=word,
                               font=FONTS["italic"], fg=COLORS["text_secondary"],
                               wraplength=text_wraplength, justify=LEFT)
            word_label.pack(anchor=W, pady=(0, PAD["pad_md"]))
            sep = Frame(frame, height=2, bg=COLORS["separator"])
            sep.pack(fill=X, pady=(0, PAD["pad_md"]))
        elif is_phrase:
            word_label = Label(frame, text=word,
                               font=FONTS["heading"], wraplength=text_wraplength, justify=LEFT)
            word_label.pack(anchor=W, pady=(0, PAD["pad_md"]))
        else:
            word_label = Label(frame, text=word, font=FONTS["title"])
            word_label.pack(pady=(0, PAD["pad_md"]))

        self._wrap_labels.append((word_label, "sentence"))

        # 检查是否为多单词短语
        if is_phrase:
            # 显示短语翻译结果
            translation = data.get("translation", "")
            from_lang = data.get("from_language", "")
            to_lang = data.get("to_language", "")
            suggestion = data.get("suggestion", "")

            if translation:
                translation_frame = Frame(frame)
                translation_frame.pack(fill=X, pady=PAD["pad_md"])

                if result_type == "phrase_translation":
                    Label(translation_frame, text="翻译:", font=FONTS["label_bold"]).pack(anchor=W)
                elif result_type == "llm_translation":
                    Label(translation_frame, text="AI 翻译:", font=FONTS["label_bold"], fg=COLORS["primary"]).pack(anchor=W)
                elif result_type == "keyword_detection":
                    Label(translation_frame, text="提示:", font=FONTS["label_bold"], fg=COLORS["warning"]).pack(anchor=W)

                trans_label = Label(translation_frame, text=translation,
                                    font=FONTS["body"], fg=COLORS["text_primary"],
                                    wraplength=text_wraplength, justify=LEFT)
                trans_label.pack(fill=X, anchor=W)
                self._wrap_labels.append((trans_label, "sentence"))

                if from_lang and to_lang:
                    lang_label = Label(translation_frame, text=f"{from_lang} → {to_lang}",
                                       font=FONTS["small"], fg=COLORS["text_secondary"])
                    lang_label.pack(anchor=W)

                if suggestion:
                    suggest_label = Label(translation_frame, text=suggestion,
                                          font=FONTS["label"], fg=COLORS["primary"],
                                          wraplength=text_wraplength, justify=LEFT)
                    suggest_label.pack(anchor=W, pady=(PAD["pad_s"], 0))
        else:
            # 单个单词的显示逻辑
            symbols = data.get("symbols", {})

            if symbols:
                word_symbol = symbols.get("word_symbol", "")
                if word_symbol:
                    Label(frame, text=f"[{word_symbol}]", font=FONTS["body"]).pack()

                ph_en = symbols.get("ph_en", "")
                ph_am = symbols.get("ph_am", "")
                ph_en_mp3 = symbols.get("ph_en_mp3", "")
                ph_am_mp3 = symbols.get("ph_am_mp3", "")
                ph_tts_mp3 = symbols.get("ph_tts_mp3", "")

                if ph_en or ph_am:
                    pron_frame = Frame(frame)
                    pron_frame.pack(pady=PAD["pad_s"])

                    if ph_en:
                        en_btn = Button(pron_frame, text=f"EN: {ph_en}", fg=COLORS["primary"], cursor="hand2",
                                        font=FONTS["label"], command=lambda: play_audio(ph_en_mp3))
                        en_btn.pack(side=LEFT, padx=PAD["pad_s"])

                    if ph_am:
                        am_btn = Button(pron_frame, text=f"AM: {ph_am}", fg=COLORS["primary"], cursor="hand2",
                                        font=FONTS["label"], command=lambda: play_audio(ph_am_mp3))
                        am_btn.pack(side=LEFT, padx=PAD["pad_s"])

                    # 添加TTS播放按钮
                    if ph_tts_mp3:
                        tts_btn = Button(pron_frame, text="🔊 TTS", fg=COLORS["success_text"], cursor="hand2",
                                         font=FONTS["label"], command=lambda: play_audio(ph_tts_mp3))
                        tts_btn.pack(side=LEFT, padx=PAD["pad_s"])

                parts = symbols.get("parts", [])
                if parts:
                    meanings_frame = Frame(frame)
                    meanings_frame.pack(fill=X, pady=PAD["pad_md"])

                    Label(meanings_frame, text="Meanings:", font=FONTS["label_bold"]).pack(anchor=W)

                    for part in parts:
                        part_name = part.get("part", "")
                        means = part.get("means", [])

                        if part_name and means:
                            part_label = Label(meanings_frame, text=f"{part_name}:",
                                               font=FONTS["label_bold"], fg=COLORS["text_primary"])
                            part_label.pack(anchor=W, pady=(PAD["pad_s"], 0))

                            means_text = ", ".join(means[:10])
                            mean_label = Label(meanings_frame, text=means_text,
                                               font=FONTS["small"], fg=COLORS["text_secondary"],
                                               wraplength=text_wraplength, justify=LEFT)
                            mean_label.pack(anchor=W, padx=(PAD["pad_md"], 0))

        # 显示例句（如果有）
        sentences = data.get("sentences", [])
        if sentences and not is_long_text:
            sentences_frame = Frame(frame)
            sentences_frame.pack(fill=X, pady=PAD["pad_md"])

            Label(sentences_frame, text="例句:", font=FONTS["label_bold"]).pack(anchor=W)

            for i, sentence in enumerate(sentences[:5]):
                en_text = sentence.get("en", "")
                cn_text = sentence.get("cn", "")
                tts_url = sentence.get("ttsUrl", "")

                if en_text and cn_text:
                    sentence_frame = Frame(sentences_frame)
                    sentence_frame.pack(fill=X, pady=PAD["pad_s"])

                    en_frame = Frame(sentence_frame)
                    en_frame.pack(fill=X, anchor=W)

                    if tts_url:
                        play_btn = Button(en_frame, text="🔊", fg=COLORS["success_text"], cursor="hand2",
                                          font=FONTS["small"], width=1, height=1,
                                          command=lambda url=tts_url: play_audio(url))
                        play_btn.pack(side=LEFT, padx=(0, PAD["pad_s"]))

                    en_label = Label(en_frame, text=f"{i+1}. {en_text}",
                                     font=FONTS["label"], fg=COLORS["text_primary"],
                                     wraplength=text_wraplength, justify=LEFT)
                    en_label.pack(side=LEFT, anchor=W)
                    self._wrap_labels.append((en_label, "sentence"))

                    cn_label = Label(sentence_frame, text=f"   {cn_text}",
                                     font=FONTS["small"], fg=COLORS["text_secondary"],
                                     wraplength=text_wraplength, justify=LEFT)
                    cn_label.pack(anchor=W, padx=(PAD["indent"], 0))
                    self._wrap_labels.append((cn_label, "sentence"))