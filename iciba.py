import json
import re
import requests
from typing import Optional, Dict, Any


def query_word(word: str) -> Dict[str, Any]:
    url = f"https://www.iciba.com/word?w={word}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
    if not match:
        raise ValueError("Failed to find word data on the page")
    
    data = json.loads(match.group(1))
    word_info = data.get("props", {}).get("pageProps", {}).get("initialReduxState", {}).get("word", {}).get("wordInfo", {})
    
    if not word_info:
        raise ValueError(f"Word '{word}' not found")
    
    return _parse_word_info(word_info)


def _parse_word_info(word_info: Dict) -> Dict[str, Any]:
    result = {
        "word": word_info.get("baesInfo", {}).get("word_name", ""),
        "exchanges": word_info.get("exchanges", []),
    }
    
    # 检查是否为多单词短语（翻译结果）
    translate_result = word_info.get("baesInfo", {}).get("translate_result", "")
    translate_type = word_info.get("baesInfo", {}).get("translate_type", 0)
    
    # 如果是短语翻译（translate_type == 2），优先使用翻译结果
    if translate_type == 2 and translate_result:
        result["is_phrase"] = True
        result["translation"] = translate_result
        result["from_language"] = word_info.get("baesInfo", {}).get("from", "")
        result["to_language"] = word_info.get("baesInfo", {}).get("to", "")
    else:
        # 单个单词的解析逻辑
        result["is_phrase"] = False
        
        symbols = word_info.get("baesInfo", {}).get("symbols", [])
        if symbols:
            symbol = symbols[0]
            result["symbols"] = {
                "word_symbol": symbol.get("word_symbol", ""),
                "ph_en": symbol.get("ph_en", ""),
                "ph_am": symbol.get("ph_am", ""),
                "ph_en_mp3": symbol.get("ph_en_mp3", ""),
                "ph_am_mp3": symbol.get("ph_am_mp3", ""),
                "ph_tts_mp3": symbol.get("ph_tts_mp3", ""),
                "parts": symbol.get("parts", []),
            }
            
            from_symbols_mean = symbol.get("fromSymbolsMean", [])
            if from_symbols_mean:
                result["symbols"]["from_symbols_mean"] = from_symbols_mean
    
    sentences = word_info.get("new_sentence", [{}])[0].get("sentences", [])
    result["sentences"] = [
        {
            "en": s.get("en", ""),
            "cn": s.get("cn", ""),
            "from": s.get("from", ""),
            "ttsUrl": s.get("ttsUrl", ""),
        }
        for s in sentences
    ]
    
    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python iciba.py <word>", file=sys.stderr)
        sys.exit(1)

    word = sys.argv[1]
    try:
        result = query_word(word)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)