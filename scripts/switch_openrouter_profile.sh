#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
SERVICE="finance-streamer-mvp"
ENVIRONMENT="production"
DEPLOY_AFTER="true"

usage() {
  cat <<'EOF'
用法:
  ./scripts/switch_openrouter_profile.sh <cheap|quality> [--service NAME] [--environment NAME] [--no-deploy]

示例:
  ./scripts/switch_openrouter_profile.sh cheap
  ./scripts/switch_openrouter_profile.sh quality --environment codex-preview
  ./scripts/switch_openrouter_profile.sh cheap --no-deploy
EOF
}

if [[ "${MODE}" == "-h" || "${MODE}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "${MODE}" ]]; then
  usage
  exit 1
fi
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE="${2:-}"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="${2:-}"
      shift 2
      ;;
    --no-deploy)
      DEPLOY_AFTER="false"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${SERVICE}" || -z "${ENVIRONMENT}" ]]; then
  echo "service/environment 不能为空"
  exit 1
fi

if ! command -v railway >/dev/null 2>&1; then
  echo "未找到 railway CLI，请先安装并登录。"
  exit 1
fi

case "${MODE}" in
  cheap)
    STREAM_MODELS="google/gemini-3.1-pro-preview,anthropic/claude-sonnet-4.6,openai/gpt-5.1"
    ARTICLE_MODELS="google/gemini-3.1-pro-preview,anthropic/claude-sonnet-4.6,openai/gpt-5.1"
    MESSAGE="switch openrouter profile: cheap (gemini first)"
    ;;
  quality)
    STREAM_MODELS="anthropic/claude-sonnet-4.6,google/gemini-3.1-pro-preview,openai/gpt-5.1"
    ARTICLE_MODELS="anthropic/claude-sonnet-4.6,openai/gpt-5.1,google/gemini-3.1-pro-preview"
    MESSAGE="switch openrouter profile: quality (claude first)"
    ;;
  *)
    echo "MODE 仅支持 cheap 或 quality，当前: ${MODE}"
    exit 1
    ;;
esac

echo "正在切换 OpenRouter 档位: ${MODE}"
echo "service=${SERVICE}, environment=${ENVIRONMENT}"

railway variable set \
  --service "${SERVICE}" \
  --environment "${ENVIRONMENT}" \
  --skip-deploys \
  OPENROUTER_STREAM_MODELS="${STREAM_MODELS}" \
  OPENROUTER_ARTICLE_MODELS="${ARTICLE_MODELS}"

echo "变量已更新。"

if [[ "${DEPLOY_AFTER}" == "true" ]]; then
  railway up \
    --service "${SERVICE}" \
    --environment "${ENVIRONMENT}" \
    --ci \
    -m "${MESSAGE}"
  echo "部署已完成。"
else
  echo "已跳过部署。你可稍后手动执行 railway up。"
fi

echo "当前建议检查: GET /api/status"
