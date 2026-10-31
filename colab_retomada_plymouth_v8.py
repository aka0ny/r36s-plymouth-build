# R36S Plymouth - Retomada V8.
# Conserta apenas arquivos do debhelper NO DEBIAN ISOLADO DO COLAB; NAO toca no R36S.
import os, pathlib, subprocess, shutil, traceback, urllib.request
from google.colab import files

ROOT = pathlib.Path("/content/r36s-debian-arm64")
SOURCE = ROOT / "root/plymouth-work/plymouth-24.004.60"
OUTPUT = pathlib.Path("/content/plymouth-r36s-arm64-pacotes")
LOG = pathlib.Path("/content/relatorio_plymouth_retomada_v8.txt")
SCRIPT = ROOT / "usr/local/bin/continuar-plymouth-v8.sh"
PKG = ROOT / "var/cache/apt/archives/debhelper_13.24.2_all.deb"
DH = ROOT / "usr/bin/dh"
URL = "https://deb.debian.org/debian/pool/main/d/debhelper/debhelper_13.24.2_all.deb"

def command(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout.strip()

print("=== R36S PLYMOUTH - RETOMADA V8 ===", flush=True)
print("Diagnostico e recuperacao do debhelper fora do PRoot, dentro do Colab.", flush=True)
try:
    if not (SOURCE / "debian/changelog").is_file() or not (SOURCE / ".pc/applied-patches").is_file():
        raise RuntimeError("Fonte Plymouth com patches V6 nao encontrada nesta sessao. Nao reinstalar.")
    applied = (SOURCE / ".pc/applied-patches").read_text(encoding="utf-8").splitlines()
    wanted = ["0100-r36s-null-terminal.patch", "0101-r36s-null-renderer.patch"]
    if any(applied.count(p) != 1 for p in wanted):
        raise RuntimeError("Nao foi possivel confirmar os dois patches; interrompido.")
    if not (ROOT / "usr/bin/perl").is_file():
        raise RuntimeError("Interpretador Perl nao localizado no Debian ARM64; interrompido.")

    print("Verificando /usr/bin/dh no sistema de arquivos visto pelo Colab:", DH.exists(), flush=True)
    if not DH.exists():
        if PKG.is_file():
            print("Pacote debhelper recuperado do cache APT local.", flush=True)
        else:
            print("Pacote nao encontrado no cache; baixando apenas debhelper (aprox. 900 KB).", flush=True)
            PKG.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(URL, str(PKG))
        info = {key: command(["dpkg-deb", "-f", str(PKG), key])
                for key in ("Package", "Version", "Architecture")}
        print("Pacote:", info, flush=True)
        if info != {"Package": "debhelper", "Version": "13.24.2", "Architecture": "all"}:
            raise RuntimeError("Metadados do pacote inesperados; sem extracao.")
        listing = command(["dpkg-deb", "--contents", str(PKG)])
        if not any(x.strip().endswith("./usr/bin/dh") for x in listing.splitlines()):
            raise RuntimeError("Arquivo /usr/bin/dh nao consta no pacote; sem extracao.")
        command(["dpkg-deb", "-x", str(PKG), str(ROOT)])
        if not DH.is_file():
            raise RuntimeError("Extracao terminou mas /usr/bin/dh continua ausente no Colab.")
        DH.chmod(DH.stat().st_mode | 0o111)
        print("Arquivos debhelper restaurados na base isolada ARM64.", flush=True)
    else:
        print("Arquivo dh existe no Colab. Verificando agora dentro do PRoot.", flush=True)

    sh = r'''#!/bin/bash
set -Eeuo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export DEBIAN_FRONTEND=noninteractive LC_ALL=C LANG=C TZ=Etc/UTC SYSTEMD_OFFLINE=1
echo '[V8] Checando o comando dh:'
ls -l /usr/bin/dh
command -v dh
perl -c /usr/bin/dh
dh --help >/dev/null
echo '[V8] Debhelper funcional, compilando Plymouth:'
cd /root/plymouth-work/plymouth-24.004.60
for p in 0100-r36s-null-terminal.patch 0101-r36s-null-renderer.patch; do
  grep -Fxq "$p" .pc/applied-patches || { echo "ERRO: patch faltando: $p"; exit 38; }
done
echo '[4/4] Compilando Plymouth ARM64 (V8)...'
DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -b -us -uc -j2
mkdir -p /content/plymouth-r36s-arm64-pacotes
find /root/plymouth-work -maxdepth 1 -name '*_arm64.deb' -exec cp -v {} /content/plymouth-r36s-arm64-pacotes/ \;
test -s /content/plymouth-r36s-arm64-pacotes/plymouth_24.004.60-5+r36s1_arm64.deb
test -s /content/plymouth-r36s-arm64-pacotes/libplymouth5_24.004.60-5+r36s1_arm64.deb
for f in /content/plymouth-r36s-arm64-pacotes/*.deb; do
  dpkg-deb --field "$f" Package Version Architecture
done
sha256sum /content/plymouth-r36s-arm64-pacotes/*.deb > /content/plymouth-r36s-arm64-pacotes/SHA256SUMS.txt
echo 'COMPILACAO_CONCLUIDA_ARM64_V8'
'''
    SCRIPT.write_text(sh, encoding="utf-8")
    SCRIPT.chmod(0o755)
    cmd = ["proot", "-0", "-r", str(ROOT),
           "-b", "/dev", "-b", "/proc", "-b", "/sys", "-b", "/content:/content",
           "-b", "/etc/resolv.conf:/etc/resolv.conf",
           "-q", "/usr/bin/qemu-aarch64-static", "-w", "/root",
           "/bin/bash", "/usr/local/bin/continuar-plymouth-v8.sh"]
    last = []
    with LOG.open("w", encoding="utf-8") as report:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, errors="replace", bufsize=1,
                                   env=dict(os.environ, LC_ALL="C", LANG="C"))
        count = 0
        for line in process.stdout:
            report.write(line)
            report.flush()
            count += 1
            last.append(line.rstrip())
            last = last[-35:]
            if count <= 25 or count % 80 == 0 or any(key in line for key in
                ("[V8]", "[4/4]", "ERRO:", "error:", "Error", "COMPILACAO_CONCLUIDA")):
                print(line.rstrip()[:350], flush=True)
        result = process.wait()
    print("Codigo final V8:", result, flush=True)
    if result == 0 and (OUTPUT / "plymouth_24.004.60-5+r36s1_arm64.deb").is_file():
        zip_name = shutil.make_archive("/content/Plymouth_R36S_ARM64_V8_PARA_VERIFICACAO",
                                       "zip", root_dir=str(OUTPUT))
        print("Pacotes concluidos, mas AINDA NAO testados no R36S.", flush=True)
        files.download(zip_name)
    else:
        print("Ainda nao concluido. Ultimas linhas:", flush=True)
        print("\n".join(last[-15:]), flush=True)
        files.download(str(LOG))
except Exception as ex:
    print("ERRO V8:", str(ex), flush=True)
    with LOG.open("a", encoding="utf-8") as report:
        traceback.print_exc(file=report)
    traceback.print_exc()
    files.download(str(LOG))
