"""
AI 程式碼審查工具主程式
"""
import argparse
import asyncio
import json
import logging
import os
import re
import sys
import tempfile

from src.ai_analyzer import AIAnalyzer
from src.config_manager import ConfigManager
from src.github_integration import GitHubIntegration
from src.repomix_handler import RepomixHandler

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])

logger = logging.getLogger(__name__)


async def main():
    """主函數"""
    # 解析命令行參數
    parser = argparse.ArgumentParser(description='AI 程式碼審查工具')
    parser.add_argument('--repo', required=False, help='程式庫名稱（格式：owner/repo）')
    parser.add_argument('--pr', type=int, required=False, help='PR 編號')
    parser.add_argument('--token', help='GitHub 訪問令牌')
    parser.add_argument('--ai-key', help='AI API 密鑰')
    parser.add_argument('--config', default='.ai-review.yml', help='配置文件路徑')
    parser.add_argument('--init', action='store_true', help='創建示例配置文件')
    parser.add_argument('--output', help='審查結果輸出路徑')

    args = parser.parse_args()

    # 初始化配置管理器
    config_manager = ConfigManager(args.config)

    # 如果要求創建示例配置文件
    if args.init:
        config_manager.create_example_config()
        logger.info("已創建示例配置文件。退出程序。")
        return

    # 讀取環境變量
    github_token = args.token or os.environ.get('GITHUB_TOKEN')
    ai_api_key = args.ai_key or os.environ.get('AI_API_KEY')

    # 檢查令牌
    if not github_token:
        logger.error("未提供 GitHub 訪問令牌。請使用 --token 參數或設置 GITHUB_TOKEN 環境變量。")
        sys.exit(1)

    if not ai_api_key:
        logger.error("未提供 AI API 密鑰。請使用 --ai-key 參數或設置 AI_API_KEY 環境變量。")
        sys.exit(1)

    # 檢查是否為 GitHub Actions 環境
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        # 從 GitHub Actions 環境變量中獲取程式庫和 PR 信息
        github_repository = os.environ.get('GITHUB_REPOSITORY')

        # 解析 PR 編號 (從 GITHUB_REF，格式如 'refs/pull/123/merge')
        github_ref = os.environ.get('GITHUB_REF', '')
        pr_match = re.search(r'refs/pull/(\d+)/merge', github_ref)
        pr_number = int(pr_match.group(1)) if pr_match else None

        # 如果命令行參數未提供，則使用環境變量
        if not args.repo:
            args.repo = github_repository

        if not args.pr and pr_number:
            args.pr = pr_number

    # 檢查程式庫和 PR 信息
    if not args.repo:
        logger.error("未提供程式庫名稱。請使用 --repo 參數。")
        sys.exit(1)

    if not args.pr:
        logger.error("未提供 PR 編號。請使用 --pr 參數。")
        sys.exit(1)

    try:
        # 初始化 GitHub 整合
        github_integration = GitHubIntegration(github_token, args.repo)

        # 獲取 PR 信息
        logger.info(f"獲取 PR #{args.pr} 信息")
        pr = github_integration.get_pr(args.pr)
        pr_title = pr.title
        pr_description = pr.body

        # 獲取 PR 中更改的文件
        logger.info("獲取 PR 中更改的文件")
        pr_files = github_integration.get_pr_files(args.pr)

        if not pr_files:
            logger.warning("PR 中沒有找到更改的文件。退出程序。")
            return

        # 獲取審查重點
        review_focus = config_manager.get_review_focus(pr_description)
        logger.info(f"審查重點: {', '.join(review_focus)}")

        # 初始化 Repomix 處理器
        repomix_handler = RepomixHandler()

        # 檢查 Repomix 是否已安裝
        if not repomix_handler.check_repomix_installed():
            logger.warning("Repomix 未安裝。將嘗試使用 npx 運行。")

        # 獲取 Repomix 配置
        repomix_config = config_manager.get_repomix_config()

        # 為 PR 生成 XML
        logger.info("使用 Repomix 生成 XML")
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as temp_file:
            xml_path = temp_file.name

        try:
            # 生成 XML
            xml_path = repomix_handler.generate_xml_for_pr(pr_files, xml_path)

            # 讀取 XML 內容
            xml_content = repomix_handler.read_xml_content(xml_path)

            # 初始化 AI 分析器
            ai_config = config_manager.get_ai_config()
            ai_analyzer = AIAnalyzer(ai_api_key, model=ai_config.get('model', 'claude-3-haiku-20240307'))

            # 使用 AI 分析程式碼
            logger.info("使用 AI 分析程式碼")
            review_suggestions = await ai_analyzer.analyze_code(xml_content, focus_areas=review_focus, repo_name=args.repo, pr_title=pr_title, pr_description=pr_description)

            # 如果指定了輸出路徑，則保存審查結果
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as file:
                    json.dump(review_suggestions, file, indent=2, ensure_ascii=False)
                logger.info(f"審查結果已保存到 {args.output}")

            # 獲取 GitHub 配置
            github_config = config_manager.get_github_config()
            comment_type = github_config.get('comment_type', 'issue')
            comment_placement = github_config.get('comment_placement', 'pr')

            # 發布審查評論
            logger.info("發布審查評論")
            if comment_type == 'issue' or comment_placement == 'pr':
                # 發布 PR 級別的評論
                github_integration.post_review_comment(args.pr, review_suggestions)
                logger.info("已發布 PR 評論")

            if comment_type == 'review' or comment_placement == 'line':
                # 發布行級評論
                github_integration.post_line_comments(args.pr, review_suggestions)
                logger.info("已發布行級評論")

            logger.info("程式碼審查完成")

        finally:
            # 清理臨時文件
            if os.path.exists(xml_path):
                os.unlink(xml_path)

    except Exception as e:
        logger.error(f"審查過程中出錯: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
