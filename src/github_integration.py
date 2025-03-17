"""
處理 GitHub 整合和 PR 評論發布的模組
"""
import json
import logging
import os

from github import Github
from github.GithubException import GithubException


class GitHubIntegration:

    def __init__(self, token=None, repo_name=None):
        """
        初始化 GitHubIntegration

        Args:
            token (str, optional): GitHub 訪問令牌，默認從環境變量獲取
            repo_name (str, optional): 程式庫名稱（格式：'owner/repo'）
        """
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("未提供 GitHub 訪問令牌")

        self.github = Github(self.token)
        self.repo_name = repo_name
        self.logger = logging.getLogger(__name__)

        # 如果提供了 repo_name，則獲取程式庫對象
        self.repo = None
        if self.repo_name:
            try:
                self.repo = self.github.get_repo(self.repo_name)
            except GithubException as e:
                self.logger.error(f"獲取程式庫時出錯: {e}")
                raise

    def set_repo(self, repo_name):
        """
        設置程式庫

        Args:
            repo_name (str): 程式庫名稱（格式：'owner/repo'）
        """
        try:
            self.repo_name = repo_name
            self.repo = self.github.get_repo(repo_name)
        except GithubException as e:
            self.logger.error(f"設置程式庫時出錯: {e}")
            raise

    def get_pr(self, pr_number):
        """
        獲取 PR 對象

        Args:
            pr_number (int): PR 編號

        Returns:
            github.PullRequest.PullRequest: PR 對象
        """
        if not self.repo:
            raise ValueError("未設置程式庫")

        try:
            return self.repo.get_pull(pr_number)
        except GithubException as e:
            self.logger.error(f"獲取 PR 時出錯: {e}")
            raise

    def get_pr_files(self, pr_number):
        """
        獲取 PR 中更改的文件列表

        Args:
            pr_number (int): PR 編號

        Returns:
            list: 更改的文件路徑列表
        """
        try:
            pr = self.get_pr(pr_number)
            return [file.filename for file in pr.get_files()]
        except Exception as e:
            self.logger.error(f"獲取 PR 文件時出錯: {e}")
            raise

    def post_review_comment(self, pr_number, review_suggestions):
        """
        在 PR 上發布審查評論

        Args:
            pr_number (int): PR 編號
            review_suggestions (dict): 審查建議

        Returns:
            github.IssueComment.IssueComment: 創建的評論對象
        """
        try:
            pr = self.get_pr(pr_number)

            # 格式化評論內容
            comment = self._format_review_comment(review_suggestions)

            # 發布評論
            return pr.create_issue_comment(comment)

        except Exception as e:
            self.logger.error(f"發布評論時出錯: {e}")
            raise

    def post_line_comments(self, pr_number, review_suggestions):
        """
        在 PR 上發布行級評論

        Args:
            pr_number (int): PR 編號
            review_suggestions (dict): 審查建議

        Returns:
            github.PullRequestReview.PullRequestReview: 創建的審查對象
        """
        try:
            pr = self.get_pr(pr_number)

            # 提取具體的檔案和行級建議
            suggestions = review_suggestions.get("suggestions", [])
            file_comments = []

            for suggestion in suggestions:
                # 僅處理包含文件和行信息的建議
                if "file" in suggestion and "line" in suggestion:
                    file_path = suggestion["file"]
                    line_info = suggestion["line"]

                    # 處理行號信息（可能是單行或範圍）
                    line_number = None
                    if isinstance(line_info, (int, str)) and str(line_info).isdigit():
                        line_number = int(line_info)
                    elif "-" in str(line_info):
                        # 對於範圍，使用範圍的起始行
                        line_parts = str(line_info).split("-")
                        if line_parts[0].strip().isdigit():
                            line_number = int(line_parts[0].strip())

                    if line_number:
                        # 格式化評論內容
                        comment_body = f"**{suggestion.get('category', '評論')} ({suggestion.get('severity', '提示')})**\n\n"
                        comment_body += suggestion.get('description', '')

                        if suggestion.get('suggestion'):
                            comment_body += f"\n\n**建議**: {suggestion['suggestion']}"

                        file_comments.append({"path": file_path, "line": line_number, "body": comment_body})

            # 如果有具體的行評論，則創建正式審查
            if file_comments:
                # 總結評論
                summary = f"# AI 程式碼審查\n\n**總體評估**: {review_suggestions.get('overall_assessment', '無評估')}\n\n"
                summary += review_suggestions.get('summary', '無總結')

                # 創建審查
                return pr.create_review(
                    body=summary,
                    event="COMMENT",  # 可以是 "APPROVE", "REQUEST_CHANGES" 或 "COMMENT"
                    comments=file_comments)

            return None

        except Exception as e:
            self.logger.error(f"發布行級評論時出錯: {e}")
            raise

    def _format_review_comment(self, review_suggestions):
        """
        格式化審查評論

        Args:
            review_suggestions (dict): 審查建議

        Returns:
            str: 格式化的評論
        """
        # 標題和總結
        comment = "# AI 程式碼審查\n\n"
        comment += f"**總體評估**: {review_suggestions.get('overall_assessment', '無評估')}\n\n"
        comment += f"## 摘要\n\n{review_suggestions.get('summary', '無總結')}\n\n"

        # 具體建議
        suggestions = review_suggestions.get("suggestions", [])
        if suggestions:
            comment += "## 詳細建議\n\n"

            for i, suggestion in enumerate(suggestions, 1):
                severity = suggestion.get("severity", "info")
                category = suggestion.get("category", "一般")

                comment += f"### {i}. {category} ({severity})\n\n"

                if "file" in suggestion:
                    file_info = f"**文件**: `{suggestion['file']}`"

                    if "line" in suggestion:
                        file_info += f" **行**: {suggestion['line']}"

                    comment += f"{file_info}\n\n"

                if "description" in suggestion:
                    comment += f"{suggestion['description']}\n\n"

                if "suggestion" in suggestion:
                    comment += f"**建議**: {suggestion['suggestion']}\n\n"

        comment += "\n---\n*由 AI 程式碼審查工具自動生成*"

        return comment
