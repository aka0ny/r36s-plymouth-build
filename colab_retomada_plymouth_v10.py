# R36S Plymouth - Retomada V10
# Disponibilizar dh via /usr/local/bin no Debian isolado Colab, sem reinstalar pacotes.
import os, pathlib, subprocess, shutil, traceback, hashlib
from google.colab import files

ROOT = pathlib.Path("/content/r36s-debian-arm64")
SOURCE = ROOT / "root/plymouth-work/plymouth-24.004.60"
ORIGINAL_DH = ROOT / "usr/bin/dh"
ALTERNATE_DH = ROOT / "usr/local/bin/dh"
OUTPUT = pathlib.Path("/content/plymouth-r36s-arm64-pacotes")
LOG = pathlib.Path("/content/relatorio_plymouth_retomada_v10.txt")
SCRIPT = ROOT / "usr/local/bin/continuar-plymouth-v10.sh"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

print("=== R36S PLYMOUTH - RETOMADA V10 ===", flush=True)
print("Nao modifica o cartao R36S. Nao reinstala pacotes.", flush=True)
try:
    if not ORIGINAL_DH.is_file() or not (SOURCE / ".pc/applied-patches").is_file():
        raise RuntimeError("Ambiente e fonte Plymouth da V9 indisponiveis; parei.")
    src = ORIGINAL_DH.read_bytes()
    if not src.startswith(b"#!/usr/bin/perl") or b"debhelper" not in src[:700]:
        raise RuntimeError("dh original nao parece o executavel oficial do debhelper.")
    expected = ("0100-r36s-null-terminal.patch", "0101-r36s-null-renderer.patch")
    applied = (SOURCE / ".pc/applied-patches").read_text(encoding="utf-8").splitlines()
    if any(applied.count(p) != 1 for p in expected):
        raise RuntimeError("Os dois patches do Plymouth nao estao confirmados nesta sessao.")
    if "24.004.60-5+r36s1" not in (SOURCE / "debian/changelog").read_text(encoding="utf-8")[:150]:
        raise RuntimeError("Versao modificada Plymouth incorreta; sem compilar.")
    if ALTERNATE_DH.exists():
        if sha(ORIGINAL_DH) != sha(ALTERNATE_DH):
            raise RuntimeError("Ja existe outro executavel em /usr/local/bin/dh. Nao substitui.")
    else:
        ALTERNATE_DH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ORIGINAL_DH, ALTERNATE_DH)
        ALTERNATE_DH.chmod(ALTERNATE_DH.stat().st_mode | 0o111)
    if sha(ORIGINAL_DH) != sha(ALTERNATE_DH):
        raise RuntimeError("Copia do dh nao corresponde ao arquivo original.")
    print("dh copiado e verificado byte a byte em /usr/local/bin/dh.", flush=True)

    shell = r'''#!/bin/bash
set -Eeuo pipefail
export PATH=/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin
export LANG=C LC_ALL=C DEBIAN_FRONTEND=noninteractive SYSTEMD_OFFLINE=1
echo '[V10] Verificando caminhos:'
ls -l /usr/bin/dh /usr/local/bin/dh 2>&1 || true
echo '[V10] Resolucao do comando:'
command -v dh || true
if [ ! -x /usr/local/bin/dh ]; then
  echo 'ERRO: o PRoot tambem nao consegue ver /usr/local/bin/dh.'
  exit 40
fi
echo '[V10] Testando interpretador Perl:'
perl -c /usr/local/bin/dh
echo '[V10] Testando o debhelper:'
/usr/local/bin/dh --help >/dev/null
echo '[V10] dh funcional pelo caminho alternativo!'
cd /root/plymouth-work/plymouth-24.004.60
for p in 0100-r36s-null-terminal.patch 0101-r36s-null-renderer.patch; do
  grep -Fxq "$p" .pc/applied-patches || { echo "ERRO: patch ausente: $p"; exit 41; }
done
echo '[4/4] Compilando Plymouth ARM64 com dh via /usr/local/bin...'
DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -b -us -uc -j2
mkdir -p /content/plymouth-r36s-arm64-pacotes
find /root/plymouth-work -maxdepth 1 -name '*_arm64.deb' -exec cp -v {} /content/plymouth-r36s-arm64-pacotes/ \;
test -s /content/plymouth-r36s-arm64-pacotes/plymouth_24.004.60-5+r36s1_arm64.deb
test -s /content/plymouth-r36s-arm64-pacotes/libplymouth5_24.004.60-5+r36s1_arm64.deb
for f in /content/plymouth-r36s-arm64-pacotes/*.deb; do
  dpkg-deb --field "$f" Package Version Architecture
done
sha256sum /content/plymouth-r36s-arm64-pacotes/*.deb > /content/plymouth-r36s-arm64-pacotes/SHA256SUMS.txt
echo 'COMPILACAO_CONCLUIDA_ARM64_V10'
'''
    SCRIPT.write_text(shell, encoding="utf-8")
    SCRIPT.chmod(0o755)
    cmd = ["proot", "-0", "-r", str(ROOT),
           "-b", "/dev", "-b", "/proc", "-b", "/sys",
           "-b", "/content:/content", "-b", "/etc/resolv.conf:/etc/resolv.conf",
           "-q", "/usr/bin/qemu-aarch64-static", "-w", "/root",
           "/bin/bash", "/usr/local/bin/continuar-plymouth-v10.sh"]
    last = []
    with LOG.open("w", encoding="utf-8") as f:
        f.write("V10 HOST: /usr/local/bin/dh sha256=" + sha(ALTERNATE_DH) + "\n")
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             bufsize=1, text=True, errors="replace",
                             env=dict(os.environ, LANG="C", LC_ALL="C"))
        n = 0
        for line in p.stdout:
            f.write(line)
            f.flush()
            n += 1
            last.append(line.rstrip())
            last = last[-40:]
            if n <= 20 or n % 80 == 0 or any(marker in line for marker in
                ("[V10]", "[4/4]", "ERRO:", "error:", "Error", "COMPILACAO_CONCLUIDA")):
                print(line.rstrip()[:380], flush=True)
        result = p.wait()
    print("Codigo de saida V10:", result, flush=True)
    if result == 0 and (OUTPUT / "plymouth_24.004.60-5+r36s1_arm64.deb").is_file():
        archive = shutil.make_archive("/content/Plymouth_R36S_ARM64_V10_PARA_VERIFICACAO",
                                      "zip", root_dir=str(OUTPUT))
        print("PACOTES CONSTRUIDOS. AINDA NAO TESTADOS NO R36S.", flush=True)
        files.download(archive)
    else:
        print("Nao concluiu. Ultimas mensagens:\n" + "\n".join(last[-18:]), flush=True)
        files.download(str(LOG))
except Exception as exc:
    print("ERRO V10:", str(exc), flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        traceback.print_exc(file=f)
    traceback.print_exc()
    files.download(str(LOG))
