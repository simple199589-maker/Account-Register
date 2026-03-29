#!/bin/sh
set -eu

APP_DIR="/app"
DATA_DIR="${APP_DATA_DIR:-/app/data}"

link_runtime_path() {
  target_path="$1"
  link_path="$2"

  if [ -L "$link_path" ]; then
    rm -f "$link_path"
  elif [ -e "$link_path" ]; then
    rm -rf "$link_path"
  fi

  ln -s "$target_path" "$link_path"
}

mkdir -p "$DATA_DIR/codex_tokens"

if [ ! -f "$DATA_DIR/config.json" ]; then
  cp "$APP_DIR/config.example.json" "$DATA_DIR/config.json"
  echo "[docker] 已初始化 $DATA_DIR/config.json，请按需填写真实配置。"
fi

touch \
  "$DATA_DIR/registered_accounts.txt" \
  "$DATA_DIR/stable_proxy.txt" \
  "$DATA_DIR/ak.txt" \
  "$DATA_DIR/rk.txt"

link_runtime_path "$DATA_DIR/config.json" "$APP_DIR/config.json"
link_runtime_path "$DATA_DIR/registered_accounts.txt" "$APP_DIR/registered_accounts.txt"
link_runtime_path "$DATA_DIR/stable_proxy.txt" "$APP_DIR/stable_proxy.txt"
link_runtime_path "$DATA_DIR/ak.txt" "$APP_DIR/ak.txt"
link_runtime_path "$DATA_DIR/rk.txt" "$APP_DIR/rk.txt"
link_runtime_path "$DATA_DIR/codex_tokens" "$APP_DIR/codex_tokens"

exec "$@"
