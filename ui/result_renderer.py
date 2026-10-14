"""词典结果内容渲染器。

职责：决定「查到的数据长什么样」，把 data 渲染成控件放进给定 frame。
文本一律用只读 SelectableText 承载，支持鼠标划选复制；其按容器宽度
自动 word-warp 并把高度贴合内容。窗口级行为与换行登记不再由本类负责。
"""
from tkinter import Label, Frame, Button, LEFT, W, X
from ui.ui_constants import COLORS, FONTS, PAD
from ui.selectable_text import SelectableText
from services.audio_player import play_audio


class ResultRenderer:
    """把一条词典/LLM 结果渲染进目标 frame。"""

    def __init__(self, frame, get_frame_width):
        self.frame = frame
        self._width = get_frame_width

    def _text(self, master, text, font, fg, pad=6):
        """返回一个只读可选中文本控件（高度贴合、随容器换行）。"""
        return SelectableText(master, text, font=font, fg=fg, bg=None, pad=pad)

    def update_wraplength(self, frame_width):
        """兼容旧回调（换行现由 SelectableText 自动处理）。"""
        return

    def render(self, data):
        word = data.get("word", "")
        result_type = data.get("result_type", "")
        is_phrase = data.get("is_phrase", False)

        frame = self.frame
        is_long_text = len(word) > 80

        if is_long_text:
            self._text(frame, word, FONTS["italic"], COLORS["text_secondary"]).pack(
                anchor=W, pady=(0, PAD["pad_md"]))
            Frame(frame, height=2, bg=COLORS["separator"]).pack(fill=X, pady=(0, PAD["pad_md"]))
        elif is_phrase:
            self._text(frame, word, FONTS["heading"], COLORS["text_primary"]).pack(
                anchor=W, pady=(0, PAD["pad_md"]))
        else:
            self._text(frame, word, FONTS["title"], COLORS["text_primary"]).pack(
                pady=(0, PAD["pad_md"]))

        if is_phrase:
            self._render_translation(frame, data, result_type)
        else:
            self._render_symbols(frame, data)

        sentences = data.get("sentences", [])
        if sentences and not is_long_text:
            self._render_sentences(frame, sentences)

    # ---------- 各区块 ----------
    def _render_translation(self, frame, data, result_type):
        translation = data.get("translation", "")
        from_lang = data.get("from_language", "")
        to_lang = data.get("to_language", "")
        suggestion = data.get("suggestion", "")

        if not translation:
            return
        translation_frame = Frame(frame)
        translation_frame.pack(fill=X, pady=PAD["pad_md"])

        if result_type == "phrase_translation":
            Label(translation_frame, text="翻译:", font=FONTS["label_bold"]).pack(anchor=W)
        elif result_type == "llm_translation":
            Label(translation_frame, text="AI 翻译:", font=FONTS["label_bold"],
                  fg=COLORS["primary"]).pack(anchor=W)
        elif result_type == "keyword_detection":
            Label(translation_frame, text="提示:", font=FONTS["label_bold"],
                  fg=COLORS["warning"]).pack(anchor=W)

        trans_label = self._text(translation_frame, translation, FONTS["body"],
                                 COLORS["text_primary"])
        trans_label.pack(fill=X, anchor=W)

        if from_lang and to_lang:
            Label(translation_frame,
                  text=f"{from_lang} → {to_lang}",
                  font=FONTS["small"], fg=COLORS["text_secondary"]).pack(anchor=W)

        if suggestion:
            self._text(translation_frame, suggestion, FONTS["label"],
                       COLORS["primary"]).pack(anchor=W, pady=(PAD["pad_s"], 0))

    def _render_symbols(self, frame, data):
        symbols = data.get("symbols", {})
        if not symbols:
            return

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
                Button(pron_frame, text=f"EN: {ph_en}", fg=COLORS["primary"], cursor="hand2",
                       font=FONTS["label"],
                       command=lambda: play_audio(ph_en_mp3)).pack(side=LEFT, padx=PAD["pad_s"])
            if ph_am:
                Button(pron_frame, text=f"AM: {ph_am}", fg=COLORS["primary"], cursor="hand2",
                       font=FONTS["label"],
                       command=lambda: play_audio(ph_am_mp3)).pack(side=LEFT, padx=PAD["pad_s"])
            if ph_tts_mp3:
                Button(pron_frame, text="🔊 TTS", fg=COLORS["success_text"], cursor="hand2",
                       font=FONTS["label"],
                       command=lambda: play_audio(ph_tts_mp3)).pack(side=LEFT, padx=PAD["pad_s"])

        parts = symbols.get("parts", [])
        if parts:
            meanings_frame = Frame(frame)
            meanings_frame.pack(fill=X, pady=PAD["pad_md"])
            Label(meanings_frame, text="Meanings:", font=FONTS["label_bold"]).pack(anchor=W)
            for part in parts:
                part_name = part.get("part", "")
                means = part.get("means", [])
                if part_name and means:
                    Label(meanings_frame, text=f"{part_name}:",
                          font=FONTS["label_bold"], fg=COLORS["text_primary"]).pack(
                        anchor=W, pady=(PAD["pad_s"], 0))
                    means_text = ", ".join(means[:10])
                    self._text(meanings_frame, means_text, FONTS["small"],
                               COLORS["text_secondary"]).pack(anchor=W, padx=(PAD["pad_md"], 0))

    def _render_sentences(self, frame, sentences):
        sentences_frame = Frame(frame)
        sentences_frame.pack(fill=X, pady=PAD["pad_md"])
        Label(sentences_frame, text="例句:", font=FONTS["label_bold"]).pack(anchor=W)

        for i, sentence in enumerate(sentences[:5]):
            en_text = sentence.get("en", "")
            cn_text = sentence.get("cn", "")
            tts_url = sentence.get("ttsUrl", "")
            if not (en_text and cn_text):
                continue

            row = Frame(sentences_frame)
            row.pack(fill=X, pady=PAD["pad_s"])

            top = Frame(row)
            top.pack(fill=X, anchor=W)
            if tts_url:
                Button(top, text="🔊", fg=COLORS["success_text"], cursor="hand2",
                       font=FONTS["small"], width=1, height=1,
                       command=lambda url=tts_url: play_audio(url)).pack(
                    side=LEFT, padx=(0, PAD["pad_s"]))
            self._text(top, f"{i+1}. {en_text}", FONTS["label"], COLORS["text_primary"]).pack(
                fill=X, side=LEFT, anchor=W)

            self._text(row, f"   {cn_text}", FONTS["small"], COLORS["text_secondary"]).pack(
                fill=X, anchor=W, padx=(PAD["indent"], 0))