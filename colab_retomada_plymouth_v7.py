# R36S Plymouth - Retomada V7: diagnostica debhelper/dh e continua compilacao
import pathlib, subprocess, shutil, traceback, os
from google.colab import files

ROOT = pathlib.Path("/content/r36s-debian-arm64")
SRC = ROOT / "root/plymouth-work/plymouth-24.004.60"
LOG = pathlib.Path("/content/relatorio_plymouth_retomada_v7.txt")
OUT = pathlib.Path("/content/plymouth-r36s-arm64-pacotes")
SCRIPT = ROOT / "usr/local/bin/continuar-plymouth-v7.sh"

print("=== R36S PLYMOUTH - RETOMADA V7 ===", flush=True)
print("Verificando ferramenta dh/debhelper; usando patches e fontes da V6.", flush=True)
try:
    if not (SRC / "debian/changelog").is_file():
        raise RuntimeError("Fontes Plymouth da V6 ausentes nesta sessao do Colab.")
    if "24.004.60-5+r36s1" not in (SRC / "debian/changelog").read_text(encoding="utf-8")[:250]:
        raise RuntimeError("Versao Plymouth modificada inesperada. Nao compilar.")
    series = (SRC / "debian/patches/series").read_text(encoding="utf-8")
    done = (SRC / ".pc/applied-patches")
    if not done.is_file():
        raise RuntimeError("Registro dos patches aplicados nao encontrado.")
    applied = done.read_text(encoding="utf-8").splitlines()
    patches = ["0100-r36s-null-terminal.patch", "0101-r36s-null-renderer.patch"]
    if any(applied.count(p) != 1 or series.splitlines().count(p) != 1 for p in patches):
        raise RuntimeError("Nao foi possivel confirmar os dois patches em uso. Parei.")
    print("Dois patches confirmados, versao 24.004.60-5+r36s1.", flush=True)

    sh = r'''#!/bin/bash
set -Eeuo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export LANG=C LC_ALL=C DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC SYSTEMD_OFFLINE=1
echo '[V7] PATH efetivo:' "$PATH"
echo '[V7] Estado debhelper:'
dpkg-query -W debhelper || true
echo '[V7] Arquivos dh/perl:'
ls -l /usr/bin/dh /usr/bin/perl /usr/bin/make 2>&1 || true
echo '[V7] Verificando disponibilidade do comando dh:'
if [ ! -x /usr/bin/dh ]; then
  echo '[V7] dh ausente: reinstalando somente debhelper.'
  apt-get -o APT::Sandbox::User=root -o APT::Sandbox::Seccomp=false \
    -o Acquire::Retries=2 install -y --reinstall debhelper
fi
if [ ! -x /usr/bin/dh ]; then
  echo 'ERRO: dh continua ausente apos tentativa de reparo.'
  exit 27
fi
if ! command -v dh; then
  echo 'ERRO: o dh nao esta visivel no PATH, apesar de instalado.'
  exit 28
fi
echo '[V7] Verificando o interpretador e sintaxe do dh:'
head -n 1 /usr/bin/dh
perl -c /usr/bin/dh
echo '[V7] Testando execucao do dh:'
dh --help >/dev/null
echo '[V7] dh funciona. Iniciando a compilacao.'
cd /root/plymouth-work/plymouth-24.004.60
for p in 0100-r36s-null-terminal.patch 0101-r36s-null-renderer.patch; do
  grep -Fxq "$p" .pc/applied-patches || { echo "ERRO: patch faltando: $p"; exit 29; }
done
echo '[4/4] Compilando Plymouth ARM64 com debhelper validado...'
DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -b -us -uc -j2
mkdir -p /content/plymouth-r36s-arm64-pacotes
find /root/plymouth-work -maxdepth 1 -name '*_arm64.deb' -exec cp -v {} /content/plymouth-r36s-arm64-pacotes/ \;
test -s /content/plymouth-r36s-arm64-pacotes/plymouth_24.004.60-5+r36s1_arm64.deb
test -s /content/plymouth-r36s-arm64-pacotes/libplymouth5_24.004.60-5+r36s1_arm64.deb
for f in /content/plymouth-r36s-arm64-pacotes/*.deb; do
  dpkg-deb --field "$f" Package Version Architecture
done
sha256sum /content/plymouth-r36s-arm64-pacotes/*.deb > /content/plymouth-r36s-arm64-pacotes/SHA256SUMS.txt
echo 'COMPILACAO_CONCLUIDA_ARM64_V7'
'''
    SCRIPT.write_text(sh, encoding="utf-8")
    SCRIPT.chmod(0o755)
    cmd = ["proot", "-0", "-r", str(ROOT),
           "-b", "/dev", "-b", "/proc", "-b", "/sys",
           "-b", "/content:/content", "-b", "/etc/resolv.conf:/etc/resolv.conf",
           "-q", "/usr/bin/qemu-aarch64-static", "-w", "/root",
           "/bin/bash", "/usr/local/bin/continuar-plymouth-v7.sh"]
    env = dict(os.environ, LC_ALL="C", LANG="C")
    with LOG.open("w", encoding="utf-8") as fh:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", bufsize=1, env=env)
        last = []
        n = 0
        for line in proc.stdout:
            fh.write(line)
            fh.flush()
            n += 1
            last.append(line.rstrip())
            last = last[-40:]
            if n <= 35 or n % 80 == 0 or any(k in line for k in
                ("[V7]", "[4/4]", "ERRO:", "error:", "Error", "COMPILACAO_CONCLUIDA")):
                print(line.rstrip()[:370], flush=True)
        code = proc.wait()
    print("Codigo de saida V7:", code, flush=True)
    if code == 0 and (OUT / "plymouth_24.004.60-5+r36s1_arm64.deb").is_file():
        zip_name = shutil.make_archive("/content/Plymouth_R36S_ARM64_V7_PARA_VERIFICACAO",
                                       "zip", root_dir=str(OUT))
        print("PACOTES GERADOS; NAO TESTADOS NO R36S.", flush=True)
        files.download(zip_name)
    else:
        print("Nao concluiu; ultimas linhas:", flush=True)
        print("\n".join(last[-18:]), flush=True)
        files.download(str(LOG))
except Exception as ex:
    print("ERRO V7:", str(ex), flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        traceback.print_exc(file=fh)
    traceback.print_exc()
    files.download(str(LOG))
