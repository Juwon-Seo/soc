#!/usr/bin/env python3
"""프로젝트(claude.ai)에 올려 둔 선수 원자료 묶음을 풀어 players/<선수>/ 에 저장.

묶음 파일: claude/src/<선수>_bundle.b85.txt (여러 조각이면 <선수>_bundle.part1.b85.txt, part2 …)
          레반도프스키만 lewy_bundle.b64.txt
묶음 안은 tar + xz(lzma) + base85(또는 base64).

사용:
  1) claude.ai 프로젝트에서 claude/src/ 의 *_bundle*.txt 파일을 내려받아 한 폴더(예: ~/Downloads/bundles)에 둔다.
  2) python3 tools/unbundle.py ~/Downloads/bundles
"""
import base64, io, lzma, os, re, sys, tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "players")


def main(folder):
    groups = {}
    for f in sorted(os.listdir(folder)):
        m = re.match(r"(.+?)_bundle(?:\.part(\d+))?\.(b85|b64)\.txt$", f)
        if m:
            groups.setdefault((m.group(1), m.group(3)), []).append((int(m.group(2) or 0), f))
    if not groups:
        sys.exit("묶음 파일(*_bundle*.txt)을 찾지 못함: " + folder)
    for (name, enc), parts in sorted(groups.items()):
        text = "".join(open(os.path.join(folder, f), encoding="utf-8").read().strip() for _, f in sorted(parts))
        raw = (base64.b85decode if enc == "b85" else base64.b64decode)(text)
        data = lzma.decompress(raw)
        dest = os.path.join(OUT, name)
        os.makedirs(dest, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            tf.extractall(dest, filter="data") if sys.version_info >= (3, 12) else tf.extractall(dest)
        print("%-16s %2d조각 → players/%s (%d개 파일)" % (name, len(parts), name, sum(len(fs) for _, _, fs in os.walk(dest))))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
