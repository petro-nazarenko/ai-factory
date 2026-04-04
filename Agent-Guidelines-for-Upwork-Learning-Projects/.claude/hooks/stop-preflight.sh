#!/usr/bin/env bash
# .claude/hooks/stop-preflight.sh
# Stop hook: запускает preflight.sh, результат возвращает как JSON systemMessage.
# Если lint или pytest упали — устанавливает continue:false, чтобы Claude увидел ошибки.

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Быстрый выход без проверок: SKIP_PREFLIGHT=1 claude
if [ "${SKIP_PREFLIGHT:-0}" = "1" ]; then
    echo '{"systemMessage": "⚡ Preflight skipped (SKIP_PREFLIGHT=1)"}'
    exit 0
fi

OUTPUT=$(bash preflight.sh 2>&1)
CODE=$?

# Выводим JSON для Claude Code
python3 - "$OUTPUT" "$CODE" <<'PY'
import json, sys

output = sys.argv[1]
code   = int(sys.argv[2])

result = {"systemMessage": output}
if code != 0:
    result["continue"]   = False
    result["stopReason"] = "Preflight failed — исправь ошибки перед завершением"

print(json.dumps(result))
PY
