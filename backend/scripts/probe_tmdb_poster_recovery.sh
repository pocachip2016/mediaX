#!/usr/bin/env bash
# probe_tmdb_poster_recovery.sh
# Step 0 — null poster_path 캐시 행이 /images(언어 무제약)로 회수 가능한지 측정.
# A = /images에 포스터 실재(회수가능), B = 진짜 부재.
# 사용: bash backend/scripts/probe_tmdb_poster_recovery.sh [표본수per구간]
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1   # backend/

N="${1:-15}"   # popularity 구간별 표본 수
KEY="$(grep -E '^TMDB_API_KEY=' .env 2>/dev/null | cut -d= -f2-)"
if [ -z "${KEY:-}" ]; then echo "FAIL: TMDB_API_KEY 없음 (.env)"; exit 1; fi
PSQL="docker exec mediax-postgres-1 psql -U media_ax -d media_ax -t -A"

# /images posters 개수 + ko/en/무언어 보유 여부 반환
imgcount() {  # $1=kind(movie|tv) $2=id  -> "총개수|ko|en|nolang"
  curl -s "https://api.themoviedb.org/3/$1/$2/images?api_key=$KEY" | python3 -c '
import sys,json
try: d=json.load(sys.stdin)
except: print("0|0|0|0"); sys.exit()
p=d.get("posters",[])
ko=sum(1 for x in p if x.get("iso_639_1")=="ko")
en=sum(1 for x in p if x.get("iso_639_1")=="en")
nl=sum(1 for x in p if not x.get("iso_639_1"))
print(f"{len(p)}|{ko}|{en}|{nl}")' 2>/dev/null
}

probe_kind() {  # $1=movie|tv  $2=table
  local kind="$1" table="$2"
  echo "════════ $kind ($table) ════════"
  # popularity 구간: 상(>5) / 중(1~5) / 하(>0,<1)
  for band in "high:popularity>5" "mid:popularity>1 AND popularity<=5" "low:popularity>0 AND popularity<=1"; do
    local label="${band%%:*}" cond="${band#*:}"
    local ids
    ids="$($PSQL -c "SELECT id FROM $table WHERE (poster_path IS NULL OR poster_path='') AND $cond ORDER BY random() LIMIT $N;" 2>/dev/null | tr '\n' ' ')"
    local total=0 a=0 ko=0 en=0 nl=0
    for id in $ids; do
      [ -z "$id" ] && continue
      total=$((total+1))
      IFS='|' read -r cnt k e n <<< "$(imgcount "$kind" "$id")"
      [ "${cnt:-0}" -gt 0 ] 2>/dev/null && a=$((a+1))
      [ "${k:-0}" -gt 0 ] 2>/dev/null && ko=$((ko+1))
      [ "${e:-0}" -gt 0 ] 2>/dev/null && en=$((en+1))
      [ "${n:-0}" -gt 0 ] 2>/dev/null && nl=$((nl+1))
    done
    if [ "$total" -gt 0 ]; then
      printf "  [%-4s] 표본 %2d | /images포스터 실재(A) %2d (%3d%%) | ko %2d  en %2d  무언어 %2d\n" \
        "$label" "$total" "$a" "$((100*a/total))" "$ko" "$en" "$nl"
    else
      printf "  [%-4s] 해당 구간 null 행 없음\n" "$label"
    fi
  done
}

echo "=== TMDB 포스터 회수 가능성 프로브 (구간별 표본 $N건, 무작위) ==="
echo "A=/images에 포스터 실재(회수가능)  B=진짜 부재"
echo
probe_kind movie tmdb_movie_cache
probe_kind tv    tmdb_tv_cache
echo
echo "해석: A%가 높은 구간 → 백필 가치 큼 / 낮은 구간 → 진짜 부재 우세, 백필 제외 권장"
