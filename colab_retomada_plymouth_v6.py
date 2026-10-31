# R36S Plymouth - Retomada V6 no mesmo runtime Colab V5.
# Nao reinstala Debian, nao toca no R36S e verifica se patches foram realmente aplicados.
import os, pathlib, subprocess, shutil, traceback
from google.colab import files

ROOT = pathlib.Path("/content/r36s-debian-arm64")
SOURCE = ROOT / "root/plymouth-work/plymouth-24.004.60"
LOG = pathlib.Path("/content/relatorio_plymouth_retomada_v6.txt")
OUT = pathlib.Path("/content/plymouth-r36s-arm64-pacotes")
SCRIPT = ROOT / "usr/local/bin/continuar-plymouth-v6.sh"
P1 = "0100-r36s-null-terminal.patch"
P2 = "0101-r36s-null-renderer.patch"

print("=== R36S PLYMOUTH - RETOMADA V6 ===", flush=True)
print("Usando codigo Plymouth e dependencias ja preparados na V5.", flush=True)
try:
    if not (SOURCE / "debian/patches/series").is_file():
        raise RuntimeError("Codigo-fonte da V5 nao encontrado nesta sessao do Colab. Nao vou recomecar.")
    for patch_name in (P1, P2):
        patch = SOURCE / "debian/patches" / patch_name
        if not patch.is_file() or "diff --git" not in patch.read_text(encoding="utf-8", errors="replace"):
            raise RuntimeError("Patch ausente ou invalido: " + patch_name)
    series = (SOURCE / "debian/patches/series").read_text(encoding="utf-8")
    for patch_name in (P1, P2):
        if series.splitlines().count(patch_name) != 1:
            raise RuntimeError("Patch nao consta exatamente uma vez em series: " + patch_name)
    print("Dois patches encontrados e registrados na serie Debian.", flush=True)

    shell = r'''#!/bin/bash
set -Eeuo pipefail
export LANG=C LC_ALL=C DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC SYSTEMD_OFFLINE=1
cd /root/plymouth-work/plymouth-24.004.60
echo '[V6] Aplicando patches com dpkg-source --before-build...'
dpkg-source --before-build .
echo '[V6] Verificando controle de patches aplicados...'
for p in 0100-r36s-null-terminal.patch 0101-r36s-null-renderer.patch; do
  if ! grep -Fxq "$p" .pc/applied-patches; then
    echo "ERRO: patch nao foi efetivamente aplicado: $p"
    exit 22
  fi
done
echo '[V6] Dois patches confirmados como aplicados!'
if ! grep -q '^plymouth (24.004.60-5+r36s1) ' debian/changelog; then
  python3 - <<'PY'
from pathlib import Path
p=Path("debian/changelog")
header="""plymouth (24.004.60-5+r36s1) trixie; urgency=medium

  * Backport upstream null-terminal guards, LP: #2103533.
  * Build experimental para teste no R36S (nao instalado).

 -- R36S Plymouth Build <noreply@example.invalid>  Sat, 31 Oct 2026 15:00:00 +0000

"""
p.write_text(header+p.read_text())
PY
fi
echo '[4/4] Compilando Plymouth ARM64 com patches verificados...'
DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -b -us -uc -j2
mkdir -p /content/plymouth-r36s-arm64-pacotes
find /root/plymouth-work -maxdepth 1 -name '*_arm64.deb' -exec cp -v {} /content/plymouth-r36s-arm64-pacotes/ \;
test -s /content/plymouth-r36s-arm64-pacotes/plymouth_24.004.60-5+r36s1_arm64.deb
test -s /content/plymouth-r36s-arm64-pacotes/libplymouth5_24.004.60-5+r36s1_arm64.deb
for f in /content/plymouth-r36s-arm64-pacotes/*.deb; do
  dpkg-deb --field "$f" Package Version Architecture
done
sha256sum /content/plymouth-r36s-arm64-pacotes/*.deb > /content/plymouth-r36s-arm64-pacotes/SHA256SUMS.txt
echo 'COMPILACAO_CONCLUIDA_ARM64_V6'
'''
    SCRIPT.write_text(shell, encoding="utf-8")
    SCRIPT.chmod(0o755)
    cmd = ["proot", "-0", "-r", str(ROOT),
           "-b", "/dev", "-b", "/proc", "-b", "/sys", "-b", "/content:/content",
           "-b", "/etc/resolv.conf:/etc/resolv.conf",
           "-q", "/usr/bin/qemu-aarch64-static", "-w", "/root",
           "/bin/bash", "/usr/local/bin/continuar-plymouth-v6.sh"]
    env = dict(os.environ, LANG="C", LC_ALL="C")
    with LOG.open("w", encoding="utf-8") as report:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", bufsize=1, env=env)
        n, last = 0, []
        for line in proc.stdout:
            n += 1
            report.write(line)
            report.flush()
            last.append(line.rstrip())
            last = last[-35:]
            if n <= 18 or n % 75 == 0 or "ERRO:" in line or "error:" in line or "failed" in line.lower() or "[4/4]" in line or "COMPILACAO_CONCLUIDA" in line:
                print(line.rstrip()[:350], flush=True)
        code = proc.wait()
    print("Codigo de saida V6:", code, flush=True)
    if code == 0 and (OUT / "plymouth_24.004.60-5+r36s1_arm64.deb").is_file():
        z = shutil.make_archive("/content/Plymouth_R36S_ARM64_V6_PARA_TESTES", "zip", root_dir=str(OUT))
        print("Pacotes criados. Ainda NAO validados no hardware R36S.", flush=True)
        files.download(z)
    else:
        print("A V6 nao concluiu. Ultimas mensagens:", flush=True)
        print("\n".join(last[-20:]), flush=True)
        files.download(str(LOG))
except Exception as ex:
    print("ERRO V6:", str(ex), flush=True)
    with LOG.open("a", encoding="utf-8") as report:
        traceback.print_exc(file=report)
    traceback.print_exc()
    files.download(str(LOG))
