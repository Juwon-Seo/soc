#!/usr/bin/env python3
"""클럽 SOC 계산기 빌드.

src/index.html + src/data/*.js  ->  dist/ 아래 세 가지 결과물

  dist/club-soc.html           데이터를 모두 안에 넣은 단독 실행 파일(더블클릭으로 열림, 약 4MB)
  dist/club-soc.artifact.html  게시용 단일 파일(앞뒤 doctype/body 껍데기 없음, Claude Code 아티팩트 게시용).
                               v1.256부터 데이터·본문 스크립트를 gzip+base64로 압축해 넣고, 열 때 브라우저의
                               DecompressionStream으로 풀어 실행(아티팩트 한도 16MiB 때문, 15.3MB → 약 5MB)
  dist/club-soc.packed-test.html  압축 게시본에 껍데기를 붙인 시험용(브라우저로 열어 압축본이 정상인지 확인)
  dist/dev.html                데이터를 src/data/ 에서 따로 읽는 개발용(수정 직후 바로 열어 보기)

사용: python3 tools/build.py
"""
import os, re, sys, gzip, base64

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

    # 게시용 압축본: 첫 데이터 태그부터 본문 스크립트 끝까지를 하나의 JS로 이어 붙여 gzip+base64
    first = TAG.search(html).start()
    main_open = html.index("<script>", first)
    main_close = html.index("</script>", main_open)
    if TAG.search(html, main_open):
        sys.exit("본문 <script> 뒤에 데이터 태그가 있음(압축본은 데이터 → 본문 순서를 가정)")
    between = TAG.sub("", html[first:main_open])
    if between.strip():
        sys.exit("데이터 태그와 본문 <script> 사이에 다른 내용이 있음: %r" % between.strip()[:80])
    js = "".join(open(os.path.join(SRC, "data", f), encoding="utf-8").read().rstrip("\n") + "\n;\n" for f in tags)
    js += html[main_open + len("<script>"):main_close]
    b64 = base64.b64encode(gzip.compress(js.encode("utf-8"), 9, mtime=0)).decode("ascii")
    loader = ('<div id="socBoot" style="padding:24px;font:14px sans-serif;color:#888">계산기 불러오는 중…</div>\n'
              '<script type="text/plain" id="socZ">' + b64 + '</script>\n'
              '<script>(async()=>{const box=document.getElementById("socBoot");'
              'try{if(typeof DecompressionStream!=="function")throw new Error("이 브라우저는 압축 풀기(DecompressionStream)를 지원하지 않습니다. 최신 브라우저로 열어 주세요.");'
              'const s=document.getElementById("socZ").textContent;const bin=atob(s);const u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);'
              'const txt=await new Response(new Blob([u]).stream().pipeThrough(new DecompressionStream("gzip"))).text();'
              'const sc=document.createElement("script");sc.textContent=txt;box.remove();document.body.appendChild(sc)}'
              'catch(e){box.textContent="불러오지 못했습니다: "+e.message}})()</script>')
    packed = html[:first] + loader + html[main_close + len("</script>"):]

    os.makedirs(DIST, exist_ok=True)
    outs = {
        "club-soc.html": HEAD + inlined + ("" if inlined.endswith("\n") else "\n") + TAIL,
        "club-soc.artifact.html": packed,
        "club-soc.packed-test.html": HEAD + packed + ("" if packed.endswith("\n") else "\n") + TAIL,
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
