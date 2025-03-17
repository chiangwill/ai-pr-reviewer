"""
處理 Repomix 轉換和 XML 生成的模組
"""
import logging
import os
import shutil
import subprocess
import tempfile


class RepomixHandler:

    def __init__(self, repo_path=None):
        """
        初始化 RepomixHandler

        Args:
            repo_path (str, optional): 程式碼庫的本地路徑。如果為 None，則使用當前目錄
        """
        self.repo_path = repo_path or os.getcwd()
        self.logger = logging.getLogger(__name__)

    def check_repomix_installed(self):
        """
        檢查 Repomix 是否已安裝

        Returns:
            bool: Repomix 是否已安裝
        """
        try:
            subprocess.run(['npx', 'repomix', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            self.logger.warning("Repomix 未安裝，將嘗試使用 npx 運行")
            return False

    def generate_xml(self, output_path=None, include_patterns=None, exclude_patterns=None):
        """
        使用 Repomix 生成程式碼庫的 XML 表示

        Args:
            output_path (str, optional): XML 輸出文件的路徑
            include_patterns (str, optional): 要包含的文件模式，逗號分隔
            exclude_patterns (str, optional): 要排除的文件模式，逗號分隔

        Returns:
            str: 生成的 XML 文件的路徑
        """
        temp_dir = None
        original_dir = os.getcwd()

        try:
            # 如果提供了 repo_path，則切換到該目錄
            if self.repo_path and self.repo_path != original_dir:
                os.chdir(self.repo_path)

            # 如果未提供輸出路徑，則建立臨時目錄
            if not output_path:
                temp_dir = tempfile.mkdtemp()
                output_path = os.path.join(temp_dir, "repo.xml")

            # 構建 Repomix 命令
            cmd = ['npx', 'repomix', '--style', 'xml']

            if output_path:
                cmd.extend(['--output', output_path])

            if include_patterns:
                cmd.extend(['--include', include_patterns])

            if exclude_patterns:
                cmd.extend(['--ignore', exclude_patterns])

            # 執行 Repomix 命令
            self.logger.info(f"執行 Repomix 命令: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)

            # 驗證輸出文件存在
            if not os.path.exists(output_path):
                raise FileNotFoundError(f"Repomix 未能生成輸出文件: {output_path}")

            return output_path

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Repomix 執行失敗: {e}")
            raise
        except Exception as e:
            self.logger.error(f"生成 XML 時出錯: {e}")
            raise
        finally:
            # 恢復原始目錄
            os.chdir(original_dir)

    def generate_xml_for_pr(self, pr_files, output_path=None):
        """
        為 PR 中更改的文件生成 XML

        Args:
            pr_files (list): PR 中更改的文件列表
            output_path (str, optional): XML 輸出文件的路徑

        Returns:
            str: 生成的 XML 文件的路徑
        """
        # 將文件列表轉換為 include 模式
        include_patterns = ",".join(pr_files)

        return self.generate_xml(output_path, include_patterns)

    def read_xml_content(self, xml_path):
        """
        讀取 XML 文件內容

        Args:
            xml_path (str): XML 文件的路徑

        Returns:
            str: XML 文件的內容
        """
        try:
            with open(xml_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            self.logger.error(f"讀取 XML 文件時出錯: {e}")
            raise
