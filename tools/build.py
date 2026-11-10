#!/usr/bin/env python3
"""클럽 SOC 계산기 빌드.

src/index.html + src/data/*.js  ->  dist/ 아래 세 가지 결과물

  dist/club-soc.html           데이터를 모두 안에 넣은 단독 실행 파일(더블클릭으로 열림, 약 4MB)
  dist/club-soc.artifact.html  위와 같지만 앞뒤 doctype/body 껍데기가 없는 게시용 단일 파일
                               (Claude Code 아티팩트 게시용 — 상대 경로 파일을 못 쓰므로 한 파일이어야 함)
  dist/dev.html                데이터를 src/data/ 에서 따로 읽는 개발용(수정 직후 바로 열어 보기)

사용: python3 tools/build.py
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DIST = os.path.join(ROOT, "dist")

# 플랫폼(claude.ai 아티팩트)이 게시본 앞뒤에 붙이는 껍데기와 같은 것
HEAD = ('<!doctype html><html><head><meta charset=utf8>'
        '<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>:root{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);'
        'padding-bottom:env(safe-area-inset-bottom,0px)}html{scroll-padding-top:env(safe-area-inset-top,0px)}'
        'body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000}'
        'img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}</style></head><body>\n')
TAIL = "</body></html>\n"

TAG = re.compile(r'<script src="data/([a-z0-9_]+\.js)"></script>')


def main():
    html = open(os.path.join(SRC, "index.html"), encoding="utf-8").read()
    tags = TAG.findall(html)
    if not tags:
        sys.exit("index.html 에서 <script src=\"data/…\"> 태그를 찾지 못함")
    # 태그가 가리키는 파일이 모두 있고, data/ 안의 파일이 모두 태그로 걸려 있는지 확인
    on_disk = sorted(f for f in os.listdir(os.path.join(SRC, "data")) if f.endswith(".js"))
    missing = [t for t in tags if t not in on_disk]
    unused = [f for f in on_disk if f not in tags]
    if missing:
        sys.exit("태그는 있는데 파일이 없음: %s" % missing)
    if unused:
        sys.exit("파일은 있는데 index.html 에 <script src> 태그가 없음: %s" % unused)
    if len(set(tags)) != len(tags):
        sys.exit("같은 데이터 파일 태그가 두 번 이상 있음")

    def inline(m):
        body = open(os.path.join(SRC, "data", m.group(1)), encoding="utf-8").read()
        if "</script" in body.lower():
            sys.exit("%s 안에 </script 가 있어 인라인할 수 없음" % m.group(1))
        return "<script>\n" + body.rstrip("\n") + "\n</script>"

    inlined = TAG.sub(inline, html)
    dev = TAG.sub(lambda m: '<script src="../src/data/%s"></script>' % m.group(1), html)

    os.makedirs(DIST, exist_ok=True)
    outs = {
        "club-soc.html": HEAD + inlined + ("" if inlined.endswith("\n") else "\n") + TAIL,
        "club-soc.artifact.html": inlined,
        "dev.html": HEAD + dev + ("" if dev.endswith("\n") else "\n") + TAIL,
    }
    for name, text in outs.items():
        with open(os.path.join(DIST, name), "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print("%-26s %9.1f KB" % (name, len(text.encode("utf-8")) / 1024))
    ver = re.search(r"(v1\.\d+)</span>", html)
    print("버전 문구:", ver.group(1) if ver else "(못 찾음)", "· 데이터 파일", len(tags), "개")


if __name__ == "__main__":
    main()
