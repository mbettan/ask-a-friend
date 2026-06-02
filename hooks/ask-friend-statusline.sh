#!/usr/bin/env bash
flag="$HOME/.config/ask-a-friend/.active"
[ -f "$flag" ] || exit 0
mode=$(cat "$flag" 2>/dev/null)
[ "$mode" = "off" ] && exit 0
# cyan badge
suffix=$(echo "$mode" | sed 's/gemini-2.5-pro/PRO/' | tr '[:lower:]' '[:upper:]')
printf '\033[38;5;44m[FRIEND:%s]\033[0m' "$suffix"
