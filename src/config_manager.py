"""
處理配置和用戶偏好的模組
"""
import logging
import os
import re

import yaml


class ConfigManager:

    def __init__(self, config_path=None):
        """
        初始化 ConfigManager

        Args:
            config_path (str, optional): 配置文件路徑，默認為 '.ai-review.yml'
        """
        self.config_path = config_path or '.ai-review.yml'
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()

    def _load_config(self):
        """
        加載配置文件

        Returns:
            dict: 配置字典
        """
        default_config = {
            'review_focus': ['code_quality', 'architecture', 'security', 'performance', 'maintainability'],
            'ai': {
                'model': 'claude-3-haiku-20240307',
                'max_tokens': 4000
            },
            'github': {
                'comment_type': 'issue',  # 'issue' 或 'review'
                'comment_placement': 'pr'  # 'pr' 或 'line'
            },
            'repomix': {
                'style': 'xml',
                'include_patterns': None,
                'exclude_patterns': None
            }
        }

        # 如果配置文件存在，則加載
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as file:
                    user_config = yaml.safe_load(file)

                    # 合併默認配置和用戶配置
                    if user_config:
                        # 遞歸合併配置
                        config = self._merge_configs(default_config, user_config)
                    else:
                        config = default_config

                    return config
            except Exception as e:
                self.logger.error(f"加載配置文件時出錯: {e}")
                return default_config
        else:
            self.logger.warning(f"配置文件 '{self.config_path}' 不存在，使用默認配置")
            return default_config

    def _merge_configs(self, default_config, user_config):
        """
        遞歸合併配置

        Args:
            default_config (dict): 默認配置
            user_config (dict): 用戶配置

        Returns:
            dict: 合併後的配置
        """
        config = default_config.copy()

        for key, value in user_config.items():
            if key in config and isinstance(config[key], dict) and isinstance(value, dict):
                config[key] = self._merge_configs(config[key], value)
            else:
                config[key] = value

        return config

    def parse_pr_focus(self, pr_description):
        """
        從 PR 描述中解析審查重點

        Args:
            pr_description (str): PR 描述

        Returns:
            list: 審查重點列表
        """
        if not pr_description:
            return []

        # 查找類似 "AI-REVIEW-FOCUS: #security #performance" 的標記
        focus_match = re.search(r'AI-REVIEW-FOCUS:\s*(.*?)(?:\n|$)', pr_description)

        if focus_match:
            focus_text = focus_match.group(1).strip()
            # 提取所有 #tag 格式的標籤
            tags = re.findall(r'#(\w+)', focus_text)
            return tags

        return []

    def get_review_focus(self, pr_description=None):
        """
        獲取審查重點

        Args:
            pr_description (str, optional): PR 描述，用於覆蓋配置文件中的設定

        Returns:
            list: 審查重點列表
        """
        # 從配置中獲取默認重點
        default_focus = self.config.get('review_focus', [])

        # 如果提供了 PR 描述，則從中解析重點
        pr_focus = self.parse_pr_focus(pr_description) if pr_description else []

        # 如果 PR 中指定了重點，則使用這些重點；否則使用默認重點
        return pr_focus if pr_focus else default_focus

    def get_ai_config(self):
        """
        獲取 AI 配置

        Returns:
            dict: AI 配置字典
        """
        return self.config.get('ai', {})

    def get_github_config(self):
        """
        獲取 GitHub 配置

        Returns:
            dict: GitHub 配置字典
        """
        return self.config.get('github', {})

    def get_repomix_config(self):
        """
        獲取 Repomix 配置

        Returns:
            dict: Repomix 配置字典
        """
        return self.config.get('repomix', {})

    def create_example_config(self, output_path='.ai-review.yml.example'):
        """
        創建示例配置文件

        Args:
            output_path (str, optional): 輸出路徑

        Returns:
            str: 創建的配置文件的路徑
        """
        example_config = {
            'review_focus': [
                'code_quality',  # 代碼質量
                'architecture',  # 架構一致性
                'security',  # 安全性
                'performance',  # 性能
                'maintainability',  # 可維護性
                'best_practices'  # 最佳實踐
            ],
            'ai': {
                'model': 'claude-3-haiku-20240307',  # AI 模型
                'max_tokens': 4000  # 最大代幣數
            },
            'github': {
                # 評論類型：'issue' 為普通評論，'review' 為正式審查
                'comment_type': 'issue',
                # 評論放置：'pr' 為 PR 級別，'line' 為行級別
                'comment_placement': 'pr'
            },
            'repomix': {
                'style': 'xml',  # 輸出格式
                'include_patterns': None,  # 包含模式
                'exclude_patterns': None  # 排除模式
            }
        }

        try:
            with open(output_path, 'w', encoding='utf-8') as file:
                yaml.dump(example_config, file, default_flow_style=False, allow_unicode=True)

            self.logger.info(f"已創建示例配置文件: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"創建示例配置文件時出錯: {e}")
            raise
