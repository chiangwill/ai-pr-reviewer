"""
處理 AI 分析和程式碼審查建議生成的模組
"""
import json
import logging
import os

import httpx


class AIAnalyzer:

    def __init__(self, api_key=None, model="claude-3-haiku-20240307"):
        """
        初始化 AIAnalyzer

        Args:
            api_key (str, optional): AI API 密鑰，默認從環境變量獲取
            model (str, optional): 要使用的 AI 模型
        """
        self.api_key = api_key or os.environ.get("AI_API_KEY")
        if not self.api_key:
            raise ValueError("未提供 AI API 密鑰")

        self.model = model
        self.logger = logging.getLogger(__name__)

    async def analyze_code(self, xml_content, focus_areas=None, repo_name=None, pr_title=None, pr_description=None):
        """
        使用 AI 分析程式碼並生成審查建議

        Args:
            xml_content (str): 程式碼的 XML 表示
            focus_areas (list, optional): 審查重點領域列表
            repo_name (str, optional): 程式庫名稱
            pr_title (str, optional): PR 標題
            pr_description (str, optional): PR 描述

        Returns:
            dict: 包含審查建議的字典
        """
        try:
            # 構建提示詞
            prompt = self._build_prompt(xml_content, focus_areas, repo_name, pr_title, pr_description)

            # 調用 AI API
            self.logger.info("正在調用 AI API 進行程式碼分析")

            # 假設我們使用 Anthropic's Claude API
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post("https://api.anthropic.com/v1/messages",
                                             headers={
                                                 "x-api-key": self.api_key,
                                                 "anthropic-version": "2023-06-01",
                                                 "content-type": "application/json"
                                             },
                                             json={
                                                 "model": self.model,
                                                 "max_tokens": 4000,
                                                 "messages": [{
                                                     "role": "user",
                                                     "content": prompt
                                                 }],
                                                 "temperature": 0.3
                                             })

                if response.status_code != 200:
                    self.logger.error(f"AI API 調用失敗: {response.status_code} {response.text}")
                    raise Exception(f"AI API 調用失敗: {response.status_code}")

                result = response.json()
                ai_response = result["content"][0]["text"]

                # 解析 AI 回應並結構化為審查建議
                review_suggestions = self._parse_ai_response(ai_response)

                return review_suggestions

        except Exception as e:
            self.logger.error(f"程式碼分析時出錯: {e}")
            raise

    def _build_prompt(self, xml_content, focus_areas=None, repo_name=None, pr_title=None, pr_description=None):
        """
        構建 AI 提示詞

        Args:
            xml_content (str): 程式碼的 XML 表示
            focus_areas (list, optional): 審查重點領域列表
            repo_name (str, optional): 程式庫名稱
            pr_title (str, optional): PR 標題
            pr_description (str, optional): PR 描述

        Returns:
            str: AI 提示詞
        """
        # 限制 XML 內容長度以避免超出上下文窗口
        max_xml_length = 100000  # 這個值可能需要根據使用的 AI 模型調整
        truncated_xml = xml_content[:max_xml_length] if len(xml_content) > max_xml_length else xml_content

        prompt_parts = []

        # 添加基本指令
        prompt_parts.append("你是一位專業的程式碼審查專家。請審查以下程式碼並提供建議。")

        # 添加程式庫和 PR 資訊
        if repo_name:
            prompt_parts.append(f"程式庫：{repo_name}")
        if pr_title:
            prompt_parts.append(f"PR 標題：{pr_title}")
        if pr_description:
            prompt_parts.append(f"PR 描述：{pr_description}")

        # 添加審查重點
        if focus_areas:
            focus_str = "、".join(focus_areas)
            prompt_parts.append(f"請特別關注以下方面：{focus_str}")

        # 添加輸出格式指令
        prompt_parts.append("""
請以以下 JSON 格式提供你的審查結果：

```json
{
  "summary": "對 PR 的簡要總結，最多 3-5 句話",
  "overall_assessment": "良好 | 需要改進 | 有重大問題",
  "suggestions": [
    {
      "file": "檔案路徑",
      "line": "行號或行範圍（如果適用）",
      "severity": "critical | high | medium | low | praise",
      "category": "架構 | 安全性 | 性能 | 可維護性 | 代碼風格 | 其他",
      "description": "對問題的詳細描述",
      "suggestion": "如何改進的建議"
    }
  ]
}
```

請只返回 JSON 格式的結果，不要添加其他解釋或前言。
        """)

        # 添加程式碼的 XML 表示
        prompt_parts.append("以下是程式碼的 XML 表示：")
        prompt_parts.append(truncated_xml)

        return "\n\n".join(prompt_parts)

    def _parse_ai_response(self, ai_response):
        """
        解析 AI 回應並結構化為審查建議

        Args:
            ai_response (str): AI 的原始回應

        Returns:
            dict: 結構化的審查建議
        """
        try:
            # 嘗試提取 JSON 部分
            json_start = ai_response.find('```json')
            json_end = ai_response.rfind('```')

            if json_start != -1 and json_end != -1:
                json_start += 7  # 跳過 ```json
                json_content = ai_response[json_start:json_end].strip()
                return json.loads(json_content)

            # 如果沒有 JSON 格式，嘗試直接解析整個回應
            try:
                return json.loads(ai_response)
            except:
                # 如果無法解析為 JSON，則返回原始回應
                return {"summary": "無法解析 AI 回應為 JSON 格式", "overall_assessment": "無法確定", "raw_response": ai_response}

        except Exception as e:
            self.logger.error(f"解析 AI 回應時出錯: {e}")
            return {"summary": f"解析 AI 回應時出錯: {str(e)}", "overall_assessment": "無法確定", "raw_response": ai_response}
